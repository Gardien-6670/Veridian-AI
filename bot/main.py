"""
Bot Discord Veridian AI - Point d'entrée principal
Charge tous les cogs et établit la connexion avec Discord
"""

import os
import discord
from discord.ext import commands, tasks
from loguru import logger
from dotenv import load_dotenv
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Charger les variables d'environnement
load_dotenv()

# Créer dossier logs s'il n'existe pas
Path('logs').mkdir(exist_ok=True)

# Configuration des logs
logger.remove()  # Supprimer handler par défaut
logger.add(
    "logs/bot.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
)
logger.add(
    "logs/errors.log",
    rotation="500 MB",
    retention="30 days",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
)
logger.add(sys.stdout, format="{message}", level="INFO")

# Import config après logs setup
from bot.config import VERSION, VERSION_EMOJI
from bot.config import DASHBOARD_URL

# Heure de démarrage du bot (sera mise à jour dans on_ready)
_bot_start_time: datetime | None = None

# Fonction d'initialisation DB
def initialize_database():
    """Initialise la base de données (DB_NAME) et applique le schema/migrations."""
    try:
        import mysql.connector
        from mysql.connector import Error

        db_name = os.getenv("DB_NAME") or "veridian"

        # Connexion sans sélection de DB pour créer la DB DB_NAME (si besoin)
        try:
            conn = mysql.connector.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=int(os.getenv('DB_PORT', 3306)),
                user=os.getenv('DB_USER', 'root'),
                password=os.getenv('DB_PASSWORD', ''),
                connection_timeout=10,
                use_unicode=True,
                charset='utf8mb4',
                autocommit=True
            )

            cursor = conn.cursor()
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.close()
            conn.close()

            # Appliquer le schema/migrations sur la DB cible (best-effort).
            try:
                from api.db_migrate import ensure_database_schema
                ensure_database_schema()
            except Exception as e:
                # Most common cause: MySQL user missing ALTER/CREATE privileges.
                logger.error(f"[db] Migration a echoue: {e}")
                return False

            logger.info("✓ Base de données vérifiée/initialisée + migrations appliquées")
            return True
        except Error as err:
            logger.error(f"✗ Erreur initialisation DB: {err}")
            return False
    except Exception as e:
        logger.error(f"✗ Erreur critique DB: {e}")
        return False

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(
    command_prefix="/",
    intents=intents,
    help_command=None
)


@bot.event
async def on_ready():
    """Événement déclenché quand le bot est prêt."""
    global _bot_start_time
    _bot_start_time = datetime.now(timezone.utc)
    
    status_text = f"{VERSION_EMOJI} v{VERSION}"
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name=status_text
        ),
        status=discord.Status.online
    )
    
    logger.info(f"✓ Bot connecté en tant que {bot.user}")
    logger.info(f"✓ ID bot: {bot.user.id}")
    logger.info(f"✓ Version: {VERSION}")
    logger.info(f"✓ Nombre de serveurs: {len(bot.guilds)}")
    
    # Synchroniser les commandes slash
    try:
        synced = await bot.tree.sync()
        logger.info(f"✓ {len(synced)} commandes slash synchronisées")
    except Exception as e:
        logger.error(f"✗ Erreur synchronisation commandes: {e}")

    # S'assurer que tous les serveurs actuels existent en DB (au cas où)
    try:
        from bot.db.models import GuildModel
        for g in bot.guilds:
            try:
                GuildModel.create(g.id, g.name)
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Guild DB sync failed: {e}")
    
    # Démarrer le heartbeat (mise à jour du statut en DB)
    if not heartbeat_loop.is_running():
        heartbeat_loop.start()
        logger.info("✓ Heartbeat démarré (intervalle: 60s)")

    # Démarrer le poller de déploiement du message d'ouverture des tickets
    if not ticket_open_deploy_loop.is_running():
        ticket_open_deploy_loop.start()
        logger.info("✓ Ticket deploy poller démarré (intervalle: 30s)")
    
    # Premier heartbeat immédiat
    await _update_bot_status()


@tasks.loop(seconds=30)
async def ticket_open_deploy_loop():
    """Poll DB for guilds that need (re)deploy of ticket open message."""
    await _deploy_ticket_open_messages()


@ticket_open_deploy_loop.before_loop
async def before_ticket_open_deploy_loop():
    await bot.wait_until_ready()


async def _deploy_ticket_open_messages():
    try:
        from bot.db.models import GuildModel
        from bot.cogs.tickets import TicketOpenButtonView, TicketOpenSelectView
        import json

        # Handle delete requests first (to avoid editing a message that should be removed)
        delete_rows = []
        try:
            # We reuse get_all and filter here to avoid adding too many new model methods.
            # If perf becomes an issue, add a dedicated query method.
            delete_rows = [g for g in GuildModel.get_all() if int(g.get("ticket_open_delete_requested") or 0) == 1]
        except Exception:
            delete_rows = []

        for cfg in delete_rows[:25]:
            guild_id = int(cfg.get("id") or 0)
            if not guild_id:
                continue
            guild = bot.get_guild(guild_id)
            if not guild:
                continue

            channel_id = cfg.get("ticket_open_channel_id")
            try:
                channel_id = int(channel_id) if channel_id else None
            except Exception:
                channel_id = None

            msg_id = cfg.get("ticket_open_message_id")
            if not (channel_id and msg_id):
                GuildModel.ack_ticket_open_delete(guild_id)
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await bot.fetch_channel(channel_id)
                except Exception:
                    channel = None
            if channel is None:
                GuildModel.ack_ticket_open_delete(guild_id)
                continue

            try:
                message = await channel.fetch_message(int(msg_id))
                await message.delete()
            except Exception:
                # If it can't be fetched/deleted, clear anyway to unblock
                pass
            GuildModel.ack_ticket_open_delete(guild_id)

        rows = GuildModel.get_needing_ticket_open_deploy(limit=25)
        if not rows:
            return

        for cfg in rows:
            guild_id = int(cfg.get("id") or 0)
            if not guild_id:
                continue

            guild = bot.get_guild(guild_id)
            if not guild:
                # Bot not in guild or cache not ready: keep flag, try later
                continue

            channel_id = cfg.get("ticket_open_channel_id")
            try:
                channel_id = int(channel_id) if channel_id else None
            except Exception:
                channel_id = None
            if not channel_id:
                # Nothing to deploy to; ack to avoid endless loop
                GuildModel.ack_ticket_open_deploy(guild_id, message_id=cfg.get("ticket_open_message_id"))
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await bot.fetch_channel(channel_id)
                except Exception:
                    channel = None
            if channel is None:
                GuildModel.set_ticket_open_deploy_error(guild_id, f"Channel introuvable: {channel_id}")
                continue

            content = (cfg.get("ticket_open_message") or "").strip() or "Cliquez ci-dessous pour ouvrir un ticket."

            # Build view
            selector_enabled = int(cfg.get("ticket_selector_enabled") or 0) == 1
            if selector_enabled:
                placeholder = (cfg.get("ticket_selector_placeholder") or "Sélectionnez le type de ticket")
                options_raw = cfg.get("ticket_selector_options")
                options = []
                try:
                    if isinstance(options_raw, str):
                        options = json.loads(options_raw) if options_raw.strip() else []
                    elif isinstance(options_raw, list):
                        options = options_raw
                except Exception:
                    options = []
                view = TicketOpenSelectView(bot, guild_id=guild_id, placeholder=placeholder, options=options)
            else:
                view = TicketOpenButtonView(
                    bot,
                    guild_id=guild_id,
                    label=(cfg.get("ticket_button_label") or "Ouvrir un ticket"),
                    style=(cfg.get("ticket_button_style") or "primary"),
                    emoji=(cfg.get("ticket_button_emoji") or None),
                )

            # Send or edit existing
            msg_id = cfg.get("ticket_open_message_id")
            message = None
            try:
                if msg_id:
                    message = await channel.fetch_message(int(msg_id))
            except Exception:
                message = None

            try:
                if message:
                    await message.edit(content=content, view=view)
                    GuildModel.ack_ticket_open_deploy(guild_id, message_id=int(message.id))
                else:
                    sent = await channel.send(content=content, view=view)
                    GuildModel.ack_ticket_open_deploy(guild_id, message_id=int(sent.id))
            except Exception as e:
                logger.warning(f"Ticket open deploy failed for guild {guild_id}: {e}")
                GuildModel.set_ticket_open_deploy_error(guild_id, str(e))
                continue

    except Exception as e:
        logger.debug(f"ticket_open_deploy_loop: {e}")


@tasks.loop(seconds=60)
async def heartbeat_loop():
    """Met à jour le statut du bot en DB toutes les 60 secondes.
    Le dashboard lit cette table pour afficher l'indicateur 'BOT EN LIGNE',
    l'uptime, le nombre de serveurs, la latence, etc.
    """
    await _update_bot_status()


@heartbeat_loop.before_loop
async def before_heartbeat():
    """Attend que le bot soit prêt avant de démarrer le heartbeat."""
    await bot.wait_until_ready()


async def _update_bot_status():
    """Écrit les métriques du bot dans vai_bot_status (id=1)."""
    try:
        from bot.db.models import BotStatusModel
        
        guild_count = len(bot.guilds)
        user_count = sum(g.member_count or 0 for g in bot.guilds)
        channel_count = sum(len(g.channels) for g in bot.guilds)
        latency_ms = round(bot.latency * 1000, 2) if bot.latency else 0
        shard_count = bot.shard_count or 1
        
        uptime_sec = 0
        if _bot_start_time:
            uptime_sec = int((datetime.now(timezone.utc) - _bot_start_time).total_seconds())
        
        BotStatusModel.update(
            guild_count=guild_count,
            user_count=user_count,
            uptime_sec=uptime_sec,
            version=VERSION,
            latency_ms=latency_ms,
            shard_count=shard_count,
            channel_count=channel_count,
            started_at=_bot_start_time.strftime('%Y-%m-%d %H:%M:%S') if _bot_start_time else None,
        )
        logger.debug(f"♥ Heartbeat: {guild_count} guilds, {user_count} users, {uptime_sec}s uptime, {latency_ms}ms latency")
    except Exception as e:
        logger.warning(f"⚠ Heartbeat échoué: {e}")


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Événement déclenché quand le bot rejoint un serveur."""
    logger.info(f"✓ Bot ajouté au serveur: {guild.name} ({guild.id})")
    
    # Créer l'enregistrement en DB
    from bot.db.models import GuildModel
    GuildModel.create(guild.id, guild.name)

    # DM au owner avec le lien de configuration
    try:
        owner = None
        try:
            if guild.owner:
                owner = guild.owner
        except Exception:
            owner = None

        if not owner and guild.owner_id:
            try:
                owner = await bot.fetch_user(int(guild.owner_id))
            except Exception:
                owner = None

        if owner:
            await owner.send(
                f"Merci d'avoir ajouté **Veridian AI** sur **{guild.name}**.\n"
                f"Configure le bot via le dashboard : {DASHBOARD_URL}\n"
                "Sélectionne ton serveur puis configure Tickets / Support / Langue."
            )
    except Exception as e:
        logger.debug(f"DM owner failed for guild {guild.id}: {e}")
    
    # Mettre à jour le statut immédiatement (nouveau serveur)
    await _update_bot_status()


@bot.event
async def on_guild_remove(guild: discord.Guild):
    """Événement déclenché quand le bot quitte un serveur."""
    logger.info(f"✗ Bot supprimé du serveur: {guild.name} ({guild.id})")
    
    # Mettre à jour le statut immédiatement (serveur perdu)
    await _update_bot_status()


async def load_cogs():
    """Charge tous les cogs depuis le dossier cogs/"""
    cogs_dir = 'bot/cogs'
    
    for filename in os.listdir(cogs_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            cog_name = filename[:-3]
            try:
                await bot.load_extension(f'bot.cogs.{cog_name}')
                logger.info(f"✓ Cog chargé: {cog_name}")
            except Exception as e:
                logger.error(f"✗ Erreur chargement cog {cog_name}: {e}")


async def main():
    """Fonction principale."""
    logger.info(f"🚀 Démarrage Veridian AI {VERSION}")
    
    # Initialiser la base de données
    if not initialize_database():
        logger.error("✗ Impossible d'initialiser la base de données")
        return
    
    # Charger les cogs
    await load_cogs()
    
    # Lancer le bot
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("✗ DISCORD_TOKEN non défini dans .env")
        return
    
    try:
        await bot.start(token)
    except discord.errors.LoginFailure:
        logger.error("✗ Erreur d'authentification Discord")
    except Exception as e:
        logger.error(f"✗ Erreur démarrage bot: {e}")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot arrêté par l'utilisateur")

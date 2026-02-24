"""
Bot Discord Veridian AI - Point d'entrée principal
Charge tous les cogs et établit la connexion avec Discord
"""

import os
import discord
from discord.ext import commands
from loguru import logger
from dotenv import load_dotenv
import asyncio
import sys
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

# Fonction d'initialisation DB
def initialize_database():
    """Initialise la base de données si elle n'existe pas."""
    try:
        import mysql.connector
        from mysql.connector import Error
        
        # Lecture du script schema.sql
        schema_path = Path('database/schema.sql')
        if not schema_path.exists():
            logger.error(f"✗ Fichier schema.sql non trouvé: {schema_path}")
            return False
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        # Connexion sans sélection de DB pour créer la DB
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
            
            # Split statements by ';' and filter empty/comments
            statements = []
            current = ''
            for line in schema_sql.split('\n'):
                line = line.rstrip()
                if line.startswith('--') or not line.strip():
                    continue
                current += ' ' + line
                if line.rstrip().endswith(';'):
                    stmt = current.strip()
                    if stmt:
                        statements.append(stmt)
                    current = ''
            
            cursor = conn.cursor()
            for statement in statements:
                try:
                    cursor.execute(statement)
                except Error as e:
                    logger.warning(f"⚠ {e}")
            
            cursor.close()
            conn.close()
            
            logger.info("✓ Base de données vérifiée/initialisée")
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


@bot.event
async def on_guild_join(guild: discord.Guild):
    """Événement déclenché quand le bot rejoint un serveur."""
    logger.info(f"✓ Bot ajouté au serveur: {guild.name} ({guild.id})")
    
    # Créer l'enregistrement en DB
    from bot.db.models import GuildModel
    GuildModel.create(guild.id, guild.name)


@bot.event
async def on_guild_remove(guild: discord.Guild):
    """Événement déclenché quand le bot quitte un serveur."""
    logger.info(f"✗ Bot supprimé du serveur: {guild.name} ({guild.id})")


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

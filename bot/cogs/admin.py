"""
Cog: Admin - Commandes reservees au Bot Owner.
La configuration, la validation des commandes et la gestion des abonnements
sont desormais gerees exclusivement via le dashboard (veridiancloud.xyz/dashboard).
Ce cog ne conserve que les commandes strictement necessaires au fonctionnement
du bot lui-meme et non realisables autrement.
"""

import discord
from discord.ext import commands
from loguru import logger
from bot.config import BOT_OWNER_DISCORD_ID, VERSION
from bot.db.models import BotStatusModel
import time

_start_time = time.time()


class AdminCog(commands.Cog):
    """Commandes systeme reservees au Bot Owner."""

    def __init__(self, bot):
        self.bot = bot
        logger.info("Cog Admin charge")

    def _is_owner(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == BOT_OWNER_DISCORD_ID

    # ------------------------------------------------------------------
    # /ping  - verifier que le bot repond
    # ------------------------------------------------------------------

    @discord.app_commands.command(name="ping", description="Verifier la latence du bot")
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)
        uptime_sec = int(time.time() - _start_time)
        h, rem     = divmod(uptime_sec, 3600)
        m, s       = divmod(rem, 60)
        await interaction.response.send_message(
            f"Pong! Latence : **{latency_ms}ms** | Uptime : **{h}h {m}m {s}s**",
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /dashboard - lien vers le panel
    # ------------------------------------------------------------------

    @discord.app_commands.command(
        name="dashboard",
        description="Acceder au panel de configuration"
    )
    async def dashboard_link(self, interaction: discord.Interaction):
        """Envoie le lien vers le dashboard en ephemere."""
        await interaction.response.send_message(
            "Configurez le bot et gerez vos tickets sur le panel :\n"
            "https://veridiancloud.xyz/dashboard",
            ephemeral=True
        )

    # ------------------------------------------------------------------
    # /sync  - synchroniser les slash commands (owner uniquement)
    # ------------------------------------------------------------------

    @discord.app_commands.command(
        name="sync",
        description="[Owner] Synchroniser les slash commands"
    )
    async def sync_commands(self, interaction: discord.Interaction):
        if not self._is_owner(interaction):
            await interaction.response.send_message("Acces refuse.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            synced = await self.bot.tree.sync()
            await interaction.followup.send(
                f"{len(synced)} commande(s) synchronisee(s).",
                ephemeral=True
            )
            logger.info(f"{len(synced)} slash commands synchronisees")
        except Exception as e:
            await interaction.followup.send(f"Erreur sync: {e}", ephemeral=True)

    # ------------------------------------------------------------------
    # Heartbeat : le bot met a jour son etat en DB toutes les 5 min
    # ------------------------------------------------------------------

    @commands.Cog.listener()
    async def on_ready(self):
        """Demarre la tache de heartbeat vers la DB."""
        self.bot.loop.create_task(self._heartbeat_loop())

    async def _heartbeat_loop(self):
        import asyncio
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                guild_count = len(self.bot.guilds)
                user_count  = sum(g.member_count or 0 for g in self.bot.guilds)
                uptime_sec  = int(time.time() - _start_time)
                BotStatusModel.update(guild_count, user_count, uptime_sec, VERSION)
            except Exception as e:
                logger.error(f"Heartbeat erreur: {e}")
            await asyncio.sleep(300)  # toutes les 5 minutes


async def setup(bot):
    await bot.add_cog(AdminCog(bot))

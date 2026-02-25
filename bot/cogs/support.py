"""
Cog: Support Public IA - Repond automatiquement dans les channels designes.
Les commandes de configuration sont gerees via le dashboard.
"""

import discord
from discord.ext import commands
from loguru import logger
from bot.db.models import GuildModel, SubscriptionModel, UserModel
from bot.services.groq_client import GroqClient
from bot.services.translator import TranslatorService
from bot.config import MIN_MESSAGE_LENGTH, PLAN_LIMITS, DASHBOARD_URL


class SupportCog(commands.Cog):
    """Support public IA dans les channels designes."""

    def __init__(self, bot):
        self.bot         = bot
        self.groq_client = GroqClient()
        self.translator  = TranslatorService()
        logger.info("Cog Support Public charge")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        guild_config = GuildModel.get(message.guild.id)
        if (not guild_config
                or not guild_config.get("support_channel_id")
                or not guild_config.get("public_support", 1)
                or message.channel.id != guild_config["support_channel_id"]):
            return

        if len(message.content.split()) < MIN_MESSAGE_LENGTH:
            return

        async with message.channel.typing():
            try:
                language = self.translator.detect_language(message.content)
                response = self.groq_client.generate_support_response(
                    message.content,
                    guild_name=message.guild.name,
                    language=language
                )
                await message.reply(response[:2000], mention_author=False,
                                    suppress_embeds=True)
                logger.info(f"Reponse support envoyee sur {message.guild.id}")

            except Exception as e:
                logger.error(f"Erreur support IA: {e}")
                try:
                    await message.reply(
                        "Une erreur s'est produite. Veuillez ouvrir un ticket.",
                        mention_author=False
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # /language
    # ------------------------------------------------------------------

    @discord.app_commands.command(name="language", description="Definir votre langue preferee")
    @discord.app_commands.describe(language="Code langue ISO-639-1 (ex: en, fr, es)")
    async def set_language(self, interaction: discord.Interaction, language: str):
        await interaction.response.defer(ephemeral=True)
        if len(language) != 2 or not language.isalpha():
            await interaction.followup.send(
                "Format invalide. Exemple : 'en', 'fr', 'de'", ephemeral=True
            )
            return
        lang = language.lower()
        UserModel.upsert(interaction.user.id, interaction.user.name, lang)
        await interaction.followup.send(
            f"Langue preferee definie sur : **{lang.upper()}**", ephemeral=True
        )
        logger.info(f"Langue {interaction.user.id} -> {lang}")

    # ------------------------------------------------------------------
    # /premium
    # ------------------------------------------------------------------

    @discord.app_commands.command(name="premium", description="Voir les plans disponibles")
    async def premium_info(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="Plans Veridian AI",
            color=discord.Color.gold(),
            description=(
                "Upgrade via le panel ou avec la commande `/pay`.\n"
                f"{DASHBOARD_URL}"
            )
        )
        embed.add_field(
            name="Free",
            value="50 tickets/mois | 5 langues | Support public limite",
            inline=False
        )
        embed.add_field(
            name="Premium (2 EUR/mois)",
            value="500 tickets/mois | 20 langues | KB 50 entrees | Transcriptions",
            inline=False
        )
        embed.add_field(
            name="Pro (5 EUR/mois)",
            value="Illimite | Toutes langues | KB illimitee | Suggestions staff | Stats avancees",
            inline=False
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------
    # /status
    # ------------------------------------------------------------------

    @discord.app_commands.command(name="status", description="Voir l'abonnement du serveur")
    async def subscription_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            sub = SubscriptionModel.get(interaction.guild.id)
            if not sub:
                embed = discord.Embed(
                    title="Abonnement",
                    description="Ce serveur est en plan **Free**.",
                    color=discord.Color.greyple()
                )
            else:
                plan    = sub["plan"].upper()
                expires = sub.get("expires_at", "Indefini")
                embed   = discord.Embed(
                    title="Abonnement",
                    description=f"Ce serveur est en plan **{plan}**.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Expire le", value=str(expires))
            embed.set_footer(text=f"Utilisez /pay ou visitez {DASHBOARD_URL}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Erreur subscription_status: {e}")
            await interaction.followup.send(f"Erreur : {e}", ephemeral=True)


async def setup(bot):
    await bot.add_cog(SupportCog(bot))

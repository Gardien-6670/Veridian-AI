"""
Cog: Support Public IA - Répond automatiquement aux questions dans les channels désignés
"""

import discord
from discord.ext import commands
from loguru import logger
from bot.db.models import GuildModel, SubscriptionModel
from bot.services.groq_client import GroqClient
from bot.services.translator import TranslatorService
from bot.config import MIN_MESSAGE_LENGTH


class SupportCog(commands.Cog):
    """Support public IA dans les channels désignés."""
    
    def __init__(self, bot):
        self.bot = bot
        self.groq_client = GroqClient()
        self.translator = TranslatorService()
        logger.info("✓ Cog Support Public chargé")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Écoute tous les messages et répond aux questions."""
        
        # Ignorer les messages du bot
        if message.author.bot:
            return

        # Ignorer les DM
        if not message.guild:
            return

        # Vérifier si le channel est configuré pour le support
        guild_config = GuildModel.get(message.guild.id)
        if not guild_config or not guild_config['support_channel_id']:
            return

        if message.channel.id != guild_config['support_channel_id']:
            return

        # Vérifier la longueur minimale
        if len(message.content.split()) < MIN_MESSAGE_LENGTH:
            return

        # Détecter si c'est une question
        is_question = self.groq_client.detect_question(message.content)
        if not is_question:
            return

        # Afficher l'indicateur de "typing"
        async with message.channel.typing():
            try:
                # Déterminer la langue
                language = self.translator.detect_language(message.content)

                # Vérifier la limite du plan (si applicable)
                subscription = SubscriptionModel.get(message.guild.id)

                # Générer la réponse IA
                response = self.groq_client.generate_support_response(
                    message.content,
                    guild_name=message.guild.name,
                    language=language
                )

                # Envoyer la réponse en reply au message
                await message.reply(
                    response[:2000],  # Limite Discord
                    mention_author=False,
                    suppress_embeds=True
                )

                logger.info(f"✓ Réponse support envoyée sur {message.guild.id}")

            except Exception as e:
                logger.error(f"✗ Erreur support IA: {e}")
                try:
                    await message.reply(
                        "❌ Une erreur s'est produite. Veuillez ouvrir un ticket.",
                        mention_author=False
                    )
                except:
                    pass

    @discord.app_commands.command(
        name="language",
        description="Définir votre langue préférée"
    )
    @discord.app_commands.describe(language="Code langue (en, fr, es, de, it, ...)")
    async def set_language(self, interaction: discord.Interaction, language: str):
        """Permet à l'utilisateur de définir sa langue préférée."""
        
        await interaction.response.defer(ephemeral=True)

        try:
            # Validation simple du code langue
            if len(language) != 2 or not language.isalpha():
                await interaction.followup.send(
                    "❌ Format invalide. Utilisez un code langue ISO-639-1 (ex: 'en', 'fr')"
                )
                return

            # Mettre à jour en DB (ou créer l'utilisateur)
            from bot.db.models import UserModel
            user = UserModel.get(interaction.user.id)
            if user:
                UserModel.update(interaction.user.id, preferred_language=language.lower())
            else:
                UserModel.create(
                    interaction.user.id,
                    interaction.user.name,
                    language.lower()
                )

            await interaction.followup.send(
                f"✅ Langue préférée définie à: **{language.upper()}**",
                ephemeral=True
            )

            logger.info(f"✓ Langue de {interaction.user.id} définie à {language}")

        except Exception as e:
            logger.error(f"✗ Erreur set_language: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}")

    @discord.app_commands.command(
        name="premium",
        description="Voir les plans disponibles"
    )
    async def premium_info(self, interaction: discord.Interaction):
        """Affiche les informations sur les plans premium."""
        
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(
            title="🚀 Plans Veridian AI",
            color=discord.Color.gold(),
            description="Choisissez le plan qui vous convient le mieux!"
        )

        embed.add_field(
            name="📦 Free",
            value="""
            • 50 tickets/mois
            • 5 langues
            • Support public IA limité
            """,
            inline=True
        )

        embed.add_field(
            name="⭐ Premium (2€/mois)",
            value="""
            • 500 tickets/mois
            • 20 langues
            • Base de connaissances (50 entrées)
            • Transcriptions complètes
            """,
            inline=True
        )

        embed.add_field(
            name="🔥 Pro (5€/mois)",
            value="""
            • ∞ Tickets/mois
            • Toutes les langues
            • Base de connaissances illimitée
            • Suggestions du staff IA
            • Statistiques avancées
            """,
            inline=True
        )

        embed.set_footer(text="Utilisez /pay pour commencer")

        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.app_commands.command(
        name="status",
        description="Voir son statut d'abonnement"
    )
    async def subscription_status(self, interaction: discord.Interaction):
        """Affiche le statut d'abonnement de l'utilisateur sur le serveur."""
        
        await interaction.response.defer(ephemeral=True)

        try:
            subscription = SubscriptionModel.get(interaction.guild.id)

            if not subscription:
                embed = discord.Embed(
                    title="📊 Statut d'Abonnement",
                    description=f"Ce serveur est en plan **Free**.",
                    color=discord.Color.greyple()
                )
            else:
                plan = subscription['plan'].upper()
                expires = subscription.get('expires_at', 'Jamais')

                embed = discord.Embed(
                    title="📊 Statut d'Abonnement",
                    description=f"Ce serveur est en plan **{plan}**.",
                    color=discord.Color.green()
                )
                embed.add_field(name="Expire le", value=str(expires), inline=False)

            embed.set_footer(text="Utilisez /pay pour upgrade")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"✗ Erreur subscription_status: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)


async def setup(bot):
    """Charge le cog Support Public."""
    await bot.add_cog(SupportCog(bot))

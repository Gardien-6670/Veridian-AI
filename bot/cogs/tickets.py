"""
Cog: Système de Tickets - Gestion complète des tickets de support
"""

import discord
from discord.ext import commands
from loguru import logger
from bot.db.models import TicketModel, GuildModel, UserModel, SubscriptionModel
from bot.services.translator import TranslatorService
from bot.services.groq_client import GroqClient
from bot.config import TICKET_CHANNEL_PREFIX, DB_TABLE_PREFIX, BOT_OWNER_DISCORD_ID


class TicketsCog(commands.Cog):
    """Gère les tickets de support avec traduction en temps réel."""
    
    def __init__(self, bot):
        self.bot = bot
        self.translator = TranslatorService()
        self.groq_client = GroqClient()
        logger.info("✓ Cog Tickets chargé")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Écoute tous les messages pour traiter les réponses en tickets."""
        
        # Ignorer les messages du bot
        if message.author.bot:
            return

        # Vérifier si c'est un message dans un ticket
        ticket = TicketModel.get_by_channel(message.channel.id)
        if not ticket:
            return

        # Détection de langue et traduction si nécessaire
        user_language = self.translator.detect_language(message.content)
        staff_language = ticket['staff_language']

        # Si l'utilisateur écrit dans une langue différente du staff, traduire
        if user_language != staff_language and message.author.id == ticket['user_id']:
            translated_text, from_cache = self.translator.translate_message_for_staff(
                message.content, user_language, staff_language
            )

            # Envoyer message éphémère au staff avec traduction
            cache_indicator = "🔄" if from_cache else "🌐"
            ephemeral_msg = f"{cache_indicator} **Traduit depuis** {user_language}:\n>>> {translated_text}"
            
            try:
                await message.channel.send(ephemeral_msg, delete_after=300)
                logger.info(f"✓ Message traduit envoyé pour ticket {ticket['id']}")
            except Exception as e:
                logger.error(f"✗ Erreur envoi traduction: {e}")

        logger.debug(f"Message traité dans ticket {ticket['id']}")

    @discord.app_commands.command(name="ticket", description="Ouvrir un ticket de support")
    async def open_ticket(self, interaction: discord.Interaction):
        """Ouvre un nouveau ticket de support."""
        
        await interaction.response.defer(ephemeral=True)

        try:
            # Récupérer la config du serveur
            guild_config = GuildModel.get(interaction.guild.id)
            if not guild_config:
                await interaction.followup.send(
                    "❌ Le bot n'est pas configuré sur ce serveur. Contactez un admin."
                )
                return

            if not guild_config['ticket_category_id']:
                await interaction.followup.send(
                    "❌ La catégorie des tickets n'est pas configurée. Contactez un admin."
                )
                return

            # Créer le channel du ticket
            category = interaction.guild.get_channel(guild_config['ticket_category_id'])
            if not category:
                await interaction.followup.send("❌ Catégorie non trouvée.")
                return

            channel_name = f"{TICKET_CHANNEL_PREFIX}-{interaction.user.name}-{interaction.user.id}"
            ticket_channel = await interaction.guild.create_text_channel(
                channel_name,
                category=category,
                overwrites={
                    interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    interaction.user: discord.PermissionOverwrite(read_messages=True),
                    interaction.guild.me: discord.PermissionOverwrite(read_messages=True),
                }
            )

            # Ajouter le staff role si configuré
            if guild_config['staff_role_id']:
                staff_role = interaction.guild.get_role(guild_config['staff_role_id'])
                if staff_role:
                    await ticket_channel.set_permissions(
                        staff_role,
                        read_messages=True
                    )

            # Déterminer la langue de l'utilisateur
            user_language = self.translator.detect_language(
                interaction.user.name
            ) or guild_config['default_language']

            # Créer l'enregistrement en DB
            ticket_id = TicketModel.create(
                guild_id=interaction.guild.id,
                user_id=interaction.user.id,
                channel_id=ticket_channel.id,
                user_language=user_language,
                staff_language=guild_config['default_language']
            )

            # Assurer que l'utilisateur existe en DB
            UserModel.create(
                user_id=interaction.user.id,
                username=interaction.user.name,
                preferred_language=user_language
            ) if not UserModel.get(interaction.user.id) else None

            # Message de bienvenue
            embed = discord.Embed(
                title="🎫 Nouveau Ticket de Support",
                color=discord.Color.blue(),
                description="Bienvenue! Décrivez votre problème ci-dessous. Un membre du staff vous aidera bientôt."
            )
            embed.add_field(name="Ticket ID", value=f"`{ticket_id}`", inline=False)
            embed.add_field(name="Langue détectée", value=user_language.upper(), inline=True)

            # Vue avec bouton Fermer
            view = TicketCloseView(ticket_id, self.bot)
            await ticket_channel.send(embed=embed, view=view)

            # Feedback à l'utilisateur
            await interaction.followup.send(
                f"✅ Ticket créé! Accédez-y ici: {ticket_channel.mention}",
                ephemeral=True
            )

            logger.info(f"✓ Ticket {ticket_id} créé pour {interaction.user.id}")

        except Exception as e:
            logger.error(f"✗ Erreur création ticket: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}")

    @discord.app_commands.command(name="close", description="Fermer le ticket courant")
    async def close_ticket(self, interaction: discord.Interaction, reason: str = "Non spécifié"):
        """Ferme le ticket courant."""
        
        await interaction.response.defer(ephemeral=True)

        try:
            ticket = TicketModel.get_by_channel(interaction.channel.id)
            if not ticket:
                await interaction.followup.send("❌ Ceci n'est pas un channel de ticket.")
                return

            # Vérifier les permissions (user ou staff)
            is_user = interaction.user.id == ticket['user_id']
            is_staff = interaction.user.guild_permissions.administrator or \
                      interaction.user.id == BOT_OWNER_DISCORD_ID

            if not (is_user or is_staff):
                await interaction.followup.send("❌ Vous n'avez pas la permission de fermer ce ticket.")
                return

            # Générer résumé IA
            summary = f"Ticket fermé. Raison: {reason}"
            try:
                # Récupérer les messages du ticket (à implémenter)
                summary = self.groq_client.generate_ticket_summary([], ticket['user_language'])
            except Exception as e:
                logger.warning(f"Impossible de générer le résumé: {e}")

            # Fermer en DB
            TicketModel.close(ticket['id'], transcript=summary, close_reason=reason)

            # Envoyer transcription en DM à l'utilisateur et au staff
            user = await self.bot.fetch_user(ticket['user_id'])
            if user:
                embed = discord.Embed(
                    title="📋 Transcription du Ticket",
                    description=summary,
                    color=discord.Color.greyple()
                )
                await user.send(embed=embed)

            await interaction.followup.send("✅ Ticket fermé. Transcription envoyée en DM.")
            logger.info(f"✓ Ticket {ticket['id']} fermé")

            # Archiver et supprimer le channel après 24h
            # À implémenter avec une tâche async

        except Exception as e:
            logger.error(f"✗ Erreur fermeture ticket: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}")


# ============================================================================
# Vue avec bouton Fermer
# ============================================================================

class TicketCloseView(discord.ui.View):
    def __init__(self, ticket_id: int, bot):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.bot = bot

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger, emoji="❌")
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Ferme le ticket."""
        # Rediriger vers la commande /close
        await interaction.response.send_message(
            "Utilisez la commande `/close` pour fermer le ticket.",
            ephemeral=True
        )


async def setup(bot):
    """Charge le cog Tickets."""
    await bot.add_cog(TicketsCog(bot))

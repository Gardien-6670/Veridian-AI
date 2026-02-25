"""
Cog: Tickets - Gestion des tickets de support avec traduction en temps reel.
La configuration du systeme (category, staff role, etc.) se fait via le dashboard.
"""

import discord
from discord.ext import commands
from loguru import logger
from bot.db.models import TicketModel, GuildModel, UserModel, SubscriptionModel
from bot.services.translator import TranslatorService
from bot.services.groq_client import GroqClient
from bot.config import TICKET_CHANNEL_PREFIX, BOT_OWNER_DISCORD_ID


class TicketsCog(commands.Cog):
    """Tickets de support avec traduction en temps reel."""

    def __init__(self, bot):
        self.bot         = bot
        self.translator  = TranslatorService()
        self.groq_client = GroqClient()
        logger.info("Cog Tickets charge")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        ticket = TicketModel.get_by_channel(message.channel.id)
        if not ticket or ticket["status"] == "closed":
            return

        if len(message.content.strip()) < 3:
            return

        user_language  = self.translator.detect_language(message.content)
        staff_language = ticket["staff_language"]

        # Traduction si l'utilisateur ecrit dans une autre langue que le staff
        if (user_language != staff_language
                and message.author.id == ticket["user_id"]
                and user_language):
            try:
                translated_text, from_cache = self.translator.translate_message_for_staff(
                    message.content, user_language, staff_language
                )
                source = "cache" if from_cache else "API"
                await message.channel.send(
                    f"[Traduit {user_language} -> {staff_language} ({source})] {translated_text}",
                    delete_after=300
                )
                logger.debug(f"Traduction envoyee pour ticket {ticket['id']}")
            except Exception as e:
                logger.error(f"Erreur traduction ticket {ticket['id']}: {e}")

    # ------------------------------------------------------------------
    # /ticket - ouvrir un ticket
    # ------------------------------------------------------------------

    @discord.app_commands.command(name="ticket", description="Ouvrir un ticket de support")
    async def open_ticket(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild_config = GuildModel.get(interaction.guild.id)
        if not guild_config:
            await interaction.followup.send(
                "Le bot n'est pas encore configure sur ce serveur. "
                "Demandez a un administrateur de le configurer via le panel : "
                "https://veridiancloud.xyz/dashboard",
                ephemeral=True
            )
            return

        category_id = guild_config.get("ticket_category_id")
        if not category_id:
            await interaction.followup.send(
                "La categorie des tickets n'est pas configuree. "
                "Configurez-la sur https://veridiancloud.xyz/dashboard",
                ephemeral=True
            )
            return

        category = interaction.guild.get_channel(int(category_id))
        if not category:
            await interaction.followup.send(
                "Categorie des tickets introuvable. Verifiez la configuration sur le panel.",
                ephemeral=True
            )
            return

        # Creer le channel
        channel_name  = f"{TICKET_CHANNEL_PREFIX}-{interaction.user.name[:16]}-{interaction.user.id}"
        ticket_channel = await interaction.guild.create_text_channel(
            channel_name,
            category=category,
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user:               discord.PermissionOverwrite(read_messages=True),
                interaction.guild.me:           discord.PermissionOverwrite(read_messages=True),
            }
        )

        # Permissions du role staff
        staff_role_id = guild_config.get("staff_role_id")
        if staff_role_id:
            staff_role = interaction.guild.get_role(int(staff_role_id))
            if staff_role:
                await ticket_channel.set_permissions(staff_role, read_messages=True)

        # Langue de l'utilisateur
        user_db = UserModel.get(interaction.user.id)
        user_language = (
            user_db.get("preferred_language")
            if user_db and user_db.get("preferred_language") != "auto"
            else self.translator.detect_language(interaction.user.name)
                 or guild_config.get("default_language", "en")
        )

        # Creer en DB avec username
        ticket_id = TicketModel.create(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            user_username=interaction.user.name,
            channel_id=ticket_channel.id,
            user_language=user_language,
            staff_language=guild_config.get("default_language", "en")
        )

        # Upsert utilisateur
        UserModel.upsert(interaction.user.id, interaction.user.name, user_language)

        # Message de bienvenue
        embed = discord.Embed(
            title="Ticket de Support",
            color=discord.Color.blue(),
            description=(
                "Bienvenue ! Decrivez votre probleme ci-dessous.\n"
                "Un membre du staff vous repondra bientot.\n\n"
                f"Ticket ID : `{ticket_id}` | Langue detectee : `{user_language.upper()}`"
            )
        )
        view = TicketCloseView(ticket_id, self.bot)
        await ticket_channel.send(embed=embed, view=view)

        await interaction.followup.send(
            f"Ticket cree : {ticket_channel.mention}", ephemeral=True
        )
        logger.info(f"Ticket {ticket_id} cree pour {interaction.user.id} sur {interaction.guild.id}")

    # ------------------------------------------------------------------
    # /close - fermer le ticket courant
    # ------------------------------------------------------------------

    @discord.app_commands.command(name="close", description="Fermer ce ticket")
    @discord.app_commands.describe(reason="Raison de la cloture (optionnel)")
    async def close_ticket(self, interaction: discord.Interaction, reason: str = "Non specifiee"):
        await interaction.response.defer(ephemeral=True)

        ticket = TicketModel.get_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.followup.send(
                "Cette commande est reservee aux channels de tickets.", ephemeral=True
            )
            return

        is_user  = interaction.user.id == ticket["user_id"]
        is_staff = (
            interaction.user.guild_permissions.administrator
            or interaction.user.id == BOT_OWNER_DISCORD_ID
        )

        if not (is_user or is_staff):
            await interaction.followup.send("Permission refusee.", ephemeral=True)
            return

        # Generer le resume IA si disponible
        transcript = f"Ticket ferme. Raison : {reason}"
        try:
            transcript = self.groq_client.generate_ticket_summary(
                [], ticket["user_language"]
            )
        except Exception as e:
            logger.warning(f"Resume IA non genere: {e}")

        TicketModel.close(ticket["id"], transcript=transcript, close_reason=reason)

        # Envoyer la transcription en DM
        try:
            user  = await self.bot.fetch_user(ticket["user_id"])
            embed = discord.Embed(
                title="Resume du ticket",
                description=transcript,
                color=discord.Color.greyple()
            )
            await user.send(embed=embed)
        except Exception:
            pass

        await interaction.followup.send(
            "Ticket ferme. Resume envoye en DM.", ephemeral=True
        )
        logger.info(f"Ticket {ticket['id']} ferme par {interaction.user.id}")


# ============================================================================
# Vue avec bouton Fermer
# ============================================================================

class TicketCloseView(discord.ui.View):
    def __init__(self, ticket_id: int, bot):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.bot       = bot

    @discord.ui.button(label="Fermer le ticket", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = TicketModel.get(self.ticket_id)
        if not ticket:
            await interaction.response.send_message("Ticket introuvable.", ephemeral=True)
            return

        is_user  = interaction.user.id == ticket["user_id"]
        is_staff = interaction.user.guild_permissions.administrator
        if not (is_user or is_staff):
            await interaction.response.send_message("Permission refusee.", ephemeral=True)
            return

        TicketModel.close(self.ticket_id, close_reason="Ferme via bouton")
        button.disabled = True
        await interaction.response.edit_message(
            content="Ticket ferme.", view=self
        )
        logger.info(f"Ticket {self.ticket_id} ferme via bouton par {interaction.user.id}")


async def setup(bot):
    await bot.add_cog(TicketsCog(bot))

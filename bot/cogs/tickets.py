"""
Cog: Tickets - Gestion des tickets de support avec traduction en temps reel.
La configuration du systeme (category, staff role, etc.) se fait via le dashboard.
"""

import discord
from discord.ext import commands
from loguru import logger
import json

from bot.db.models import TicketModel, GuildModel, UserModel, TicketMessageModel
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

    def _build_ticket_welcome_embed(self, *, ticket_id: int,
                                   user_language: str | None,
                                   staff_language: str | None) -> discord.Embed:
        def fmt_lang(code: str | None, pending_label: str) -> str:
            if not code or code == "auto":
                return pending_label
            return code.upper()

        ul = fmt_lang(user_language, "Détection en cours…")
        sl = fmt_lang(staff_language, "AUTO")

        embed = discord.Embed(
            title="Ticket de Support",
            color=discord.Color.blue(),
            description=(
                "Bienvenue ! Décrivez votre problème ci-dessous.\n"
                "Le bot détectera votre langue à partir de votre premier message.\n"
                "Un membre du staff vous répondra bientôt."
            ),
        )
        embed.add_field(name="Ticket ID", value=f"`{ticket_id}`", inline=True)
        embed.add_field(name="Langue utilisateur", value=f"`{ul}`", inline=True)
        embed.add_field(name="Langue staff", value=f"`{sl}`", inline=True)
        return embed

    async def _try_update_welcome_embed(self, channel: discord.TextChannel, ticket_id: int):
        try:
            ticket = TicketModel.get(ticket_id)
            if not ticket:
                return
            msg_id = ticket.get("initial_message_id")
            if not msg_id:
                return
            try:
                welcome_msg = await channel.fetch_message(int(msg_id))
            except Exception:
                return

            embed = self._build_ticket_welcome_embed(
                ticket_id=ticket_id,
                user_language=ticket.get("user_language"),
                staff_language=ticket.get("staff_language"),
            )
            await welcome_msg.edit(embed=embed, view=TicketCloseView(ticket_id, self.bot))
        except Exception as e:
            logger.debug(f"Update welcome embed failed for ticket {ticket_id}: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        ticket = TicketModel.get_by_channel(message.channel.id)
        if not ticket or ticket["status"] == "closed":
            return
        text = (message.content or "").strip()
        if not text and not message.attachments:
            return

        guild_config = GuildModel.get(message.guild.id) or {}
        auto_translate = bool(guild_config.get("auto_translate", 1))

        is_ticket_user = message.author.id == ticket["user_id"]
        detected_lang = self.translator.detect_language(text) if text else None

        translated_text = None
        from_cache = False
        target_language = None

        # ── User message: detect user language on first real message ───────────
        if is_ticket_user:
            ticket_user_lang = ticket.get("user_language")
            if not ticket_user_lang or ticket_user_lang == "auto":
                if detected_lang:
                    TicketModel.update(ticket["id"], user_language=detected_lang)
                    ticket["user_language"] = detected_lang

                    # Upsert user: keep 'auto' if explicitly set otherwise store detected.
                    user_db = UserModel.get(message.author.id)
                    if not user_db or (user_db.get("preferred_language") in (None, "", "auto")):
                        UserModel.upsert(message.author.id, message.author.name, detected_lang)
                    else:
                        UserModel.upsert(message.author.id, message.author.name, user_db.get("preferred_language"))

                    await self._try_update_welcome_embed(message.channel, ticket["id"])

            staff_lang = ticket.get("staff_language") or guild_config.get("default_language") or "en"
            if staff_lang == "auto":
                staff_lang = guild_config.get("default_language") or "en"

            # Prefer per-message detection for translation source; fall back to stored ticket language.
            user_lang = detected_lang or (ticket.get("user_language") if ticket.get("user_language") not in (None, "", "auto") else None)

            if auto_translate and user_lang and staff_lang and user_lang != staff_lang:
                try:
                    translated_text, from_cache = self.translator.translate_message_for_staff(
                        message.content, user_lang, staff_lang
                    )
                    target_language = staff_lang

                    embed = discord.Embed(
                        description=translated_text[:4000],
                        color=discord.Color.blurple(),
                    )
                    embed.set_author(
                        name=f"Traduction · {user_lang.upper()} → {staff_lang.upper()} ({'cache' if from_cache else 'api'})"
                    )
                    await message.channel.send(embed=embed, reference=message, mention_author=False)
                    logger.debug(f"Traduction user->staff envoyee pour ticket {ticket['id']}")
                except Exception as e:
                    logger.error(f"Erreur traduction ticket {ticket['id']}: {e}")

            # Stocker le message (et la traduction si presente)
            try:
                attachments = []
                for a in (message.attachments or []):
                    attachments.append({
                        "url": a.url,
                        "filename": a.filename,
                        "size": a.size,
                        "content_type": a.content_type,
                    })
                TicketMessageModel.create(
                    ticket_id=ticket["id"],
                    author_id=message.author.id,
                    author_username=message.author.name,
                    discord_message_id=message.id,
                    original_content=message.content,
                    translated_content=translated_text,
                    original_language=user_lang,
                    target_language=target_language,
                    from_cache=from_cache,
                    attachments_json=json.dumps(attachments, ensure_ascii=False) if attachments else None,
                )
            except Exception as e:
                logger.warning(f"DB store ticket message failed (ticket {ticket['id']}): {e}")

            return

        # ── Staff (or other participant) message: detect staff language if needed ──
        staff_lang = ticket.get("staff_language")
        if not staff_lang or staff_lang == "auto":
            if detected_lang:
                staff_lang = detected_lang
                TicketModel.update(ticket["id"], staff_language=staff_lang)
                ticket["staff_language"] = staff_lang
                await self._try_update_welcome_embed(message.channel, ticket["id"])
            else:
                staff_lang = guild_config.get("default_language") or "en"

        # User language might still be pending if the user hasn't typed yet.
        user_lang = ticket.get("user_language")
        if not user_lang or user_lang == "auto":
            user_db = UserModel.get(ticket["user_id"])
            if user_db and user_db.get("preferred_language") not in (None, "", "auto"):
                user_lang = user_db.get("preferred_language")

        # Prefer per-message detection for translation source.
        staff_src_lang = detected_lang or staff_lang

        if auto_translate and staff_src_lang and user_lang and staff_src_lang != user_lang:
            try:
                translated_text, from_cache = self.translator.translate_response_for_user(
                    message.content, staff_src_lang, user_lang
                )
                target_language = user_lang

                embed = discord.Embed(
                    description=translated_text[:4000],
                    color=discord.Color.green(),
                )
                embed.set_author(
                    name=f"Traduction · {staff_src_lang.upper()} → {user_lang.upper()} ({'cache' if from_cache else 'api'})"
                )
                await message.channel.send(embed=embed, reference=message, mention_author=False)
                logger.debug(f"Traduction staff->user envoyee pour ticket {ticket['id']}")
            except Exception as e:
                logger.error(f"Erreur traduction ticket {ticket['id']}: {e}")

        # Stocker le message (et la traduction si presente)
        try:
            attachments = []
            for a in (message.attachments or []):
                attachments.append({
                    "url": a.url,
                    "filename": a.filename,
                    "size": a.size,
                    "content_type": a.content_type,
                })
            TicketMessageModel.create(
                ticket_id=ticket["id"],
                author_id=message.author.id,
                author_username=message.author.name,
                discord_message_id=message.id,
                original_content=message.content,
                translated_content=translated_text,
                original_language=staff_src_lang,
                target_language=target_language,
                from_cache=from_cache,
                attachments_json=json.dumps(attachments, ensure_ascii=False) if attachments else None,
            )
        except Exception as e:
            logger.warning(f"DB store ticket message failed (ticket {ticket['id']}): {e}")

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

        # Langue: on attend le premier message de l'utilisateur pour detecter.
        # (Ne pas detecter depuis le pseudo: trop peu fiable)
        user_db = UserModel.get(interaction.user.id)
        user_language = (
            user_db.get("preferred_language")
            if user_db and user_db.get("preferred_language") not in (None, "", "auto")
            else "auto"
        )
        staff_language = guild_config.get("default_language") or "en"

        # Creer en DB avec username
        ticket_id = TicketModel.create(
            guild_id=interaction.guild.id,
            user_id=interaction.user.id,
            user_username=interaction.user.name,
            channel_id=ticket_channel.id,
            user_language=user_language,
            staff_language=staff_language
        )
        if not ticket_id:
            try:
                await ticket_channel.delete(reason="DB ticket create failed")
            except Exception:
                pass
            await interaction.followup.send(
                "Erreur: impossible de créer le ticket en base de données. Réessayez plus tard.",
                ephemeral=True,
            )
            return

        # Upsert utilisateur
        UserModel.upsert(interaction.user.id, interaction.user.name, user_language)

        # Message de bienvenue
        embed = self._build_ticket_welcome_embed(
            ticket_id=ticket_id,
            user_language=user_language,
            staff_language=staff_language,
        )
        view = TicketCloseView(ticket_id, self.bot)
        welcome_msg = await ticket_channel.send(embed=embed, view=view)
        try:
            TicketModel.update(ticket_id, initial_message_id=welcome_msg.id)
        except Exception:
            pass

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
            msgs = TicketMessageModel.get_by_ticket(ticket["id"])
            # Limiter pour eviter un prompt trop long.
            last = msgs[-60:] if msgs else []
            conversation = [
                {"author": m.get("author_username") or str(m.get("author_id")), "content": m.get("original_content") or ""}
                for m in last
            ]
            lang = ticket.get("user_language") or ticket.get("staff_language") or "en"
            if lang == "auto":
                lang = ticket.get("staff_language") or "en"
            transcript = self.groq_client.generate_ticket_summary(conversation, lang)
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

        # Resume IA (best-effort)
        transcript = ""
        try:
            msgs = TicketMessageModel.get_by_ticket(self.ticket_id)
            last = msgs[-60:] if msgs else []
            conversation = [
                {"author": m.get("author_username") or str(m.get("author_id")), "content": m.get("original_content") or ""}
                for m in last
            ]
            lang = ticket.get("user_language") or ticket.get("staff_language") or "en"
            if lang == "auto":
                lang = ticket.get("staff_language") or "en"
            transcript = GroqClient().generate_ticket_summary(conversation, lang)
        except Exception:
            transcript = ""

        TicketModel.close(self.ticket_id, transcript=transcript, close_reason="Ferme via bouton")
        button.disabled = True
        await interaction.response.edit_message(
            content="Ticket ferme.", view=self
        )
        logger.info(f"Ticket {self.ticket_id} ferme via bouton par {interaction.user.id}")


async def setup(bot):
    await bot.add_cog(TicketsCog(bot))

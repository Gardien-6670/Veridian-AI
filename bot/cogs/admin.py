"""
Cog: Admin - Commandes réservées au Bot Owner
Validation de paiements, révocation d'abonnements, gestion des commandes
"""

import discord
from discord.ext import commands
from loguru import logger
from bot.db.models import OrderModel, SubscriptionModel, PaymentModel, GuildModel
from bot.config import BOT_OWNER_DISCORD_ID, PRICING
from datetime import datetime, timedelta


class AdminCog(commands.Cog):
    """Commandes réservées au Bot Owner."""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("✓ Cog Admin chargé")

    def is_bot_owner(self):
        """Vérifie que l'utilisateur est le Bot Owner."""
        async def predicate(interaction: discord.Interaction) -> bool:
            if interaction.user.id != BOT_OWNER_DISCORD_ID:
                await interaction.response.send_message(
                    "❌ Seul le Bot Owner peut utiliser cette commande.",
                    ephemeral=True
                )
                return False
            return True
        return commands.check(predicate)

    @discord.app_commands.command(name="validate", description="[Admin] Valider une commande")
    @discord.app_commands.describe(
        order_id="Numéro de commande (ex: VAI-202501-4823)",
        plan="Plan: premium ou pro"
    )
    async def validate_order(self, interaction: discord.Interaction, order_id: str, plan: str):
        """Valide manuellement un paiement PayPal ou Carte Cadeau."""
        
        if interaction.user.id != BOT_OWNER_DISCORD_ID:
            await interaction.response.send_message(
                "❌ Seul le Bot Owner peut utiliser cette commande.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Récupérer la commande
            order = OrderModel.get(order_id)
            if not order:
                await interaction.followup.send(f"❌ Commande `{order_id}` non trouvée.")
                return

            # Mettre à jour le statut
            OrderModel.update_status(order_id, 'paid', 'Validée par admin')

            # Créer l'abonnement
            duration_days = 30  # Par défaut 1 mois
            SubscriptionModel.create(
                guild_id=order['guild_id'],
                user_id=order['user_id'],
                plan=plan,
                payment_id=order['id'],
                duration_days=duration_days
            )

            # Notifier l'utilisateur
            user = await self.bot.fetch_user(order['user_id'])
            if user:
                guild = self.bot.get_guild(order['guild_id'])
                guild_name = guild.name if guild else f"Guild {order['guild_id']}"

                embed = discord.Embed(
                    title="✅ Paiement Confirmé",
                    color=discord.Color.green(),
                    description=f"Votre abonnement **{plan.upper()}** a été activé sur **{guild_name}** ! Merci ✨"
                )
                await user.send(embed=embed)

            await interaction.followup.send(
                f"✅ Commande `{order_id}` validée et abonnement activé.",
                ephemeral=True
            )

            logger.info(f"✓ Commande {order_id} validée par admin")

        except Exception as e:
            logger.error(f"✗ Erreur validate_order: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}")

    @discord.app_commands.command(name="revoke", description="[Admin] Révoquer un abonnement")
    @discord.app_commands.describe(user="Utilisateur dont révoquer l'abonnement")
    async def revoke_subscription(self, interaction: discord.Interaction, user: discord.User):
        """Désactive l'abonnement d'un utilisateur."""
        
        if interaction.user.id != BOT_OWNER_DISCORD_ID:
            await interaction.response.send_message(
                "❌ Seul le Bot Owner peut utiliser cette commande.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Récupérer le guild depuis le contexte (ou demander)
            guild_id = interaction.guild.id if interaction.guild else None
            if not guild_id:
                await interaction.followup.send("❌ Utilisez cette commande dans un serveur Discord.")
                return

            # Désactiver l'abonnement
            SubscriptionModel.deactivate(guild_id)

            # Notifier l'utilisateur
            embed = discord.Embed(
                title="⚠️ Abonnement Résilié",
                color=discord.Color.red(),
                description=f"Votre abonnement sur ce serveur a été résilié."
            )
            await user.send(embed=embed)

            await interaction.followup.send(
                f"✅ Abonnement de {user.mention} résilié.",
                ephemeral=True
            )

            logger.info(f"✓ Abonnement de {user.id} révoqué")

        except Exception as e:
            logger.error(f"✗ Erreur revoke_subscription: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}")

    @discord.app_commands.command(name="orders", description="[Admin] Voir les commandes en attente")
    async def list_pending_orders(self, interaction: discord.Interaction):
        """Liste toutes les commandes en attente de validation."""
        
        if interaction.user.id != BOT_OWNER_DISCORD_ID:
            await interaction.response.send_message(
                "❌ Seul le Bot Owner peut utiliser cette commande.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            orders = OrderModel.list_pending()

            if not orders:
                await interaction.followup.send(
                    "✅ Aucune commande en attente.",
                    ephemeral=True
                )
                return

            # Créer un embed avec les commandes
            embed = discord.Embed(
                title="📋 Commandes en Attente",
                color=discord.Color.blue(),
                description=f"Total: **{len(orders)}** commande(s)"
            )

            for order in orders[:10]:  # Afficher max 10 pour ne pas être trop long
                user_mention = f"<@{order['user_id']}>"
                guild = self.bot.get_guild(order['guild_id'])
                guild_name = guild.name if guild else f"Guild {order['guild_id']}"

                field_value = f"""
                **Méthode**: {order['method'].upper()}
                **Plan**: {order['plan'].upper()}
                **Montant**: {order['amount']:.2f}€
                **Guild**: {guild_name}
                **Crée le**: <t:{int(order['created_at'].timestamp())}:R>
                """

                embed.add_field(
                    name=f"`{order['order_id']}` - {user_mention}",
                    value=field_value,
                    inline=False
                )

            embed.set_footer(text="Utilisez /validate [order_id] [plan] pour valider")
            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"✓ Commandes listées: {len(orders)}")

        except Exception as e:
            logger.error(f"✗ Erreur list_pending_orders: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}")

    @discord.app_commands.command(name="setup", description="[Admin] Configurer le bot")
    @discord.app_commands.describe(
        support_channel="Channel pour le support public IA",
        ticket_category="Catégorie pour les tickets",
        staff_role="Rôle du staff"
    )
    async def setup_bot(self, interaction: discord.Interaction, 
                       support_channel: discord.TextChannel,
                       ticket_category: discord.CategoryChannel,
                       staff_role: discord.Role):
        """Configure le bot pour le serveur."""
        
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Vous devez être admin du serveur.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # Créer ou mettre à jour la config du guild
            guild_config = GuildModel.get(interaction.guild.id)
            if guild_config:
                GuildModel.update(
                    interaction.guild.id,
                    support_channel_id=support_channel.id,
                    ticket_category_id=ticket_category.id,
                    staff_role_id=staff_role.id
                )
            else:
                GuildModel.create(
                    guild_id=interaction.guild.id,
                    name=interaction.guild.name
                )
                GuildModel.update(
                    interaction.guild.id,
                    support_channel_id=support_channel.id,
                    ticket_category_id=ticket_category.id,
                    staff_role_id=staff_role.id
                )

            embed = discord.Embed(
                title="✅ Configuration Terminée",
                color=discord.Color.green(),
                description="Le bot est maintenant configuré pour ce serveur!"
            )
            embed.add_field(name="Channel Support IA", value=support_channel.mention, inline=True)
            embed.add_field(name="Catégorie Tickets", value=ticket_category.name, inline=True)
            embed.add_field(name="Rôle Staff", value=staff_role.mention, inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"✓ Bot configuré pour {interaction.guild.id}")

        except Exception as e:
            logger.error(f"✗ Erreur setup_bot: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}")


async def setup(bot):
    """Charge le cog Admin."""
    await bot.add_cog(AdminCog(bot))

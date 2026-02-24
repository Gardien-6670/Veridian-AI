"""
Service de notifications: envoi de DM au Bot Owner avec embeds et boutons
"""

import discord
from loguru import logger
from typing import Optional
from bot.config import BOT_OWNER_DISCORD_ID


class NotificationService:
    def __init__(self, bot):
        """Initialise le service de notifications."""
        self.bot = bot
        logger.info("✓ Service de Notifications initialisé")

    async def send_paypal_order_notification(self, user_id: int, order_id: str, 
                                             plan: str, amount: float, guild_id: int):
        """
        Envoie une notification au Bot Owner pour une commande PayPal.
        Inclut les 4 boutons d'action (Payé, Non payé, Incomplet, Détails)
        
        Args:
            user_id: ID Discord de l'utilisateur
            order_id: Numéro de commande
            plan: Plan (premium/pro)
            amount: Montant attendu
            guild_id: ID du serveur Discord
        """
        try:
            owner = await self.bot.fetch_user(BOT_OWNER_DISCORD_ID)
            if not owner:
                logger.warning(f"✗ Bot Owner {BOT_OWNER_DISCORD_ID} non trouvé")
                return

            guild = self.bot.get_guild(guild_id)
            guild_name = guild.name if guild else f"Guild {guild_id}"

            user = await self.bot.fetch_user(user_id)
            username = user.name if user else f"User {user_id}"

            # Embed avec les infos
            embed = discord.Embed(
                title="💳 Nouvelle commande PayPal",
                color=discord.Color.gold(),
                description=f"Une nouvelle commande PayPal doit être validée."
            )
            embed.add_field(name="Order ID", value=f"`{order_id}`", inline=False)
            embed.add_field(name="Utilisateur", value=f"{username} (<@{user_id}>)", inline=True)
            embed.add_field(name="ID Discord", value=f"`{user_id}`", inline=True)
            embed.add_field(name="Serveur", value=guild_name, inline=True)
            embed.add_field(name="Plan", value=plan.upper(), inline=True)
            embed.add_field(name="Montant attendu", value=f"{amount:.2f}€", inline=True)
            embed.timestamp = discord.utils.utcnow()

            # Boutons d'action
            view = PaymentButtonView(order_id, self.bot)

            await owner.send(embed=embed, view=view)
            logger.info(f"✓ Notification PayPal envoyée au Bot Owner pour {order_id}")

        except Exception as e:
            logger.error(f"✗ Erreur envoi notification PayPal: {e}")

    async def send_giftcard_order_notification(self, user_id: int, order_id: str,
                                               plan: str, amount: float, guild_id: int,
                                               giftcard_code: str, image_url: Optional[str] = None):
        """
        Envoie une notification au Bot Owner pour une commande carte cadeau.
        Inclut le code et l'image (si fournie)
        
        Args:
            user_id: ID Discord de l'utilisateur
            order_id: Numéro de commande
            plan: Plan (premium/pro)
            amount: Montant attendu
            guild_id: ID du serveur Discord
            giftcard_code: Code de la carte cadeau
            image_url: URL de l'image de la carte (optionnel)
        """
        try:
            owner = await self.bot.fetch_user(BOT_OWNER_DISCORD_ID)
            if not owner:
                logger.warning(f"✗ Bot Owner {BOT_OWNER_DISCORD_ID} non trouvé")
                return

            guild = self.bot.get_guild(guild_id)
            guild_name = guild.name if guild else f"Guild {guild_id}"

            user = await self.bot.fetch_user(user_id)
            username = user.name if user else f"User {user_id}"

            # Embed avec les infos
            embed = discord.Embed(
                title="🎁 Nouvelle commande Carte Cadeau",
                color=discord.Color.brand_green(),
                description=f"Une nouvelle commande par carte cadeau doit être validée."
            )
            embed.add_field(name="Order ID", value=f"`{order_id}`", inline=False)
            embed.add_field(name="Utilisateur", value=f"{username} (<@{user_id}>)", inline=True)
            embed.add_field(name="ID Discord", value=f"`{user_id}`", inline=True)
            embed.add_field(name="Serveur", value=guild_name, inline=True)
            embed.add_field(name="Plan", value=plan.upper(), inline=True)
            embed.add_field(name="Montant attendu", value=f"{amount:.2f}€", inline=True)
            embed.add_field(name="Code Carte", value=f"`{giftcard_code}`", inline=False)
            
            if image_url:
                embed.set_image(url=image_url)
            
            embed.timestamp = discord.utils.utcnow()

            # Boutons d'action
            view = PaymentButtonView(order_id, self.bot)

            await owner.send(embed=embed, view=view)
            logger.info(f"✓ Notification Carte Cadeau envoyée au Bot Owner pour {order_id}")

        except Exception as e:
            logger.error(f"✗ Erreur envoi notification carte cadeau: {e}")

    async def notify_user_payment_confirmed(self, user_id: int, plan: str, guild_id: int):
        """Notifie l'utilisateur que son paiement a été accepté."""
        try:
            user = await self.bot.fetch_user(user_id)
            guild = self.bot.get_guild(guild_id)
            guild_name = guild.name if guild else f"Guild {guild_id}"

            embed = discord.Embed(
                title="✅ Paiement Confirmé",
                color=discord.Color.green(),
                description=f"Votre abonnement **{plan.upper()}** a été activé sur **{guild_name}** ! Merci ✨"
            )

            await user.send(embed=embed)
            logger.info(f"✓ Notification confirmation paiement envoyée à {user_id}")

        except Exception as e:
            logger.error(f"✗ Erreur notification utilisateur: {e}")

    async def notify_user_payment_pending(self, user_id: int, order_id: str):
        """Notifie l'utilisateur que son paiement est en attente de validation."""
        try:
            user = await self.bot.fetch_user(user_id)

            embed = discord.Embed(
                title="⏳ Commande en Attente",
                color=discord.Color.orange(),
                description=f"Votre commande `{order_id}` est en attente de validation. Cela peut prendre jusqu'à 24h."
            )

            await user.send(embed=embed)
            logger.info(f"✓ Notification attente envoyée à {user_id}")

        except Exception as e:
            logger.error(f"✗ Erreur notification attente: {e}")


# ============================================================================
# Vue avec boutons pour les actions PayPal/Giftcard
# ============================================================================

class PaymentButtonView(discord.ui.View):
    def __init__(self, order_id: str, bot):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.bot = bot

    @discord.ui.button(label="✅ Payé", style=discord.ButtonStyle.success)
    async def paid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Marque la commande comme payée."""
        await interaction.response.defer()
        # À implémenter: logique de validation et activation du plan
        logger.info(f"Bouton PAYÉ cliqué pour {self.order_id}")

    @discord.ui.button(label="❌ Non payé", style=discord.ButtonStyle.danger)
    async def not_paid_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Marque la commande comme non payée."""
        await interaction.response.defer()
        # À implémenter: logique de rejet
        logger.info(f"Bouton NON PAYÉ cliqué pour {self.order_id}")

    @discord.ui.button(label="⚠️ Montant incomplet", style=discord.ButtonStyle.secondary)
    async def partial_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Marque la commande comme partiellement payée."""
        await interaction.response.defer()
        # À implémenter: logique de paiement partiel
        logger.info(f"Bouton INCOMPLET cliqué pour {self.order_id}")

    @discord.ui.button(label="🔍 Détails", style=discord.ButtonStyle.primary)
    async def details_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Affiche les détails de la commande."""
        await interaction.response.defer()
        # À implémenter: affichage des détails
        logger.info(f"Bouton DÉTAILS cliqué pour {self.order_id}")

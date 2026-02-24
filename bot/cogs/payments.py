"""
Cog: Paiements - Gestion des commandes PayPal, Cartes Cadeaux et Crypto
"""

import discord
from discord.ext import commands
from loguru import logger
import random
import datetime
from bot.db.models import OrderModel, SubscriptionModel, PaymentModel, UserModel, GuildModel
from bot.services.notifications import NotificationService
from bot.services.oxapay import OxaPayClient
from bot.config import BOT_OWNER_DISCORD_ID, PRICING


class PaymentsCog(commands.Cog):
    """Gère tous les paiements (PayPal, Giftcard, Crypto)."""
    
    def __init__(self, bot):
        self.bot = bot
        self.notifications = NotificationService(bot)
        self.oxapay = OxaPayClient()
        logger.info("✓ Cog Paiements chargé")

    @staticmethod
    def generate_order_id() -> str:
        """Génère un numéro de commande unique au format VAI-YYYYMM-XXXX"""
        now = datetime.datetime.now()
        rand = random.randint(1000, 9999)
        return f'VAI-{now.year}{now.month:02d}-{rand}'

    @discord.app_commands.command(name="pay", description="Initier un paiement")
    @discord.app_commands.describe(
        method="Méthode de paiement: paypal, giftcard, ou crypto",
        plan="Plan: premium ou pro"
    )
    @discord.app_commands.choices(
        method=[
            discord.app_commands.Choice(name="PayPal", value="paypal"),
            discord.app_commands.Choice(name="Carte Cadeau", value="giftcard"),
            discord.app_commands.Choice(name="Crypto (BTC, ETH, USDT)", value="crypto"),
        ],
        plan=[
            discord.app_commands.Choice(name="Premium (2€/mois)", value="premium"),
            discord.app_commands.Choice(name="Pro (5€/mois)", value="pro"),
        ]
    )
    async def pay(self, interaction: discord.Interaction, method: str, plan: str):
        """Initie un paiement pour upgrader le serveur."""
        
        # Vérifier que l'utilisateur est admin
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Vous devez être admin du serveur pour faire un paiement.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        try:
            amount = PRICING.get(plan, 0)
            if amount == 0:
                await interaction.followup.send("❌ Plan invalide.")
                return

            # Créer la commande en DB
            order_id = self.generate_order_id()
            OrderModel.create(
                order_id=order_id,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                method=method,
                plan=plan,
                amount=amount
            )

            # Router selon la méthode
            if method == "paypal":
                await self._handle_paypal(interaction, order_id, plan, amount)

            elif method == "giftcard":
                await self._handle_giftcard(interaction, order_id, plan, amount)

            elif method == "crypto":
                await self._handle_crypto(interaction, order_id, plan, amount)

            logger.info(f"✓ Paiement initialisé: {order_id} ({method})")

        except Exception as e:
            logger.error(f"✗ Erreur pay: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}")

    async def _handle_paypal(self, interaction: discord.Interaction, order_id: str, plan: str, amount: float):
        """Flux PayPal: affiche les instructions et envoie notification au Bot Owner."""
        
        import os
        paypal_email = os.getenv('PAYPAL_EMAIL', '[Email PayPal non configuré]')

        embed = discord.Embed(
            title="💳 Paiement PayPal",
            color=discord.Color.blue(),
            description="Veuillez envoyer le paiement via PayPal en suivant les instructions ci-dessous."
        )
        embed.add_field(name="Plan", value=plan.upper(), inline=True)
        embed.add_field(name="Montant", value=f"{amount:.2f}€", inline=True)
        embed.add_field(
            name="Instructions",
            value=f"""
            1. Envoyez le paiement à: **{paypal_email}**
            2. Dans le commentaire, mettez: **{order_id}**
            3. Attendez la confirmation (max 24h)
            
            ⚠️ **IMPORTANT**: Sans le numéro de commande, votre paiement ne sera pas reconnu!
            """,
            inline=False
        )
        embed.set_footer(text="Votre commande sera vérifiée dans les 24 heures")

        await interaction.followup.send(embed=embed, ephemeral=True)

        # Envoyer notification au Bot Owner
        await self.notifications.send_paypal_order_notification(
            interaction.user.id,
            order_id,
            plan,
            amount,
            interaction.guild.id
        )

    async def _handle_giftcard(self, interaction: discord.Interaction, order_id: str, plan: str, amount: float):
        """Flux Carte Cadeau: demande le code et l'image."""
        
        embed = discord.Embed(
            title="🎁 Carte Cadeau",
            color=discord.Color.green(),
            description="Veuillez répondre aux messages ci-dessous avec votre code et image de carte."
        )
        embed.add_field(name="Plan", value=plan.upper(), inline=True)
        embed.add_field(name="Montant", value=f"{amount:.2f}€", inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

        # Envoyer message pour demander le code
        def check(msg):
            return msg.author.id == interaction.user.id and isinstance(msg.channel, discord.DMChannel)

        try:
            # DM à l'utilisateur pour demander le code
            dm_embed = discord.Embed(
                title="Code Carte Cadeau",
                description=f"Envoyez le code de votre carte cadeau (commande: {order_id})"
            )
            dm_msg = await interaction.user.send(embed=dm_embed)

            # Attendre la réponse avec le code
            code_msg = await self.bot.wait_for('message', check=check, timeout=600)
            giftcard_code = code_msg.content

            # Demander l'image
            img_embed = discord.Embed(
                title="Image Carte Cadeau",
                description="Maintenant, envoyez une image de votre carte cadeau (joint le fichier)"
            )
            await interaction.user.send(embed=img_embed)

            # Attendre la réponse avec l'image
            img_msg = await self.bot.wait_for('message', check=check, timeout=600)
            
            image_url = None
            if img_msg.attachments:
                image_url = img_msg.attachments[0].url

            # Stocker en DB
            OrderModel.create(
                order_id=order_id,
                user_id=interaction.user.id,
                guild_id=interaction.guild.id,
                method='giftcard',
                plan=plan,
                amount=amount
            )

            # Envoyer notification au Bot Owner
            await self.notifications.send_giftcard_order_notification(
                interaction.user.id,
                order_id,
                plan,
                amount,
                interaction.guild.id,
                giftcard_code,
                image_url
            )

            await interaction.user.send(
                "✅ Merci! Votre commande est en attente de validation (max 24h)."
            )

        except asyncio.TimeoutError:
            await interaction.user.send("❌ Délai dépassé. Veuillez recommencer.")
        except Exception as e:
            logger.error(f"✗ Erreur giftcard: {e}")
            await interaction.user.send(f"❌ Erreur: {str(e)}")

    async def _handle_crypto(self, interaction: discord.Interaction, order_id: str, plan: str, amount: float):
        """Flux OxaPay: crée une invoice et envoie le lien de paiement."""
        
        await interaction.followup.send(
            "⏳ Génération de l'invoice crypto en cours...",
            ephemeral=True
        )

        try:
            # Créer l'invoice via OxaPay
            callback_url = "https://veridiancloud.xyz/webhook/oxapay"
            
            invoice = await self.oxapay.create_invoice(
                interaction.user.id,
                amount,
                order_id,
                callback_url
            )

            if not invoice or 'payLink' not in invoice:
                await interaction.followup.send(
                    "❌ Erreur lors de la création de l'invoice. Veuillez réessayer.",
                    ephemeral=True
                )
                return

            pay_link = invoice['payLink']

            embed = discord.Embed(
                title="🪙 Paiement Crypto",
                color=discord.Color.gold(),
                description="Cliquez sur le bouton ci-dessous pour effectuer votre paiement."
            )
            embed.add_field(name="Plan", value=plan.upper(), inline=True)
            embed.add_field(name="Montant", value=f"{amount:.2f}€", inline=True)

            view = discord.ui.View()
            view.add_item(discord.ui.Button(label="💳 Payer Maintenant", url=pay_link))

            await interaction.followup.send(
                embed=embed,
                view=view,
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"✗ Erreur crypto: {e}")
            await interaction.followup.send(f"❌ Erreur: {str(e)}", ephemeral=True)


import asyncio


async def setup(bot):
    """Charge le cog Paiements."""
    await bot.add_cog(PaymentsCog(bot))

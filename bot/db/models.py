"""
Modèles et fonctions CRUD pour toutes les tables Veridian AI
Respecte la structure de schéma définie dans le cahier des charges
"""

from datetime import datetime, timedelta
from bot.db.connection import get_db_context
from bot.config import DB_TABLE_PREFIX
from loguru import logger
from typing import Optional, List, Dict, Any


# ============================================================================
# VAI_GUILDS
# ============================================================================

class GuildModel:
    @staticmethod
    def create(guild_id: int, name: str, tier: str = 'free') -> bool:
        """Crée un enregistrement de serveur."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}guilds 
                    (id, name, tier) 
                    VALUES (%s, %s, %s)
                """
                cursor.execute(query, (guild_id, name, tier))
                logger.info(f"✓ Serveur {guild_id} créé")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur création serveur: {e}")
                return False

    @staticmethod
    def get(guild_id: int) -> Optional[Dict]:
        """Récupère les infos d'un serveur."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}guilds WHERE id = %s"
            cursor.execute(query, (guild_id,))
            return cursor.fetchone()

    @staticmethod
    def update(guild_id: int, **kwargs) -> bool:
        """Met à jour les infos d'un serveur."""
        if not kwargs:
            return False
        
        with get_db_context() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
            values = list(kwargs.values()) + [guild_id]
            
            query = f"UPDATE {DB_TABLE_PREFIX}guilds SET {set_clause} WHERE id = %s"
            try:
                cursor.execute(query, values)
                logger.info(f"✓ Serveur {guild_id} mis à jour")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur mise à jour serveur: {e}")
                return False


# ============================================================================
# VAI_USERS
# ============================================================================

class UserModel:
    @staticmethod
    def create(user_id: int, username: str, preferred_language: str = 'auto') -> bool:
        """Crée un enregistrement utilisateur."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}users 
                    (id, username, preferred_language) 
                    VALUES (%s, %s, %s)
                """
                cursor.execute(query, (user_id, username, preferred_language))
                logger.info(f"✓ Utilisateur {user_id} créé")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur création utilisateur: {e}")
                return False

    @staticmethod
    def get(user_id: int) -> Optional[Dict]:
        """Récupère les infos d'un utilisateur."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}users WHERE id = %s"
            cursor.execute(query, (user_id,))
            return cursor.fetchone()

    @staticmethod
    def update(user_id: int, **kwargs) -> bool:
        """Met à jour un utilisateur."""
        if not kwargs:
            return False
        
        with get_db_context() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
            values = list(kwargs.values()) + [user_id]
            
            query = f"UPDATE {DB_TABLE_PREFIX}users SET {set_clause} WHERE id = %s"
            try:
                cursor.execute(query, values)
                logger.info(f"✓ Utilisateur {user_id} mis à jour")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur mise à jour utilisateur: {e}")
                return False


# ============================================================================
# VAI_TICKETS
# ============================================================================

class TicketModel:
    @staticmethod
    def create(guild_id: int, user_id: int, channel_id: int, user_language: str, 
               staff_language: str = 'en') -> Optional[int]:
        """Crée un nouveau ticket."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}tickets 
                    (guild_id, user_id, channel_id, user_language, staff_language, status) 
                    VALUES (%s, %s, %s, %s, %s, 'open')
                """
                cursor.execute(query, (guild_id, user_id, channel_id, user_language, staff_language))
                ticket_id = cursor.lastrowid
                logger.info(f"✓ Ticket {ticket_id} créé")
                return ticket_id
            except Exception as e:
                logger.error(f"✗ Erreur création ticket: {e}")
                return None

    @staticmethod
    def get(ticket_id: int) -> Optional[Dict]:
        """Récupère les infos d'un ticket."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}tickets WHERE id = %s"
            cursor.execute(query, (ticket_id,))
            return cursor.fetchone()

    @staticmethod
    def get_by_channel(channel_id: int) -> Optional[Dict]:
        """Récupère un ticket par son channel_id."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}tickets WHERE channel_id = %s"
            cursor.execute(query, (channel_id,))
            return cursor.fetchone()

    @staticmethod
    def close(ticket_id: int, transcript: str = "", close_reason: str = "") -> bool:
        """Ferme un ticket."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            query = f"""
                UPDATE {DB_TABLE_PREFIX}tickets 
                SET status = 'closed', transcript = %s, close_reason = %s, closed_at = NOW() 
                WHERE id = %s
            """
            try:
                cursor.execute(query, (transcript, close_reason, ticket_id))
                logger.info(f"✓ Ticket {ticket_id} fermé")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur fermeture ticket: {e}")
                return False

    @staticmethod
    def update(ticket_id: int, **kwargs) -> bool:
        """Met à jour un ticket."""
        if not kwargs:
            return False
        
        with get_db_context() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
            values = list(kwargs.values()) + [ticket_id]
            
            query = f"UPDATE {DB_TABLE_PREFIX}tickets SET {set_clause} WHERE id = %s"
            try:
                cursor.execute(query, values)
                logger.info(f"✓ Ticket {ticket_id} mis à jour")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur mise à jour ticket: {e}")
                return False


# ============================================================================
# VAI_ORDERS
# ============================================================================

class OrderModel:
    @staticmethod
    def create(order_id: str, user_id: int, guild_id: int, method: str, plan: str, 
               amount: float) -> Optional[int]:
        """Crée une nouvelle commande."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}orders 
                    (order_id, user_id, guild_id, method, plan, amount, status) 
                    VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                """
                cursor.execute(query, (order_id, user_id, guild_id, method, plan, amount))
                order_db_id = cursor.lastrowid
                logger.info(f"✓ Commande {order_id} créée")
                return order_db_id
            except Exception as e:
                logger.error(f"✗ Erreur création commande: {e}")
                return None

    @staticmethod
    def get(order_id: str) -> Optional[Dict]:
        """Récupère une commande par order_id."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}orders WHERE order_id = %s"
            cursor.execute(query, (order_id,))
            return cursor.fetchone()

    @staticmethod
    def update_status(order_id: str, status: str, admin_note: str = "") -> bool:
        """Met à jour le statut d'une commande."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            query = f"""
                UPDATE {DB_TABLE_PREFIX}orders 
                SET status = %s, admin_note = %s, validated_at = NOW() 
                WHERE order_id = %s
            """
            try:
                cursor.execute(query, (status, admin_note, order_id))
                logger.info(f"✓ Commande {order_id} statut -> {status}")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur mise à jour commande: {e}")
                return False

    @staticmethod
    def list_pending() -> List[Dict]:
        """Liste toutes les commandes en attente."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}orders WHERE status = 'pending' ORDER BY created_at DESC"
            cursor.execute(query)
            return cursor.fetchall()


# ============================================================================
# VAI_SUBSCRIPTIONS
# ============================================================================

class SubscriptionModel:
    @staticmethod
    def create(guild_id: int, user_id: int, plan: str, payment_id: int, 
               duration_days: Optional[int] = None) -> bool:
        """Crée un nouvel abonnement."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                expires_at = None
                if duration_days:
                    expires_at = datetime.now() + timedelta(days=duration_days)
                
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}subscriptions 
                    (guild_id, user_id, plan, started_at, expires_at, is_active, payment_id) 
                    VALUES (%s, %s, %s, NOW(), %s, 1, %s)
                """
                cursor.execute(query, (guild_id, user_id, plan, expires_at, payment_id))
                logger.info(f"✓ Abonnement créé pour {guild_id} - plan {plan}")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur création abonnement: {e}")
                return False

    @staticmethod
    def get(guild_id: int) -> Optional[Dict]:
        """Récupère l'abonnement d'un serveur."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}subscriptions WHERE guild_id = %s AND is_active = 1"
            cursor.execute(query, (guild_id,))
            return cursor.fetchone()

    @staticmethod
    def deactivate(guild_id: int) -> bool:
        """Désactive l'abonnement d'un serveur."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            query = f"UPDATE {DB_TABLE_PREFIX}subscriptions SET is_active = 0 WHERE guild_id = %s"
            try:
                cursor.execute(query, (guild_id,))
                logger.info(f"✓ Abonnement désactivé pour {guild_id}")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur désactivation: {e}")
                return False


# ============================================================================
# VAI_PAYMENTS - Historique des paiements
# ============================================================================

class PaymentModel:
    @staticmethod
    def create(user_id: int, guild_id: int, method: str, amount: float, 
               currency: str, plan: str, order_id: str = None, status: str = 'completed') -> Optional[int]:
        """Crée un nouveau paiement."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}payments 
                    (user_id, guild_id, order_id, method, amount, currency, plan, status) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (user_id, guild_id, order_id, method, amount, currency, plan, status))
                payment_id = cursor.lastrowid
                logger.info(f"✓ Paiement {payment_id} créé - Status: {status}")
                return payment_id
            except Exception as e:
                logger.error(f"✗ Erreur création paiement: {e}")
                return None

    @staticmethod
    def get(payment_id: int) -> Optional[Dict]:
        """Récupère un paiement par ID."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}payments WHERE id = %s"
            cursor.execute(query, (payment_id,))
            return cursor.fetchone()

    @staticmethod
    def list_by_user(user_id: int) -> List[Dict]:
        """Liste tous les paiements d'un utilisateur."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}payments WHERE user_id = %s ORDER BY paid_at DESC"
            cursor.execute(query, (user_id,))
            return cursor.fetchall()

    @staticmethod
    def update_status(payment_id: int, status: str) -> bool:
        """Met à jour le statut d'un paiement."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            query = f"UPDATE {DB_TABLE_PREFIX}payments SET status = %s WHERE id = %s"
            try:
                cursor.execute(query, (status, payment_id))
                logger.info(f"✓ Paiement {payment_id} statut -> {status}")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur mise à jour paiement: {e}")
                return False


# ============================================================================
# VAI_TRANSLATIONS_CACHE
# ============================================================================

class TranslationCacheModel:
    @staticmethod
    def get(content_hash: str) -> Optional[Dict]:
        """Récupère une traduction du cache."""
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            query = f"SELECT * FROM {DB_TABLE_PREFIX}translations_cache WHERE content_hash = %s"
            cursor.execute(query, (content_hash,))
            result = cursor.fetchone()
            
            if result:
                # Incrémenter hit_count
                cursor.execute(
                    f"UPDATE {DB_TABLE_PREFIX}translations_cache SET hit_count = hit_count + 1 WHERE content_hash = %s",
                    (content_hash,)
                )
                conn.commit()
            
            return result

    @staticmethod
    def store(content_hash: str, original_text: str, translated_text: str, 
              source_language: str, target_language: str) -> bool:
        """Stocke une traduction dans le cache."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT IGNORE INTO {DB_TABLE_PREFIX}translations_cache 
                    (content_hash, original_text, translated_text, source_language, target_language) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (content_hash, original_text, translated_text, source_language, target_language))
                logger.debug(f"✓ Traduction stockée en cache")
                return True
            except Exception as e:
                logger.error(f"✗ Erreur stockage cache: {e}")
                return False


# ============================================================================
# DashboardSessionModel - Sessions OAuth2 pour dashboard web
# ============================================================================

class DashboardSessionModel:
    """Gère les sessions OAuth2 Discord pour accès dashboard"""
    
    @staticmethod
    def create(discord_user_id: int, discord_username: str, access_token: str,
               jwt_token: str, expires_at) -> int:
        """Créer une nouvelle session"""
        try:
            query = """
            INSERT INTO vai_dashboard_sessions 
            (discord_user_id, discord_username, access_token, jwt_token, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            """
            cursor.execute(query, (discord_user_id, discord_username, access_token, jwt_token, expires_at))
            connection.commit()
            logger.debug(f"✓ Session dashboard créée pour {discord_username}")
            return cursor.lastrowid
        except Exception as e:
            logger.error(f"✗ Erreur création session dashboard: {e}")
            return None
    
    @staticmethod
    def get_by_token(jwt_token: str) -> dict:
        """Récupérer une session par JWT token"""
        try:
            query = "SELECT * FROM vai_dashboard_sessions WHERE jwt_token = %s AND expires_at > NOW()"
            cursor.execute(query, (jwt_token,))
            result = cursor.fetchone()
            if result:
                logger.debug(f"✓ Session trouvée")
                return dict(result)
            return None
        except Exception as e:
            logger.error(f"✗ Erreur récupération session: {e}")
            return None
    
    @staticmethod
    def revoke_token(jwt_token: str) -> bool:
        """Révoquer un JWT token"""
        try:
            query = "DELETE FROM vai_dashboard_sessions WHERE jwt_token = %s"
            cursor.execute(query, (jwt_token,))
            connection.commit()
            logger.debug(f"✓ Token révoqué")
            return True
        except Exception as e:
            logger.error(f"✗ Erreur révocation token: {e}")
            return False

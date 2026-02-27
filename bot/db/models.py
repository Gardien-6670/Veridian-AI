"""
Modeles et fonctions CRUD pour toutes les tables Veridian AI v0.2
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
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}guilds (id, name, tier)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE name = VALUES(name)
                """
                cursor.execute(query, (guild_id, name, tier))
                logger.info(f"Guild {guild_id} cree/mis a jour")
                return True
            except Exception as e:
                logger.error(f"Erreur creation guild: {e}")
                return False

    @staticmethod
    def get(guild_id: int) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT * FROM {DB_TABLE_PREFIX}guilds WHERE id = %s", (guild_id,))
            return cursor.fetchone()

    @staticmethod
    def get_all() -> List[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT * FROM {DB_TABLE_PREFIX}guilds ORDER BY created_at DESC")
            return cursor.fetchall()

    @staticmethod
    def update(guild_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        with get_db_context() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
            values = list(kwargs.values()) + [guild_id]
            query = f"UPDATE {DB_TABLE_PREFIX}guilds SET {set_clause} WHERE id = %s"
            try:
                cursor.execute(query, values)
                logger.info(f"Guild {guild_id} mis a jour: {list(kwargs.keys())}")
                return True
            except Exception as e:
                logger.error(f"Erreur mise a jour guild: {e}")
                return False

    @staticmethod
    def get_ids() -> List[int]:
        """Retourne tous les IDs de guilds enregistrees."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id FROM {DB_TABLE_PREFIX}guilds")
            return [int(row[0]) for row in cursor.fetchall()]


# ============================================================================
# VAI_USERS
# ============================================================================

class UserModel:

    @staticmethod
    def upsert(user_id: int, username: str, preferred_language: str = 'auto') -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}users (id, username, preferred_language, last_seen_at)
                    VALUES (%s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        username = VALUES(username),
                        last_seen_at = NOW()
                """
                cursor.execute(query, (user_id, username, preferred_language))
                return True
            except Exception as e:
                logger.error(f"Erreur upsert utilisateur: {e}")
                return False

    @staticmethod
    def create(user_id: int, username: str, preferred_language: str = 'auto') -> bool:
        return UserModel.upsert(user_id, username, preferred_language)

    @staticmethod
    def get(user_id: int) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT * FROM {DB_TABLE_PREFIX}users WHERE id = %s", (user_id,))
            return cursor.fetchone()

    @staticmethod
    def update(user_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        with get_db_context() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
            values = list(kwargs.values()) + [user_id]
            query = f"UPDATE {DB_TABLE_PREFIX}users SET {set_clause} WHERE id = %s"
            try:
                cursor.execute(query, values)
                return True
            except Exception as e:
                logger.error(f"Erreur mise a jour utilisateur: {e}")
                return False

    @staticmethod
    def count() -> int:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {DB_TABLE_PREFIX}users")
            return cursor.fetchone()[0]


# ============================================================================
# VAI_TICKETS
# ============================================================================

class TicketModel:

    @staticmethod
    def create(guild_id: int, user_id: int, channel_id: int,
               user_language: str | None, staff_language: str = 'en',
               user_username: str = None) -> Optional[int]:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}tickets
                    (guild_id, user_id, user_username, channel_id, user_language, staff_language, status)
                    VALUES (%s, %s, %s, %s, %s, %s, 'open')
                """
                cursor.execute(query, (guild_id, user_id, user_username,
                                       channel_id, user_language, staff_language))
                ticket_id = cursor.lastrowid
                logger.info(f"Ticket {ticket_id} cree pour guild {guild_id}")
                return ticket_id
            except Exception as e:
                logger.error(f"Erreur creation ticket: {e}")
                return None

    @staticmethod
    def get(ticket_id: int) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(f"SELECT * FROM {DB_TABLE_PREFIX}tickets WHERE id = %s", (ticket_id,))
            return cursor.fetchone()

    @staticmethod
    def get_by_channel(channel_id: int) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT * FROM {DB_TABLE_PREFIX}tickets WHERE channel_id = %s",
                (channel_id,)
            )
            return cursor.fetchone()

    @staticmethod
    def get_by_guild(guild_id: int, status: str = None,
                     page: int = 1, limit: int = 50) -> List[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            offset = (page - 1) * limit
            if status:
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}tickets "
                    f"WHERE guild_id = %s AND status = %s "
                    f"ORDER BY opened_at DESC LIMIT %s OFFSET %s",
                    (guild_id, status, limit, offset)
                )
            else:
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}tickets "
                    f"WHERE guild_id = %s "
                    f"ORDER BY opened_at DESC LIMIT %s OFFSET %s",
                    (guild_id, limit, offset)
                )
            return cursor.fetchall()

    @staticmethod
    def count_by_guild(guild_id: int, status: str = None) -> int:
        with get_db_context() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute(
                    f"SELECT COUNT(*) FROM {DB_TABLE_PREFIX}tickets WHERE guild_id = %s AND status = %s",
                    (guild_id, status)
                )
            else:
                cursor.execute(
                    f"SELECT COUNT(*) FROM {DB_TABLE_PREFIX}tickets WHERE guild_id = %s",
                    (guild_id,)
                )
            return cursor.fetchone()[0]

    @staticmethod
    def count_this_month(guild_id: int) -> int:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {DB_TABLE_PREFIX}tickets "
                f"WHERE guild_id = %s "
                f"AND YEAR(opened_at) = YEAR(CURDATE()) "
                f"AND MONTH(opened_at) = MONTH(CURDATE())",
                (guild_id,),
            )
            return cursor.fetchone()[0]

    @staticmethod
    def count_today() -> int:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {DB_TABLE_PREFIX}tickets WHERE DATE(opened_at) = CURDATE()"
            )
            return cursor.fetchone()[0]

    @staticmethod
    def close(ticket_id: int, transcript: str = "", close_reason: str = "") -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            query = f"""
                UPDATE {DB_TABLE_PREFIX}tickets
                SET status = 'closed', transcript = %s, close_reason = %s, closed_at = NOW()
                WHERE id = %s
            """
            try:
                cursor.execute(query, (transcript, close_reason, ticket_id))
                logger.info(f"Ticket {ticket_id} ferme")
                return True
            except Exception as e:
                logger.error(f"Erreur fermeture ticket: {e}")
                return False

    @staticmethod
    def update(ticket_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        with get_db_context() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
            values = list(kwargs.values()) + [ticket_id]
            query = f"UPDATE {DB_TABLE_PREFIX}tickets SET {set_clause} WHERE id = %s"
            try:
                cursor.execute(query, values)
                return True
            except Exception as e:
                logger.error(f"Erreur update ticket: {e}")
                return False

    @staticmethod
    def get_language_stats(guild_id: int) -> List[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT user_language, COUNT(*) as count FROM {DB_TABLE_PREFIX}tickets "
                f"WHERE guild_id = %s AND MONTH(opened_at) = MONTH(NOW()) "
                f"GROUP BY user_language ORDER BY count DESC",
                (guild_id,)
            )
            return cursor.fetchall()

    @staticmethod
    def get_daily_counts(guild_id: int, days: int = 7) -> List[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT DATE(opened_at) as day, COUNT(*) as count "
                f"FROM {DB_TABLE_PREFIX}tickets "
                f"WHERE guild_id = %s AND opened_at >= DATE_SUB(NOW(), INTERVAL %s DAY) "
                f"GROUP BY DATE(opened_at) ORDER BY day ASC",
                (guild_id, days)
            )
            return cursor.fetchall()


# ============================================================================
# VAI_TICKET_MESSAGES
# ============================================================================

class TicketMessageModel:

    @staticmethod
    def create(
        ticket_id: int,
        author_id: int,
        author_username: str,
        discord_message_id: int | None,
        original_content: str,
        translated_content: str = None,
        original_language: str = None,
        target_language: str = None,
        from_cache: bool = False,
        attachments_json: str | None = None,
    ) -> Optional[int]:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}ticket_messages
                    (ticket_id, author_id, author_username, discord_message_id,
                     original_content, translated_content, original_language,
                     target_language, from_cache, attachments_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    ticket_id, author_id, author_username, discord_message_id,
                    original_content, translated_content, original_language,
                    target_language, int(from_cache), attachments_json
                ))
                return cursor.lastrowid
            except Exception as e:
                logger.error(f"Erreur creation message ticket: {e}")
                return None

    @staticmethod
    def get_by_ticket(ticket_id: int) -> List[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT * FROM {DB_TABLE_PREFIX}ticket_messages "
                f"WHERE ticket_id = %s ORDER BY sent_at ASC",
                (ticket_id,)
            )
            return cursor.fetchall()


# ============================================================================
# VAI_ORDERS
# ============================================================================

class OrderModel:

    @staticmethod
    def create(order_id: str, user_id: int, guild_id: int, method: str,
               plan: str, amount: float, user_username: str = None,
               guild_name: str = None) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}orders
                    (order_id, user_id, user_username, guild_id, guild_name,
                     method, plan, amount, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                """
                cursor.execute(query, (order_id, user_id, user_username,
                                       guild_id, guild_name, method, plan, amount))
                logger.info(f"Commande {order_id} creee")
                return True
            except Exception as e:
                logger.error(f"Erreur creation commande: {e}")
                return False

    @staticmethod
    def get(order_id: str) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT * FROM {DB_TABLE_PREFIX}orders WHERE order_id = %s",
                (order_id,)
            )
            return cursor.fetchone()

    @staticmethod
    def list_pending(limit: int = 100) -> List[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT * FROM {DB_TABLE_PREFIX}orders "
                f"WHERE status = 'pending' ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
            return cursor.fetchall()

    @staticmethod
    def list_all(page: int = 1, limit: int = 50, status: str = None) -> List[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            offset = (page - 1) * limit
            if status:
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}orders "
                    f"WHERE status = %s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (status, limit, offset)
                )
            else:
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}orders "
                    f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset)
                )
            return cursor.fetchall()

    @staticmethod
    def update_status(order_id: str, status: str, admin_note: str = None,
                      validated_by: int = None) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                if status in ('paid', 'partial', 'rejected'):
                    query = f"""
                        UPDATE {DB_TABLE_PREFIX}orders
                        SET status = %s, admin_note = %s, validated_by = %s, validated_at = NOW()
                        WHERE order_id = %s
                    """
                    cursor.execute(query, (status, admin_note, validated_by, order_id))
                else:
                    cursor.execute(
                        f"UPDATE {DB_TABLE_PREFIX}orders SET status = %s WHERE order_id = %s",
                        (status, order_id)
                    )
                logger.info(f"Commande {order_id} statut -> {status}")
                return True
            except Exception as e:
                logger.error(f"Erreur update commande: {e}")
                return False

    @staticmethod
    def count_pending() -> int:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {DB_TABLE_PREFIX}orders WHERE status = 'pending'"
            )
            return cursor.fetchone()[0]

    @staticmethod
    def update_giftcard(order_id: str, giftcard_code: str,
                        giftcard_image_url: str = None) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"UPDATE {DB_TABLE_PREFIX}orders "
                    f"SET giftcard_code = %s, giftcard_image_url = %s WHERE order_id = %s",
                    (giftcard_code, giftcard_image_url, order_id)
                )
                return True
            except Exception as e:
                logger.error(f"Erreur update giftcard: {e}")
                return False


# ============================================================================
# VAI_PAYMENTS
# ============================================================================

class PaymentModel:

    @staticmethod
    def create(user_id: int, guild_id: int, method: str, amount: float,
               currency: str = 'EUR', plan: str = None,
               order_id: str = None, status: str = 'completed',
               oxapay_invoice_id: str = None) -> Optional[int]:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}payments
                    (user_id, guild_id, order_id, method, amount, currency,
                     plan, status, oxapay_invoice_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (user_id, guild_id, order_id, method,
                                       amount, currency, plan, status, oxapay_invoice_id))
                payment_id = cursor.lastrowid
                logger.info(f"Paiement {payment_id} cree - {method} {amount}{currency}")
                return payment_id
            except Exception as e:
                logger.error(f"Erreur creation paiement: {e}")
                return None

    @staticmethod
    def get(payment_id: int) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT * FROM {DB_TABLE_PREFIX}payments WHERE id = %s",
                (payment_id,)
            )
            return cursor.fetchone()

    @staticmethod
    def revenue_this_month() -> float:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COALESCE(SUM(amount), 0) FROM {DB_TABLE_PREFIX}payments "
                f"WHERE status = 'completed' AND MONTH(paid_at) = MONTH(NOW())"
            )
            return float(cursor.fetchone()[0])


# ============================================================================
# VAI_SUBSCRIPTIONS
# ============================================================================

class SubscriptionModel:

    @staticmethod
    def create(guild_id: int, user_id: int, plan: str,
               payment_id: int = None, duration_days: int = 30) -> bool:
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
                    ON DUPLICATE KEY UPDATE
                        plan = VALUES(plan),
                        started_at = NOW(),
                        expires_at = VALUES(expires_at),
                        is_active = 1,
                        payment_id = VALUES(payment_id)
                """
                cursor.execute(query, (guild_id, user_id, plan, expires_at, payment_id))
                logger.info(f"Abonnement {plan} cree/mis a jour pour guild {guild_id}")
                return True
            except Exception as e:
                logger.error(f"Erreur creation abonnement: {e}")
                return False

    @staticmethod
    def get(guild_id: int) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT * FROM {DB_TABLE_PREFIX}subscriptions "
                f"WHERE guild_id = %s AND is_active = 1",
                (guild_id,)
            )
            return cursor.fetchone()

    @staticmethod
    def get_by_guild(guild_id: int) -> Optional[Dict]:
        return SubscriptionModel.get(guild_id)

    @staticmethod
    def deactivate(guild_id: int) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"UPDATE {DB_TABLE_PREFIX}subscriptions SET is_active = 0 WHERE guild_id = %s",
                    (guild_id,)
                )
                logger.info(f"Abonnement desactive pour guild {guild_id}")
                return True
            except Exception as e:
                logger.error(f"Erreur desactivation abonnement: {e}")
                return False

    @staticmethod
    def count_active() -> int:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {DB_TABLE_PREFIX}subscriptions WHERE is_active = 1"
            )
            return cursor.fetchone()[0]


# ============================================================================
# VAI_KNOWLEDGE_BASE
# ============================================================================

class KnowledgeBaseModel:

    @staticmethod
    def create(guild_id: int, question: str, answer: str,
               category: str = None, created_by: int = None) -> Optional[int]:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}knowledge_base
                    (guild_id, question, answer, category, created_by, is_active)
                    VALUES (%s, %s, %s, %s, %s, 1)
                """
                cursor.execute(query, (guild_id, question, answer, category, created_by))
                kb_id = cursor.lastrowid
                logger.info(f"Entree KB {kb_id} creee pour guild {guild_id}")
                return kb_id
            except Exception as e:
                logger.error(f"Erreur creation KB: {e}")
                return None

    @staticmethod
    def get_by_guild(guild_id: int, active_only: bool = True) -> List[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            if active_only:
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}knowledge_base "
                    f"WHERE guild_id = %s AND is_active = 1 ORDER BY priority DESC, created_at ASC",
                    (guild_id,)
                )
            else:
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}knowledge_base "
                    f"WHERE guild_id = %s ORDER BY priority DESC, created_at ASC",
                    (guild_id,)
                )
            return cursor.fetchall()

    @staticmethod
    def get(kb_id: int) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT * FROM {DB_TABLE_PREFIX}knowledge_base WHERE id = %s",
                (kb_id,)
            )
            return cursor.fetchone()

    @staticmethod
    def update(kb_id: int, **kwargs) -> bool:
        if not kwargs:
            return False
        with get_db_context() as conn:
            cursor = conn.cursor()
            set_clause = ", ".join([f"{k} = %s" for k in kwargs.keys()])
            values = list(kwargs.values()) + [kb_id]
            try:
                cursor.execute(
                    f"UPDATE {DB_TABLE_PREFIX}knowledge_base SET {set_clause} WHERE id = %s",
                    values
                )
                return True
            except Exception as e:
                logger.error(f"Erreur update KB: {e}")
                return False

    @staticmethod
    def delete(kb_id: int) -> bool:
        """Suppression logique (is_active = 0)."""
        return KnowledgeBaseModel.update(kb_id, is_active=0)

    @staticmethod
    def hard_delete(kb_id: int) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"DELETE FROM {DB_TABLE_PREFIX}knowledge_base WHERE id = %s",
                    (kb_id,)
                )
                return True
            except Exception as e:
                logger.error(f"Erreur suppression KB: {e}")
                return False

    @staticmethod
    def count(guild_id: int) -> int:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM {DB_TABLE_PREFIX}knowledge_base "
                f"WHERE guild_id = %s AND is_active = 1",
                (guild_id,)
            )
            return cursor.fetchone()[0]


# ============================================================================
# VAI_TRANSLATIONS_CACHE
# ============================================================================

class TranslationCacheModel:

    @staticmethod
    def get(content_hash: str) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT * FROM {DB_TABLE_PREFIX}translations_cache WHERE content_hash = %s",
                (content_hash,)
            )
            result = cursor.fetchone()
            if result:
                cursor.execute(
                    f"UPDATE {DB_TABLE_PREFIX}translations_cache "
                    f"SET hit_count = hit_count + 1 WHERE content_hash = %s",
                    (content_hash,)
                )
            return result

    @staticmethod
    def store(content_hash: str, original_text: str, translated_text: str,
              source_language: str, target_language: str) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT IGNORE INTO {DB_TABLE_PREFIX}translations_cache
                    (content_hash, original_text, translated_text, source_language, target_language)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(query, (content_hash, original_text, translated_text,
                                       source_language, target_language))
                return True
            except Exception as e:
                logger.error(f"Erreur stockage cache traduction: {e}")
                return False


# ============================================================================
# VAI_DASHBOARD_SESSIONS
# ============================================================================

class DashboardUserModel:

    @staticmethod
    def upsert(discord_user_id: int, discord_username: str = None,
               email: str = None, email_verified: bool = False,
               avatar_url: str = None) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}dashboard_users
                    (discord_user_id, discord_username, email, email_verified, avatar_url, last_login_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON DUPLICATE KEY UPDATE
                        discord_username = VALUES(discord_username),
                        email = VALUES(email),
                        email_verified = VALUES(email_verified),
                        avatar_url = VALUES(avatar_url),
                        last_login_at = NOW()
                """
                cursor.execute(query, (
                    discord_user_id,
                    discord_username,
                    email,
                    int(bool(email_verified)),
                    avatar_url,
                ))
                return True
            except Exception as e:
                logger.error(f"Erreur upsert dashboard user: {e}")
                return False

    @staticmethod
    def count() -> int:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {DB_TABLE_PREFIX}dashboard_users")
            return int(cursor.fetchone()[0])


class DashboardSessionModel:

    @staticmethod
    def create(discord_user_id: int, discord_username: str, access_token: str,
               jwt_token: str, expires_at, guild_ids_json: str | None = None) -> Optional[int]:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                try:
                    query = f"""
                        INSERT INTO {DB_TABLE_PREFIX}dashboard_sessions
                        (discord_user_id, discord_username, access_token, jwt_token, guild_ids_json, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(query, (discord_user_id, discord_username,
                                           access_token, jwt_token, guild_ids_json, expires_at))
                except Exception as e:
                    # Backward compatible with older schemas without `guild_ids_json`.
                    msg = str(e).lower()
                    if "unknown column" in msg and "guild_ids_json" in msg:
                        query = f"""
                            INSERT INTO {DB_TABLE_PREFIX}dashboard_sessions
                            (discord_user_id, discord_username, access_token, jwt_token, expires_at)
                            VALUES (%s, %s, %s, %s, %s)
                        """
                        cursor.execute(query, (discord_user_id, discord_username,
                                               access_token, jwt_token, expires_at))
                    else:
                        raise
                logger.debug(f"Session dashboard creee pour {discord_username}")
                return cursor.lastrowid
            except Exception as e:
                logger.error(f"Erreur creation session dashboard: {e}")
                return None

    @staticmethod
    def token_status(jwt_token: str) -> str:
        """
        Returns one of: valid | revoked | expired | missing

        Notes:
        - Uses MySQL NOW() for expiry comparison (server time).
        - Backward compatible with schemas without `is_revoked`.
        """
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    f"SELECT expires_at, (expires_at > NOW()) AS not_expired, is_revoked "
                    f"FROM {DB_TABLE_PREFIX}dashboard_sessions WHERE jwt_token = %s LIMIT 1",
                    (jwt_token,),
                )
                row = cursor.fetchone()
                if not row:
                    return "missing"
                if int(row.get("is_revoked", 0) or 0) == 1:
                    return "revoked"
                return "valid" if int(row.get("not_expired", 0) or 0) == 1 else "expired"
            except Exception as e:
                msg = str(e).lower()
                if "unknown column" in msg and "is_revoked" in msg:
                    cursor.execute(
                        f"SELECT expires_at, (expires_at > NOW()) AS not_expired "
                        f"FROM {DB_TABLE_PREFIX}dashboard_sessions WHERE jwt_token = %s LIMIT 1",
                        (jwt_token,),
                    )
                    row = cursor.fetchone()
                    if not row:
                        return "missing"
                    return "valid" if int(row.get("not_expired", 0) or 0) == 1 else "expired"
                raise

    @staticmethod
    def get_by_token(jwt_token: str) -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                status = DashboardSessionModel.token_status(jwt_token)
                if status != "valid":
                    return None
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}dashboard_sessions WHERE jwt_token = %s LIMIT 1",
                    (jwt_token,),
                )
                return cursor.fetchone()
            except Exception as e:
                # Backward compatibility: older schemas didn't have `is_revoked`.
                # In that case, fall back to simple expiry validation.
                msg = str(e).lower()
                if "unknown column" in msg and "is_revoked" in msg:
                    cursor.execute(
                        f"SELECT * FROM {DB_TABLE_PREFIX}dashboard_sessions "
                        f"WHERE jwt_token = %s AND expires_at > NOW()",
                        (jwt_token,)
                    )
                    return cursor.fetchone()
                raise

    @staticmethod
    def allowed_guild_ids(jwt_token: str) -> list[int] | None:
        """
        Returns the allowed guild IDs for this session (from DB), or None if unavailable.
        """
        import json
        row = DashboardSessionModel.get_by_token(jwt_token)
        if not row:
            return None
        raw = row.get("guild_ids_json")
        if raw is None:
            return None
        try:
            data = raw
            if isinstance(raw, (str, bytes, bytearray)):
                data = json.loads(raw)
            out: list[int] = []
            for x in (data or []):
                try:
                    out.append(int(x))
                except Exception:
                    pass
            return out
        except Exception:
            return None

    @staticmethod
    def revoke_token(jwt_token: str) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"UPDATE {DB_TABLE_PREFIX}dashboard_sessions "
                    f"SET is_revoked = 1 WHERE jwt_token = %s",
                    (jwt_token,)
                )
                return True
            except Exception as e:
                msg = str(e).lower()
                if "unknown column" in msg and "is_revoked" in msg:
                    # Old schema: no `is_revoked` flag -> delete row to revoke.
                    try:
                        cursor.execute(
                            f"DELETE FROM {DB_TABLE_PREFIX}dashboard_sessions WHERE jwt_token = %s",
                            (jwt_token,)
                        )
                        return True
                    except Exception as e2:
                        logger.error(f"Erreur suppression session (fallback revoke): {e2}")
                        return False
                logger.error(f"Erreur revocation token: {e}")
                return False


# ============================================================================
# VAI_AUDIT_LOG
# ============================================================================

class AuditLogModel:

    @staticmethod
    def log(actor_id: int, action: str, guild_id: int = None,
            actor_username: str = None, target_id: str = None,
            details: dict = None, ip_address: str = None) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                import json
                query = f"""
                    INSERT INTO {DB_TABLE_PREFIX}audit_log
                    (actor_id, actor_username, guild_id, action, target_id, details, ip_address)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(query, (
                    actor_id, actor_username, guild_id, action, target_id,
                    json.dumps(details) if details else None, ip_address
                ))
                return True
            except Exception as e:
                logger.error(f"Erreur audit log: {e}")
                return False

    @staticmethod
    def get_recent(guild_id: int = None, limit: int = 50) -> List[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            if guild_id:
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}audit_log "
                    f"WHERE guild_id = %s ORDER BY created_at DESC LIMIT %s",
                    (guild_id, limit)
                )
            else:
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}audit_log "
                    f"ORDER BY created_at DESC LIMIT %s",
                    (limit,)
                )
            return cursor.fetchall()


# ============================================================================
# VAI_BOT_STATUS
# ============================================================================

class BotStatusModel:

    @staticmethod
    def update(guild_count: int, user_count: int, uptime_sec: int, version: str,
               latency_ms: float = 0, shard_count: int = 1,
               channel_count: int = 0, started_at=None) -> bool:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"UPDATE {DB_TABLE_PREFIX}bot_status "
                    f"SET guild_count=%s, user_count=%s, uptime_sec=%s, version=%s, "
                    f"latency_ms=%s, shard_count=%s, channel_count=%s, started_at=%s "
                    f"WHERE id=1",
                    (guild_count, user_count, uptime_sec, version,
                     latency_ms, shard_count, channel_count, started_at)
                )
                return True
            except Exception as e:
                logger.error(f"Erreur update bot status: {e}")
                return False

    @staticmethod
    def get() -> Optional[Dict]:
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                f"SELECT *, "
                f"(TIMESTAMPDIFF(SECOND, updated_at, NOW()) < 120) AS is_online "
                f"FROM {DB_TABLE_PREFIX}bot_status WHERE id = 1"
            )
            row = cursor.fetchone()
            if row:
                row['is_online'] = bool(row.get('is_online', 0))
            return row


# ============================================================================
# VAI_TEMP_CODES - Codes d'echange temporaires post-OAuth
# ============================================================================

class TempCodeModel:

    @staticmethod
    def create(code: str, jwt_token: str, user: dict, guilds: list) -> bool:
        import json
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"INSERT INTO {DB_TABLE_PREFIX}temp_codes "
                    f"(code, jwt_token, user_json, guilds_json, expires_at) "
                    f"VALUES (%s, %s, %s, %s, DATE_ADD(NOW(), INTERVAL 60 SECOND))",
                    (code, jwt_token, json.dumps(user), json.dumps(guilds))
                )
                return True
            except Exception as e:
                logger.error(f"Erreur creation temp_code: {e}")
                return False

    @staticmethod
    def consume(code: str) -> Optional[Dict]:
        """
        Consomme le code (usage unique).
        Retourne {jwt_token, user, guilds} ou None si invalide/expire/deja utilise.
        """
        import json
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            try:
                # Lire ET marquer comme utilise en une transaction atomique
                cursor.execute(
                    f"SELECT * FROM {DB_TABLE_PREFIX}temp_codes "
                    f"WHERE code = %s AND used = 0 AND expires_at > NOW()"
                    f" FOR UPDATE",
                    (code,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                # Marquer comme utilise immediatement
                cursor.execute(
                    f"UPDATE {DB_TABLE_PREFIX}temp_codes SET used = 1 WHERE code = %s",
                    (code,)
                )
                return {
                    "jwt":    row["jwt_token"],
                    "user":   json.loads(row["user_json"]),
                    "guilds": json.loads(row["guilds_json"]),
                }
            except Exception as e:
                logger.error(f"Erreur consommation temp_code: {e}")
                return None

    @staticmethod
    def cleanup() -> int:
        """Supprime les codes expires ou deja utilises. A appeler periodiquement."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"DELETE FROM {DB_TABLE_PREFIX}temp_codes "
                    f"WHERE expires_at < NOW() OR used = 1"
                )
                count = cursor.rowcount
                if count:
                    logger.debug(f"{count} temp_codes nettoyes")
                return count
            except Exception as e:
                logger.error(f"Erreur cleanup temp_codes: {e}")
                return 0

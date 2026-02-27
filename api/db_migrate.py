from __future__ import annotations

import os
from pathlib import Path

from loguru import logger

from bot.config import DB_TABLE_PREFIX
from bot.db.connection import get_db_context


def _is_truthy(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []

    in_single = False
    in_double = False
    in_backtick = False
    in_line_comment = False
    in_block_comment = False

    def is_escaped(pos: int) -> bool:
        # Count backslashes just before this position
        bs = 0
        j = pos - 1
        while j >= 0 and sql[j] == "\\":
            bs += 1
            j -= 1
        return (bs % 2) == 1

    i = 0
    n = len(sql)
    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
                continue
            i += 1
            continue

        if not (in_single or in_double or in_backtick):
            if ch == "-" and nxt == "-":
                in_line_comment = True
                i += 2
                continue
            if ch == "#":
                in_line_comment = True
                i += 1
                continue
            if ch == "/" and nxt == "*":
                in_block_comment = True
                i += 2
                continue

        if ch == "'" and not (in_double or in_backtick) and not is_escaped(i):
            in_single = not in_single
        elif ch == '"' and not (in_single or in_backtick) and not is_escaped(i):
            in_double = not in_double
        elif ch == "`" and not (in_single or in_double):
            in_backtick = not in_backtick

        if ch == ";" and not (in_single or in_double or in_backtick):
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)

    return statements


def _apply_schema_file(sql_path: Path) -> None:
    sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
    statements = _split_sql_statements(sql_text)

    with get_db_context() as conn:
        cursor = conn.cursor()
        for stmt in statements:
            head = stmt.lstrip().split(None, 2)[:2]
            head_str = " ".join(head).lower()
            if head_str.startswith("create database") or head_str.startswith("use "):
                continue

            try:
                cursor.execute(stmt)
            except Exception as e:
                # Make schema execution idempotent enough for startup runs.
                msg = str(e).lower()
                ignorable = (
                    "duplicate key name" in msg
                    or "duplicate column name" in msg
                    or "already exists" in msg
                )
                if ignorable:
                    continue
                raise


def _column_info(table_name: str, column_name: str) -> dict | None:
    with get_db_context() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND column_name = %s
            """,
            (table_name, column_name),
        )
        return cursor.fetchone()


def _table_exists(table_name: str) -> bool:
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = DATABASE()
              AND table_name = %s
            LIMIT 1
            """,
            (table_name,),
        )
        return cursor.fetchone() is not None


def _ensure_dashboard_sessions_migrations() -> None:
    table = f"{DB_TABLE_PREFIX}dashboard_sessions"
    if not _table_exists(table):
        return

    # Add is_revoked if missing.
    if _column_info(table, "is_revoked") is None:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"ALTER TABLE {table} ADD COLUMN is_revoked TINYINT(1) DEFAULT 0"
            )

    # Add guild_ids_json if missing.
    if _column_info(table, "guild_ids_json") is None:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"ALTER TABLE {table} "
                f"ADD COLUMN guild_ids_json JSON NULL "
                f"COMMENT 'Liste des guild_ids autorises (owner/admin) au login'"
            )

    # Ensure jwt_token is TEXT (older init.sql used VARCHAR(500)).
    info = _column_info(table, "jwt_token")
    if info and (info.get("data_type") or "").lower() in {"varchar", "char"}:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN jwt_token TEXT")

    # Ensure access_token can hold Discord access tokens comfortably.
    info = _column_info(table, "access_token")
    max_len = info.get("character_maximum_length") if info else None
    if info and (info.get("data_type") or "").lower() in {"varchar", "char"} and (max_len or 0) < 500:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(f"ALTER TABLE {table} MODIFY COLUMN access_token VARCHAR(500)")


def _ensure_bot_status_migrations() -> None:
    """Ajoute les nouvelles colonnes a vai_bot_status si elles manquent."""
    table = f"{DB_TABLE_PREFIX}bot_status"
    if not _table_exists(table):
        return

    new_columns = {
        "channel_count": "INT DEFAULT 0 COMMENT 'Nombre total de channels accessibles'",
        "latency_ms":    "FLOAT DEFAULT 0 COMMENT 'Latence WebSocket Discord en ms'",
        "shard_count":   "INT DEFAULT 1 COMMENT 'Nombre de shards actifs'",
        "started_at":    "TIMESTAMP NULL COMMENT 'Heure de demarrage du bot'",
    }

    for col_name, col_def in new_columns.items():
        if _column_info(table, col_name) is None:
            with get_db_context() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")
                    logger.info(f"[db] Colonne {col_name} ajoutee a {table}")
                except Exception as e:
                    if "duplicate column" not in str(e).lower():
                        logger.warning(f"[db] ALTER {table}.{col_name}: {e}")


def _ensure_ticket_migrations() -> None:
    """Ajoute les colonnes necessaires pour update embed + stockage complet messages."""
    tickets_table = f"{DB_TABLE_PREFIX}tickets"
    if _table_exists(tickets_table):
        if _column_info(tickets_table, "initial_message_id") is None:
            with get_db_context() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        f"ALTER TABLE {tickets_table} "
                        f"ADD COLUMN initial_message_id BIGINT NULL "
                        f"COMMENT 'Message embed initial du ticket (pour mise a jour langue)'"
                    )
                    logger.info(f"[db] Colonne initial_message_id ajoutee a {tickets_table}")
                except Exception as e:
                    if "duplicate column" not in str(e).lower():
                        logger.warning(f"[db] ALTER {tickets_table}.initial_message_id: {e}")

    msgs_table = f"{DB_TABLE_PREFIX}ticket_messages"
    if _table_exists(msgs_table):
        if _column_info(msgs_table, "discord_message_id") is None:
            with get_db_context() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        f"ALTER TABLE {msgs_table} "
                        f"ADD COLUMN discord_message_id BIGINT NULL "
                        f"COMMENT 'Discord Message ID'"
                    )
                    logger.info(f"[db] Colonne discord_message_id ajoutee a {msgs_table}")
                except Exception as e:
                    if "duplicate column" not in str(e).lower():
                        logger.warning(f"[db] ALTER {msgs_table}.discord_message_id: {e}")

        if _column_info(msgs_table, "attachments_json") is None:
            with get_db_context() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        f"ALTER TABLE {msgs_table} "
                        f"ADD COLUMN attachments_json JSON NULL "
                        f"COMMENT 'Liste d attachments (urls, filenames, etc.)'"
                    )
                    logger.info(f"[db] Colonne attachments_json ajoutee a {msgs_table}")
                except Exception as e:
                    if "duplicate column" not in str(e).lower():
                        logger.warning(f"[db] ALTER {msgs_table}.attachments_json: {e}")


def _ensure_knowledge_base_migrations() -> None:
    """Ajoute les colonnes KB manquantes (schema drift)."""
    table = f"{DB_TABLE_PREFIX}knowledge_base"
    if not _table_exists(table):
        return

    if _column_info(table, "is_active") is None:
        with get_db_context() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"ALTER TABLE {table} "
                    f"ADD COLUMN is_active TINYINT(1) DEFAULT 1"
                )
                logger.info(f"[db] Colonne is_active ajoutee a {table}")
            except Exception as e:
                if "duplicate column" not in str(e).lower():
                    logger.warning(f"[db] ALTER {table}.is_active: {e}")


def ensure_database_schema() -> None:
    """
    Creates/migrates the MySQL schema at API startup using the `database/` folder.

    This is meant to fix common drift issues (ex: missing vai_dashboard_sessions.is_revoked),
    and to auto-create tables/views in fresh environments.
    """
    if not _is_truthy(os.getenv("AUTO_DB_MIGRATE"), default=True):
        logger.info("[db] AUTO_DB_MIGRATE=0 -> skip migrations")
        return

    root = Path(__file__).resolve().parents[1]
    schema_sql = root / "database" / "schema.sql"

    if not schema_sql.exists():
        logger.warning(f"[db] schema.sql introuvable: {schema_sql}")
        return

    logger.info(f"[db] Migration schema depuis {schema_sql}")
    _apply_schema_file(schema_sql)

    # Targeted ALTERs for already-existing tables.
    _ensure_dashboard_sessions_migrations()
    _ensure_bot_status_migrations()
    _ensure_ticket_migrations()
    _ensure_knowledge_base_migrations()

    logger.info("[db] Migration OK")

-- ============================================================================
-- Schéma MySQL complet pour Veridian AI
-- Toutes les tables sont préfixées 'vai_' pour éviter les conflits
-- ============================================================================

CREATE DATABASE IF NOT EXISTS veridianai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE veridianai;

-- ============================================================================
-- VAI_GUILDS - Serveurs Discord enregistrés + configuration
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_guilds (
    id BIGINT PRIMARY KEY COMMENT 'Discord Guild ID',
    name VARCHAR(100) NOT NULL,
    prefix VARCHAR(10) DEFAULT '/',
    tier ENUM('free','premium','pro') DEFAULT 'free',
    support_channel_id BIGINT COMMENT 'Channel support public IA',
    ticket_category_id BIGINT COMMENT 'Catégorie tickets',
    staff_role_id BIGINT,
    log_channel_id BIGINT,
    default_language VARCHAR(10) DEFAULT 'en',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_tier (tier),
    KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VAI_USERS - Utilisateurs Discord
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_users (
    id BIGINT PRIMARY KEY COMMENT 'Discord User ID',
    username VARCHAR(100),
    preferred_language VARCHAR(10) DEFAULT 'auto',
    is_bot_admin TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VAI_TICKETS - Tickets de support
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    channel_id BIGINT UNIQUE COMMENT 'Channel Discord du ticket',
    status ENUM('open','closed','pending') DEFAULT 'open',
    user_language VARCHAR(10),
    staff_language VARCHAR(10) DEFAULT 'en',
    assigned_staff_id BIGINT,
    priority ENUM('low','medium','high') DEFAULT 'medium',
    close_reason TEXT,
    transcript LONGTEXT COMMENT 'Résumé IA généré à la clôture',
    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP NULL,
    KEY idx_guild_status (guild_id, status),
    KEY idx_user (user_id),
    KEY idx_opened (opened_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VAI_TICKET_MESSAGES - Messages des tickets avec traductions
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_ticket_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    ticket_id INT NOT NULL,
    author_id BIGINT,
    original_content LONGTEXT,
    translated_content LONGTEXT,
    original_language VARCHAR(10),
    target_language VARCHAR(10),
    from_cache TINYINT(1) DEFAULT 0,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_ticket (ticket_id),
    FOREIGN KEY (ticket_id) REFERENCES vai_tickets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VAI_TRANSLATIONS_CACHE - Cache des traductions avec SHA256
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_translations_cache (
    id INT AUTO_INCREMENT PRIMARY KEY,
    content_hash VARCHAR(64) UNIQUE COMMENT 'SHA256 de (text+src_lang+tgt_lang)',
    original_text LONGTEXT,
    translated_text LONGTEXT,
    source_language VARCHAR(10),
    target_language VARCHAR(10),
    hit_count INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_hash (content_hash),
    KEY idx_languages (source_language, target_language),
    KEY idx_hit_count (hit_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VAI_ORDERS - Commandes en attente (PayPal & Cartes Cadeaux)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_id VARCHAR(20) UNIQUE COMMENT 'Ex: VAI-202501-4823',
    user_id BIGINT NOT NULL,
    guild_id BIGINT,
    method ENUM('paypal','giftcard'),
    plan ENUM('premium','pro'),
    amount DECIMAL(10,2),
    status ENUM('pending','paid','partial','rejected') DEFAULT 'pending',
    paypal_email VARCHAR(200) COMMENT 'Email utilisé pour PayPal',
    giftcard_code TEXT COMMENT 'Code carte cadeau',
    giftcard_image_url TEXT COMMENT 'URL image carte',
    admin_note TEXT COMMENT 'Note admin lors validation',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    validated_at TIMESTAMP NULL,
    KEY idx_order_id (order_id),
    KEY idx_user (user_id),
    KEY idx_status (status),
    KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VAI_PAYMENTS - Historique complet des paiements
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT,
    guild_id BIGINT,
    order_id VARCHAR(20) COMMENT 'Référence vai_orders si manuel',
    method ENUM('oxapay','paypal','giftcard'),
    amount DECIMAL(10,2),
    currency VARCHAR(10),
    plan ENUM('premium','pro'),
    status ENUM('completed','failed','refunded'),
    oxapay_invoice_id VARCHAR(100) COMMENT 'ID invoice OxaPay si crypto',
    paid_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user (user_id),
    KEY idx_status (status),
    KEY idx_paid (paid_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VAI_SUBSCRIPTIONS - Abonnements actifs par serveur
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_subscriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT UNIQUE,
    user_id BIGINT COMMENT 'Qui a payé',
    plan ENUM('premium','pro'),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL COMMENT 'NULL = pas d\'expiration fixée',
    is_active TINYINT(1) DEFAULT 1,
    payment_id INT COMMENT 'FK vers vai_payments',
    KEY idx_guild (guild_id),
    KEY idx_active (is_active),
    KEY idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VAI_KNOWLEDGE_BASE - Base de connaissances par serveur (Premium)
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_knowledge_base (
    id INT AUTO_INCREMENT PRIMARY KEY,
    guild_id BIGINT NOT NULL,
    question TEXT,
    answer LONGTEXT,
    category VARCHAR(100),
    priority INT DEFAULT 0,
    created_by BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_guild (guild_id),
    KEY idx_category (category)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- VAI_DASHBOARD_SESSIONS - Sessions OAuth2 Discord pour le dashboard
-- ============================================================================

-- ============================================================================
-- VAI_DASHBOARD_USERS - Comptes dashboard (OAuth Discord) + email
-- ============================================================================

CREATE TABLE IF NOT EXISTS vai_dashboard_users (
    discord_user_id     BIGINT PRIMARY KEY COMMENT 'Discord User ID',
    discord_username    VARCHAR(100),
    email               VARCHAR(255),
    email_verified      TINYINT(1) DEFAULT 0,
    avatar_url          VARCHAR(255),
    first_login_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login_at       TIMESTAMP NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    KEY idx_email (email),
    KEY idx_last_login (last_login_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS vai_dashboard_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    discord_user_id BIGINT,
    discord_username VARCHAR(100),
    access_token VARCHAR(500) COMMENT 'Token OAuth2 Discord',
    jwt_token TEXT COMMENT 'JWT session dashboard',
    is_revoked TINYINT(1) DEFAULT 0,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_user (discord_user_id),
    KEY idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- Indexes supplémentaires pour performance
-- ============================================================================

CREATE INDEX idx_vai_guilds_tier ON vai_guilds(tier);
CREATE INDEX idx_vai_subscriptions_guild_active ON vai_subscriptions(guild_id, is_active);
CREATE INDEX idx_vai_orders_user_status ON vai_orders(user_id, status);

-- ============================================================================
-- Vues utiles
-- ============================================================================

CREATE OR REPLACE VIEW vai_active_subscriptions AS
SELECT 
    s.*,
    g.name as guild_name,
    u.username as user_name
FROM vai_subscriptions s
LEFT JOIN vai_guilds g ON s.guild_id = g.id
LEFT JOIN vai_users u ON s.user_id = u.id
WHERE s.is_active = 1 AND (s.expires_at IS NULL OR s.expires_at > NOW());

CREATE OR REPLACE VIEW vai_pending_orders_view AS
SELECT 
    o.*,
    u.username as user_name,
    g.name as guild_name
FROM vai_orders o
LEFT JOIN vai_users u ON o.user_id = u.id
LEFT JOIN vai_guilds g ON o.guild_id = g.id
WHERE o.status = 'pending'
ORDER BY o.created_at DESC;

-- ============================================================================
-- Fin du schéma
-- ============================================================================

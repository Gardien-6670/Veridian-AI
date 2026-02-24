"""
Constantes globales du projet Veridian AI
À utiliser dans tous les fichiers de configuration
"""

# Version
VERSION = "0.0.1-beta"
VERSION_EMOJI = "🧪"

# Discord Configuration
BOT_OWNER_DISCORD_ID = 1047760053509312642
ADMIN_IDS = [1047760053509312642]

# Bot Information
BOT_NAME = 'Veridian AI'
DOMAIN = 'veridiancloud.xyz'
API_DOMAIN = 'api.veridiancloud.xyz'
DASHBOARD_URL = 'https://veridiancloud.xyz/dashboard'

# Database Prefix
DB_TABLE_PREFIX = 'vai_'

# Pricing (in EUR)
PRICING = {
    'premium': 2.00,
    'pro': 5.00
}

# Plan Tiers
PLAN_TIERS = ['free', 'premium', 'pro']

# Limits per Plan
PLAN_LIMITS = {
    'free': {
        'tickets_per_month': 50,
        'languages': 5,
        'kb_entries': 0,
        'features': ['tickets', 'public_support']
    },
    'premium': {
        'tickets_per_month': 500,
        'languages': 20,
        'kb_entries': 50,
        'features': ['tickets', 'public_support', 'translations', 'transcriptions']
    },
    'pro': {
        'tickets_per_month': None,  # Unlimited
        'languages': None,  # All
        'kb_entries': None,  # Unlimited
        'features': ['tickets', 'public_support', 'translations', 'transcriptions', 'suggestions', 'advanced_stats']
    }
}

# Groq Model Configuration
GROQ_MODEL_FAST = 'llama-3.1-8b-instant'
GROQ_MODEL_QUALITY = 'llama-3.1-70b-versatile'
GROQ_DEFAULT_MODEL = GROQ_MODEL_FAST

# System Prompts
SYSTEM_PROMPT_SUPPORT = """Tu es Veridian AI, l'assistant IA du serveur Discord '{guild_name}'.
Tu réponds uniquement aux questions liées au serveur et à ses sujets.
Réponds toujours dans la même langue que l'utilisateur.
Sois concis, professionnel et bienveillant.
Si tu ne sais pas, dis-le clairement et suggère d'ouvrir un ticket.
Ne réponds PAS aux messages hors-sujet ou aux salutations simples."""

SYSTEM_PROMPT_TICKET_SUMMARY = """Tu es un assistant de support. Voici la conversation d'un ticket de support Discord.
Génère un résumé structuré en 3 parties :
1. PROBLÈME : Ce que l'utilisateur demandait (1-2 phrases)
2. RÉSOLUTION : Comment le problème a été résolu (1-2 phrases)
3. STATUT : Résolu / Non résolu / Partiel
Réponds dans la langue : {ticket_language}"""

# OxaPay Configuration
OXAPAY_BASE_URL = 'https://api.oxapay.com'
OXAPAY_MERCHANTS_REQUEST_ENDPOINT = '/merchants/request'

# Ticket Configuration
TICKET_ARCHIVE_DELAY_HOURS = 24
TICKET_CHANNEL_PREFIX = 'ticket'
MIN_MESSAGE_LENGTH = 3

# Cache Configuration
TRANSLATION_CACHE_HIT_THRESHOLD = 10

# Logging
LOG_LEVEL = 'INFO'

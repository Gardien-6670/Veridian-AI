"""
API FastAPI interne - Communication entre le bot et le dashboard
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger
import os
from datetime import datetime
from pathlib import Path

# ── Charger .env AVANT tout le reste ────────────────────────────────────────
try:
    from dotenv import load_dotenv
    for _p in [Path(".env"), Path(__file__).parent.parent / ".env", Path(__file__).parent / ".env"]:
        if _p.exists():
            load_dotenv(dotenv_path=_p, override=True)
            print(f"[dotenv] Charge depuis {_p.resolve()}")
            break
    else:
        print("[dotenv] Aucun .env trouve — variables lues depuis le systeme")
except ImportError:
    print("[dotenv] Installe python-dotenv : pip install python-dotenv")

# Créer dossier logs s'il n'existe pas
Path('logs').mkdir(exist_ok=True)

# Configuration
INTERNAL_API_SECRET = os.getenv('INTERNAL_API_SECRET', '718952f2f7daf24e6b9a7f2053c86fcc22c23b35d45165784d13ffdce591507b')
API_DOMAIN = os.getenv('API_DOMAIN', 'api.veridiancloud.xyz')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# Import version
from bot.config import VERSION

# Import routers
from api.routes.auth import router as auth_router
from api.routes.internal import router as internal_router   # ← FIX: manquait dans l'original

app = FastAPI(
    title=f"Veridian AI {VERSION} - API Interne",
    description="API pour la communication bot ↔ dashboard",
    version=VERSION
)

# ============================================================================
# CORS Configuration
# ============================================================================
CORS_ORIGINS = [
    "https://veridiancloud.xyz",
    "https://www.veridiancloud.xyz",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Include Routers
# ============================================================================
app.include_router(auth_router)
app.include_router(internal_router)   # ← FIX: routes /internal/* maintenant enregistrées

# ============================================================================
# Logging
# ============================================================================
logger.remove()
logger.add(
    "logs/api.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
)
logger.add(
    "logs/errors.log",
    rotation="500 MB",
    retention="30 days",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}"
)

# ============================================================================
# Middleware: Vérification du secret API interne
# ============================================================================
def verify_api_secret(x_api_key: str = Header(...)):
    """Vérifie la clé API interne."""
    if x_api_key != INTERNAL_API_SECRET:
        raise HTTPException(status_code=403, detail="Clé API invalide")
    return x_api_key


# ============================================================================
# Modèles Pydantic
# ============================================================================
class GuildConfigRequest(BaseModel):
    support_channel_id: int = None
    ticket_category_id: int = None
    staff_role_id: int = None
    log_channel_id: int = None
    default_language: str = 'en'


class ValidateOrderRequest(BaseModel):
    order_id: str
    plan: str


class RevokeSubscriptionRequest(BaseModel):
    guild_id: int


class SendDMRequest(BaseModel):
    user_id: int
    message: str


# ============================================================================
# Routes globales (non-prefixées par /internal/)
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Vérifie la santé de l'API."""
    try:
        from bot.db.connection import get_connection
        try:
            conn = get_connection()
            conn.close()
            db_status = "healthy"
        except Exception:
            db_status = "unhealthy"

        return {
            "status": "online",
            "version": VERSION,
            "environment": ENVIRONMENT,
            "database": db_status,
            "timestamp": datetime.utcnow().isoformat(),
            "api_domain": API_DOMAIN
        }
    except Exception as e:
        logger.error(f"✗ Health check error: {e}")
        return {"status": "degraded", "version": VERSION, "error": str(e)}


@app.post("/webhook/oxapay", tags=["Webhooks"])
async def oxapay_webhook(payload: dict, x_webhook_signature: str = Header(None)):
    """Reçoit les webhooks OxaPay."""
    try:
        from bot.services.oxapay import OxaPayClient
        from bot.db.models import OrderModel, SubscriptionModel

        oxapay = OxaPayClient()

        if not oxapay.verify_webhook_signature(payload, x_webhook_signature):
            logger.warning("✗ Signature webhook OxaPay invalide")
            raise HTTPException(status_code=403, detail="Signature invalide")

        order_id = payload.get('orderId')
        status = payload.get('status')

        if status == 'Paid':
            order = OrderModel.get(order_id)
            if order:
                OrderModel.update_status(order_id, 'paid')
                SubscriptionModel.create(
                    guild_id=order['guild_id'],
                    user_id=order['user_id'],
                    plan=order['plan'],
                    payment_id=order['id'],
                    duration_days=30
                )
                logger.info(f"✓ OxaPay webhook: {order_id} payé et activé")

        return {"status": "success"}
    except Exception as e:
        logger.error(f"✗ Erreur webhook OxaPay: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Gestionnaire personnalisé pour les exceptions HTTP."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


# ============================================================================
# Démarrage
# ============================================================================
if __name__ == '__main__':
    import uvicorn

    host = os.getenv('API_HOST', '0.0.0.0')
    port = int(os.getenv('API_PORT', 201))

    ssl_certfile = "/etc/letsencrypt/live/api.veridiancloud.xyz/fullchain.pem"
    ssl_keyfile = "/etc/letsencrypt/live/api.veridiancloud.xyz/privkey.pem"

    ssl_config = {}
    if os.path.exists(ssl_certfile) and os.path.exists(ssl_keyfile):
        ssl_config = {"ssl_certfile": ssl_certfile, "ssl_keyfile": ssl_keyfile}
        logger.info("🔒 SSL/TLS configuré")
    else:
        logger.warning("⚠️ Certificats SSL non trouvés — démarrage sans SSL")

    logger.info(f"🚀 API Veridian {VERSION} démarrage sur {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level='info', **ssl_config)
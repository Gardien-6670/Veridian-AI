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

# Créer dossier logs s'il n'existe pas
Path('logs').mkdir(exist_ok=True)

# Configuration
INTERNAL_API_SECRET = os.getenv('INTERNAL_API_SECRET', '718952f2f7daf24e6b9a7f2053c86fcc22c23b35d45165784d13ffdce591507b')
API_DOMAIN = os.getenv('API_DOMAIN', 'api.veridiancloud.xyz')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# Import version
from bot.config import VERSION

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

# Configuration Logging
logger.remove()  # Supprimer handler par défaut
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
# Middleware: Vérification du secret API
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
# Routes
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Vérifie la santé de l'API."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/internal/guild/{guild_id}/config", tags=["Guild"])
async def get_guild_config(guild_id: int, api_key: str = Depends(verify_api_secret)):
    """Récupère la configuration d'un serveur."""
    try:
        from bot.db.models import GuildModel
        guild = GuildModel.get(guild_id)
        
        if not guild:
            raise HTTPException(status_code=404, detail="Serveur non trouvé")
        
        return guild
    except Exception as e:
        logger.error(f"✗ Erreur get_guild_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/internal/guild/{guild_id}/config", tags=["Guild"])
async def update_guild_config(guild_id: int, config: GuildConfigRequest, api_key: str = Depends(verify_api_secret)):
    """Met à jour la configuration d'un serveur."""
    try:
        from bot.db.models import GuildModel
        
        update_data = config.dict(exclude_unset=True)
        success = GuildModel.update(guild_id, **update_data)
        
        if not success:
            raise HTTPException(status_code=400, detail="Mise à jour échouée")
        
        return {"status": "success", "guild_id": guild_id}
    except Exception as e:
        logger.error(f"✗ Erreur update_guild_config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/internal/guild/{guild_id}/tickets", tags=["Tickets"])
async def get_guild_tickets(guild_id: int, status: str = None, api_key: str = Depends(verify_api_secret)):
    """Récupère les tickets d'un serveur."""
    try:
        from bot.db.connection import get_db_context
        from bot.config import DB_TABLE_PREFIX
        
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            
            if status:
                query = f"SELECT * FROM {DB_TABLE_PREFIX}tickets WHERE guild_id = %s AND status = %s ORDER BY opened_at DESC"
                cursor.execute(query, (guild_id, status))
            else:
                query = f"SELECT * FROM {DB_TABLE_PREFIX}tickets WHERE guild_id = %s ORDER BY opened_at DESC"
                cursor.execute(query, (guild_id,))
            
            tickets = cursor.fetchall()
            return {"tickets": tickets}
    except Exception as e:
        logger.error(f"✗ Erreur get_guild_tickets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/internal/guild/{guild_id}/stats", tags=["Stats"])
async def get_guild_stats(guild_id: int, api_key: str = Depends(verify_api_secret)):
    """Récupère les statistiques d'un serveur."""
    try:
        from bot.db.connection import get_db_context
        from bot.config import DB_TABLE_PREFIX
        
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Nombre de tickets ce mois
            cursor.execute(
                f"SELECT COUNT(*) as count FROM {DB_TABLE_PREFIX}tickets WHERE guild_id = %s AND MONTH(opened_at) = MONTH(NOW())",
                (guild_id,)
            )
            tickets_month = cursor.fetchone()['count']
            
            # Langues utilisées
            cursor.execute(
                f"SELECT user_language, COUNT(*) as count FROM {DB_TABLE_PREFIX}tickets WHERE guild_id = %s GROUP BY user_language",
                (guild_id,)
            )
            languages = cursor.fetchall()
            
            return {
                "guild_id": guild_id,
                "tickets_this_month": tickets_month,
                "languages": languages
            }
    except Exception as e:
        logger.error(f"✗ Erreur get_guild_stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/internal/validate-order", tags=["Orders"])
async def validate_order(request: ValidateOrderRequest, api_key: str = Depends(verify_api_secret)):
    """Valide manuellement une commande."""
    try:
        from bot.db.models import OrderModel, SubscriptionModel
        
        # Récupérer la commande
        order = OrderModel.get(request.order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Commande non trouvée")
        
        # Mettre à jour le statut
        OrderModel.update_status(request.order_id, 'paid')
        
        # Créer l'abonnement
        SubscriptionModel.create(
            guild_id=order['guild_id'],
            user_id=order['user_id'],
            plan=request.plan,
            payment_id=order['id'],
            duration_days=30
        )
        
        return {"status": "success", "order_id": request.order_id}
    except Exception as e:
        logger.error(f"✗ Erreur validate_order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/internal/revoke-sub", tags=["Subscriptions"])
async def revoke_subscription(request: RevokeSubscriptionRequest, api_key: str = Depends(verify_api_secret)):
    """Révoque un abonnement."""
    try:
        from bot.db.models import SubscriptionModel
        
        success = SubscriptionModel.deactivate(request.guild_id)
        if not success:
            raise HTTPException(status_code=400, detail="Révocation échouée")
        
        return {"status": "success", "guild_id": request.guild_id}
    except Exception as e:
        logger.error(f"✗ Erreur revoke_subscription: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhook/oxapay", tags=["Webhooks"])
async def oxapay_webhook(payload: dict, x_webhook_signature: str = Header(None)):
    """Reçoit les webhooks OxaPay."""
    try:
        from bot.services.oxapay import OxaPayClient
        from bot.db.models import OrderModel, SubscriptionModel
        
        oxapay = OxaPayClient()
        
        # Vérifier la signature
        if not oxapay.verify_webhook_signature(payload, x_webhook_signature):
            logger.warning("✗ Signature webhook OxaPay invalide")
            raise HTTPException(status_code=403, detail="Signature invalide")
        
        # Traiter le webhook
        order_id = payload.get('orderId')
        status = payload.get('status')
        
        if status == 'Paid':
            # Mettre à jour la commande
            order = OrderModel.get(order_id)
            if order:
                OrderModel.update_status(order_id, 'paid')
                
                # Créer l'abonnement
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


if __name__ == '__main__':
    import uvicorn
    
    # Endpoint health
    @app.get('/health')
    async def health_check():
        """Vérification de santé de l'API avec infos système."""
        try:
            from bot.db.connection import get_connection
            
            # Test DB
            try:
                conn = get_connection()
                conn.close()
                db_status = "healthy"
            except:
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
            return {
                "status": "degraded",
                "version": VERSION,
                "error": str(e)
            }
    
    # Démarrer le serveur
    host = os.getenv('API_HOST', '127.0.0.1')
    port = int(os.getenv('API_PORT', 201))
    
    # Configuration SSL/TLS avec Let's Encrypt
    ssl_certfile = "/etc/letsencrypt/live/api.veridiancloud.xyz/fullchain.pem"
    ssl_keyfile = "/etc/letsencrypt/live/api.veridiancloud.xyz/privkey.pem"
    
    # Vérifier que les certificats existent
    ssl_config = {}
    if os.path.exists(ssl_certfile) and os.path.exists(ssl_keyfile):
        ssl_config = {
            "ssl_certfile": ssl_certfile,
            "ssl_keyfile": ssl_keyfile
        }
        logger.info(f"🔒 SSL/TLS configuré — Certificat Let's Encrypt chargé")
    else:
        logger.warning(f"⚠️ Certificats SSL non trouvés à {ssl_certfile} et {ssl_keyfile}")
        logger.warning(f"⚠️ Démarrage sans SSL (HTTP non-sécurisé)")
    
    logger.info(f"🚀 API Veridian {VERSION} démarrage sur {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level='info', **ssl_config)

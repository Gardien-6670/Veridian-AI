"""
API Interne - Routes pour gestion de configuration et données
Communication Bot ↔ Dashboard
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from typing import Optional
from bot.db.connection import get_db_context
from bot.db.models import GuildModel, TicketModel, UserModel, SubscriptionModel
from bot.config import PLAN_LIMITS
import os

router = APIRouter(prefix="/internal", tags=["internal"])


def verify_api_secret(x_api_secret: str = Header(None)):
    """Vérifier la clé API interne"""
    expected_secret = os.getenv("INTERNAL_API_SECRET")
    if not x_api_secret or x_api_secret != expected_secret:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# ============================================================================
# Routes de Configuration Guild
# ============================================================================

@router.get("/guild/{guild_id}/config", dependencies=[Depends(verify_api_secret)])
def get_guild_config(guild_id: int):
    """Récupérer la configuration d'un serveur"""
    with get_db_context() as db:
        guild = GuildModel.get_by_id(guild_id)
        if not guild:
            raise HTTPException(status_code=404, detail="Guild not found")
        return {
            "guild_id": guild_id,
            "name": guild.get("name"),
            "tier": guild.get("tier"),
            "support_channel_id": guild.get("support_channel_id"),
            "ticket_category_id": guild.get("ticket_category_id"),
            "staff_role_id": guild.get("staff_role_id"),
            "log_channel_id": guild.get("log_channel_id"),
            "default_language": guild.get("default_language"),
        }


@router.put("/guild/{guild_id}/config", dependencies=[Depends(verify_api_secret)])
def update_guild_config(guild_id: int, config: dict):
    """Mettre à jour la configuration d'un serveur"""
    with get_db_context() as db:
        GuildModel.update(guild_id, **config)
        return {"status": "success", "message": "Guild config updated"}


# ============================================================================
# Routes Tickets
# ============================================================================

@router.get("/guild/{guild_id}/tickets", dependencies=[Depends(verify_api_secret)])
def get_guild_tickets(
    guild_id: int,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 20
):
    """Récupérer les tickets d'un serveur avec pagination"""
    with get_db_context() as db:
        tickets = TicketModel.get_by_guild(guild_id)
        
        # Filtrer par statut si spécifié
        if status:
            tickets = [t for t in tickets if t.get("status") == status]
        
        # Pagination
        total = len(tickets)
        start = (page - 1) * limit
        end = start + limit
        paginated = tickets[start:end]
        
        return {
            "guild_id": guild_id,
            "total": total,
            "page": page,
            "limit": limit,
            "tickets": paginated
        }


@router.get("/ticket/{ticket_id}/transcript", dependencies=[Depends(verify_api_secret)])
def get_ticket_transcript(ticket_id: int):
    """Récupérer la transcription d'un ticket"""
    with get_db_context() as db:
        ticket = TicketModel.get_by_id(ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        return {
            "ticket_id": ticket_id,
            "guild_id": ticket.get("guild_id"),
            "user_id": ticket.get("user_id"),
            "status": ticket.get("status"),
            "transcript": ticket.get("transcript"),
            "opened_at": ticket.get("opened_at"),
            "closed_at": ticket.get("closed_at")
        }


# ============================================================================
# Routes Statistiques
# ============================================================================

@router.get("/guild/{guild_id}/stats", dependencies=[Depends(verify_api_secret)])
def get_guild_stats(guild_id: int):
    """Récupérer les statistiques d'un serveur"""
    with get_db_context() as db:
        # Récupérer tous les tickets
        tickets = TicketModel.get_by_guild(guild_id)
        
        # Compter par statut
        total_tickets = len(tickets)
        open_tickets = len([t for t in tickets if t.get("status") == "open"])
        closed_tickets = len([t for t in tickets if t.get("status") == "closed"])
        
        # Récupérer l'abonnement
        subscription = SubscriptionModel.get_by_guild(guild_id)
        
        return {
            "guild_id": guild_id,
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "closed_tickets": closed_tickets,
            "current_plan": subscription.get("plan") if subscription else "free",
            "is_subscribed": subscription and subscription.get("is_active") if subscription else False
        }


# ============================================================================
# Routes Utilisateurs
# ============================================================================

@router.get("/user/{user_id}/subscription", dependencies=[Depends(verify_api_secret)])
def get_user_subscription(user_id: int):
    """Récupérer l'abonnement d'un utilisateur sur tous les serveurs"""
    with get_db_context() as db:
        user = UserModel.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "user_id": user_id,
            "username": user.get("username"),
            "preferred_language": user.get("preferred_language"),
            "is_bot_admin": user.get("is_bot_admin")
        }


@router.put("/user/{user_id}/language", dependencies=[Depends(verify_api_secret)])
def update_user_language(user_id: int, language: str):
    """Mettre à jour la langue préférée d'un utilisateur"""
    # Valider la langue
    valid_languages = ["en", "fr", "de", "es", "it", "pt", "ja", "ko", "zh", "auto"]
    if language not in valid_languages:
        raise HTTPException(status_code=400, detail=f"Invalid language: {language}")
    
    with get_db_context() as db:
        UserModel.update(user_id, preferred_language=language)
        return {"status": "success", "user_id": user_id, "language": language}


# ============================================================================
# Routes Health & Info
# ============================================================================

@router.get("/health", dependencies=[Depends(verify_api_secret)])
def health_check():
    """Vérifier la santé de l'API"""
    try:
        with get_db_context() as db:
            # Tester la connexion DB
            return {"status": "ok", "service": "internal-api"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")


@router.get("/info", dependencies=[Depends(verify_api_secret)])
def get_api_info():
    """Récupérer les infos sur l'API"""
    return {
        "name": "Veridian AI Internal API",
        "version": "2.0.0",
        "endpoints": {
            "guild_config": "/internal/guild/{guild_id}/config",
            "guild_tickets": "/internal/guild/{guild_id}/tickets",
            "guild_stats": "/internal/guild/{guild_id}/stats",
            "user_subscription": "/internal/user/{user_id}/subscription",
            "health": "/internal/health"
        }
    }

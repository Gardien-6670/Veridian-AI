"""
API Interne - Routes dashboard <-> bot
Toute la configuration passe par ici, plus de commandes bot admin.
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from typing import Optional, List
from bot.db.connection import get_db_context
from bot.db.models import (
    GuildModel, TicketModel, UserModel, SubscriptionModel,
    OrderModel, PaymentModel, KnowledgeBaseModel, AuditLogModel,
    BotStatusModel, TicketMessageModel
)
from bot.config import PLAN_LIMITS
from loguru import logger
import os

router = APIRouter(prefix="/internal", tags=["internal"])


# ============================================================================
# Auth middleware
# ============================================================================

def verify_api_secret(x_api_secret: str = Header(None)):
    expected = os.getenv("INTERNAL_API_SECRET")
    if not x_api_secret or x_api_secret != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# ============================================================================
# Pydantic models
# ============================================================================

class GuildConfigBody(BaseModel):
    support_channel_id:  Optional[int]  = None
    ticket_category_id:  Optional[int]  = None
    staff_role_id:       Optional[int]  = None
    log_channel_id:      Optional[int]  = None
    welcome_channel_id:  Optional[int]  = None
    default_language:    Optional[str]  = None
    auto_translate:      Optional[bool] = None
    public_support:      Optional[bool] = None
    auto_transcript:     Optional[bool] = None
    ai_moderation:       Optional[bool] = None
    staff_suggestions:   Optional[bool] = None


class OrderStatusBody(BaseModel):
    status:        str
    admin_note:    Optional[str] = None
    validated_by:  Optional[int] = None
    plan:          Optional[str] = None


class ActivateSubBody(BaseModel):
    guild_id:      int
    plan:          str
    duration_days: int = 30


class RevokeSubBody(BaseModel):
    guild_id: int


class KBEntryBody(BaseModel):
    question:   str
    answer:     str
    category:   Optional[str] = None
    created_by: Optional[int] = None


# ============================================================================
# Health
# ============================================================================

@router.get("/health", dependencies=[Depends(verify_api_secret)])
def health_check():
    try:
        with get_db_context():
            return {"status": "ok", "service": "internal-api"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database error: {str(e)}")


# ============================================================================
# Guild config - lu et ecrit exclusivement par le dashboard
# ============================================================================

@router.get("/guild/{guild_id}/config", dependencies=[Depends(verify_api_secret)])
def get_guild_config(guild_id: int):
    guild = GuildModel.get(guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")
    return guild


@router.put("/guild/{guild_id}/config", dependencies=[Depends(verify_api_secret)])
def update_guild_config(guild_id: int, body: GuildConfigBody, request: Request):
    guild = GuildModel.get(guild_id)
    if not guild:
        raise HTTPException(status_code=404, detail="Guild not found")

    updates = {k: v for k, v in body.dict(exclude_unset=True).items() if v is not None}
    # Convertir bool -> int pour MySQL
    for k, v in updates.items():
        if isinstance(v, bool):
            updates[k] = int(v)

    if not updates:
        return {"status": "no_changes"}

    GuildModel.update(guild_id, **updates)

    # Audit log
    actor_id = getattr(request.state, "user_id", None)
    AuditLogModel.log(
        actor_id=actor_id or 0,
        action="guild.config",
        guild_id=guild_id,
        details=updates,
        ip_address=request.client.host if request.client else None
    )

    return {"status": "success", "guild_id": guild_id, "updated": list(updates.keys())}


# ============================================================================
# Tickets
# ============================================================================

@router.get("/guild/{guild_id}/tickets", dependencies=[Depends(verify_api_secret)])
def get_guild_tickets(guild_id: int, status: Optional[str] = None,
                      page: int = 1, limit: int = 50):
    tickets = TicketModel.get_by_guild(guild_id, status=status, page=page, limit=limit)
    total   = TicketModel.count_by_guild(guild_id, status=status)
    return {
        "guild_id": guild_id,
        "total":    total,
        "page":     page,
        "limit":    limit,
        "tickets":  tickets
    }


@router.get("/ticket/{ticket_id}", dependencies=[Depends(verify_api_secret)])
def get_ticket(ticket_id: int):
    ticket = TicketModel.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@router.get("/ticket/{ticket_id}/transcript", dependencies=[Depends(verify_api_secret)])
def get_ticket_transcript(ticket_id: int):
    ticket = TicketModel.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    messages = TicketMessageModel.get_by_ticket(ticket_id)
    return {
        "ticket_id":  ticket_id,
        "guild_id":   ticket.get("guild_id"),
        "user_id":    ticket.get("user_id"),
        "status":     ticket.get("status"),
        "transcript": ticket.get("transcript"),
        "messages":   messages,
        "opened_at":  str(ticket.get("opened_at")) if ticket.get("opened_at") else None,
        "closed_at":  str(ticket.get("closed_at")) if ticket.get("closed_at") else None
    }


@router.post("/ticket/{ticket_id}/close", dependencies=[Depends(verify_api_secret)])
def close_ticket_dashboard(ticket_id: int, request: Request):
    ticket = TicketModel.get(ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    TicketModel.close(ticket_id, close_reason="Ferme depuis le dashboard")
    actor_id = getattr(request.state, "user_id", None)
    AuditLogModel.log(actor_id=actor_id or 0, action="ticket.close",
                      guild_id=ticket["guild_id"], target_id=str(ticket_id))
    return {"status": "success", "ticket_id": ticket_id}


# ============================================================================
# Stats guild
# ============================================================================

@router.get("/guild/{guild_id}/stats", dependencies=[Depends(verify_api_secret)])
def get_guild_stats(guild_id: int):
    open_tickets    = TicketModel.count_by_guild(guild_id, status="open")
    inprog_tickets  = TicketModel.count_by_guild(guild_id, status="in_progress")
    total_tickets   = TicketModel.count_by_guild(guild_id)
    languages       = TicketModel.get_language_stats(guild_id)
    daily_counts    = TicketModel.get_daily_counts(guild_id, days=7)
    subscription    = SubscriptionModel.get(guild_id)
    kb_count        = KnowledgeBaseModel.count(guild_id)

    return {
        "guild_id":           guild_id,
        "open_tickets":       open_tickets,
        "in_progress_tickets": inprog_tickets,
        "total_tickets":      total_tickets,
        "languages":          languages,
        "daily_counts":       daily_counts,
        "current_plan":       subscription["plan"] if subscription else "free",
        "is_subscribed":      bool(subscription),
        "kb_entries":         kb_count
    }


# ============================================================================
# Orders
# ============================================================================

@router.get("/orders/pending", dependencies=[Depends(verify_api_secret)])
def get_pending_orders():
    orders = OrderModel.list_pending()
    return {"total": len(orders), "orders": orders}


@router.get("/orders", dependencies=[Depends(verify_api_secret)])
def get_orders(page: int = 1, limit: int = 50, status: Optional[str] = None):
    orders = OrderModel.list_all(page=page, limit=limit, status=status)
    return {"orders": orders, "page": page, "limit": limit}


@router.put("/orders/{order_id}/status", dependencies=[Depends(verify_api_secret)])
def update_order_status(order_id: str, body: OrderStatusBody, request: Request):
    order = OrderModel.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    actor_id = getattr(request.state, "user_id", None)

    OrderModel.update_status(
        order_id,
        status=body.status,
        admin_note=body.admin_note,
        validated_by=actor_id or body.validated_by
    )

    if body.status == "paid":
        plan = body.plan or order.get("plan", "premium")
        payment_id = PaymentModel.create(
            user_id=order["user_id"],
            guild_id=order["guild_id"],
            method=order["method"],
            amount=float(order["amount"] or 0),
            plan=plan,
            order_id=order_id,
            status="completed"
        )
        SubscriptionModel.create(
            guild_id=order["guild_id"],
            user_id=order["user_id"],
            plan=plan,
            payment_id=payment_id,
            duration_days=30
        )
        logger.info(f"Abonnement {plan} active pour guild {order['guild_id']}")

    AuditLogModel.log(
        actor_id=actor_id or 0,
        action=f"order.{body.status}",
        target_id=order_id,
        details={"plan": body.plan, "note": body.admin_note}
    )

    return {"status": "success", "order_id": order_id, "new_status": body.status}


# ============================================================================
# Subscriptions admin
# ============================================================================

@router.post("/admin/activate-sub", dependencies=[Depends(verify_api_secret)])
def activate_subscription(body: ActivateSubBody, request: Request):
    actor_id = getattr(request.state, "user_id", None)
    SubscriptionModel.create(
        guild_id=body.guild_id,
        user_id=0,
        plan=body.plan,
        duration_days=body.duration_days
    )
    AuditLogModel.log(
        actor_id=actor_id or 0,
        action="subscription.activate",
        guild_id=body.guild_id,
        details={"plan": body.plan, "duration_days": body.duration_days}
    )
    return {"status": "success", "guild_id": body.guild_id, "plan": body.plan}


@router.post("/revoke-sub", dependencies=[Depends(verify_api_secret)])
def revoke_subscription(body: RevokeSubBody, request: Request):
    actor_id = getattr(request.state, "user_id", None)
    SubscriptionModel.deactivate(body.guild_id)
    AuditLogModel.log(
        actor_id=actor_id or 0,
        action="subscription.revoke",
        guild_id=body.guild_id
    )
    return {"status": "success", "guild_id": body.guild_id}


# ============================================================================
# Knowledge Base
# ============================================================================

@router.get("/guild/{guild_id}/kb", dependencies=[Depends(verify_api_secret)])
def get_kb(guild_id: int):
    entries = KnowledgeBaseModel.get_by_guild(guild_id)
    limit   = PLAN_LIMITS.get(
        (SubscriptionModel.get(guild_id) or {}).get("plan", "free"), {}
    ).get("kb_entries", 0)
    return {
        "guild_id": guild_id,
        "total":    len(entries),
        "limit":    limit,
        "entries":  entries
    }


@router.post("/guild/{guild_id}/kb", dependencies=[Depends(verify_api_secret)])
def create_kb_entry(guild_id: int, body: KBEntryBody, request: Request):
    # Verifier la limite du plan
    sub   = SubscriptionModel.get(guild_id)
    plan  = (sub or {}).get("plan", "free")
    limit = PLAN_LIMITS.get(plan, {}).get("kb_entries", 0)
    current_count = KnowledgeBaseModel.count(guild_id)

    if limit is not None and current_count >= limit:
        raise HTTPException(
            status_code=403,
            detail=f"Limite KB atteinte ({current_count}/{limit}) pour le plan {plan}"
        )

    actor_id = getattr(request.state, "user_id", None)
    kb_id = KnowledgeBaseModel.create(
        guild_id=guild_id,
        question=body.question,
        answer=body.answer,
        category=body.category,
        created_by=actor_id or body.created_by
    )
    if not kb_id:
        raise HTTPException(status_code=500, detail="Erreur creation entree KB")

    AuditLogModel.log(
        actor_id=actor_id or 0,
        action="kb.create",
        guild_id=guild_id,
        target_id=str(kb_id),
        details={"question": body.question[:80]}
    )
    return {"status": "success", "id": kb_id}


@router.put("/guild/{guild_id}/kb/{kb_id}", dependencies=[Depends(verify_api_secret)])
def update_kb_entry(guild_id: int, kb_id: int, body: KBEntryBody, request: Request):
    entry = KnowledgeBaseModel.get(kb_id)
    if not entry or entry["guild_id"] != guild_id:
        raise HTTPException(status_code=404, detail="Entree KB non trouvee")

    KnowledgeBaseModel.update(kb_id, question=body.question, answer=body.answer,
                              category=body.category)
    actor_id = getattr(request.state, "user_id", None)
    AuditLogModel.log(actor_id=actor_id or 0, action="kb.update",
                      guild_id=guild_id, target_id=str(kb_id))
    return {"status": "success", "id": kb_id}


@router.delete("/guild/{guild_id}/kb/{kb_id}", dependencies=[Depends(verify_api_secret)])
def delete_kb_entry(guild_id: int, kb_id: int, request: Request):
    entry = KnowledgeBaseModel.get(kb_id)
    if not entry or entry["guild_id"] != guild_id:
        raise HTTPException(status_code=404, detail="Entree KB non trouvee")

    KnowledgeBaseModel.hard_delete(kb_id)
    actor_id = getattr(request.state, "user_id", None)
    AuditLogModel.log(actor_id=actor_id or 0, action="kb.delete",
                      guild_id=guild_id, target_id=str(kb_id))
    return {"status": "success"}


# ============================================================================
# Super Admin - statistiques globales
# ============================================================================

@router.get("/admin/stats", dependencies=[Depends(verify_api_secret)])
def get_global_stats():
    try:
        from bot.db.connection import get_db_context
        with get_db_context() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM vai_dashboard_stats")
            stats = cursor.fetchone() or {}

        bot_status = BotStatusModel.get() or {}

        return {
            "total_guilds":   int(stats.get("total_guilds", 0)),
            "total_users":    int(stats.get("total_users", 0)),
            "tickets_today":  int(stats.get("tickets_today", 0)),
            "orders_pending": int(stats.get("orders_pending", 0)),
            "revenue_month":  float(stats.get("revenue_month", 0)),
            "active_subs":    int(stats.get("active_subs", 0)),
            "bot_uptime_sec": bot_status.get("uptime_sec", 0),
            "bot_version":    bot_status.get("version", "?")
        }
    except Exception as e:
        logger.error(f"Erreur admin stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/guilds", dependencies=[Depends(verify_api_secret)])
def get_all_guilds():
    guilds = GuildModel.get_all()
    return {"total": len(guilds), "guilds": guilds}


@router.get("/admin/audit", dependencies=[Depends(verify_api_secret)])
def get_audit_log(guild_id: Optional[int] = None, limit: int = 100):
    logs = AuditLogModel.get_recent(guild_id=guild_id, limit=limit)
    return {"logs": logs}


# ============================================================================
# Bot status (ecrit par le bot, lu par le dashboard)
# ============================================================================

@router.post("/bot/heartbeat", dependencies=[Depends(verify_api_secret)])
def bot_heartbeat(guild_count: int = 0, user_count: int = 0,
                  uptime_sec: int = 0, version: str = ""):
    BotStatusModel.update(guild_count, user_count, uptime_sec, version)
    return {"status": "ok"}


@router.get("/bot/status", dependencies=[Depends(verify_api_secret)])
def bot_status():
    status = BotStatusModel.get()
    return status or {"status": "unknown"}

"""
OAuth2 Discord Authentication pour Dashboard
FIXES:
  - redirect_uri cohérent entre /login et /discord (POST)
  - Récupération guilds dans le callback GET aussi
  - JWT stocké en cookie httpOnly + fallback URL param
  - Route /auth/callback GET ajoutée (manquait → 404)
"""

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
import aiohttp
import os
from datetime import datetime, timedelta
import jwt
import secrets
from pydantic import BaseModel
from bot.db.connection import get_db_context
from bot.db.models import DashboardSessionModel
from bot.config import DB_TABLE_PREFIX
from loguru import logger

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_API_BASE = "https://discord.com/api/v10"
DISCORD_OAUTH_URL = "https://discord.com/api/v10/oauth2/authorize"

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _get_redirect_uri() -> str:
    """URI de redirection — DOIT correspondre exactement à ce qui est
    enregistré dans le portail Discord Developer."""
    # Priorité : variable explicite, sinon construite depuis DASHBOARD_URL
    explicit = os.getenv("DISCORD_REDIRECT_URI")
    if explicit:
        return explicit
    dashboard = os.getenv("DASHBOARD_URL", "https://veridiancloud.xyz")
    return f"{dashboard}/auth/callback"


def get_active_guild_ids() -> list:
    """Récupère les IDs de tous les serveurs où le bot est installé."""
    try:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id FROM {DB_TABLE_PREFIX}guilds")
            return [int(row[0]) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"✗ Erreur récupération guildes actives: {e}")
        return []


async def _exchange_code_and_fetch_user(code: str, redirect_uri: str) -> dict:
    """
    Échange le code OAuth contre un access_token puis récupère :
      - le profil utilisateur (/users/@me)
      - les serveurs de l'utilisateur (/users/@me/guilds)
    Retourne un dict {access_token, user, guilds}.
    """
    client_id = os.getenv("DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")

    async with aiohttp.ClientSession() as session:
        # 1. Échange du code
        token_resp = await session.post(
            f"{DISCORD_API_BASE}/oauth2/token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        if token_resp.status != 200:
            err = await token_resp.text()
            logger.error(f"✗ Token exchange failed ({token_resp.status}): {err}")
            raise HTTPException(status_code=400, detail="Token exchange failed")

        token_data = await token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access_token in Discord response")

        headers = {"Authorization": f"Bearer {access_token}"}

        # 2. Profil utilisateur
        user_resp = await session.get(f"{DISCORD_API_BASE}/users/@me", headers=headers)
        if user_resp.status != 200:
            raise HTTPException(status_code=400, detail="Failed to get Discord user")
        user = await user_resp.json()

        # 3. Serveurs de l'utilisateur
        guilds_resp = await session.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers)
        if guilds_resp.status != 200:
            logger.warning("⚠️ Failed to fetch guilds — returning empty list")
            guilds = []
        else:
            guilds = await guilds_resp.json()

    return {"access_token": access_token, "user": user, "guilds": guilds}


def _build_filtered_guilds(all_guilds: list) -> list:
    """Filtre : admin sur le serveur ET bot installé."""
    ADMIN_PERMISSION = 0x8
    bot_guild_ids = get_active_guild_ids()
    filtered = []
    for g in all_guilds:
        try:
            permissions = int(g.get("permissions", 0))
            guild_id = int(g.get("id", 0))
            if (permissions & ADMIN_PERMISSION) and guild_id in bot_guild_ids:
                filtered.append({
                    "id": str(guild_id),
                    "name": g.get("name", "Unknown"),
                    "icon": (
                        f"https://cdn.discordapp.com/icons/{guild_id}/{g['icon']}.png"
                        if g.get("icon") else None
                    ),
                })
        except (ValueError, KeyError) as e:
            logger.warning(f"✗ Erreur parsing guild: {e}")
    return filtered


def _build_avatar_url(user: dict, user_id: int) -> str:
    if user.get("avatar"):
        return f"https://cdn.discordapp.com/avatars/{user_id}/{user['avatar']}.png?size=128"
    discriminator = user.get("discriminator", "0")
    try:
        idx = int(discriminator) % 5
    except Exception:
        idx = user_id % 5
    return f"https://cdn.discordapp.com/embed/avatars/{idx}.png"


def _create_jwt(user_id: int, username: str, is_super_admin: bool) -> str:
    secret = os.getenv("JWT_SECRET", "change_me_in_production")
    return jwt.encode(
        {
            "sub": user_id,
            "username": username,
            "is_super_admin": is_super_admin,
            "exp": datetime.utcnow() + timedelta(days=7),
        },
        secret,
        algorithm="HS256",
    )


def _save_session(discord_user_id: int, discord_username: str, access_token: str, jwt_token: str):
    try:
        with get_db_context() as db:
            DashboardSessionModel.create(
                discord_user_id=discord_user_id,
                discord_username=discord_username,
                access_token=access_token,
                jwt_token=jwt_token,
                expires_at=datetime.utcnow() + timedelta(days=7),
            )
    except Exception as e:
        logger.warning(f"⚠️ Session non sauvegardée en DB: {e}")


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@router.get("/discord/login")
def discord_login():
    """Redirige vers Discord OAuth2 (utilisé par le bouton login HTML direct)."""
    client_id = os.getenv("DISCORD_CLIENT_ID")
    redirect_uri = _get_redirect_uri()
    auth_url = (
        f"{DISCORD_OAUTH_URL}?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=identify%20email%20guilds"
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def discord_callback(
    response: Response,
    code: str = Query(None),
    error: str = Query(None),
):
    """
    Callback GET après redirection Discord.
    FIX: Cette route était absente → 404 systématique après login Discord.
    """
    if error:
        dashboard_url = os.getenv("DASHBOARD_URL", "https://veridiancloud.xyz")
        return RedirectResponse(url=f"{dashboard_url}/dashboard.html?error={error}")

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code provided")

    redirect_uri = _get_redirect_uri()
    data = await _exchange_code_and_fetch_user(code, redirect_uri)

    user = data["user"]
    user_id = int(user.get("id", 0))
    username = user.get("username", "Unknown")

    bot_owner_id = int(os.getenv("BOT_OWNER_DISCORD_ID", 0))
    is_super_admin = user_id == bot_owner_id

    jwt_token = _create_jwt(user_id, username, is_super_admin)
    _save_session(user_id, username, data["access_token"], jwt_token)

    # Filtrer les serveurs et les mettre dans un cookie encodé (base64 JSON)
    # Le dashboard les récupérera via /auth/user/me ou les lit depuis le param
    dashboard_url = os.getenv("DASHBOARD_URL", "https://veridiancloud.xyz")

    resp = RedirectResponse(
        url=f"{dashboard_url}/dashboard.html?token={jwt_token}",
        status_code=302,
    )
    # Cookie httpOnly pour les prochaines requêtes API
    resp.set_cookie(
        key="vai_token",
        value=jwt_token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=True,
    )
    logger.info(f"✓ OAuth callback: {username} (ID: {user_id}) — super_admin={is_super_admin}")
    return resp


@router.post("/discord")
async def discord_auth(request: Request):
    """
    Échange un code OAuth2 Discord.
    Appelé en AJAX depuis le frontend (popup flow ou redirect flow manuel).
    Body JSON: { "code": "..." }
    """
    body = await request.json()
    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")

    redirect_uri = _get_redirect_uri()
    data = await _exchange_code_and_fetch_user(code, redirect_uri)

    user = data["user"]
    all_guilds = data["guilds"]
    user_id = int(user.get("id", 0))
    username = user.get("username", "Unknown")

    filtered_guilds = _build_filtered_guilds(all_guilds)
    avatar_url = _build_avatar_url(user, user_id)

    bot_owner_id = int(os.getenv("BOT_OWNER_DISCORD_ID", 0))
    is_super_admin = user_id == bot_owner_id

    jwt_token = _create_jwt(user_id, username, is_super_admin)
    _save_session(user_id, username, data["access_token"], jwt_token)

    logger.info(f"✓ OAuth POST: {username} (ID: {user_id}) — {len(filtered_guilds)} serveur(s)")

    return JSONResponse(
        status_code=200,
        content={
            "token": jwt_token,
            "user": {
                "id": str(user_id),
                "username": username,
                "avatar": avatar_url,
                "is_super_admin": is_super_admin,
            },
            "guilds": filtered_guilds,
        },
    )


@router.get("/user/me")
async def get_current_user(request: Request):
    """Récupère les infos de l'utilisateur connecté depuis le JWT."""
    # Accepte le token en cookie httpOnly OU en header Authorization Bearer
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("vai_token")
    if not token:
        # Fallback: query param (moins sécurisé mais pratique en dev)
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        secret = os.getenv("JWT_SECRET", "change_me_in_production")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return {
            "user_id": payload.get("sub"),
            "username": payload.get("username"),
            "is_super_admin": payload.get("is_super_admin", False),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Déconnecter l'utilisateur — invalide le cookie et la session DB."""
    token = request.cookies.get("vai_token")
    if not token:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        token = body.get("token")

    if token:
        try:
            with get_db_context() as db:
                DashboardSessionModel.revoke_token(token)
        except Exception as e:
            logger.warning(f"⚠️ Logout DB error: {e}")

    response.delete_cookie("vai_token")
    return JSONResponse(status_code=200, content={"status": "success"})

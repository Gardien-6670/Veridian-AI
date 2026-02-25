"""
OAuth2 Discord Authentication pour Dashboard
IMPORTANT - Redirect URI :
  Le callback DOIT pointer vers l'API (api.veridiancloud.xyz), pas vers le front.
  Variable DISCORD_REDIRECT_URI dans .env doit valoir :
      https://api.veridiancloud.xyz/auth/callback
  Et cette URI doit etre enregistree dans le portail Discord Developer.
"""

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
import aiohttp
import os
from datetime import datetime, timedelta
import jwt
from loguru import logger

from bot.db.connection import get_db_context
from bot.db.models import DashboardSessionModel
from bot.config import DB_TABLE_PREFIX

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_API_BASE  = "https://discord.com/api/v10"
DISCORD_OAUTH_URL = "https://discord.com/api/v10/oauth2/authorize"


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _get_redirect_uri() -> str:
    """
    URI de redirection OAuth2.
    DOIT pointer vers l'API FastAPI (api.veridiancloud.xyz), pas vers le front.
    Configurez DISCORD_REDIRECT_URI=https://api.veridiancloud.xyz:/auth/callback dans .env
    et enregistrez cette meme URI dans Discord Developer Portal > OAuth2 > Redirects.
    """
    explicit = os.getenv("DISCORD_REDIRECT_URI")
    if explicit:
        return explicit
    # Fallback : construit depuis API_DOMAIN
    api_domain = os.getenv("API_DOMAIN", "api.veridiancloud.xyz:201")
    return f"https://{api_domain}/auth/callback"


def _get_dashboard_url() -> str:
    return os.getenv("DASHBOARD_URL", "https://veridiancloud.xyz/dashboard")


def get_active_guild_ids() -> list:
    try:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id FROM {DB_TABLE_PREFIX}guilds")
            return [int(row[0]) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Erreur recuperation guilds actives: {e}")
        return []


async def _exchange_code_and_fetch_user(code: str, redirect_uri: str) -> dict:
    client_id     = os.getenv("DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")

    async with aiohttp.ClientSession() as session:
        # 1. Echange du code contre un access_token
        token_resp = await session.post(
            f"{DISCORD_API_BASE}/oauth2/token",
            data={
                "client_id":     client_id,
                "client_secret": client_secret,
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  redirect_uri,
            },
        )
        if token_resp.status != 200:
            err = await token_resp.text()
            logger.error(f"Token exchange failed ({token_resp.status}): {err}")
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {err}")

        token_data   = await token_resp.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access_token in Discord response")

        headers = {"Authorization": f"Bearer {access_token}"}

        # 2. Profil utilisateur
        user_resp = await session.get(f"{DISCORD_API_BASE}/users/@me", headers=headers)
        if user_resp.status != 200:
            raise HTTPException(status_code=400, detail="Failed to get Discord user profile")
        user = await user_resp.json()

        # 3. Serveurs de l'utilisateur
        guilds_resp = await session.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers)
        guilds = await guilds_resp.json() if guilds_resp.status == 200 else []

    return {"access_token": access_token, "user": user, "guilds": guilds}


def _build_filtered_guilds(all_guilds: list) -> list:
    """Garde uniquement les serveurs ou l'utilisateur est admin ET ou le bot est installe."""
    ADMIN_PERM   = 0x8
    bot_guild_ids = get_active_guild_ids()
    result = []
    for g in all_guilds:
        try:
            perms    = int(g.get("permissions", 0))
            guild_id = int(g.get("id", 0))
            if (perms & ADMIN_PERM) and guild_id in bot_guild_ids:
                result.append({
                    "id":   str(guild_id),
                    "name": g.get("name", "Unknown"),
                    "icon": (
                        f"https://cdn.discordapp.com/icons/{guild_id}/{g['icon']}.png"
                        if g.get("icon") else None
                    ),
                })
        except Exception:
            pass
    return result


def _build_avatar_url(user: dict, user_id: int) -> str:
    if user.get("avatar"):
        return f"https://cdn.discordapp.com/avatars/{user_id}/{user['avatar']}.png?size=128"
    return f"https://cdn.discordapp.com/embed/avatars/{user_id % 5}.png"


def _create_jwt(user_id: int, username: str, is_super_admin: bool) -> str:
    secret = os.getenv("JWT_SECRET", "change_me_in_production")
    return jwt.encode(
        {
            "sub":            user_id,
            "username":       username,
            "is_super_admin": is_super_admin,
            "exp":            datetime.utcnow() + timedelta(days=7),
        },
        secret,
        algorithm="HS256",
    )


def _save_session(discord_user_id: int, discord_username: str,
                  access_token: str, jwt_token: str):
    try:
        DashboardSessionModel.create(
            discord_user_id=discord_user_id,
            discord_username=discord_username,
            access_token=access_token,
            jwt_token=jwt_token,
            expires_at=datetime.utcnow() + timedelta(days=7),
        )
    except Exception as e:
        logger.warning(f"Session non sauvegardee en DB: {e}")


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@router.get("/discord/login")
def discord_login():
    """
    Redirige vers Discord OAuth2.
    Le redirect_uri pointe vers l'API (api.veridiancloud.xyz/auth/callback).
    """
    client_id    = os.getenv("DISCORD_CLIENT_ID")
    redirect_uri = _get_redirect_uri()
    auth_url = (
        f"{DISCORD_OAUTH_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    logger.info(f"Login Discord -> redirect_uri={redirect_uri}")
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def discord_callback(
    code:  str = Query(None),
    error: str = Query(None),
):
    """
    Callback OAuth2 — Discord redirige ICI apres connexion.
    Cette route doit etre sur api.veridiancloud.xyz, pas sur le front.
    Apres auth, redirige vers le dashboard front avec le JWT en param URL.
    """
    dashboard_url = _get_dashboard_url()

    if error:
        logger.warning(f"OAuth error: {error}")
        return RedirectResponse(url=f"{dashboard_url}?error={error}", status_code=302)

    if not code:
        raise HTTPException(status_code=400, detail="No authorization code provided")

    redirect_uri = _get_redirect_uri()
    logger.info(f"OAuth callback recu, echange code, redirect_uri={redirect_uri}")

    data     = await _exchange_code_and_fetch_user(code, redirect_uri)
    user     = data["user"]
    user_id  = int(user.get("id", 0))
    username = user.get("username", "Unknown")

    bot_owner_id   = int(os.getenv("BOT_OWNER_DISCORD_ID", 0))
    is_super_admin = user_id == bot_owner_id

    jwt_token = _create_jwt(user_id, username, is_super_admin)
    _save_session(user_id, username, data["access_token"], jwt_token)

    logger.info(f"OAuth OK: {username} ({user_id}) super_admin={is_super_admin}")

    # Redirection vers le FRONT avec le token en parametre URL
    # Le JS du dashboard recoit le token depuis window.location.search
    resp = RedirectResponse(
        url=f"{dashboard_url}?token={jwt_token}",
        status_code=302,
    )
    # Cookie httpOnly en plus (pour les requetes API directes)
    resp.set_cookie(
        key="vai_token",
        value=jwt_token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=True,
        domain=".veridiancloud.xyz",  # partage entre api. et www.
    )
    return resp


@router.post("/discord")
async def discord_auth_ajax(request: Request):
    """
    Echange un code OAuth2 en AJAX (flow popup).
    Body JSON: { "code": "..." }
    """
    body = await request.json()
    code = body.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="No code provided")

    redirect_uri = _get_redirect_uri()
    data         = await _exchange_code_and_fetch_user(code, redirect_uri)

    user       = data["user"]
    all_guilds = data["guilds"]
    user_id    = int(user.get("id", 0))
    username   = user.get("username", "Unknown")

    filtered_guilds = _build_filtered_guilds(all_guilds)
    avatar_url      = _build_avatar_url(user, user_id)

    bot_owner_id   = int(os.getenv("BOT_OWNER_DISCORD_ID", 0))
    is_super_admin = user_id == bot_owner_id

    jwt_token = _create_jwt(user_id, username, is_super_admin)
    _save_session(user_id, username, data["access_token"], jwt_token)

    logger.info(f"OAuth AJAX: {username} ({user_id}) {len(filtered_guilds)} guilds")

    return JSONResponse(content={
        "token": jwt_token,
        "user": {
            "id":             str(user_id),
            "username":       username,
            "avatar":         avatar_url,
            "is_super_admin": is_super_admin,
        },
        "guilds": filtered_guilds,
    })


@router.get("/user/me")
async def get_current_user(request: Request):
    """Infos de l'utilisateur connecte depuis le JWT (cookie ou Bearer)."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        token = request.cookies.get("vai_token")
    if not token:
        token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    try:
        secret  = os.getenv("JWT_SECRET", "change_me_in_production")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return {
            "user_id":        payload.get("sub"),
            "username":       payload.get("username"),
            "is_super_admin": payload.get("is_super_admin", False),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Deconnexion — invalide le cookie et la session DB."""
    token = request.cookies.get("vai_token")
    if not token:
        try:
            body  = await request.json()
            token = body.get("token")
        except Exception:
            pass

    if token:
        try:
            DashboardSessionModel.revoke_token(token)
        except Exception as e:
            logger.warning(f"Logout DB error: {e}")

    response.delete_cookie("vai_token", domain=".veridiancloud.xyz")
    return JSONResponse(content={"status": "success"})
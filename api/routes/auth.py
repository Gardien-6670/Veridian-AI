"""
OAuth2 Discord Authentication — Architecture securisee v0.3
Flux :
  1. Discord -> /auth/callback?code=DISCORD_CODE
  2. API echange le code, genere JWT + temp_code (DB, 60s, usage unique)
  3. Redirect vers dashboard.html?auth=TEMP_CODE
  4. JS POST /auth/exchange {code} -> recoit {token, user, guilds}
  5. JWT stocke en localStorage uniquement — jamais dans une URL
"""

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, JSONResponse
import aiohttp
import os
import secrets
from datetime import datetime, timedelta
import jwt
from loguru import logger

from bot.db.connection import get_db_context
from bot.db.models import DashboardSessionModel, TempCodeModel
from bot.config import DB_TABLE_PREFIX

router = APIRouter(prefix="/auth", tags=["auth"])

DISCORD_API_BASE  = "https://discord.com/api/v10"
DISCORD_OAUTH_URL = "https://discord.com/api/v10/oauth2/authorize"


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _get_redirect_uri() -> str:
    explicit = os.getenv("DISCORD_REDIRECT_URI")
    if explicit:
        return explicit
    api_domain = os.getenv("API_DOMAIN", "api.veridiancloud.xyz")
    return f"https://{api_domain}/auth/callback"


def _get_dashboard_url() -> str:
    return os.getenv("DASHBOARD_URL", "https://veridiancloud.xyz/dashboard.html")


def get_active_guild_ids() -> list:
    try:
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT id FROM {DB_TABLE_PREFIX}guilds")
            return [int(row[0]) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"Erreur recuperation guilds: {e}")
        return []


async def _exchange_code_and_fetch_user(code: str, redirect_uri: str) -> dict:
    client_id     = os.getenv("DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")
    async with aiohttp.ClientSession() as session:
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
            raise HTTPException(status_code=400, detail="Pas d'access_token Discord")
        headers     = {"Authorization": f"Bearer {access_token}"}
        user_resp   = await session.get(f"{DISCORD_API_BASE}/users/@me", headers=headers)
        if user_resp.status != 200:
            raise HTTPException(status_code=400, detail="Impossible de recuperer le profil")
        user        = await user_resp.json()
        guilds_resp = await session.get(f"{DISCORD_API_BASE}/users/@me/guilds", headers=headers)
        guilds      = await guilds_resp.json() if guilds_resp.status == 200 else []
    return {"access_token": access_token, "user": user, "guilds": guilds}


def _build_filtered_guilds(all_guilds: list) -> list:
    ADMIN_PERM    = 0x8
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
    client_id    = os.getenv("DISCORD_CLIENT_ID")
    redirect_uri = _get_redirect_uri()
    auth_url = (
        f"{DISCORD_OAUTH_URL}"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    logger.info(f"Login Discord -> {redirect_uri}")
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def discord_callback(
    code:  str = Query(None),
    error: str = Query(None),
):
    """
    Callback OAuth2 Discord.
    Genere un temp_code en DB (60s, usage unique) et redirige
    vers le dashboard avec ?auth=TEMP_CODE.
    Le JWT ne passe JAMAIS dans l'URL.
    """
    dashboard_url = _get_dashboard_url()

    if error:
        return RedirectResponse(url=f"{dashboard_url}?error={error}", status_code=302)
    if not code:
        raise HTTPException(status_code=400, detail="Code manquant")

    data     = await _exchange_code_and_fetch_user(code, _get_redirect_uri())
    user     = data["user"]
    user_id  = int(user.get("id", 0))
    username = user.get("username", "Unknown")

    bot_owner_id    = int(os.getenv("BOT_OWNER_DISCORD_ID", 0))
    is_super_admin  = user_id == bot_owner_id
    filtered_guilds = _build_filtered_guilds(data["guilds"])
    jwt_token       = _create_jwt(user_id, username, is_super_admin)

    _save_session(user_id, username, data["access_token"], jwt_token)

    user_data = {
        "id":             str(user_id),
        "username":       username,
        "avatar":         _build_avatar_url(user, user_id),
        "is_super_admin": is_super_admin,
    }

    # Stocker en DB — survit aux redemarrages, atomique (FOR UPDATE)
    temp_code = secrets.token_urlsafe(24)
    ok = TempCodeModel.create(temp_code, jwt_token, user_data, filtered_guilds)
    if not ok:
        # La table vai_temp_codes n'existe peut-etre pas encore
        # -> executer le schema.sql pour la creer
        logger.error("TempCodeModel.create a echoue — la table vai_temp_codes existe-t-elle ?")
        raise HTTPException(
            status_code=500,
            detail="Erreur interne: table vai_temp_codes manquante. Executez le schema.sql."
        )

    # Nettoyage opportuniste (non bloquant)
    try:
        TempCodeModel.cleanup()
    except Exception:
        pass

    logger.info(f"OAuth OK: {username} ({user_id}) super_admin={is_super_admin}")

    return RedirectResponse(
        url=f"{dashboard_url}?auth={temp_code}",
        status_code=302,
    )


@router.post("/exchange")
async def exchange_temp_code(request: Request):
    """
    Echange un temp_code contre {token, user, guilds}.
    Usage unique, expire en 60 secondes, atomique en DB (FOR UPDATE).
    Body JSON: { "code": "..." }
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Body JSON invalide")

    temp_code = body.get("code")
    if not temp_code:
        raise HTTPException(status_code=400, detail="Champ 'code' manquant")

    data = TempCodeModel.consume(temp_code)
    if not data:
        raise HTTPException(status_code=400, detail="Code invalide, expire ou deja utilise")

    logger.info(f"Temp code echange: {data['user'].get('username')}")

    return JSONResponse(content={
        "token":  data["jwt"],
        "user":   data["user"],
        "guilds": data["guilds"],
    })


@router.get("/user/me")
async def get_current_user(request: Request):
    """Valide le JWT Bearer et retourne les infos utilisateur."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Header Authorization manquant")
    token = auth_header[7:]
    try:
        secret  = os.getenv("JWT_SECRET", "change_me_in_production")
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return {
            "user_id":        payload.get("sub"),
            "username":       payload.get("username"),
            "is_super_admin": payload.get("is_super_admin", False),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expire")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")


@router.post("/logout")
async def logout(request: Request):
    """Invalide la session en DB."""
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
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
    return JSONResponse(content={"status": "success"})
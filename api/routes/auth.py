"""
OAuth2 Discord Authentication pour Dashboard
"""

from fastapi import APIRouter, HTTPException, Query
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


# ============================================================================
# Pydantic Models
# ============================================================================

class DiscordCodeRequest(BaseModel):
    code: str


# ============================================================================
# Helper Functions
# ============================================================================

def get_active_guild_ids() -> list:
    """Récupère les IDs de tous les serveurs où le bot est installé (vai_guilds)."""
    try:
        with get_db_context() as conn:
            cursor = conn.cursor()
            query = f"SELECT id FROM {DB_TABLE_PREFIX}guilds"
            cursor.execute(query)
            result = cursor.fetchall()
            return [int(row[0]) for row in result]
    except Exception as e:
        logger.error(f"✗ Erreur lors de la récupération des guildes actives: {e}")
        return []


# ============================================================================
# Routes
# ============================================================================

@router.get("/discord/login")
def discord_login():
    """Rediriger vers Discord OAuth2"""
    client_id = os.getenv("DISCORD_CLIENT_ID")
    redirect_uri = os.getenv("DASHBOARD_URL", "http://localhost:3000") + "/auth/callback"
    
    auth_url = (
        f"{DISCORD_OAUTH_URL}?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"response_type=code&"
        f"scope=identify%20email%20guilds"
    )
    
    return RedirectResponse(url=auth_url)


@router.get("/discord/callback")
async def discord_callback(code: str = Query(None), error: str = Query(None)):
    """Callback OAuth2 Discord"""
    
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code provided")
    
    try:
        client_id = os.getenv("DISCORD_CLIENT_ID")
        client_secret = os.getenv("DISCORD_CLIENT_SECRET")
        redirect_uri = os.getenv("DASHBOARD_URL", "http://localhost:3000") + "/auth/callback"
        
        # Échanger le code pour un token
        async with aiohttp.ClientSession() as session:
            # Obtenir l'access token
            token_response = await session.post(
                f"{DISCORD_API_BASE}/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri
                }
            )
            
            if token_response.status != 200:
                raise HTTPException(status_code=400, detail="Failed to exchange code")
            
            token_data = await token_response.json()
            access_token = token_data.get("access_token")
            
            # Récupérer les infos utilisateur
            user_response = await session.get(
                f"{DISCORD_API_BASE}/users/@me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if user_response.status != 200:
                raise HTTPException(status_code=400, detail="Failed to get user info")
            
            user_data = await user_response.json()
        
        discord_user_id = int(user_data.get("id"))
        discord_username = user_data.get("username")
        
        # Générer un JWT token
        jwt_secret = os.getenv("JWT_SECRET", "change_me")
        jwt_token = jwt.encode(
            {
                "sub": discord_user_id,
                "username": discord_username,
                "exp": datetime.utcnow() + timedelta(days=7)
            },
            jwt_secret,
            algorithm="HS256"
        )
        
        # Sauvegarder la session
        with get_db_context() as db:
            DashboardSessionModel.create(
                discord_user_id=discord_user_id,
                discord_username=discord_username,
                access_token=access_token,
                jwt_token=jwt_token,
                expires_at=datetime.utcnow() + timedelta(days=7)
            )
        
        # Rediriger vers le dashboard avec le JWT
        dashboard_url = os.getenv("DASHBOARD_URL", "http://localhost:3000")
        return RedirectResponse(
            url=f"{dashboard_url}?token={jwt_token}",
            status_code=302
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")


@router.post("/discord")
async def discord_auth(request: DiscordCodeRequest):
    """
    Échange un code OAuth2 Discord contre les infos utilisateur + serveurs filtrés.
    Appelé depuis le navigateur (frontend) après redirection OAuth.
    """
    if not request.code:
        raise HTTPException(status_code=400, detail="No code provided")
    
    try:
        client_id = os.getenv("DISCORD_CLIENT_ID")
        client_secret = os.getenv("DISCORD_CLIENT_SECRET")
        redirect_uri = os.getenv("DISCORD_REDIRECT_URI", "https://veridiancloud.xyz/dashboard.html")
        
        # Étape 1: Échanger le code contre un access_token
        async with aiohttp.ClientSession() as session:
            token_response = await session.post(
                f"{DISCORD_API_BASE}/oauth2/token",
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "grant_type": "authorization_code",
                    "code": request.code,
                    "redirect_uri": redirect_uri
                }
            )
            
            if token_response.status != 200:
                error_text = await token_response.text()
                logger.error(f"✗ Discord token exchange failed: {error_text}")
                raise HTTPException(status_code=400, detail="Token exchange failed")
            
            token_data = await token_response.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                logger.error("✗ No access_token in Discord response")
                raise HTTPException(status_code=400, detail="Invalid token response")
            
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Étape 2: Récupérer le profil utilisateur
            user_response = await session.get(
                f"{DISCORD_API_BASE}/users/@me",
                headers=headers
            )
            
            if user_response.status != 200:
                logger.error(f"✗ Failed to get Discord user info: {user_response.status}")
                raise HTTPException(status_code=400, detail="Failed to get user info")
            
            user = await user_response.json()
            user_id = int(user.get("id", 0))
            
            # Étape 3: Récupérer tous les serveurs de l'utilisateur
            guilds_response = await session.get(
                f"{DISCORD_API_BASE}/users/@me/guilds",
                headers=headers
            )
            
            if guilds_response.status != 200:
                logger.error(f"✗ Failed to get Discord guilds: {guilds_response.status}")
                raise HTTPException(status_code=400, detail="Failed to get guilds")
            
            all_guilds = await guilds_response.json()
        
        # Étape 4: Filtrer les serveurs
        # Conditions:
        # - Utilisateur est admin (permission & 0x8)
        # - Bot Veridian AI est installé sur le serveur (dans vai_guilds)
        ADMIN_PERMISSION = 0x8
        bot_guild_ids = get_active_guild_ids()
        
        filtered_guilds = []
        for guild in all_guilds:
            try:
                permissions = int(guild.get("permissions", 0))
                guild_id = int(guild.get("id", 0))
                
                # Vérifier si l'utilisateur est admin ET si le bot est sur le serveur
                is_admin = (permissions & ADMIN_PERMISSION) != 0
                bot_installed = guild_id in bot_guild_ids
                
                if is_admin and bot_installed:
                    filtered_guilds.append({
                        "id": str(guild_id),
                        "name": guild.get("name", "Unknown"),
                        "icon": f"https://cdn.discordapp.com/icons/{guild_id}/{guild['icon']}.png" 
                                if guild.get("icon") else None,
                    })
            except (ValueError, KeyError) as e:
                logger.warning(f"✗ Erreur parsing guild: {e}")
                continue
        
        # Étape 5: Construire l'URL de l'avatar utilisateur
        avatar_url = None
        if user.get("avatar"):
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{user['avatar']}.png?size=128"
        else:
            # Avatar par défaut Discord (basé sur le discriminateur ou user ID)
            discriminator = user.get("discriminator", "0")
            try:
                avatar_num = int(discriminator) % 5
            except:
                avatar_num = int(user_id) % 5
            avatar_url = f"https://cdn.discordapp.com/embed/avatars/{avatar_num}.png"
        
        # Vérifier si l'utilisateur est Bot Owner
        bot_owner_id = int(os.getenv("BOT_OWNER_DISCORD_ID", 0))
        is_super_admin = user_id == bot_owner_id
        
        logger.info(f"✓ OAuth Discord: {user.get('username')} (ID: {user_id}) — {len(filtered_guilds)} serveurs")
        
        return JSONResponse(
            status_code=200,
            content={
                "user": {
                    "id": str(user_id),
                    "username": user.get("username", "Unknown"),
                    "avatar": avatar_url,
                    "is_super_admin": is_super_admin,
                },
                "guilds": filtered_guilds
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"✗ Erreur dans discord_auth: {e}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")


@router.post("/logout")
def logout(token: str = Query(None)):
    """Déconnecter l'utilisateur"""
    if not token:
        raise HTTPException(status_code=400, detail="No token provided")
    
    try:
        with get_db_context() as db:
            # Invalider le token en DB
            DashboardSessionModel.revoke_token(token)
        
        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Logged out"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/user/me")
async def get_current_user(token: str = Query(None)):
    """Récupérer les infos de l'utilisateur connecté"""
    
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    
    try:
        jwt_secret = os.getenv("JWT_SECRET", "change_me")
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        
        user_id = payload.get("sub")
        username = payload.get("username")
        
        return {
            "user_id": user_id,
            "username": username
        }
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

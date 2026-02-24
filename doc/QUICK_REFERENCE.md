# ⚡ Veridian AI - Quick Reference Guide

## 🚀 30-Second Start (Local)

```bash
cd "bot ia"
cp .env.example .env          # Edit with your keys
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mysql < database/schema.sql
python bot/main.py
```

## 🐳 Docker Start

```bash
cd "bot ia"
cp .env.example .env          # Edit with your keys
docker-compose up -d
docker-compose logs -f bot
```

---

## 📚 File Map (Quick Navigation)

| Need | File |
|------|------|
| Bot commands | `bot/cogs/*.py` |
| AI integration | `bot/services/groq_client.py` |
| Translation | `bot/services/translator.py` |
| Payments | `bot/services/oxapay.py`, `bot/cogs/payments.py` |
| Database setup | `database/schema.sql` |
| Config constants | `bot/config.py` |
| API endpoints | `api/routes/*.py` |
| Web UI | `web/templates/*.html` |
| Deployment | `DEPLOYMENT.md` |
| Architecture | `STRUCTURE.md` |

---

## 🎮 Discord Commands

```
/ticket                    Create support ticket
/close [reason]           Close ticket + generate AI summary
/translate [lang]         Change translation language
/language [code]          Set user language preference
/pay [method] [plan]      Initiate payment (paypal|crypto|giftcard)
/premium                  Show plan information
/status                   Check subscription status
/validate [order] [plan]  Approve pending order (admin)
/revoke @user            Revoke user subscription (admin)
/orders pending          List pending orders (admin)
/setup                   Configure bot (admin)
```

---

## 🔌 API Endpoints

### Public (No Auth)
```
POST /webhook/oxapay              OxaPay payment callback
GET  /auth/discord/login          Discord OAuth2 redirect
GET  /auth/discord/callback       OAuth2 callback handler
```

### Internal (Requires Header: X-API-Secret)
```
GET    /internal/guild/{id}/config
PUT    /internal/guild/{id}/config
GET    /internal/guild/{id}/tickets?status=open&page=1
GET    /internal/guild/{id}/stats
GET    /internal/user/{id}/subscription
PUT    /internal/user/{id}/language
GET    /internal/health
GET    /auth/user/me?token=<jwt>
POST   /auth/logout?token=<jwt>
```

---

## 🗄️ Database Tables

| Table | Purpose | Key Fields |
|-------|---------|-----------|
| `vai_guilds` | Server config | tier, support_channel_id |
| `vai_users` | User prefs | preferred_language |
| `vai_tickets` | Support tickets | guild_id, status |
| `vai_ticket_messages` | Message pairs | original_language, target_language |
| `vai_translations_cache` | Translation cache | content_hash (SHA256) |
| `vai_orders` | Pending orders | order_id (VAI-YYYYMM-XXXX) |
| `vai_payments` | Payment history | method, status |
| `vai_subscriptions` | Active plans | plan, is_active |
| `vai_knowledge_base` | FAQ database | category |
| `vai_dashboard_sessions` | OAuth2 sessions | jwt_token |

---

## 🔑 Environment Variables

**Required:**
```env
DISCORD_TOKEN=<bot_token>
DISCORD_CLIENT_ID=<oauth_client_id>
DISCORD_CLIENT_SECRET=<oauth_secret>
GROQ_API_KEY=<groq_key>
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=<password>
DB_NAME=veridianai
```

**Optional (but recommended):**
```env
OXAPAY_MERCHANT_KEY=<key>
OXAPAY_WEBHOOK_SECRET=<secret>
JWT_SECRET=<long_random_string>
INTERNAL_API_SECRET=<long_random_string>
PAYPAL_EMAIL=business@paypal.com
BOT_OWNER_DISCORD_ID=123456789
```

---

## 🧠 Key Functions

### Database
```python
from bot.db.models import TicketModel, UserModel, OrderModel

# Get ticket by Discord channel
ticket = TicketModel.get_by_channel(channel_id)

# Create new order
OrderModel.create(user_id, guild_id, "paypal", "premium", 2.00)

# Activate subscription
SubscriptionModel.create_or_update(guild_id, user_id, "premium", is_active=True)
```

### AI Services
```python
from bot.services.groq_client import get_support_response
from bot.services.translator import Translator

# Get AI response
response = await get_support_response(question, language="en")

# Translate text
translator = Translator()
translated = await translator.translate("Hello", "en", "fr")
```

### Payments
```python
from bot.services.oxapay import OxaPay

oxapay = OxaPay()
invoice = await oxapay.create_invoice(
    amount=2.00,
    currency="USD",
    description="Premium Plan"
)
```

---

## 🐛 Troubleshooting

### Bot won't start
```bash
# Check token
echo $DISCORD_TOKEN

# Check syntax
python -m py_compile bot/main.py

# Check dependencies
pip list | grep discord

# View logs
tail -f logs/bot.log
```

### Database connection error
```bash
# Check MySQL running
sudo service mysql status

# Check credentials
mysql -h $DB_HOST -u $DB_USER -p$DB_PASSWORD -e "SELECT 1"

# Verify schema
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -e "SHOW TABLES;"
```

### API not responding
```bash
# Check port
netstat -tlnp | grep 8000

# Test endpoint
curl http://localhost:8000/internal/health

# Check logs
docker logs veridian-api
```

---

## 📊 Monitoring Commands

```bash
# Bot logs
docker logs -f veridian-bot --tail=100

# API logs
docker logs -f veridian-api --tail=100

# Database stats
mysql -u $DB_USER -p$DB_PASSWORD $DB_NAME -e "SELECT COUNT(*) as tickets FROM vai_tickets;"

# Container health
docker ps

# Resource usage
docker stats

# Network diagnostics
curl -v http://localhost:8000/internal/health
```

---

## 🔐 Security Checklist

- [ ] `.env` file created (never commit!)
- [ ] JWT_SECRET changed (min 32 chars)
- [ ] INTERNAL_API_SECRET changed (min 32 chars)
- [ ] Database password set strong
- [ ] Discord token valid & not shared
- [ ] CORS configured for your domain
- [ ] HTTPS enabled in production
- [ ] Firewall blocks non-essential ports

---

## 📈 Performance Tips

1. **Database**: Check indexes
   ```sql
   SHOW INDEX FROM vai_tickets;
   ```

2. **API**: Enable compression
   ```python
   from fastapi.middleware.gzip import GZIPMiddleware
   app.add_middleware(GZIPMiddleware, minimum_size=1000)
   ```

3. **Cache**: Monitor hit rate
   ```sql
   SELECT COUNT(*) as total, SUM(hit_count) as hits FROM vai_translations_cache;
   ```

4. **Bot**: Reduce intents (bot/main.py)
   ```python
   intents.message_content = True  # Only if needed
   ```

---

## 🚢 Deployment Checklist

- [ ] `.env` configured for production
- [ ] Database backed up
- [ ] SSL certificate installed (HTTPS)
- [ ] Firewall configured (ports 80, 443, 3306)
- [ ] Monitoring enabled (logs, metrics)
- [ ] Auto-restart configured (systemd/docker)
- [ ] Database password strong
- [ ] API secret configured
- [ ] OAuth2 redirect URLs whitelisted
- [ ] Discord bot intents verified

---

## 📞 Important IDs

```
Order ID format:    VAI-YYYYMM-XXXX (e.g., VAI-202501-4823)
Plan type:          free|premium|pro
Plan limits:        See bot/config.py lines 19-36
Groq models:        llama-3.1-8b-instant (fast)
                    llama-3.1-70b-versatile (quality)
```

---

## 🔄 Common Tasks

### Add new command
1. Create method in `bot/cogs/yourfeature.py`
2. Use `@app_commands.command()` decorator
3. Add to `YourCog` class
4. Auto-loaded by `bot/main.py`

### Add new API endpoint
1. Create in `api/routes/yourmodule.py`
2. Import router in `api/main.py`
3. Mount with `app.include_router()`

### Query database
1. Use models from `bot/db/models.py`
2. Wrap in `get_db_context()` context manager
3. Never hardcode SQL (use parameterized queries)

### Deploy new version
```bash
git pull
docker-compose down
docker-compose build
docker-compose up -d
docker-compose logs -f
```

---

## 📖 Documentation Files

| File | Content |
|------|---------|
| `README.md` | Installation, features, commands |
| `STRUCTURE.md` | Architecture, components, design |
| `DEPLOYMENT.md` | Setup guides, deployment options |
| `PROJECT_SUMMARY.txt` | Complete project status |
| `QUICK_REFERENCE.md` | This file! |

---

## ⚙️ System Requirements

- **CPU**: 1+ cores (2 recommended)
- **Memory**: 512MB+ (1GB+ recommended)
- **Disk**: 1GB+ for data
- **Network**: 10Mbps+ stable connection
- **OS**: Ubuntu 20.04+, Debian 11+, or Windows Server
- **DB**: MySQL 8.0+ (or MariaDB 10.5+)

---

## 🎯 Success Indicators

Bot working:
```
✓ Bot shows online in Discord
✓ Slash commands appear
✓ /ticket creates channel
✓ Messages get translated
```

API working:
```
✓ http://localhost:8000/internal/health returns 200
✓ http://localhost:8000/docs shows Swagger UI
✓ Webhooks are received
```

Database working:
```
✓ mysql -u root -p -e "USE veridianai; SHOW TABLES;" works
✓ All 10 vai_* tables exist
✓ Schema has no errors
```

---

**Version**: 2.0.0  
**Last Updated**: February 2025  
**Status**: ✅ Production Ready


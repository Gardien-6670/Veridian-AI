# 🚀 Deployment Guide - Veridian AI

## Quick Start (Local Development)

### Prerequisites
- Python 3.11+
- MySQL 8.0+
- Git
- Discord Bot Token

### Step 1: Clone & Setup
```bash
cd "bot ia"
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment
```bash
cp .env.example .env
```

**Edit `.env` with your values:**
```env
DISCORD_TOKEN=your_token_here
GROQ_API_KEY=your_groq_key_here
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_db_password
# ... other settings
```

### Step 4: Setup Database
```bash
# Option 1: Using MySQL command line
mysql -u root -p < database/schema.sql

# Option 2: Using MySQL client
mysql -u root -p
> source database/schema.sql;
```

### Step 5: Run Bot
```bash
python bot/main.py
```

### Step 6: Run API (separate terminal)
```bash
cd api
uvicorn main:app --reload --port 8000
```

Both should show:
- Bot: `✓ Bot logged in`
- API: `Uvicorn running on http://127.0.0.1:8000`

---

## Docker Deployment (Production)

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+

### Step 1: Prepare Environment
```bash
cd "bot ia"
cp .env.example .env
# Edit .env with production values
```

### Step 2: Build & Start
```bash
docker-compose up -d
```

### Step 3: Verify Services
```bash
docker-compose ps

# Should show:
# veridian-mysql   Running (healthy)
# veridian-bot     Running
# veridian-api     Running
# veridian-nginx   Running (if enabled)
```

### Step 4: Check Logs
```bash
# Bot logs
docker-compose logs -f bot

# API logs
docker-compose logs -f api

# Database logs
docker-compose logs -f mysql
```

### Step 5: Scaling (Optional)
```bash
# Increase replicas
docker-compose up -d --scale api=3

# Stop all
docker-compose down
```

---

## VPS Deployment (Ubuntu 22.04)

### 1. Server Setup
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

### 2. Clone Repository
```bash
cd /home/ubuntu
git clone <your_repo_url> veridian-bot
cd veridian-bot
```

### 3. Configure & Deploy
```bash
# Setup environment
cp .env.example .env
nano .env  # Edit with your API keys and settings

# Start services
docker-compose up -d

# Create backup of database
docker exec veridian-mysql mysqldump -u root -p$DB_PASSWORD veridianai > backup.sql
```

### 4. Setup Reverse Proxy (Nginx)
```bash
# Install Nginx
sudo apt install -y nginx certbot python3-certbot-nginx

# Create config
sudo nano /etc/nginx/sites-available/veridian

# Content:
server {
    listen 80;
    server_name api.veridiancloud.xyz;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Enable site
sudo ln -s /etc/nginx/sites-available/veridian /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# Enable HTTPS (Let's Encrypt)
sudo certbot --nginx -d api.veridiancloud.xyz
```

### 5. Setup Monitoring
```bash
# Install htop to monitor resources
sudo apt install -y htop

# Monitor containers
watch -n 1 docker stats

# View application logs
docker-compose logs -f --tail=100
```

---

## AWS Deployment (ECS + RDS)

### 1. Create RDS MySQL Instance
```bash
# AWS Console → RDS → Create Database
# Engine: MySQL 8.0
# Instance: db.t3.micro
# Storage: 20GB
# No public access (private subnet)
```

### 2. Create ECS Cluster
```bash
# AWS Console → ECS → Create Cluster
# Cluster name: veridian-cluster
# Infrastructure: EC2
# Instance type: t3.medium
```

### 3. Create Task Definition
```bash
# Register task definition with:
# - bot: Python 3.11 image
# - api: Python 3.11 image
# Environment variables from Parameter Store
# Mount logs to CloudWatch
```

### 4. Deploy Services
```bash
# ECS Service for bot
# Service: veridian-bot
# Task definition: veridian-bot:latest
# Desired count: 1
# Log group: /ecs/veridian

# ECS Service for API
# Service: veridian-api
# Task definition: veridian-api:latest
# Desired count: 2 (auto-scaling)
# Load balancer: Application Load Balancer
# Log group: /ecs/api
```

---

## Database Management

### Backup Database
```bash
# Local
mysqldump -u root -p veridianai > backup.sql

# Docker
docker exec veridian-mysql mysqldump -u root -p$DB_PASSWORD veridianai > backup.sql

# Automated (daily at 2am)
0 2 * * * /home/ubuntu/backup.sh
```

### Restore Database
```bash
# From backup
mysql -u root -p veridianai < backup.sql

# Docker
docker exec -i veridian-mysql mysql -u root -p$DB_PASSWORD veridianai < backup.sql
```

### Monitor Database
```bash
# Connect to MySQL
docker exec -it veridian-mysql mysql -u root -p$DB_PASSWORD veridianai

# Check active connections
SHOW PROCESSLIST;

# Check table sizes
SELECT TABLE_NAME, ROUND(((data_length + index_length) / 1024 / 1024), 2) AS size_mb
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'veridianai'
ORDER BY (data_length + index_length) DESC;
```

---

## Troubleshooting

### Bot won't connect
```bash
# Check token
echo $DISCORD_TOKEN

# Verify bot has required intents in Discord Developer Portal:
# - Message Content Intent
# - Server Members Intent

# Check logs
docker-compose logs bot | tail -50
```

### API not responding
```bash
# Check if running
docker-compose ps api

# Check port 8000
curl http://localhost:8000/internal/health

# Restart API
docker-compose restart api
```

### Database connection failed
```bash
# Check MySQL is running
docker-compose ps mysql

# Check credentials in .env
grep DB_ .env

# Connect to MySQL
mysql -h localhost -u $DB_USER -p $DB_NAME

# Check tables exist
USE veridianai;
SHOW TABLES;
```

### Out of memory
```bash
# Check resource usage
docker stats

# Increase memory limits in docker-compose.yml
# services:
#   mysql:
#     mem_limit: 1g

# Restart services
docker-compose down && docker-compose up -d
```

---

## Performance Optimization

### Database
```sql
-- Check slow queries
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 2;

-- Add indexes if needed
CREATE INDEX idx_guild_created ON vai_tickets(guild_id, created_at);

-- Monitor query performance
EXPLAIN SELECT * FROM vai_tickets WHERE guild_id = 123;
```

### API
```python
# In api/main.py, enable compression
from fastapi.middleware.gzip import GZIPMiddleware
app.add_middleware(GZIPMiddleware, minimum_size=1000)

# Increase worker count
gunicorn --workers 4 --worker-class uvicorn.workers.UvicornWorker api.main:app
```

### Bot
```python
# Increase intents only for needed events
# In bot/main.py
intents.message_content = True  # Only if needed
intents.members = True           # Only if needed
```

---

## Monitoring & Alerts

### CloudWatch (AWS)
```bash
# View logs
aws logs tail /ecs/veridian-bot --follow

# Create alarm
aws cloudwatch put-metric-alarm \
  --alarm-name veridian-bot-error \
  --alarm-actions arn:aws:sns:region:account:topic \
  --metric-name TaskCount \
  --threshold 0 \
  --comparison-operator LessThanOrEqualToThreshold
```

### Datadog (Optional)
```bash
# Add monitoring agent to Docker container
docker run -d --name datadog-agent \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  -v /proc/:/host/proc/:ro \
  -v /sys/fs/cgroup/:/host/sys/fs/cgroup:ro \
  -e DD_API_KEY=$DD_API_KEY \
  -e DD_SITE=datadoghq.com \
  gcr.io/datadoghq/agent:latest
```

---

## Update Process

### Update Code
```bash
# Pull latest
git pull origin main

# Update dependencies
pip install -r requirements.txt --upgrade

# Rebuild Docker images
docker-compose build --no-cache
```

### Database Migration
```bash
# For schema changes
mysql < database/migrations/001_add_new_column.sql

# Verify
docker exec veridian-mysql mysql -u root -p$DB_PASSWORD veridianai -e "DESCRIBE vai_tickets;"
```

### Rolling Update
```bash
# Update API (stateless, safe)
docker-compose up -d --no-deps --build api

# Update bot (may cause brief downtime)
docker-compose up -d --no-deps --build bot

# Verify
docker-compose logs --tail=50 -f
```

---

## Maintenance Checklist

- [ ] Weekly: Check disk space (`df -h`)
- [ ] Weekly: Review logs for errors (`docker logs -f`)
- [ ] Monthly: Update dependencies (`pip list --outdated`)
- [ ] Monthly: Backup database (`mysqldump`)
- [ ] Monthly: Check certificate expiry (`certbot certificates`)
- [ ] Quarterly: Update Docker images (`docker pull`)
- [ ] Quarterly: Review performance metrics

---

## Support & Help

- **Discord**: [Support Server](https://discord.gg/veridian)
- **Logs**: Check `logs/bot.log` and `docker-compose logs`
- **Issues**: GitHub Issues or email support@veridiancloud.xyz
- **Docs**: https://docs.veridiancloud.xyz/deployment

---

**Last Updated:** February 2025  
**Version:** 2.0.0

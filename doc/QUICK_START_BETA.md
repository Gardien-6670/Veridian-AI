# 🚀 Quick Start - Veridian AI v0.0.1-beta

## 1️⃣ Configuration initiale

### Cloner/télécharger le projet
```bash
cd "bot ia"
```

### Créer le fichier .env
```bash
cp .env.example .env
nano .env  # Éditer avec vos valeurs
```

### Paramètres essentiels
```env
# Discord
DISCORD_TOKEN=your_token_here
DISCORD_CLIENT_ID=your_id_here
BOT_OWNER_DISCORD_ID=1047760053509312642

# Groq (au moins la clé 1)
GROQ_API_KEY_1=sk_your_key_here
GROQ_API_KEY_2=sk_optional_2
GROQ_API_KEY_3=sk_optional_3
GROQ_API_KEY_4=sk_optional_4

# Base de données
DB_HOST=localhost
DB_PORT=3306
DB_USER=veridian_user
DB_PASSWORD=your_password

# API
API_DOMAIN=api.veridiancloud.xyz
ENVIRONMENT=development
```

## 2️⃣ Installation des dépendances

### Avec venv (recommandé)
```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# ou: venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Ou globally
```bash
pip3 install -r requirements.txt
```

## 3️⃣ Base de données

### MySQL doit être en cours d'exécution
```bash
# Vérifier la connexion
mysql -h localhost -u veridian_user -p -e "SELECT VERSION();"
```

### Le bot créera les tables automatiquement au démarrage ✓
- Pas besoin de lancer `mysql < database/schema.sql`
- Les tables sont vérifiées et créées si manquantes

## 4️⃣ Démarrer le bot

### Mode simple
```bash
python3 bot/main.py
```

### Mode watch (auto-reload)
```bash
pip install python-watchdog
python -m watchdog.auto_reload bot/main.py
```

### Vérifier les logs
```bash
tail -f logs/bot.log
tail -f logs/errors.log
```

## 5️⃣ Démarrer l'API (optionnel)

### Autre terminal
```bash
python3 api/main.py
```

### Ou avec Uvicorn
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Tester l'API
```bash
curl http://localhost:8000/health
# Vérifier /docs sur http://localhost:8000/docs
```

## 6️⃣ Docker (optionnel)

### Démarrer tous les services
```bash
docker-compose up -d
docker-compose logs -f bot
```

### Arrêter
```bash
docker-compose down
```

## ✅ Checklist de vérification

- [ ] DISCORD_TOKEN configuré dans .env
- [ ] GROQ_API_KEY_1 configuré
- [ ] MySQL est accessible et en cours
- [ ] Dossier `logs/` existe
- [ ] Bot démarre sans erreurs
- [ ] Commandes slash disponibles dans Discord
- [ ] API /health répond (si lancée)
- [ ] Banneau "BÊTA v0.0.1" visible sur le dashboard

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'discord'"
```bash
pip install -r requirements.txt
```

### "Cannot connect to database"
- Vérifier MySQL est en cours: `mysql -u root -e "SELECT 1"`
- Vérifier DB_HOST, DB_USER, DB_PASSWORD dans .env
- Créer l'utilisateur MySQL si nécessaire

### "DISCORD_TOKEN not defined"
- Vérifier que .env a DISCORD_TOKEN=...
- Redémarrer le bot

### "No module named 'loguru'"
```bash
pip install loguru
```

## 📚 Documentation complète
- BETA_RELEASE_NOTES.md - Changements v0.0.1-beta
- README.md - Features complètes
- DEPLOYMENT.md - Guide déploiement
- STRUCTURE.md - Architecture détaillée

---
**Version**: 0.0.1-beta | **Date**: 2025-02-23

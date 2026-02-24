# 🧪 Veridian AI v0.0.1-beta - Notes de Version

## 📋 Changements Majeurs

### Version: 0.0.1-beta (2025-02-23)

#### ✨ Nouvelles Fonctionnalités
- **Gestion 4 clés Groq API** avec fallback automatique
  - Si une clé est saturée, le bot bascule automatiquement vers la suivante
  - Configuration: `GROQ_API_KEY_1`, `GROQ_API_KEY_2`, `GROQ_API_KEY_3`, `GROQ_API_KEY_4`
  - Les clés manquantes ne causent pas d'erreur au démarrage

- **Auto-initialisation database**
  - Le bot crée automatiquement la base de données au démarrage
  - Exécute `database/init.sql` s'il n'existe pas
  - Vérifie la connexion avant de charger les cogs

- **Logging centralisé**
  - `logs/bot.log` - Logs principaux du bot
  - `logs/api.log` - Logs de l'API
  - `logs/errors.log` - Erreurs uniquement
  - Rotation automatique (500 MB ou 30 jours)

- **Banneau bêta sur le site web**
  - Banneau jaune en haut du dashboard
  - Affiche "VERSION BÊTA 0.0.1"
  - Badge BETA dans le titre du bot

- **Endpoint /health pour l'API**
  - GET `/health` retourne infos système
  - Version, statut DB, environnement, timestamp

- **Configuration API par domaine**
  - Variable `API_DOMAIN` pour `api.veridiancloud.xyz`
  - Configuration d'environnement (dev/staging/production)

#### 🔧 Améliorations Techniques
- Statut du bot Discord affiche `🧪 v0.0.1-beta`
- Version globale: `VERSION = "0.0.1-beta"` dans `bot/config.py`
- Logging amélioré avec format structuré: timestamp, level, message
- Gestion d'erreurs Groq avec retry automatique
- Message d'erreur Groq plus informatif (n°clé, raison)

#### 🚀 Déploiement
- Docker-compose compatible avec v0.0.1-beta
- `.env.example` mis à jour avec 4 clés Groq
- Configuration API séparable (localhost vs api.veridiancloud.xyz)

## 📝 Configuration Requise

### .env - Nouvelles variables
```bash
GROQ_API_KEY_1=sk_...    # Clé 1 (obligatoire minimum)
GROQ_API_KEY_2=sk_...    # Clé 2 (optionnel)
GROQ_API_KEY_3=sk_...    # Clé 3 (optionnel)
GROQ_API_KEY_4=sk_...    # Clé 4 (optionnel)

API_DOMAIN=api.veridiancloud.xyz  # Domaine API
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=development  # ou production
```

## 🧪 Tester la Bêta

### Démarrage manuel
```bash
pip install -r requirements.txt
python3 bot/main.py
```

### Docker
```bash
docker-compose up -d
docker-compose logs -f bot
```

### Vérifier la DB
```bash
mysql -u root -p veridianai -e "SHOW TABLES LIKE 'vai_%';"
```

### Tester l'API
```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs
```

## ⚠️ Limitations Bêta
- Version de test, peuvent avoir des bugs
- Signaler tout problème sur Discord
- Pas recommandé pour production (attendez v0.1.0)

## 🐛 Bugs Connus
Aucun pour le moment.

## 📚 Documentation
- Voir DEPLOYMENT.md pour instructions complètes
- Voir README.md pour les features
- Voir STRUCTURE.md pour l'architecture

---
Release: 2025-02-23 | Version: 0.0.1-beta

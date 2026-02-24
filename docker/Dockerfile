FROM python:3.11-slim

WORKDIR /app

# Installer dépendances système
RUN apt-get update && apt-get install -y \
    gcc \
    mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Copier et installer dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code
COPY bot ./bot
COPY .env .

# Créer répertoires de logs
RUN mkdir -p logs

# Lancer le bot
CMD ["python", "bot/main.py"]

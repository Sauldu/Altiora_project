FROM python:3.11-slim
LABEL maintainer="Test Automation Team"
LABEL description="Orchestrateur principal pour automatisation de tests IA"

WORKDIR /app

# Installer les dépendances système
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copier les requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code source
COPY src/ /app/src/
COPY configs/ /app/configs/

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Port par défaut (API REST si ajoutée)
EXPOSE 8000

# Commande par défaut
CMD ["python", "-m", "src.test_automation_orchestrator"]

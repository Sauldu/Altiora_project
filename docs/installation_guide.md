# Guide d'Installation Complet pour Altiora

Ce guide vous accompagnera à travers les étapes nécessaires pour installer et configurer Altiora, un assistant IA personnel intelligent capable d'automatiser des tâches complexes de génie logiciel.

## Prérequis

Assurez-vous d'avoir les éléments suivants installés sur votre système :

- **Python 3.11+** : Le langage de programmation principal du projet.
- **pip** : Le gestionnaire de paquets Python (normalement inclus avec Python).
- **Git** : Pour cloner le dépôt du projet.
- **Docker Desktop** (ou Docker Engine et Docker Compose) : Pour exécuter les microservices conteneurisés.

## Étapes d'Installation

### 1. Cloner le Dépôt

Ouvrez votre terminal ou invite de commande et exécutez la commande suivante pour cloner le dépôt du projet :

```bash
git clone https://github.com/votre_utilisateur/Altiora_project.git # Remplacez par l'URL réelle de votre dépôt
cd Altiora_project
```

### 2. Configuration de l'Environnement

Le projet utilise un fichier `.env` pour gérer les variables d'environnement. Un exemple est fourni :

1. Copiez le fichier `.env.example` vers `.env` :

```bash
cp .env.example .env
# Sur Windows, vous pouvez utiliser :
# copy .env.example .env
```

2. **Éditez le fichier `.env`** : Ouvrez le fichier `.env` avec un éditeur de texte et ajustez les valeurs selon votre environnement. Les variables importantes incluent :

    - `OLLAMA_HOST` : L'URL de votre instance Ollama (par défaut `http://localhost:11434`).
    - `ALM_API_URL`, `ALM_API_KEY` : Pour l'intégration avec votre système ALM (si utilisé).
    - `REDIS_URL` : L'URL de votre instance Redis (par défaut `redis://localhost:6379`).
    - `JWT_SECRET_KEY` : La clé secrète pour l'authentification JWT. **Il est crucial de définir une clé secrète forte ici.**

### 3. Création de l'Environnement Virtuel et Installation des Dépendances Python

Il est fortement recommandé d'utiliser un environnement virtuel pour isoler les dépendances du projet.

1. Créez l'environnement virtuel :

```bash
python -m venv .venv
```

2. Activez l'environnement virtuel :

    - **Sur macOS/Linux** :

    ```bash
source .venv/bin/activate
```

    - **Sur Windows (Command Prompt)** :

    ```bash
.venv\Scripts\activate.bat
```

    - **Sur Windows (PowerShell)** :

    ```powershell
.venv\Scripts\Activate.ps1
```

3. Installez les dépendances Python :

```bash
pip install -r requirements.txt
```

4. Installez les navigateurs Playwright (nécessaire pour l'exécution des tests) :

```bash
playwright install
```

### 4. Lancement des Services

Altiora s'appuie sur Ollama pour les modèles d'IA et d'autres microservices conteneurisés via Docker Compose.

1. **Lancez Ollama** :

Assurez-vous que le serveur Ollama est en cours d'exécution. Vous pouvez le lancer via :

```bash
ollama serve
```

Si vous n'avez pas Ollama installé, suivez les instructions sur [ollama.ai](https://ollama.ai/download).

2. **Démarrez les microservices Docker Compose** :

Dans le répertoire racine du projet, exécutez :

```bash
docker-compose up -d
```

Cette commande va construire (si nécessaire) et démarrer les conteneurs pour les services Redis, OCR, ALM, Excel, Playwright, Auth et Dash.

### 5. Vérification de l'Installation

Vous pouvez vérifier que les services sont en cours d'exécution en accédant à leurs points de terminaison de santé (si disponibles) ou en exécutant les tests :

```bash
# Exemple de vérification de santé (si les services sont exposés sur localhost)
curl http://localhost:8001/health # Service OCR
curl http://localhost:8002/health # Service ALM
curl http://localhost:8003/health # Service Excel
curl http://localhost:8005/health # Service Auth

# Accéder à la documentation API (Swagger UI)
# Pour le service ALM: http://localhost:8002/docs
# Pour le service Excel: http://localhost:8003/docs
# Pour le service Auth: http://localhost:8005/docs

# Accéder au Dashboard
# http://localhost:8050

# Exécuter les tests du projet
pytest
```

### 6. Utilisation de Base

Une fois tous les services en cours d'exécution, vous pouvez interagir avec l'orchestrateur via le CLI. Voir le `README.md` pour plus de détails sur les commandes disponibles.

### 7. Troubleshooting

- **Problèmes de port** : Si un service Docker ne démarre pas, vérifiez que les ports (ex: 8001, 8002, 8003, 8004, 8005, 8050, 11434, 6379) ne sont pas déjà utilisés par d'autres applications sur votre système.
- **Ollama** : Assurez-vous que les modèles `qwen3-sfd-analyzer` et `starcoder2-playwright` sont bien téléchargés et disponibles dans Ollama. Vous pouvez les télécharger manuellement si nécessaire (`ollama pull qwen3-sfd-analyzer`, `ollama pull starcoder2-playwright`).
- **Dépendances Python** : Si vous rencontrez des erreurs d'importation, assurez-vous que votre environnement virtuel est activé et que toutes les dépendances de `requirements.txt` sont installées.
- **Base de données d'authentification**: Le service d'authentification utilise une base de données SQLite qui sera créée dans un volume Docker. Si vous avez besoin de la réinitialiser, vous pouvez supprimer le volume avec `docker volume rm altiora_auth_db`.

### 8. Conclusion

Vous avez maintenant installé et configuré Altiora sur votre machine locale. Vous pouvez commencer à utiliser l'assistant pour automatiser des tâches complexes de génie logiciel. Pour plus d'informations, consultez la [documentation officielle](https://github.com/votre_utilisateur/Altiora_project/docs) du projet.
# Projet Altiora

Assistant IA personnel avec architecture microservices.
+ Gestion complète du cycle de vie des tests logiciels.

## Installation

1. Cloner le repository
2. Copier `.env.example` vers `.env`
3. Installer les dépendances : `pip install -r requirements.txt`
4. Lancer Ollama : `ollama serve`
5. Démarrer les services : `docker-compose up -d`

## Architecture

```
Altiora_project/
|-- .env.example                                             # Fichier d'exemple pour les variables d'environnement
|-- .gitignore                                               # Fichiers et dossiers à ignorer par Git
|-- CHANGELOG.md                                             # Journal des modifications du projet
|-- docker_compose.yml                                       # Définition des services pour Docker Compose
|-- docker-compose-validation.sh                             # Script de validation pour docker-compose
|-- Dockerfile                                               # Instructions pour construire l'image Docker principale
|-- export.py                                                # Script pour exporter des données ou modèles
|-- pytest.ini                                               # Fichier de configuration pour Pytest
|-- README.md                                                # Fichier d'information principal du projet
|-- requirements.txt                                         # Liste des dépendances Python du projet
|-- setup-script.py                                          # Script d'installation et de configuration
|-- structure.txt                                            # Description de la structure du projet (ce fichier)
|
|-- .github/                                                 # 📁 Configuration pour GitHub
|   \---workflows/                                            # 📁 Workflows d'intégration continue (CI/CD)
|       \---ci-cd.yml                                        # Workflow pour le déploiement et les tests automatisés
|
|-- cli/                                                     # 📁 Interface en ligne de commande
|   |-- __init__.py                                          # Initialiseur du package cli
|   |-- main.py                                              # Point d'entrée de l'application CLI
|   \---commands/                                            # 📁 Commandes CLI spécifiques
|
|-- configs/                                                 # 📁 Fichiers de configuration centralisés
|   |-- __init__.py                                          # Initialiseur du package configs
|   |-- config_module.py                                     # Module de configuration Pydantic pour les paramètres
|   |-- emergency_webhooks.yaml                              # Webhooks pour les alertes d'urgence
|   |-- env-example-complete.yaml                            # Exemple complet de fichier d'environnement
|   |-- error_handling.yaml                                  # Configuration pour la gestion des erreurs
|   |-- master_config.yaml                                   # Fichier de configuration principal
|   |-- models_config.yaml                                   # Configuration des modèles de langue
|   |-- models.yaml                                          # Définition des modèles utilisés
|   |-- ollama_config.json                                   # Paramètres de configuration pour Ollama
|   |-- ollama_optimized.yaml                                # Configuration optimisée pour Ollama
|   |-- prometheus.yml                                       # Configuration pour la surveillance avec Prometheus
|   |-- retry_config.yaml                                    # Stratégies de nouvelle tentative pour les opérations réseau
|   |-- roles.yaml                                           # Définition des rôles et permissions (RBAC)
|   |-- services.yaml                                        # Configuration des micro-services
|   |-- settings_legacy.py                                   # Anciens paramètres de configuration (legacy)
|   |-- settings_loader.py                                   # Chargeur de configuration
|   |-- training_config.json                                 # Configuration pour l'entraînement des modèles
|   \---validator.py                                        # Script de validation pour la configuration
|
|-- data/                                                    # 📁 Données utilisées par l'application
|   |-- models/                                              # 📁 Modèles de machine learning sauvegardés
|   |-- scenarios/                                           # 📁 Scénarios de test ou d'utilisation
|   |-- temp/                                                # 📁 Fichiers de données temporaires
|   \---training/                                            # 📁 Données pour l'entraînement des modèles
|
|-- docker/                                                  # 📁 Fichiers de configuration spécifiques à Docker
|
|-- docs/                                                    # 📁 Documentation du projet
|   |-- ARCHITECTURE.md                                      # Description de l'architecture globale
|   |-- env-documentation.md                                 # Documentation des variables d'environnement
|   |-- generate_docs.py                                     # Script pour générer la documentation
|   |-- installation_guide.md                                # Guide d'installation
|   \---examples/                                            # 📁 Exemples d'utilisation
|
|-- guardrails/                                              # 🔒 Modules de sécurité et de contrôle
|   |-- __init__.py                                          # Initialiseur du package guardrails
|   |-- admin_control_system.py                              # Système de contrôle pour les administrateurs
|   |-- admin_dashboard.py                                   # Interface pour le tableau de bord administrateur
|   |-- emergency_handler.py                                 # Gestionnaire des situations d'urgence
|   |-- ethical_safeguards.py                                # Garde-fous éthiques pour l'IA
|   |-- interaction_guardrail.py                             # Filtres pour les interactions utilisateur
|   |-- policy_enforcer.py                                   # Application des politiques de sécurité
|   \---toxicity_guardrail.py                                # Détection de contenu toxique
|
|-- logs/                                                    # 📁 Fichiers de logs de l'application
|
|-- models/                                                  # 📁 Modèles de données ou schémas (non-ML)
|
|-- policies/                                                # 📋 Règles métier et politiques
|   |-- __init__.py                                          # Initialiseur du package policies
|   |-- business_rules.py                                    # Implémentation des règles métier
|   |-- excel_policy.py                                      # Politiques spécifiques au traitement Excel
|   |-- privacy_policy.py                                    # Politiques de confidentialité des données
|   \---toxicity_policy.py                                   # Politiques relatives à la toxicité du contenu
|
|-- post_processing/                                         # 🧹 Nettoyage et formatage des sorties
|   |-- __init__.py                                          # Initialiseur du package post_processing
|   |-- code_validator.py                                    # Validation et linting du code généré
|   |-- excel_formatter.py                                   # Formatage des fichiers Excel
|   \---output_sanitizer.py                                  # Nettoyage des sorties (ex: masquage de PII)
|
|-- scripts/                                                 # 🛠️ Scripts utilitaires pour le développement
|   |-- audit_query.py                                       # Script pour interroger les logs d'audit
|   |-- backup_redis.sh                                      # Script de sauvegarde de la base de données Redis
|   |-- cpu_optimization_script.py                           # Script pour optimiser l'utilisation du CPU
|   |-- create_ephemeral_env.sh                              # Script pour créer un environnement éphémère
|   |-- diagnose_ollama.py                                   # Outil de diagnostic pour Ollama
|   |-- docker-compose.ephemeral.yml                         # Configuration Docker Compose pour l'environnement éphémère
|   |-- generate_keys.py                                     # Génération de clés de chiffrement/API
|   |-- generate_performance_report.py                       # Génération de rapports de performance
|   |-- qwen3_modelfile                                      # Définition du modèle Qwen3 pour Ollama
|   |-- run_performance_tests.sh                             # Lanceur pour les tests de performance
|   |-- setup_integration_tests.sh                           # Script de configuration des tests d'intégration
|   |-- starcoder2_modelfile                                 # Définition du modèle Starcoder2 pour Ollama
|   |-- start_dev.sh                                         # Script pour démarrer l'environnement de développement
|   \---validate_setup.py                                    # Validation de la configuration de l'environnement
|
|-- services/                                                # 📦 Micro-services conteneurisés
|   |-- alm/                                                 # 📁 Service ALM (Application Lifecycle Management)
|   |-- dash/                                                # 📁 Service pour le dashboard
|   |-- excel/                                               # 📁 Service de traitement Excel
|   |-- ocr/                                                 # 📁 Service OCR (Reconnaissance Optique de Caractères)
|   \---playwright/                                          # 📁 Service d'automatisation avec Playwright
|
|-- src/                                                     # 🎯 Cœur de l'application et de l'orchestrateur
|   |-- __init__.py                                          # Initialiseur du package src
|   |-- App.js                                               # Fichier principal pour l'interface React
|   |-- batch_processor.py                                   # Traitement des tâches en lots
|   |-- config.py                                            # Configuration principale de l'application
|   |-- error_management.py                                  # Module central de gestion des erreurs
|   |-- main.py                                              # Point d'entrée principal de l'application
|   |-- models.py                                            # Modèles de données (Pydantic/SQLAlchemy)
|   |-- orchestrator.py                                      # Orchestre le pipeline des tâches
|   |-- api/                                                 # 📁 API de l'application
|   |-- audit/                                               # 📁 Journalisation et audit
|   |-- auth/                                                # 📁 Authentification et autorisation
|   |-- cache/                                               # 📁 Gestion du cache
|   |-- components/                                          # 📁 Composants d'interface (React)
|   |-- config/                                              # 📁 Configuration spécifique au code source
|   |-- core/                                                # 📁 Logique métier principale
|   |-- dashboard/                                           # 📁 Code du dashboard
|   |-- docs/                                                # 📁 Documentation spécifique au code source
|   |-- ensemble/                                            # 📁 Techniques d'ensemble de modèles
|   |-- events/                                              # 📁 Gestion des événements
|   |-- factories/                                           # 📁 Fabriques de modèles et services
|   |-- gateway/                                             # 📁 Passerelle API
|   |-- infrastructure/                                      # 📁 Connexion aux services externes
|   |-- learning/                                            # 📁 Apprentissage et entraînement
|   |-- metrics/                                             # 📁 Métriques de performance
|   |-- middleware/                                          # 📁 Middlewares pour le traitement des requêtes
|   |-- models/                                              # 📁 Interfaces avec les modèles de langue
|   |-- modules/                                             # 📁 Modules fonctionnels
|   |-- monitoring/                                          # 📁 Surveillance et métriques
|   |-- optimization/                                        # 📁 Optimisation des performances
|   |-- playwright/                                          # 📁 Intégration avec Playwright
|   |-- plugins/                                             # 📁 Système de plugins
|   |-- qa_system/                                           # 📁 Système de questions-réponses
|   |-- rbac/                                                # 📁 Logique RBAC (Role-Based Access Control)
|   |-- redux/                                               # 📁 Gestion d'état Redux pour le frontend
|   |-- repositories/                                        # 📁 Accès aux données (ORM/Repositories)
|   |-- scaling/                                             # 📁 Mise à l'échelle de l'application
|   |-- security/                                            # 🔐 Sécurité et chiffrement
|   |-- training/                                            # 📁 Entraînement des modèles
|   |-- utils/                                               # 📁 Utilitaires divers
|   \---validation/                                          # 📁 Validation des données
|
|-- temp/                                                    # 📁 Fichiers et dossiers temporaires
|
\---tests/                                                   # 🧪 Suite de tests du projet
    |-- __init__.py                                          # Initialiseur du package tests
    |-- conftest.py                                          # Fixtures et configuration pour Pytest
    |-- test_admin_control.py                                # Tests pour le système de contrôle admin
    |-- test_altiora_core.py                                 # Tests pour le noyau de la personnalité
    |-- test_ethical_safeguards.py                           # Tests pour les garde-fous éthiques
    |-- test_fine_tuning.py                                  # Tests pour le processus de fine-tuning
    |-- test_integration.py                                  # Tests d'intégration généraux
    |-- test_interfaces.py                                   # Tests pour les interfaces des modèles
    |-- test_ocr_wrapper.py                                  # Tests pour le wrapper OCR
    |-- test_orchestrator.py                                 # Tests pour l'orchestrateur principal
    |-- test_personality_quiz.py                             # Tests pour le quiz de personnalité
    |-- test_playwright_runner.py                            # Tests pour l'exécuteur Playwright
    |-- test_retry_handler.py                                # Tests pour le gestionnaire de tentatives
    |-- test_services.py                                     # Tests pour les micro-services
    |-- integration/                                         # 📁 Tests d'intégration
    |-- performance/                                         # 📁 Tests de performance et de charge
    \---regression/                                          # 📁 Tests de régression
```

## Utilisation

### Interface en Ligne de Commande (CLI)

Le projet inclut une interface en ligne de commande pour interagir avec l'assistant.

**Commandes disponibles :**

- `python -m cli.main --help` : Affiche l'aide et la liste des commandes.
- `python -m cli.main analyze-sfd <path_to_sfd>` : Lance l'analyse d'un fichier de spécifications fonctionnelles.
- `python -m cli.main generate-tests <path_to_scenarios>` : Génère des tests à partir d'un fichier de scénarios.
- `python -m cli.main run-tests <path_to_tests>` : Exécute une suite de tests Playwright.
- `python -m cli.main full-pipeline <path_to_sfd>` : Exécute le pipeline complet : analyse SFD, génération et exécution des tests.

### Lancer les Tests

Pour exécuter la suite de tests du projet, utilisez `pytest` :

```bash
pytest
```

## Monitoring

- **Prometheus** : `http://localhost:9090`
- **Dash Dashboard** : `http://localhost:8050`

## Contribuer

Les contributions sont les bienvenues ! Veuillez suivre les étapes suivantes :

1. Fork le projet.
2. Créez une nouvelle branche (`git checkout -b feature/nouvelle-fonctionnalite`).
3. Faites vos modifications.
4. Assurez-vous que les tests passent (`pytest`).
5. Committez vos changements (`git commit -am 'Ajout de la fonctionnalité X'`).
6. Pushez vers la branche (`git push origin feature/nouvelle-fonctionnalite`).
7. Créez une nouvelle Pull Request.

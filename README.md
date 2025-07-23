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
|-- pyproject.toml                                           # Fichier de configuration du projet et de build
|-- requirements.txt                                         # Liste des dépendances Python du projet
|-- docker-compose.yml                                       # Définition des services pour Docker Compose
|-- Dockerfile                                               # Instructions pour construire l'image Docker principale
|
|-- cli/                                                     # 📁 Interface en ligne de commande
|   |-- main.py                                              # Point d'entrée de l'application CLI
|   |-- __init__.py                                          # Initialiseur du package cli
|   \---commands/                                          # 📁 Commandes CLI spécifiques
|       |-- __init__.py                                      # Initialiseur du package commands
|
|-- configs/                                                 # 📁 Fichiers de configuration centralisés
|   |-- config_module.py                                     # Module de configuration Pydantic pour les paramètres
|   |-- error_handling.yaml                                  # Configuration pour la gestion des erreurs
|   |-- models_config.yaml                                   # Configuration des modèles de langue
|   |-- models.yaml                                          # Définition des modèles utilisés
|   |-- ollama_config.json                                   # Paramètres de configuration pour Ollama
|   |-- retry_config.yaml                                    # Stratégies de nouvelle tentative pour les opérations réseau
|   |-- roles.json                                           # Définition des rôles et permissions (RBAC)
|   |-- services.yaml                                        # Configuration des micro-services
|
|-- docs/                                                    # 📁 Documentation du projet
|   |-- Architecture Assistant IA Personnel_Spcifications.md # Spécifications de l'assistant IA
|   |-- ARCHITECTURE.md                                      # Description de l'architecture globale
|   |-- env-documentation.md                                 # Documentation des variables d'environnement
|   |-- installation_guide.md                                # Guide d'installation
|   \---examples/                                          # 📁 Exemples d'utilisation
|       |-- login_test.py                                    # Exemple de script de test Playwright
|       |-- minimal_sfd.txt                                  # Exemple de document de spécification fonctionnelle
|
|-- guardrails/                                              # 🔒 Modules de sécurité et de contrôle
|   |-- __init__.py                                          # Initialiseur du package guardrails
|   |-- admin_control_system.py                              # Système de contrôle pour les administrateurs
|   |-- admin_dashboard.py                                   # Interface pour le tableau de bord administrateur
|   |-- emergency_handler.py                                 # Gestionnaire des situations d'urgence
|   |-- ethical_safeguards.py                                # Garde-fous éthiques pour l'IA
|   |-- interaction_guardrail.py                             # Filtres pour les interactions utilisateur
|   |-- policy_enforcer.py                                   # Application des politiques de sécurité
|   |-- toxicity_guardrail.py                                # Détection de contenu toxique
|
|-- policies/                                                # 📋 Règles métier et politiques
|   |-- __init__.py                                          # Initialiseur du package policies
|   |-- business_rules.py                                    # Implémentation des règles métier
|   |-- excel_policy.py                                      # Politiques spécifiques au traitement Excel
|   |-- privacy_policy.py                                    # Politiques de confidentialité des données
|   |-- toxicity_policy.py                                   # Politiques relatives à la toxicité du contenu
|
|-- post_processing/                                         # 🧹 Nettoyage et formatage des sorties
|   |-- __init__.py                                          # Initialiseur du package post_processing
|   |-- code_validator.py                                    # Validation et linting du code généré
|   |-- excel_formatter.py                                   # Formatage des fichiers Excel
|   |-- output_sanitizer.py                                  # Nettoyage des sorties (ex: masquage de PII)
|
|-- psychodesign/                                            # 🧠 Gestion de la personnalité de l'IA
|   |-- __init__.py                                          # Initialiseur du package psychodesign
|   |-- altiora_core.py                                      # Noyau de la personnalité de l'IA
|   |-- personality_evolution.py                             # Mécanisme d'évolution de la personnalité
|   |-- personality_quiz.py                                  # Quiz pour définir la personnalité initiale
|
|-- scripts/                                                 # 🛠️ Scripts utilitaires pour le développement
|   |-- audit_query.py                                       # Script pour interroger les logs d'audit
|   |-- backup_redis.sh                                      # Script de sauvegarde de la base de données Redis
|   |-- cpu_optimization_script.py                           # Script pour optimiser l'utilisation du CPU
|   |-- diagnose_ollama.py                                   # Outil de diagnostic pour Ollama
|   |-- generate_keys.py                                     # Génération de clés de chiffrement/API
|   |-- generate_performance_report.py                       # Génération de rapports de performance
|   |-- qwen3_modelfile                                      # Définition du modèle Qwen3 pour Ollama
|   |-- run_performance_tests.sh                             # Lanceur pour les tests de performance
|   |-- setup_integration_tests.sh                           # Script de configuration des tests d'intégration
|   |-- starcoder2_modelfile                                 # Définition du modèle Starcoder2 pour Ollama
|   |-- start_dev.sh                                         # Script pour démarrer l'environnement de développement
|   |-- validate_setup.py                                    # Validation de la configuration de l'environnement
|
|-- services/                                                # 📦 Micro-services conteneurisés
|   |-- alm/                                                 # 📁 Service ALM (Application Lifecycle Management)
|   |   |-- alm_service.py                                   # Logique du service ALM
|   |   |-- Dockerfile.bak                                   # Backup du Dockerfile pour le service
|   |   |-- requirements.txt                                 # Dépendances Python du service
|   |   |-- __init__.py                                      # Initialiseur du package
|   |-- excel/                                               # 📁 Service de traitement Excel
|   |   |-- Dockerfile.bak                                   # Backup du Dockerfile pour le service
|   |   |-- excel_service.py                                 # Logique du service Excel
|   |   |-- requirements.txt                                 # Dépendances Python du service
|   |   |-- __init__.py                                      # Initialiseur du package
|   |-- ocr/                                                 # 📁 Service OCR (Reconnaissance Optique de Caractères)
|   |   |-- Dockerfile.bak                                   # Backup du Dockerfile pour le service
|   |   |-- ocr_wrapper.py                                   # Wrapper pour le service OCR
|   |   |-- __init__.py                                      # Initialiseur du package
|   \---playwright/                                        # 📁 Service d'automatisation avec Playwright
|       |-- Dockerfile.bak                                   # Backup du Dockerfile pour le service
|       |-- playwright_runner.py                             # Exécuteur de tests Playwright
|       |-- requirements.txt                                 # Dépendances Python du service
|       |-- __init__.py                                      # Initialiseur du package
|
|-- src/                                                     # 🎯 Cœur de l'application et de l'orchestrateur
|   |-- App.js                                               # Fichier principal pour l'interface React (si applicable)
|   |-- batch_processor.py                                   # Traitement des tâches en lots
|   |-- config.py                                            # Configuration principale de l'application
|   |-- error_management.py                                  # Module central de gestion des erreurs
|   |-- main.py                                              # Point d'entrée principal de l'application
|   |-- models.py                                            # Modèles de données (Pydantic/SQLAlchemy)
|   |-- orchestrator.py                                      # Orchestre le pipeline des tâches
|   |-- __init__.py                                          # Initialiseur du package src
|   |-- audit/                                               # 📁 Journalisation et audit
|   |   |-- decorator.py                                     # Décorateurs pour l'audit
|   |   |-- models.py                                        # Modèles de données pour les logs d'audit
|   |   |-- ring_buffer.py                                   # Buffer circulaire pour les logs en mémoire
|   |   |-- rotation.py                                      # Logique de rotation des fichiers de log
|   |   |-- writer.py                                        # Écriture des logs sur disque/réseau
|   |-- auth/                                                # 📁 Authentification et autorisation
|   |   |-- auth_integration.py                              # Intégration avec des fournisseurs d'identité
|   |   |-- Dockerfile                                       # Dockerfile pour le service d'authentification
|   |   |-- jwt_handler.py                                   # Gestion des tokens JWT
|   |   |-- main.py                                          # Point d'entrée du service d'auth
|   |   |-- middleware.py                                    # Middleware d'authentification pour les requêtes
|   |   |-- models.py                                        # Modèles de données pour les utilisateurs/rôles
|   |   |-- password_utils.py                                # Utilitaires pour le hachage de mots de passe
|   |   |-- user_service.py                                  # Logique métier pour la gestion des utilisateurs
|   |-- components/                                          # 📁 Composants d'interface (React)
|   |   |-- Layout.js                                        # Composant de mise en page principal
|   |   |-- Reports.js                                       # Composant pour l'affichage des rapports
|   |   |-- Tests.js                                         # Composant pour l'affichage des tests
|   |-- core/                                                # 📁 Logique métier principale
|   |   |-- altiora_assistant.py                             # Classe principale de l'assistant
|   |   |-- state_manager.py                                 # Gestionnaire d'état centralisé (ex: Redis)
|   |   |-- workflow_engine.py                               # Moteur d'orchestration des workflows
|   |   |-- __init__.py                                      # Initialiseur du package
|   |-- infrastructure/                                      # 📁 Connexion aux services externes
|   |   |-- encryption.py                                    # Utilitaires de chiffrement
|   |   |-- redis_config.py                                  # Configuration de la connexion Redis
|   |   \---monitoring/                                    # 📁 Surveillance et métriques
|   |       |-- metrics.py                                   # Exposition des métriques (ex: Prometheus)
|   |-- middleware/                                          # 📁 Middlewares pour le traitement des requêtes
|   |   |-- cache_middleware.py                              # Middleware de mise en cache
|   |   |-- rbac_middleware.py                               # Middleware pour le contrôle d'accès basé sur les rôles
|   |-- models/                                              # 📁 Interfaces avec les modèles de langue
|   |   |-- qwen3/                                           # 📁 Interface pour Qwen3
|   |   |   |-- adapters.py                                  # Adaptateurs pour le fine-tuning
|   |   |   |-- fine_tuning.py                               # Scripts pour le fine-tuning
|   |   |   |-- interface.py                                 # Interface de base pour le modèle
|   |   |   |-- qwen3_interface.py                           # Implémentation spécifique pour Qwen3
|   |   \---starcoder2/                                    # 📁 Interface pour Starcoder2
|   |       |-- code_generator.py                            # Génération de code avec Starcoder2
|   |       |-- interface.py                                 # Interface de base pour le modèle
|   |       |-- starcoder2_interface.py                      # Implémentation spécifique pour Starcoder2
|   |-- rbac/                                                # 📁 Logique RBAC (Role-Based Access Control)
|   |   |-- manager.py                                       # Gestionnaire des rôles et permissions
|   |   |-- models.py                                        # Modèles de données pour les rôles/permissions
|   |-- redux/                                               # 📁 Gestion d'état Redux pour le frontend
|   |   |-- reportsSlice.js                                  # Slice pour la gestion des rapports
|   |   |-- store.js                                         # Configuration du store Redux
|   |   |-- testsSlice.js                                    # Slice pour la gestion des tests
|   \---utils/                                             # 📁 Utilitaires divers
|       |-- circuit_breaker.py                               # Implémentation du pattern Circuit Breaker
|       |-- compression.py                                   # Utilitaires de compression/décompression
|       |-- error_monitor.py                                 # Surveillance des erreurs
|       |-- memory_optimizer.py                              # Optimisation de l'utilisation mémoire
|       |-- model_loader.py                                  # Chargement des modèles de langue
|       |-- retry_handler.py                                 # Gestionnaire de nouvelles tentatives
|
\---tests/                                                  # 🧪 Suite de tests du projet
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
    |-- __init__.py                                          # Initialiseur du package tests
    |-- integration/                                         # 📁 Tests d'intégration
    |   |-- conftest.py                                      # Fixtures spécifiques à l'intégration
    |   |-- makefile                                         # Makefile pour les tests d'intégration
    |   |-- test_full_pipeline.py                            # Test du pipeline complet de bout en bout
    |   |-- test_performance.py                              # Tests de performance en intégration
    |   |-- test_services_integration.py                     # Tests d'intégration des services
    |   |-- __init__.py                                      # Initialiseur du package
    |-- performance/                                         # 📁 Tests de performance et de charge
    |   |-- config.yaml                                      # Configuration pour les tests de performance
    |   |-- test_load_testing.py                             # Tests de charge
    |   |-- test_pipeline_load.py                            # Tests de charge du pipeline
    |   |-- test_redis_performance.py                        # Tests de performance de Redis
    \---regression/                                        # 📁 Tests de régression
        |-- regression_config.yaml                           # Configuration pour les tests de régression
        |-- run_regression.py                                # Lanceur pour la suite de régression
        |-- test_regression_suite.py                         # Suite de tests de régression
        |-- __init__.py                                      # Initialiseur du package
```

## Utilisation
+ ```python
- from src.orchestrator import Orchestrator
+ from src.altiora_core import AltioraQAAssistant
+ 
+ assistant = AltioraQAAssistant()
+ # Activités multiples possibles
+ await assistant.analyze_sfd("path/to/sfd.pdf")  # Une activité parmi d'autres
+ await assistant.manage_test_suite()  # Gestion complète
+ await assistant.monitor_quality_metrics()

### Monitoring
- Prometheus : http://localhost:9090
- Dash Dashboard : http://localhost:8050
# Architecture du Projet Altiora

## 🎯 Vision Générale

Le projet Altiora vise à développer un assistant IA personnel intelligent, capable d'automatiser des tâches complexes de génie logiciel,
notamment l'analyse de spécifications fonctionnelles détaillées (SFD) et la génération de tests d'automatisation (Playwright). L'architecture est conçue pour être modulaire,
scalable et sécurisée, en s'appuyant sur des microservices et des modèles d'IA locaux.

## 🏗️ Composants Clés

L'architecture d'Altiora est articulée autour de plusieurs modules et services interconnectés :

### 1. Orchestrateur Principal (`src/orchestrator.py`)

C'est le cerveau central du système. Il coordonne l'ensemble du pipeline, de la réception d'une SFD à la génération et potentiellement à l'exécution des tests. Ses responsabilités incluent :
- La gestion du flux de travail (workflow).
- L'interaction avec les différents microservices.
- La collecte et l'agrégation des métriques de performance.
- L'intégration des règles métier et des politiques de sécurité.

### 2. Interfaces avec les Modèles d'IA (LLMs)

Altiora utilise des modèles de langage de grande taille (LLMs) pour des tâches spécifiques, interfacés via Ollama :
- **`src/models/qwen3/qwen3_interface.py` (Qwen3)** : Spécialisé dans l'analyse des SFD. Il extrait les scénarios de test, les objectifs, les préconditions, les étapes, etc. Il peut également générer des matrices de test structurées. Il intègre désormais la capacité de charger des adaptateurs de personnalité (LoRA) pour affiner son comportement.
- **`src/models/starcoder2/starcoder2_interface.py` (StarCoder2)** : Dédié à la génération de code, principalement des scripts de test Playwright, à partir des scénarios identifiés par Qwen3.

### 3. Microservices Spécialisés (`services/`)

Ces services sont des composants indépendants, souvent conteneurisés (via Docker), qui gèrent des tâches spécifiques et peuvent être appelés par l'orchestrateur :
- **Auth (`src/auth/`)**: Gère l'authentification des utilisateurs et la génération de tokens JWT. C'est un service FastAPI indépendant avec sa propre base de données SQLite.
- **OCR (`services/ocr/`)** : Extrait le texte de documents (par exemple, PDF de SFD) pour permettre leur analyse par les LLMs.
- **ALM (`services/alm/`)** : Interface avec des outils de gestion du cycle de vie des applications (Application Lifecycle Management) comme Jira ou Azure DevOps pour créer ou mettre à jour des tickets (bugs, tâches).
- **Excel (`services/excel/`)** : Gère la création et le formatage de fichiers Excel, notamment pour les matrices de test, en appliquant des règles de validation et de style.
- **Playwright (`services/playwright/`)** : Exécute les tests Playwright générés et renvoie les résultats d'exécution.
- **Dash (`services/dash/`)**: Fournit un tableau de bord interactif pour visualiser les métriques de performance et les résultats des tests.

### 4. Politiques et Garde-fous (`policies/` et `guardrails/`)

Ces modules sont cruciaux pour la sécurité, la conformité et la qualité des interactions de l'IA :
- **`policies/business_rules.py`** : Contient les règles métier strictes pour valider le code généré (par exemple, interdiction de `time.sleep()`, formatage des IDs de test, utilisation du module de rapport standard).
- **`policies/privacy_policy.py`** : Détecte et masque les informations personnelles identifiables (PII) dans le texte, gère les règles de rétention des données et le consentement, en conformité avec le RGPD.
- **`policies/toxicity_policy.py`** : Évalue le contenu pour détecter la toxicité (insultes, menaces, etc.) et les fuites de PII, avec des niveaux de gravité et des actions associées.
- **`guardrails/admin_control_system.py`** : Système centralisé pour les actions administratives (gel d'utilisateur, sauvegarde, restauration).
- **`guardrails/emergency_handler.py`** : Gère les situations d'urgence (détection de menaces graves, fuites de données) en déclenchant des actions prédéfinies (gel global, notifications).
- **`guardrails/interaction_guardrail.py`** : Un point d'entrée unique pour toutes les interactions utilisateur, appliquant les politiques de toxicité et de confidentialité en temps réel.
- **`guardrails/admin_dashboard.py`** : Une interface graphique (Tkinter) pour la supervision et le contrôle du système par les administrateateurs, affichant des métriques et permettant des actions manuelles.

### 5. Post-traitement (`post_processing/`)

Ces modules affinent les sorties de l'IA ou préparent les données pour d'autres étapes :
- **`post_processing/code_validator.py`** : Valide la syntaxe, le linting (avec Ruff) et le formatage (avec Black) du code Python généré, y compris des vérifications spécifiques à Playwright.
- **`post_processing/excel_formatter.py`** : Applique un formatage visuel aux données destinées à Excel, comme la coloration conditionnelle des lignes et l'ajustement des largeurs de colonnes.
- **`post_processing/output_sanitizer.py`** : Nettoie les réponses brutes des LLMs en supprimant les wrappers de code, les phrases d'introduction et en masquant les PII.

## 🔄 Flux de Travail Principal (SFD vers Tests)

1.  **Authentification**: L'utilisateur obtient un token JWT du service d'authentification.
2.  **Extraction SFD** : L'orchestrateur reçoit un chemin vers une SFD. Le service OCR extrait le contenu textuel.
3.  **Analyse SFD (Qwen3)** : Le contenu textuel est envoyé à Qwen3 (via `qwen3_interface`) qui analyse la spécification et extrait les scénarios de test structurés. La personnalité affinée de Qwen3 est utilisée ici.
4.  **Validation des Scénarios** : Les scénarios extraits sont validés par `policies/excel_policy` pour s'assurer de leur conformité structurelle et métier.
5.  **Génération de la Matrice de Tests** : Qwen3 génère une matrice de tests détaillée à partir des scénarios. Cette matrice est ensuite formatée par `post_processing/excel_formatter` et peut être exportée.
6.  **Importation ALM** : Les scénarios de test peuvent être importés dans un outil ALM via le service `services/alm/`.
7.  **Génération de Code (StarCoder2)** : Pour chaque scénario validé, StarCoder2 (via `starcoder2_interface`) génère le code de test Playwright correspondant. Ce code passe par `post_processing/output_sanitizer` pour le nettoyage et par `post_processing/code_validator` et `policies/business_rules` pour la validation.
8.  **Exécution des Tests** : Les tests Playwright générés sont exécutés par le service `services/playwright/`.
9.  **Rapport et Métriques** : Les résultats d'exécution sont collectés, agrégés et un rapport final est généré, incluant des métriques de performance. Les résultats sont visualisables via le service `services/dash/`.

## 🛠️ Technologies Utilisées

- **Langage** : Python
- **LLMs** : Qwen3, StarCoder2 (via Ollama)
- **Framework Web** : FastAPI
- **Base de données / Cache** : Redis, SQLite (pour l'authentification)
- **Authentification**: PyJWT, passlib
- **Tests d'automatisation** : Playwright, Pytest
- **Outils de Qualité Code** : Black, Ruff
- **Conteneurisation** : Docker, Docker Compose
- **Interface GUI** : Tkinter (pour Admin Dashboard), Dash (pour le reporting)

## 🚀 Déploiement

Le projet est conçu pour être déployé localement sur des machines individuelles (ex: Lenovo ThinkPad) via Docker Compose, assurant l'isolation et la facilité de gestion des microservices.
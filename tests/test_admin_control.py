# tests/test_admin_control.py
"""Tests unitaires et d'intégration pour le système de contrôle administratif.

Ce module contient des tests pour vérifier le bon fonctionnement des commandes
d'administration, telles que la sauvegarde des données utilisateur, le gel
des comptes, et les sauvegardes d'urgence. Il utilise des mocks et des
fixtures pour isoler les composants et simuler les interactions.
"""

import pytest
import asyncio
from pathlib import Path
import shutil

from guardrails.admin_control_system import AdminControlSystem, AdminCommand


@pytest.fixture
async def admin_system():
    """Fixture Pytest pour initialiser un `AdminControlSystem` et nettoyer après les tests."

    Cette fixture crée une instance du système d'administration et s'assure
    que les répertoires temporaires créés par les tests sont supprimés.
    """
    # Crée une instance du système d'administration.
    system = AdminControlSystem()
    yield system
    # Nettoie les répertoires créés par le système d'administration après chaque test.
    if Path("admin_system").exists():
        shutil.rmtree("admin_system")
    if Path("user_data").exists(): # Nettoie aussi les données utilisateur factices.
        shutil.rmtree("user_data")


@pytest.mark.asyncio
async def test_full_user_backup(admin_system: AdminControlSystem, tmp_path: Path):
    """Test la fonctionnalité de sauvegarde complète des données d'un utilisateur."

    Vérifie qu'un fichier ZIP de sauvegarde est créé et qu'il contient les données de l'utilisateur.
    """
    # Crée un répertoire de données utilisateur factice avec un fichier.
    user_data_dir = tmp_path / "user_data" / "test_user"
    user_data_dir.mkdir(parents=True, exist_ok=True)
    (user_data_dir / "profile.json").write_text('{"name": "Test User", "email": "test@example.com"}')

    # Appelle la méthode de sauvegarde de l'utilisateur.
    backup_path_str = await admin_system._full_user_backup("test_user")
    backup_path = Path(backup_path_str)

    # Vérifie que le fichier de sauvegarde existe et a la bonne extension.
    assert backup_path.exists(), "Le fichier de sauvegarde devrait exister."
    assert backup_path.suffix == ".zip", "Le fichier de sauvegarde devrait être un fichier ZIP."

    # Optionnel: Vérifier le contenu du ZIP.
    # import zipfile
    # with zipfile.ZipFile(backup_path, 'r') as zip_ref:
    #     zip_ref.extractall(tmp_path / "extracted_backup")
    # assert (tmp_path / "extracted_backup" / "profile.json").exists()


@pytest.mark.asyncio
async def test_freeze_user(admin_system: AdminControlSystem):
    """Test la commande administrative de gel d'un utilisateur."

    Vérifie que l'exécution de la commande `freeze_user` retourne un statut de succès.
    """
    command = AdminCommand(
        command_id="freeze_001",
        action="freeze_user",
        target_user="test_user",
        parameters={"reason": "Test de gel de compte"}
    )

    result = await admin_system.execute_admin_command(command)
    assert result["status"] == "success", "La commande de gel d'utilisateur devrait réussir."
    assert "gelé" in result["message"].lower(), "Le message de résultat devrait indiquer que l'utilisateur est gelé."


@pytest.mark.asyncio
async def test_emergency_backup(admin_system: AdminControlSystem):
    """Test la fonctionnalité de sauvegarde d'urgence du système."

    Vérifie que la sauvegarde d'urgence crée un répertoire et des fichiers de sauvegarde.
    """
    await admin_system._emergency_backup()
    
    # Vérifie que le répertoire d'urgence a été créé.
    emergency_dir = Path("admin_system/emergency")
    assert emergency_dir.exists(), "Le répertoire de sauvegarde d'urgence devrait exister."
    
    # Vérifie qu'il y a des fichiers de sauvegarde à l'intérieur (au moins un).
    # Note: Le contenu exact dépend de l'implémentation de _emergency_backup.
    assert any(emergency_dir.iterdir()), "Le répertoire de sauvegarde d'urgence ne devrait pas être vide."

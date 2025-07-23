# tests/test_admin_control.py
import pytest
import asyncio
from pathlib import Path
from guardrails.admin_control_system import AdminControlSystem, AdminCommand


@pytest.fixture
async def admin_system():
    system = AdminControlSystem()
    yield system
    # Nettoyer après les tests
    import shutil
    if Path("admin_system").exists():
        shutil.rmtree("admin_system")


@pytest.mark.asyncio
async def test_full_user_backup(admin_system):
    """Test la sauvegarde complète d'un utilisateur."""
    # Créer des fichiers de test
    Path("user_data/test_user").mkdir(parents=True, exist_ok=True)
    Path("user_data/test_user/profile.json").write_text('{"name": "Test"}')

    backup_path = await admin_system._full_user_backup("test_user")
    assert Path(backup_path).exists()
    assert backup_path.endswith(".zip")


@pytest.mark.asyncio
async def test_freeze_user(admin_system):
    """Test le gel d'un utilisateur."""
    command = AdminCommand(
        command_id="freeze_001",
        action="freeze_user",
        target_user="test_user",
        parameters={"reason": "Test freeze"}
    )

    result = await admin_system.execute_admin_command(command)
    assert result["status"] == "success"
    assert "gelé" in result["message"].lower()


@pytest.mark.asyncio
async def test_emergency_backup(admin_system):
    """Test la sauvegarde d'urgence."""
    await admin_system._emergency_backup()
    # Vérifier que des fichiers ont été créés
    emergency_dir = Path("admin_system/emergency")
    assert emergency_dir.exists()
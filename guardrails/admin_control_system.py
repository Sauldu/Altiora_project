"""
Système de Contrôle Administrateur pour Altiora
Admin unique avec contrôle total et monitoring en temps réel
"""

import json
import logging
import secrets
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from cryptography.fernet import Fernet


@dataclass
class AdminCommand:
    """Structure d'une commande administrative"""
    command_id: str
    timestamp: datetime
    action: str
    target_user: str
    parameters: Dict[str, Any]
    executed_by: str = "admin"
    approved: bool = False
    rollback_data: Optional[Dict] = None


class AdminControlSystem:
    """Système de contrôle administrateur centralisé"""

    def __init__(self, encryption_key: bytes = None):
        self.encryption_key = encryption_key or Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)

        self.admin_path = Path("admin_system")
        self.admin_path.mkdir(exist_ok=True)
        
        # Créer les sous-dossiers nécessaires
        (self.admin_path / "backups").mkdir(exist_ok=True)
        (self.admin_path / "logs").mkdir(exist_ok=True)
        (self.admin_path / "emergency").mkdir(exist_ok=True)

        self.logger = self._setup_logging()
        self.active_sessions = {}
        self.pending_changes = {}

        self.emergency_mode = False
        self.system_freeze = False
        self.config = self._load_admin_config()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_admin_command(self, command: AdminCommand) -> Dict[str, Any]:
        if self.system_freeze and command.action not in ["unfreeze", "emergency"]:
            return {"status": "error", "message": "Système gelé - contactez l'admin"}

        self.logger.info(f"Commande admin: {command.action} pour {command.target_user}")

        action_map = {
            "force_personality_change": self._force_personality_change,
            "reset_user_profile": self._reset_user_profile,
            "freeze_user": self._freeze_user,
            "emergency": self._emergency_mode,
            "view_logs": self._view_logs,
            "rollback": self._rollback_command,
        }

        handler = action_map.get(command.action)
        if handler is None:
            return {"status": "error", "message": "Commande inconnue"}

        return await handler(command)

    # ------------------------------------------------------------------
    # Command Handlers
    # ------------------------------------------------------------------

    async def _force_personality_change(self, command: AdminCommand) -> Dict[str, Any]:
        user_id = command.target_user
        changes = command.parameters.get("changes", {})

        backup = await self._backup_user_profile(user_id)
        success = await self._apply_personality_changes(user_id, changes)

        if success:
            self.logger.warning(f"Changement forcé sur {user_id}: {changes}")
            command.rollback_data = backup
            self.pending_changes[command.command_id] = command
            return {
                "status": "success",
                "message": f"Changements appliqués à {user_id}",
                "backup_id": command.command_id,
            }

        return {"status": "error", "message": "Échec de l'application"}

    async def _reset_user_profile(self, command: AdminCommand) -> Dict[str, Any]:
        user_id = command.target_user
        backup = await self._full_user_backup(user_id)
        await self._wipe_user_data(user_id)
        self.logger.critical(f"Réinitialisation complète de {user_id}")
        return {
            "status": "success",
            "message": f"Profil {user_id} réinitialisé",
            "backup_path": backup,
        }

    async def _freeze_user(self, command: AdminCommand) -> Dict[str, Any]:
        user_id = command.target_user
        reason = command.parameters.get("reason", "Admin freeze")

        frozen_file = self.admin_path / "frozen_users.json"
        frozen = self._load_json(frozen_file)
        frozen[user_id] = {
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "admin": command.executed_by,
        }

        self._save_json(frozen_file, frozen)
        return {"status": "success", "message": f"Utilisateur {user_id} gelé"}

    async def _emergency_mode(self, _command: AdminCommand) -> Dict[str, Any]:
        self.emergency_mode = True
        self.system_freeze = True
        await self._emergency_backup()
        self.logger.critical("MODE URGENCE ACTIVE")
        return {
            "status": "success",
            "message": "Mode urgence activé - tous les profils sauvegardés",
        }

    async def _view_logs(self, command: AdminCommand) -> Dict[str, Any]:
        user_id = command.target_user
        days = command.parameters.get("days", 7)
        logs = await self._filter_logs(user_id, days)
        return {"status": "success", "logs": logs, "count": len(logs)}

    async def _rollback_command(self, command: AdminCommand) -> Dict[str, Any]:
        target_command_id = command.parameters.get("target_command_id")
        original_cmd = self.pending_changes.get(target_command_id)

        if not original_cmd or not original_cmd.rollback_data:
            return {"status": "error", "message": "Commande non trouvée"}

        await self._restore_from_backup(original_cmd.rollback_data)
        del self.pending_changes[target_command_id]
        return {"status": "success", "message": f"Rollback effectué pour {target_command_id}"}

    # ------------------------------------------------------------------
    # Implemented Methods (previously stubs)
    # ------------------------------------------------------------------

    async def _full_user_backup(self, user_id: str) -> str:
        """Sauvegarde complète d'un utilisateur avec toutes ses données"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.admin_path / "backups" / user_id / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Collecter tous les fichiers utilisateur
        user_data_paths = [
            Path(f"user_data/{user_id}"),
            Path(f"altiora_core/{user_id}_profile.json"),
            Path(f"altiora_core/{user_id}_evolution.json"),
            Path(f"altiora_core/{user_id}_proposals.json"),
            Path(f"quiz_data/{user_id}_profile.json"),
        ]
        
        # Copier tous les fichiers existants
        for path in user_data_paths:
            if path.exists():
                if path.is_file():
                    dest_path = backup_dir / path.name
                    shutil.copy2(path, dest_path)
                    self.logger.info(f"Backed up: {path} -> {dest_path}")
                elif path.is_dir():
                    dest_path = backup_dir / path.name
                    shutil.copytree(path, dest_path, dirs_exist_ok=True)
                    self.logger.info(f"Backed up directory: {path} -> {dest_path}")
        
        # Créer une archive ZIP
        zip_path = self.admin_path / "backups" / user_id / f"{timestamp}_full_backup.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in backup_dir.rglob("*"):
                if file_path.is_file():
                    zipf.write(file_path, file_path.relative_to(backup_dir))
        
        # Nettoyer le dossier temporaire
        shutil.rmtree(backup_dir)
        
        self.logger.info(f"Full backup completed for {user_id}: {zip_path}")
        return str(zip_path)

    async def _wipe_user_data(self, user_id: str) -> None:
        """Efface toutes les données utilisateur de manière sécurisée"""
        # Paths à effacer
        paths_to_delete = [
            Path(f"user_data/{user_id}"),
            Path(f"altiora_core/{user_id}_profile.json"),
            Path(f"altiora_core/{user_id}_evolution.json"),
            Path(f"altiora_core/{user_id}_proposals.json"),
            Path(f"altiora_core/{user_id}.log"),
            Path(f"quiz_data/{user_id}_profile.json"),
        ]
        
        for path in paths_to_delete:
            if path.exists():
                if path.is_file():
                    # Écraser avec des données aléatoires avant suppression
                    try:
                        with open(path, 'wb') as f:
                            f.write(secrets.token_bytes(path.stat().st_size))
                        path.unlink()
                        self.logger.info(f"Securely deleted file: {path}")
                    except (IOError, OSError) as e:
                        self.logger.error(f"Error wiping file {path}: {e}")
                elif path.is_dir():
                    shutil.rmtree(path)
                    self.logger.info(f"Deleted directory: {path}")
        
        # Nettoyer aussi les caches Redis si disponibles
        # TODO: Implémenter nettoyage Redis
        
        self.logger.warning(f"All data wiped for user: {user_id}")

    async def _emergency_backup(self) -> None:
        """Sauvegarde d'urgence globale de tous les utilisateurs"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        emergency_dir = self.admin_path / "emergency" / f"backup_{timestamp}"
        emergency_dir.mkdir(parents=True, exist_ok=True)
        
        # Identifier tous les utilisateurs
        user_ids = set()
        
        # Scanner les différents répertoires pour trouver les users
        for pattern in ["user_data/*", "altiora_core/*_profile.json", "quiz_data/*_profile.json"]:
            for path in Path(".").glob(pattern):
                if path.is_dir():
                    user_ids.add(path.name)
                elif path.is_file() and "_profile.json" in path.name:
                    user_id = path.stem.replace("_profile", "")
                    user_ids.add(user_id)
        
        self.logger.info(f"Starting emergency backup for {len(user_ids)} users")
        
        # Sauvegarder chaque utilisateur
        for user_id in user_ids:
            try:
                user_backup_dir = emergency_dir / user_id
                user_backup_dir.mkdir(exist_ok=True)
                
                # Copier toutes les données utilisateur
                await self._copy_user_data_to_backup(user_id, user_backup_dir)
                
            except Exception as e:
                self.logger.error(f"Failed to backup user {user_id}: {e}")
        
        # Créer une archive globale
        final_zip = self.admin_path / "emergency" / f"emergency_backup_{timestamp}.zip"
        with zipfile.ZipFile(final_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in emergency_dir.rglob("*"):
                if file_path.is_file():
                    zipf.write(file_path, file_path.relative_to(emergency_dir))
        
        # Nettoyer le dossier temporaire
        shutil.rmtree(emergency_dir)
        
        # Sauvegarder aussi l'état du système
        system_state = {
            "timestamp": timestamp,
            "emergency_mode": self.emergency_mode,
            "system_freeze": self.system_freeze,
            "frozen_users": self._load_json(self.admin_path / "frozen_users.json"),
            "pending_changes": {k: v.__dict__ for k, v in self.pending_changes.items()},
            "config": self.config
        }
        
        state_file = self.admin_path / "emergency" / f"system_state_{timestamp}.json"
        self._save_json(state_file, system_state)
        
        self.logger.critical(f"Emergency backup completed: {final_zip}")

    async def _filter_logs(self, user_id: str, days: int) -> List[Dict[str, Any]]:
        """Filtre les logs par utilisateur et période"""
        cutoff_date = datetime.now() - timedelta(days=days)
        filtered_logs = []
        
        # Parcourir tous les fichiers de log
        log_patterns = [
            self.admin_path / "admin_commands.log",
            Path(f"altiora_core/{user_id}.log"),
            Path("logs") / f"{user_id}_*.log"
        ]
        
        for log_pattern in log_patterns:
            if log_pattern.exists() and log_pattern.is_file():
                try:
                    with open(log_pattern, 'r', encoding='utf-8') as f:
                        for line in f:
                            try:
                                # Parser les logs (format: timestamp - level - message)
                                if " - " in line:
                                    parts = line.strip().split(" - ", 2)
                                    if len(parts) >= 3:
                                        timestamp_str = parts[0]
                                        level = parts[1]
                                        message = parts[2]
                                        
                                        # Parser le timestamp
                                        try:
                                            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                                        except ValueError:
                                        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                                        
                                        # Filtrer par date et utilisateur
                                        if timestamp >= cutoff_date and (user_id in message or user_id == "all"):
                                            filtered_logs.append({
                                                "timestamp": timestamp.isoformat(),
                                                "level": level,
                                                "message": message,
                                                "source": str(log_pattern.name)
                                            })
                            except Exception as e:
                                self.logger.debug(f"Error parsing log line: {e}")
                except (IOError, OSError) as e:
                    self.logger.error(f"Error reading log file {log_pattern}: {e}")
        
        # Trier par timestamp
        filtered_logs.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return filtered_logs

    async def _restore_from_backup(self, backup_data: Dict[str, Any]) -> None:
        """Restaure depuis une sauvegarde"""
        backup_path = backup_data.get("backup_path")
        user_id = backup_data.get("user_id")
        
        if not backup_path or not Path(backup_path).exists():
            raise ValueError(f"Backup path invalid: {backup_path}")
        
        try:
            # Si c'est un fichier ZIP, extraire d'abord
            if backup_path.endswith('.zip'):
                extract_dir = Path(backup_path).parent / "temp_restore"
                extract_dir.mkdir(exist_ok=True)
                
                with zipfile.ZipFile(backup_path, 'r') as zipf:
                    zipf.extractall(extract_dir)
                
                # Restaurer depuis le dossier extrait
                await self._restore_user_data_from_directory(user_id, extract_dir)
                
                # Nettoyer
                shutil.rmtree(extract_dir)
            else:
                # Si c'est un fichier JSON encrypté
                if backup_path.endswith('.json.enc'):
                    with open(backup_path, 'rb') as f:
                        encrypted_data = f.read()
                    
                    decrypted_data = self.cipher.decrypt(encrypted_data)
                    user_data = json.loads(decrypted_data.decode())
                    
                    # Restaurer les données
                    await self._restore_user_profile(user_id, user_data)
            
            self.logger.info(f"Restored user {user_id} from backup: {backup_path}")
        except (IOError, OSError, zipfile.BadZipFile) as e:
            self.logger.error(f"Error restoring from backup {backup_path}: {e}")

    # ------------------------------------------------------------------
    # Helper methods for implementation
    # ------------------------------------------------------------------

    async def _copy_user_data_to_backup(self, user_id: str, backup_dir: Path) -> None:
        """Copie toutes les données d'un utilisateur vers un répertoire de backup"""
        patterns = [
            (f"user_data/{user_id}", backup_dir / "user_data"),
            (f"altiora_core/{user_id}_*.json", backup_dir / "altiora_core"),
            (f"quiz_data/{user_id}_*.json", backup_dir / "quiz_data"),
        ]
        
        for pattern, dest_parent in patterns:
            for path in Path(".").glob(pattern):
                if path.exists():
                    dest_parent.mkdir(parents=True, exist_ok=True)
                    if path.is_file():
                        shutil.copy2(path, dest_parent / path.name)
                    elif path.is_dir():
                        shutil.copytree(path, dest_parent / path.name, dirs_exist_ok=True)

    async def _restore_user_data_from_directory(self, user_id: str, restore_dir: Path) -> None:
        """Restaure les données utilisateur depuis un répertoire"""
        for item in restore_dir.rglob("*"):
            if item.is_file():
                # Déterminer le chemin de destination
                relative_path = item.relative_to(restore_dir)
                dest_path = Path(".") / relative_path
                
                # Créer les répertoires parents si nécessaire
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copier le fichier
                shutil.copy2(item, dest_path)

    async def _restore_user_profile(self, user_id: str, profile_data: Dict[str, Any]) -> None:
        """Restaure un profil utilisateur depuis des données JSON"""
        profile_path = Path(f"altiora_core/{user_id}_profile.json")
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(profile_data, f, indent=2, ensure_ascii=False)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_json(path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text()) if path.exists() else {}

    @staticmethod
    def _save_json(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, default=str))

    def _setup_logging(self) -> logging.Logger:
        logger = logging.getLogger("altiora_admin")
        logger.setLevel(logging.DEBUG)
        fh = logging.FileHandler(self.admin_path / "admin_commands.log")
        fh.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.ERROR)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        logger.addHandler(fh)
        logger.addHandler(ch)
        return logger

    def _load_admin_config(self) -> Dict[str, Any]:
        return self._load_json(self.admin_path / "admin_config.json") or {
            "max_personality_changes_per_day": 5,
            "require_approval_for_major_changes": True,
            "emergency_contact": "admin@company.com",
            "auto_freeze_threshold": 10,
            "backup_retention_days": 30,
        }

    # ------------------------------------------------------------------
    # Public utilities
    # ------------------------------------------------------------------

    async def _backup_user_profile(self, user_id: str) -> Dict[str, Any]:
        timestamp = datetime.now().isoformat()
        backup_path = self.admin_path / "backups" / user_id
        backup_path.mkdir(parents=True, exist_ok=True)
        backup_file = backup_path / f"{timestamp}.json.enc"

        user_data = await self._get_user_data(user_id)
        encrypted = self.cipher.encrypt(json.dumps(user_data).encode())
        backup_file.write_bytes(encrypted)

        return {"user_id": user_id, "backup_path": str(backup_file), "timestamp": timestamp}

    async def _get_user_data(self, user_id: str) -> Dict[str, Any]:
        """Récupère toutes les données d'un utilisateur"""
        user_data = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "personality": {},
            "history": [],
            "preferences": {},
            "voice_profile": {}
        }
        
        try:
            # Charger le profil de personnalité
            profile_path = Path(f"altiora_core/{user_id}_profile.json")
            if profile_path.exists():
                with open(profile_path, 'r', encoding='utf-8') as f:
                    user_data["personality"] = json.load(f)
            
            # Charger l'historique d'évolution
            evolution_path = Path(f"altiora_core/{user_id}_evolution.json")
            if evolution_path.exists():
                with open(evolution_path, 'r', encoding='utf-8') as f:
                    user_data["evolution_history"] = json.load(f)
            
            # Charger le profil du quiz
            quiz_path = Path(f"quiz_data/{user_id}_profile.json")
            if quiz_path.exists():
                with open(quiz_path, 'r', encoding='utf-8') as f:
                    quiz_data = json.load(f)
                    user_data["preferences"] = quiz_data.get("preferences", {})
                    user_data["voice_profile"] = quiz_data.get("vocal_profile", {})
        except (IOError, OSError, json.JSONDecodeError) as e:
            self.logger.error(f"Error getting user data for {user_id}: {e}")
        
        return user_data

    async def _apply_personality_changes(self, user_id: str, changes: Dict[str, Any]) -> bool:
        """Applique des changements de personnalité à un utilisateur"""
        try:
            profile_path = Path(f"altiora_core/{user_id}_profile.json")
            
            # Charger le profil existant
            if profile_path.exists():
                try:
                    with open(profile_path, 'r', encoding='utf-8') as f:
                        profile = json.load(f)
                except (IOError, OSError, json.JSONDecodeError) as e:
                    self.logger.error(f"Error reading profile for {user_id}: {e}")
                    # Créer un profil par défaut si le fichier est corrompu
                    profile = {
                        "user_id": user_id,
                        "traits": {},
                        "preferences": {},
                        "vocal_profile": {},
                        "behavioral_patterns": {},
                        "quiz_metadata": {"created_at": datetime.now().isoformat()}
                    }
            else:
                # Créer un profil par défaut si inexistant
                profile = {
                    "user_id": user_id,
                    "traits": {},
                    "preferences": {},
                    "vocal_profile": {},
                    "behavioral_patterns": {},
                    "quiz_metadata": {"created_at": datetime.now().isoformat()}
                }
            
            # Appliquer les changements
            for key, value in changes.items():
                if key == "traits" and isinstance(value, dict):
                    profile.setdefault("traits", {}).update(value)
                elif key == "preferences" and isinstance(value, dict):
                    profile.setdefault("preferences", {}).update(value)
                else:
                    profile[key] = value
            
            # Sauvegarder le profil modifié
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            with open(profile_path, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)
            
            return True
            
        except (IOError, OSError) as e:
            self.logger.error(f"Failed to apply personality changes: {e}")
            return False

    def generate_report(self) -> Dict[str, Any]:
        return {
            "total_users": len(self.active_sessions),
            "pending_changes": len(self.pending_changes),
            "emergency_mode": self.emergency_mode,
            "system_freeze": self.system_freeze,
            "last_backup": self._get_last_backup_time(),
            "recent_commands": self._get_recent_commands(10),
        }

    def _get_last_backup_time(self) -> Optional[str]:
        backups_dir = self.admin_path / "backups"
        if not backups_dir.exists():
            return None
        latest = None
        for user_dir in backups_dir.iterdir():
            for backup_file in user_dir.glob("*.json.enc"):
                if not latest or backup_file.stat().st_mtime > latest.stat().st_mtime:
                    latest = backup_file
        return str(latest) if latest else None

    def _get_recent_commands(self, count: int) -> List[Dict[str, Any]]:
        """Récupère les commandes les plus récentes depuis les logs"""
        recent_commands = []
        log_file = self.admin_path / "admin_commands.log"
        
        if log_file.exists():
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Prendre les dernières lignes
                for line in lines[-count:]:
                    if "Commande admin:" in line:
                        try:
                            parts = line.strip().split(" - ")
                            if len(parts) >= 4:
                                timestamp = parts[0]
                                message = parts[3]
                                # Extraire l'action et l'utilisateur
                                if "Commande admin:" in message:
                                    action_part = message.split("Commande admin:")[1].strip()
                                    action, user = action_part.split(" pour ")
                                    recent_commands.append({
                                        "timestamp": timestamp,
                                        "action": action,
                                        "user": user
                                    })
                        except Exception as e:
                            self.logger.debug(f"Error parsing log line: {e}")
        
        return recent_commands[:count]


# Utilitaire
def generate_admin_key() -> str:
    return secrets.token_urlsafe(32)
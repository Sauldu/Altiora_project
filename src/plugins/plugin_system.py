# src/plugins/plugin_system.py
"""Module implémentant un système de plugins dynamique pour l'application Altiora.

Ce système permet de charger des plugins à partir d'un répertoire spécifié,
de les enregistrer et de les exécuter à des points d'extension prédéfinis
(appelés "hooks"). Il fournit une interface `Plugin` que tous les plugins
doivent implémenter, assurant ainsi la modularité et l'extensibilité de l'application.
"""

import importlib.util
import inspect
import logging
from abc import ABC, abstractmethod
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Interface de base abstraite pour tous les plugins du système."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Le nom unique du plugin."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """La version du plugin."""
        pass

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]):
        """Initialise le plugin avec sa configuration."

        Cette méthode est appelée une fois lors du chargement du plugin.

        Args:
            config: Un dictionnaire de configuration pour le plugin.
        """
        pass

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Any:
        """Exécute la logique principale du plugin."

        Args:
            context: Un dictionnaire de données fournissant le contexte d'exécution au plugin.

        Returns:
            Le résultat de l'exécution du plugin.
        """
        pass


class PluginManager:
    """Gère le chargement, l'enregistrement et l'exécution des plugins."""

    def __init__(self):
        """Initialise le gestionnaire de plugins."""
        self.plugins: Dict[str, Plugin] = {} # Stocke les instances de plugins par leur nom.
        self.hooks: Dict[str, List[Plugin]] = {} # Mappe les noms de hooks aux plugins abonnés.

    async def load_plugins(self, plugin_dir: str):
        """Charge tous les plugins à partir d'un répertoire spécifié."

        Args:
            plugin_dir: Le chemin du répertoire contenant les fichiers de plugins Python.
        """
        plugin_path = Path(plugin_dir)
        if not plugin_path.is_dir():
            logger.warning(f"Le répertoire de plugins '{plugin_dir}' n'existe pas ou n'est pas un répertoire.")
            return

        logger.info(f"Chargement des plugins depuis : {plugin_dir}")
        for file in plugin_path.glob("*.py"):
            if file.name.startswith("_") or file.name == "__init__.py":
                continue # Ignore les fichiers internes.

            module_name = file.stem
            try:
                # Charge le module dynamiquement.
                spec = importlib.util.spec_from_file_location(
                    module_name,
                    file
                )
                if spec and spec.loader:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    # Recherche les classes qui implémentent l'interface Plugin.
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and
                                issubclass(obj, Plugin) and
                                obj != Plugin): # S'assure que ce n'est pas l'interface elle-même.
                            plugin_instance = obj() # Instancie le plugin.
                            await self.register_plugin(plugin_instance)
                else:
                    logger.warning(f"Impossible de charger la spécification pour le module {module_name}.")
            except Exception as e:
                logger.error(f"Erreur lors du chargement du plugin depuis {file}: {e}", exc_info=True)

    async def register_plugin(self, plugin: Plugin):
        """Enregistre une instance de plugin et l'initialise."

        Args:
            plugin: L'instance du plugin à enregistrer.
        """
        if plugin.name in self.plugins:
            logger.warning(f"Un plugin nommé '{plugin.name}' est déjà enregistré. Il sera remplacé.")
        
        await plugin.initialize({}) # Initialise le plugin (peut prendre une configuration).
        self.plugins[plugin.name] = plugin
        logger.info(f"Plugin '{plugin.name}' v{plugin.version} chargé et enregistré.")

    def hook(self, hook_name: str):
        """Décorateur pour définir un point d'extension (hook) dans le code."

        Les fonctions décorées avec `@plugin_manager.hook("nom_du_hook")`
        exécuteront les plugins enregistrés pour ce hook avant et après leur propre logique.

        Args:
            hook_name: Le nom du hook (ex: "before_sfd_analysis", "after_test_generation").

        Returns:
            Un décorateur qui peut être appliqué à une fonction asynchrone.
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Exécute les plugins enregistrés pour le hook "before_" correspondant.
                for plugin in self.hooks.get(f"before_{hook_name}", []):
                    logger.debug(f"Exécution du plugin '{plugin.name}' pour le hook 'before_{hook_name}'.")
                    await plugin.execute({"hook": hook_name, "stage": "before", "args": args, "kwargs": kwargs})

                # Exécute la fonction originale.
                result = await func(*args, **kwargs)

                # Exécute les plugins enregistrés pour le hook "after_" correspondant.
                for plugin in self.hooks.get(f"after_{hook_name}", []):
                    logger.debug(f"Exécution du plugin '{plugin.name}' pour le hook 'after_{hook_name}'.")
                    await plugin.execute({"hook": hook_name, "stage": "after", "result": result, "args": args, "kwargs": kwargs})

                return result

            return wrapper

        return decorator

    async def register_hook_plugin(self, hook_name: str, plugin: Plugin):
        """Enregistre un plugin pour un hook spécifique."

        Args:
            hook_name: Le nom du hook auquel le plugin doit s'abonner.
            plugin: L'instance du plugin à enregistrer.
        """
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(plugin)
        logger.info(f"Plugin '{plugin.name}' enregistré pour le hook '{hook_name}'.")


# ------------------------------------------------------------------
# Exemple de plugin (pour la démonstration)
# ------------------------------------------------------------------
class MetricsPlugin(Plugin):
    """Plugin de démonstration pour collecter des métriques d'exécution."""

    @property
    def name(self) -> str:
        return "metrics_collector"

    @property
    def version(self) -> str:
        return "1.0.0"

    async def initialize(self, config: Dict[str, Any]):
        self.metrics: Dict[str, List[float]] = {} # Stocke les durées d'opération.
        logger.info(f"MetricsPlugin initialisé. Config: {config}")

    async def execute(self, context: Dict[str, Any]) -> Any:
        operation = context.get("operation")
        duration = context.get("duration")
        stage = context.get("stage")
        hook = context.get("hook")

        if operation and duration is not None:
            if operation not in self.metrics:
                self.metrics[operation] = []
            self.metrics[operation].append(duration)
            logger.info(f"MetricsPlugin: Hook '{hook}' ({stage}) - Opération '{operation}' a pris {duration:.4f}s.")
        else:
            logger.debug(f"MetricsPlugin: Hook '{hook}' ({stage}) - Contexte : {context}")
        return None


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import time

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def demo():
        manager = PluginManager()

        # Crée un répertoire factice pour les plugins.
        temp_plugin_dir = Path("temp_plugins")
        temp_plugin_dir.mkdir(exist_ok=True)

        # Crée un fichier de plugin factice.
        (temp_plugin_dir / "my_metrics_plugin.py").write_text("""
from src.plugins.plugin_system import Plugin
import logging

logger = logging.getLogger(__name__)

class MyMetricsPlugin(Plugin):
    name = "my_metrics_plugin"
    version = "0.1.0"

    async def initialize(self, config):
        self.data = []
        logger.info("MyMetricsPlugin initialisé.")

    async def execute(self, context):
        if context.get("stage") == "after":
            operation_name = context.get("args", ["unknown_op"])[0]
            duration = context.get("result", 0)
            self.data.append({"operation": operation_name, "duration": duration})
            logger.info(f"[MyMetricsPlugin] Enregistré : {operation_name} - {duration:.4f}s")
        return None
""")

        print("\n--- Chargement des plugins ---")
        await manager.load_plugins(str(temp_plugin_dir))

        # Enregistre le plugin de métriques pour un hook spécifique.
        metrics_plugin_instance = MetricsPlugin()
        await manager.register_hook_plugin("process_data", metrics_plugin_instance)

        @manager.hook("process_data")
        async def process_data(item: str) -> float:
            """Fonction de démonstration qui sera instrumentée par le hook."""
            logging.info(f"Traitement de l'élément : {item}")
            delay = random.uniform(0.05, 0.2)
            await asyncio.sleep(delay)
            return delay

        print("\n--- Exécution de fonctions avec hooks ---")
        results = []
        for i in range(5):
            duration = await process_data(f"data_{i}")
            results.append(duration)

        print("\n--- Résultats des métriques collectées par le plugin ---")
        print(metrics_plugin_instance.metrics)

        print("Démonstration du PluginSystem terminée.")

        # Nettoyage.
        import shutil
        shutil.rmtree(temp_plugin_dir)

    import random
    asyncio.run(demo())

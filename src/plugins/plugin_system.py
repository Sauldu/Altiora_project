# src/plugins/plugin_system.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import importlib
import inspect
import logging
from pathlib import Path
from functools import wraps

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Interface de base pour les plugins"""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        pass

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]):
        """Initialiser le plugin"""
        pass

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Any:
        """Exécuter la logique du plugin"""
        pass


class PluginManager:
    """Gestionnaire de plugins"""

    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.hooks: Dict[str, List[Plugin]] = {}

    async def load_plugins(self, plugin_dir: str):
        """Charger tous les plugins d'un répertoire"""
        plugin_path = Path(plugin_dir)

        for file in plugin_path.glob("*.py"):
            if file.name.startswith("_"):
                continue

            module_name = file.stem
            spec = importlib.util.spec_from_file_location(
                module_name,
                file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Trouver les classes Plugin
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and
                        issubclass(obj, Plugin) and
                        obj != Plugin):
                    plugin = obj()
                    await self.register_plugin(plugin)

    async def register_plugin(self, plugin: Plugin):
        """Enregistrer un plugin"""
        await plugin.initialize({})
        self.plugins[plugin.name] = plugin
        logger.info(f"Plugin {plugin.name} v{plugin.version} chargé")

    def hook(self, hook_name: str):
        """Décorateur pour enregistrer un hook"""

        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Exécuter les plugins avant
                for plugin in self.hooks.get(f"before_{hook_name}", []):
                    await plugin.execute({"args": args, "kwargs": kwargs})

                # Exécuter la fonction
                result = await func(*args, **kwargs)

                # Exécuter les plugins après
                for plugin in self.hooks.get(f"after_{hook_name}", []):
                    result = await plugin.execute({
                        "result": result,
                        "args": args,
                        "kwargs": kwargs
                    })

                return result

            return wrapper

        return decorator


# Exemple de plugin
class MetricsPlugin(Plugin):
    """Plugin pour collecter des métriques"""

    @property
    def name(self):
        return "metrics_collector"

    @property
    def version(self):
        return "1.0.0"

    async def initialize(self, config):
        self.metrics = {}

    async def execute(self, context):
        # Collecter des métriques
        operation = context.get("operation")
        duration = context.get("duration")

        if operation not in self.metrics:
            self.metrics[operation] = []

        self.metrics[operation].append(duration)
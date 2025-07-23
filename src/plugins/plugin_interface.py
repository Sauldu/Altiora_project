# src/plugins/plugin_interface.py
from abc import ABC, abstractmethod
from typing import Dict, Any


class Plugin(ABC):
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]):
        """Initialise le plugin avec sa configuration"""
        pass

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute la logique du plugin"""
        pass

    @abstractmethod
    async def cleanup(self):
        """Nettoie les ressources du plugin"""
        pass


class PluginManager:
    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}

    async def register_plugin(self, name: str, plugin: Plugin, config: Dict[str, Any]):
        await plugin.initialize(config)
        self._plugins[name] = plugin

    async def execute_plugin(self, name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if name not in self._plugins:
            raise ValueError(f"Plugin {name} not found")
        return await self._plugins[name].execute(context)
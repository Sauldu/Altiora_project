# src/plugins/plugin_interface.py
"""Module définissant l'interface de base pour les plugins et un gestionnaire de plugins simple.

Ce module établit le contrat que tout plugin doit respecter pour être intégré
dans le système. Il fournit également une classe `PluginManager` rudimentaire
pour enregistrer et exécuter ces plugins.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class Plugin(ABC):
    """Interface abstraite de base pour tous les plugins.

    Tout plugin doit hériter de cette classe et implémenter ses méthodes abstraites.
    """

    @abstractmethod
    async def initialize(self, config: Dict[str, Any]):
        """Initialise le plugin avec sa configuration spécifique."

        Cette méthode est appelée une fois lors de l'enregistrement du plugin.

        Args:
            config: Un dictionnaire de configuration pour le plugin.
        """
        pass

    @abstractmethod
    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute la logique principale du plugin."

        Args:
            context: Un dictionnaire de données fournissant le contexte d'exécution au plugin.

        Returns:
            Un dictionnaire contenant les résultats de l'exécution du plugin.
        """
        pass

    @abstractmethod
    async def cleanup(self):
        """Nettoie les ressources allouées par le plugin."

        Cette méthode est appelée lors de l'arrêt du système ou du désenregistrement du plugin.
        """
        pass


class PluginManager:
    """Gestionnaire simple pour enregistrer et exécuter des plugins."""

    def __init__(self):
        """Initialise le gestionnaire de plugins."""
        self._plugins: Dict[str, Plugin] = {}

    async def register_plugin(self, name: str, plugin: Plugin, config: Dict[str, Any]):
        """Enregistre un plugin et l'initialise."

        Args:
            name: Le nom unique du plugin.
            plugin: L'instance du plugin à enregistrer.
            config: La configuration à passer au plugin lors de son initialisation.
        """
        if name in self._plugins:
            logger.warning(f"Un plugin nommé '{name}' est déjà enregistré. Il sera remplacé.")
        await plugin.initialize(config)
        self._plugins[name] = plugin
        logger.info(f"Plugin '{name}' enregistré et initialisé.")

    async def execute_plugin(self, name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Exécute la logique d'un plugin enregistré."

        Args:
            name: Le nom du plugin à exécuter.
            context: Le contexte d'exécution à passer au plugin.

        Returns:
            Le résultat de l'exécution du plugin.

        Raises:
            ValueError: Si le plugin n'est pas trouvé.
        """
        plugin = self._plugins.get(name)
        if not plugin:
            raise ValueError(f"Plugin '{name}' non trouvé.")
        logger.info(f"Exécution du plugin '{name}'...")
        return await plugin.execute(context)

    async def unregister_plugin(self, name: str):
        """Désenregistre un plugin et nettoie ses ressources."

        Args:
            name: Le nom du plugin à désenregistrer.
        """
        plugin = self._plugins.pop(name, None)
        if plugin:
            await plugin.cleanup()
            logger.info(f"Plugin '{name}' désenregistré et nettoyé.")
        else:
            logger.warning(f"Tentative de désenregistrer un plugin non existant : '{name}'.")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    class SimpleLoggerPlugin(Plugin):
        """Un plugin de démonstration qui loggue des messages."""
        async def initialize(self, config: Dict[str, Any]):
            self.prefix = config.get("prefix", "[LOG]")
            logging.info(f"{self.prefix} SimpleLoggerPlugin initialisé.")

        async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
            message = context.get("message", "Pas de message.")
            logging.info(f"{self.prefix} Message du plugin : {message}")
            return {"status": "logged", "processed_message": message.upper()}

        async def cleanup(self):
            logging.info(f"{self.prefix} SimpleLoggerPlugin nettoyé.")

    async def demo():
        manager = PluginManager()

        print("\n--- Enregistrement du plugin ---")
        await manager.register_plugin(
            "my_logger",
            SimpleLoggerPlugin(),
            {"prefix": "[APP_LOG]"}
        )

        print("\n--- Exécution du plugin ---")
        result = await manager.execute_plugin(
            "my_logger",
            {"message": "Ceci est un message de test."}
        )
        print(f"Résultat de l'exécution du plugin : {result}")

        print("\n--- Désenregistrement du plugin ---")
        await manager.unregister_plugin("my_logger")

        print("Démonstration du PluginManager terminée.")

    asyncio.run(demo())
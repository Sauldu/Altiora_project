from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional

T = TypeVar('T') # Type générique pour l'entité gérée par le dépôt.


class BaseRepository(ABC, Generic[T]):
    """Classe abstraite de base pour tous les dépôts (repositories).

    Définit l'interface CRUD (Create, Read, Update, Delete) que tout dépôt
    doit implémenter pour interagir avec une source de données spécifique
    (base de données, système de fichiers, API externe, etc.).
    """

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Crée une nouvelle entité dans la source de données."

        Args:
            entity: L'entité à créer.

        Returns:
            L'entité créée, potentiellement avec des champs mis à jour (ex: ID généré).
        """
        pass

    @abstractmethod
    async def get(self, id: str) -> Optional[T]:
        """Récupère une entité par son identifiant unique."

        Args:
            id: L'identifiant unique de l'entité.

        Returns:
            L'entité si trouvée, sinon None.
        """
        pass

    @abstractmethod
    async def update(self, id: str, entity: T) -> T:
        """Met à jour une entité existante dans la source de données."

        Args:
            id: L'identifiant unique de l'entité à mettre à jour.
            entity: L'entité avec les données mises à jour.

        Returns:
            L'entité mise à jour.
        """
        pass

    @abstractmethod
    async def delete(self, id: str) -> bool:
        """Supprime une entité de la source de données par son identifiant."

        Args:
            id: L'identifiant unique de l'entité à supprimer.

        Returns:
            True si l'entité a été supprimée avec succès, False sinon.
        """
        pass
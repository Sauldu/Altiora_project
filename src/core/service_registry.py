from config import ServiceConfig


class ServiceRegistry:
    """Gestion centralisée des microservices.

    Cette classe est destinée à fournir un mécanisme pour enregistrer, découvrir
    et surveiller l'état des différents microservices au sein de l'architecture Altiora.
    Les méthodes sont actuellement des stubs et devront être implémentées pour
    fournir la fonctionnalité complète.
    """
    def register(self, name: str, config: ServiceConfig):
        """Enregistre un nouveau microservice auprès du registre.

        Args:
            name: Le nom unique du service.
            config: L'objet de configuration du service (type ServiceConfig).
        """
        ...
    def discover(self, service_type: str):
        """Découvre les services disponibles d'un type donné.

        Args:
            service_type: Le type de service à découvrir (ex: 'ocr', 'alm').
        """
        ...
    def health_check_all(self):
        """Effectue une vérification de l'état de santé de tous les services enregistrés.

        Retourne un rapport sur la disponibilité et la performance des services.
        """
        ...

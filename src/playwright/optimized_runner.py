# src/playwright/optimized_runner.py
"""Module pour un runner Playwright optimisé avec gestion de pool de navigateurs.

Ce module fournit une classe `OptimizedPlaywrightRunner` qui gère un pool
de navigateurs Playwright pré-initialisés. Cela réduit le temps de démarrage
des tests et permet une exécution plus efficace en réutilisant les instances
de navigateurs. Il inclut également des optimisations pour améliorer la
performance des tests web.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Any

from playwright.async_api import async_playwright, Browser, Page

logger = logging.getLogger(__name__)


class OptimizedPlaywrightRunner:
    """Runner Playwright optimisé avec un pool de navigateurs réutilisables."""

    def __init__(self, max_browsers: int = 5):
        """Initialise le runner Playwright optimisé."

        Args:
            max_browsers: Le nombre maximal d'instances de navigateurs à maintenir dans le pool.
        """
        self.max_browsers = max_browsers
        self.browser_pool: list[Browser] = [] # Pool de navigateurs.
        self.semaphore = asyncio.Semaphore(max_browsers) # Limite le nombre de navigateurs actifs.
        self.playwright = None

    async def initialize(self):
        """Initialise le pool de navigateurs en pré-créant un certain nombre d'instances."

        Cette méthode doit être appelée une fois au démarrage de l'application.
        """
        if self.playwright is not None:
            logger.warning("Playwright est déjà initialisé.")
            return

        logger.info("Initialisation de Playwright et du pool de navigateurs...")
        self.playwright = await async_playwright().start()

        # Pré-crée un sous-ensemble de navigateurs pour réduire le temps de démarrage.
        for i in range(min(3, self.max_browsers)):
            try:
                browser = await self._create_browser()
                self.browser_pool.append(browser)
                logger.debug(f"Navigateur {i+1}/{self.max_browsers} pré-créé.")
            except Exception as e:
                logger.error(f"Échec de la pré-création du navigateur {i+1}: {e}")
        logger.info(f"Pool de navigateurs initialisé avec {len(self.browser_pool)} navigateurs.")

    async def _create_browser(self) -> Browser:
        """Crée une nouvelle instance de navigateur Chromium avec des arguments optimisés."""
        if self.playwright is None:
            raise RuntimeError("Playwright n'est pas initialisé.")

        return await self.playwright.chromium.launch(
            headless=True, # Exécute le navigateur en mode headless (sans interface graphique).
            args=[
                '--disable-blink-features=AutomationControlled', # Empêche la détection par les sites.
                '--disable-dev-shm-usage', # Contourne les problèmes de mémoire partagée dans Docker.
                '--no-sandbox', # Nécessaire dans certains environnements Docker.
                '--disable-gpu', # Désactive l'accélération GPU si non nécessaire.
                '--disable-web-security', # Peut être utile pour certains tests locaux.
                '--disable-features=IsolateOrigins,site-per-process' # Optimisations de performance.
            ]
        )

    @asynccontextmanager
    async def get_page(self) -> AsyncGenerator[Page, None]:
        """Acquiert une page Playwright depuis le pool de navigateurs."

        Utilisation avec `async with`:
        ```python
        async with runner.get_page() as page:
            await page.goto("https://example.com")
            # ... effectuer des actions sur la page.
        ```
        """
        if self.playwright is None:
            raise RuntimeError("Playwright n'est pas initialisé. Appelez `initialize()` d'abord.")

        async with self.semaphore: # Limite le nombre de navigateurs actifs simultanément.
            # Récupère un navigateur du pool ou en crée un nouveau si le pool est vide.
            browser: Browser
            if self.browser_pool:
                browser = self.browser_pool.pop()
                logger.debug(f"Navigateur récupéré du pool. Taille restante : {len(self.browser_pool)}")
            else:
                logger.info("Pool de navigateurs vide. Création d'un nouveau navigateur.")
                browser = await self._create_browser()

            # Crée un nouveau contexte de navigateur pour isoler les tests.
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080}, # Taille de la fenêtre du navigateur.
                ignore_https_errors=True, # Ignore les erreurs HTTPS (utile pour les environnements de test).
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' # User-Agent personnalisé.
            )

            page = await context.new_page()

            # Applique des optimisations de performance à la page.
            await self._apply_optimizations(page)

            try:
                yield page # Fournit la page au bloc `async with`.
            finally:
                await context.close() # Ferme le contexte de la page.
                # Remet le navigateur dans le pool s'il n'est pas plein, sinon le ferme.
                if len(self.browser_pool) < self.max_browsers:
                    self.browser_pool.append(browser)
                    logger.debug(f"Navigateur remis dans le pool. Taille actuelle : {len(self.browser_pool)}")
                else:
                    await browser.close()
                    logger.debug("Navigateur fermé (pool plein).")

    async def _apply_optimizations(self, page: Page):
        """Applique des optimisations de performance à une page Playwright."

        Ces optimisations incluent le blocage des ressources inutiles (images, CSS, polices)
        et l'interception des requêtes pour bloquer le tracking/analytics.

        Args:
            page: L'objet `Page` de Playwright à optimiser.
        """
        logger.debug("Application des optimisations de performance à la page.")
        # Bloque le chargement de certaines ressources pour accélérer les tests.
        await page.route(re.compile(r"\.(png|jpg|jpeg|gif|svg|ico)$"), lambda route: route.abort())
        await page.route(re.compile(r"\.(css|font|woff|woff2|ttf|eot)$?"), lambda route: route.abort())

        # Intercepte les requêtes pour bloquer les domaines de tracking/analytics.
        async def handle_route(route):
            if 'analytics' in route.request.url or 'tracking' in route.request.url:
                await route.abort()
            else:
                await route.continue_()

        await page.route('**/*', handle_route)

    async def close(self):
        """Ferme tous les navigateurs dans le pool et arrête l'instance Playwright."

        Cette méthode doit être appelée lors de l'arrêt de l'application pour
        libérer toutes les ressources.
        """
        logger.info("Fermeture du runner Playwright et des navigateurs...")
        for browser in self.browser_pool:
            await browser.close()
        self.browser_pool.clear()
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        logger.info("Runner Playwright fermé.")


# ------------------------------------------------------------------
# Démonstration (exemple d'utilisation)
# ------------------------------------------------------------------
if __name__ == "__main__":
    import logging
    import re # Nécessaire pour re.compile dans la démo.

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    async def demo():
        runner = OptimizedPlaywrightRunner(max_browsers=2)
        await runner.initialize()

        print("\n--- Exécution de tests simulés ---")
        async def run_test_task(task_id: int):
            print(f"Tâche {task_id} : Acquisition d'une page...")
            async with runner.get_page() as page:
                print(f"Tâche {task_id} : Page acquise. Navigation vers example.com...")
                await page.goto("https://example.com")
                title = await page.title()
                print(f"Tâche {task_id} : Titre de la page : {title}")
                await asyncio.sleep(0.5) # Simule un travail sur la page.
            print(f"Tâche {task_id} : Page relâchée.")

        # Lance plusieurs tâches en parallèle pour démontrer le pool.
        tasks = [run_test_task(i) for i in range(5)]
        await asyncio.gather(*tasks)

        print("\n--- Fermeture du runner ---")
        await runner.close()
        print("Démonstration terminée.")

    asyncio.run(demo())
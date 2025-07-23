# src/playwright/optimized_runner.py
from playwright.async_api import async_playwright, Browser
from contextlib import asynccontextmanager
import asyncio


class OptimizedPlaywrightRunner:
    """Runner Playwright optimisé avec pool de navigateurs"""

    def __init__(self, max_browsers: int = 5):
        self.max_browsers = max_browsers
        self.browser_pool = []
        self.semaphore = asyncio.Semaphore(max_browsers)

    async def initialize(self):
        """Initialiser le pool de navigateurs"""
        self.playwright = await async_playwright().start()

        # Pré-créer les navigateurs
        for _ in range(min(3, self.max_browsers)):
            browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-gpu',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            self.browser_pool.append(browser)

    @asynccontextmanager
    async def get_page(self):
        """Obtenir une page depuis le pool"""
        async with self.semaphore:
            # Récupérer ou créer un navigateur
            if self.browser_pool:
                browser = self.browser_pool.pop()
            else:
                browser = await self._create_browser()

            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                ignore_https_errors=True,
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = await context.new_page()

            # Optimisations
            await self._apply_optimizations(page)

            try:
                yield page
            finally:
                await context.close()
                # Remettre dans le pool si pas trop de navigateurs
                if len(self.browser_pool) < self.max_browsers:
                    self.browser_pool.append(browser)
                else:
                    await browser.close()

    async def _apply_optimizations(self, page):
        """Appliquer les optimisations de performance"""
        # Bloquer les ressources inutiles
        await page.route('**/*.{png,jpg,jpeg,gif,svg,ico}', lambda route: route.abort())
        await page.route('**/*.{css,font}', lambda route: route.abort())

        # Intercepter et optimiser les requêtes
        async def handle_route(route):
            if 'analytics' in route.request.url or 'tracking' in route.request.url:
                await route.abort()
            else:
                await route.continue_()

        await page.route('**/*', handle_route)
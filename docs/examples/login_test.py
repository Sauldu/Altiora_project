"""
Exemple de test Playwright généré automatiquement
Objectif : Tester la connexion utilisateur
"""
import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_user_login_success(page: Page):
    """Test de connexion réussie"""
    await page.goto("https://example.com/login")
    await page.get_by_test_id("email").fill("user@example.com")
    await page.get_by_test_id("password").fill("password123")
    await page.get_by_test_id("submit").click()
    await expect(page).to_have_url("https://example.com/dashboard")
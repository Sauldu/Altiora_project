"""
Exemple de test Playwright généré automatiquement.

Ce module contient un test Playwright asynchrone qui simule une connexion
utilisateur réussie. Il est conçu pour démontrer comment les tests Playwright
peuvent être structurés et comment interagir avec les éléments d'une page web.
"""
import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_user_login_success(page: Page):
    """Test de connexion réussie d'un utilisateur.

    Ce test effectue les étapes suivantes :
    1. Navigue vers la page de connexion (simulée).
    2. Remplit les champs d'email et de mot de passe en utilisant leurs `data-testid`.
    3. Clique sur le bouton de soumission.
    4. Vérifie que l'utilisateur est redirigé vers la page du tableau de bord.

    Args:
        page: L'objet `Page` de Playwright, fourni par la fixture pytest.
    """
    # Navigue vers l'URL de la page de connexion.
    await page.goto("https://example.com/login")
    
    # Remplit le champ d'email en utilisant son attribut `data-testid`.
    await page.get_by_test_id("email").fill("user@example.com")
    # Remplit le champ de mot de passe.
    await page.get_by_test_id("password").fill("password123")
    
    # Clique sur le bouton de soumission.
    await page.get_by_test_id("submit").click()
    
    # Vérifie que l'URL actuelle correspond à la page du tableau de bord.
    await expect(page).to_have_url("https://example.com/dashboard")

# src/__init__.py
from .orchestrator import Orchestrator
from .core.container import Container
from .auth.main import app as auth_app
from .dashboard.app import app as dashboard_app

__all__ = ['Orchestrator', 'Container', 'auth_app', 'dashboard_app']
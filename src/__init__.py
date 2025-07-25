# src/__init__.py
from ..configs.validator import validate_on_startup

from .auth.main import app as auth_app
from .core.container import Container
from .dashboard.app import app as dashboard_app
from .orchestrator import Orchestrator

settings = validate_on_startup()

__all__ = ['Orchestrator', 'Container', 'auth_app', 'dashboard_app']

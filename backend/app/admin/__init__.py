"""
Admin Dashboard for llmscm.com
Provides a web-based admin interface for managing users, projects, and system settings.
"""

from .routes import router as admin_router

__all__ = ["admin_router"]

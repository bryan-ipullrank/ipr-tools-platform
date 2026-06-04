"""Shared Flask extension singletons.

Kept in their own module so ``app/__init__.py``, ``app/auth.py``, and route
modules can all import the same instances without circular imports.
"""

from __future__ import annotations

from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "routes.login"
login_manager.login_message = "Please sign in to access the developer portal."

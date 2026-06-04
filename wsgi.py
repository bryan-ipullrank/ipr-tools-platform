"""WSGI entry point for production (PythonAnywhere).

PythonAnywhere's /var/www/<user>_pythonanywhere_com_wsgi.py should add this
project directory to sys.path and then `from wsgi import application`.
"""

from app import create_app

application = create_app()

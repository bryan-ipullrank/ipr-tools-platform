"""Local development server entry point.

Not used in production — PythonAnywhere serves the app via wsgi.py. Requires
OAUTHLIB_INSECURE_TRANSPORT=1 in .env so the OAuth dance works over http.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="localhost", port=5000, debug=True)

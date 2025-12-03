"""Flask application factory."""

import os
from flask import Flask, session
from flask_cors import CORS


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Enable CORS for development
    CORS(app, supports_credentials=True, origins=['http://localhost:5173'])

    # Load configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

    # Google OAuth config
    app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
    app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')

    # For development without HTTPS
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    # Register Google OAuth blueprint
    from web_app.auth.google import create_google_blueprint
    google_bp = create_google_blueprint()
    app.register_blueprint(google_bp, url_prefix='/api/auth')

    # Register API routes
    from web_app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Register scheduler API (already built)
    from scheduler.api import scheduler_api
    app.register_blueprint(scheduler_api)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)

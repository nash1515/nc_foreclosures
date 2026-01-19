"""Flask application factory."""

import os
from flask import Flask, session
from flask_cors import CORS

from database.connection import Session
from database.models import User


def seed_admin_user():
    """Ensure ADMIN_EMAIL user exists with admin role."""
    admin_email = os.environ.get('ADMIN_EMAIL')
    if not admin_email:
        return

    session = Session()
    try:
        user = session.query(User).filter_by(email=admin_email).first()
        if not user:
            user = User(email=admin_email, role='admin')
            session.add(user)
            session.commit()
            print(f"Created admin user: {admin_email}")
        elif user.role != 'admin':
            user.role = 'admin'
            session.commit()
            print(f"Updated user to admin: {admin_email}")
    finally:
        session.close()


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Enable CORS for development (localhost + Tailscale)
    tailscale_host = os.environ.get('TAILSCALE_HOST', '')
    allowed_origins = ['http://localhost:5173']
    if tailscale_host:
        allowed_origins.extend([
            f'http://{tailscale_host}:5173',
            f'https://{tailscale_host}:5173'
        ])
    CORS(app, supports_credentials=True, origins=allowed_origins)

    # Load configuration
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

    # Google OAuth config
    app.config['GOOGLE_OAUTH_CLIENT_ID'] = os.environ.get('GOOGLE_CLIENT_ID')
    app.config['GOOGLE_OAUTH_CLIENT_SECRET'] = os.environ.get('GOOGLE_CLIENT_SECRET')

    # For development without HTTPS
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    # Ignore scope changes from Google (they return full URLs instead of short names)
    os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'

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

    # Register cases API
    from web_app.api.cases import cases_bp
    app.register_blueprint(cases_bp, url_prefix='/api/cases')

    # Register review API
    from web_app.api.review import review_bp
    app.register_blueprint(review_bp, url_prefix='/api/review')

    # Register admin API
    from web_app.api.admin import admin_bp
    app.register_blueprint(admin_bp)

    # Register analysis API
    from web_app.api.analysis import analysis_bp
    app.register_blueprint(analysis_bp)

    # Register enrichments API
    from web_app.api.enrichments import bp as enrichments_bp
    app.register_blueprint(enrichments_bp)

    # Seed admin user from environment
    seed_admin_user()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)

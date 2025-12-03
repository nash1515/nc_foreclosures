"""Flask application factory."""

from flask import Flask
from flask_cors import CORS

def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # Enable CORS for development
    CORS(app, supports_credentials=True, origins=['http://localhost:5173'])

    # Load configuration
    app.config['SECRET_KEY'] = 'dev-secret-key-change-in-production'

    # Register blueprints
    from web_app.api.routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Register scheduler API (already built)
    from scheduler.api import scheduler_api
    app.register_blueprint(scheduler_api)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)

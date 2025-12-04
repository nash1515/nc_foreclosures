"""Main API routes."""

from flask import Blueprint, jsonify, redirect, session
from flask_dance.contrib.google import google
from database.connection import get_session
from database.models import User
from datetime import datetime

api_bp = Blueprint('api', __name__)


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})


@api_bp.route('/auth/me', methods=['GET'])
def get_current_user():
    """Get current authenticated user."""
    if not google.authorized:
        return jsonify({'error': 'Not authenticated'}), 401

    # Get user info from Google
    resp = google.get('/oauth2/v2/userinfo')
    if not resp.ok:
        return jsonify({'error': 'Failed to get user info'}), 401

    google_info = resp.json()
    email = google_info.get('email')

    # Get or create user in database
    with get_session() as db_session:
        user = db_session.query(User).filter_by(email=email).first()

        if not user:
            user = User(
                email=email,
                display_name=google_info.get('name'),
                avatar_url=google_info.get('picture')
            )
            db_session.add(user)
            db_session.commit()
        else:
            # Update last login
            user.last_login_at = datetime.utcnow()
            user.display_name = google_info.get('name')
            user.avatar_url = google_info.get('picture')
            db_session.commit()

        return jsonify({
            'id': user.id,
            'email': user.email,
            'display_name': user.display_name,
            'avatar_url': user.avatar_url
        })


@api_bp.route('/auth/login', methods=['GET'])
def login():
    """Redirect to Google OAuth."""
    return redirect('/api/auth/google')


@api_bp.route('/auth/callback', methods=['GET'])
def auth_callback():
    """Handle OAuth callback - redirect to frontend."""
    return redirect('http://localhost:5173/')


@api_bp.route('/auth/logout', methods=['POST', 'GET'])
def logout():
    """Log out current user."""
    # Clear Flask-Dance token
    if 'google_oauth_token' in session:
        del session['google_oauth_token']
    return redirect('http://localhost:5173/login')

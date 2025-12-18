"""Main API routes."""

import os
from flask import Blueprint, jsonify, redirect, session
from flask_dance.contrib.google import google
from oauthlib.oauth2.rfc6749.errors import TokenExpiredError
from sqlalchemy import func
from database.connection import get_session
from database.models import User
from datetime import datetime

api_bp = Blueprint('api', __name__)

# Check if auth is disabled
AUTH_DISABLED = os.getenv('AUTH_DISABLED', 'false').lower() == 'true'


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})


@api_bp.route('/auth/me', methods=['GET'])
def get_current_user():
    """Get current authenticated user - requires user to be in whitelist."""
    # Return mock user if auth is disabled
    if AUTH_DISABLED:
        return jsonify({
            'authenticated': True,
            'user': {
                'id': 1,
                'email': 'dev@local',
                'display_name': 'Dev User',
                'avatar_url': None,
                'role': 'admin'
            }
        })

    if not google.authorized:
        return jsonify({'authenticated': False}), 401

    # Get user info from Google
    try:
        resp = google.get('/oauth2/v2/userinfo')
    except TokenExpiredError:
        # Clear expired token and force re-login
        if 'google_oauth_token' in session:
            del session['google_oauth_token']
        return jsonify({'authenticated': False, 'error': 'Token expired'}), 401

    if not resp.ok:
        return jsonify({'authenticated': False, 'error': 'Failed to get user info'}), 401

    google_info = resp.json()
    email = google_info.get('email')

    # Check if user exists in whitelist
    with get_session() as db_session:
        user = db_session.query(User).filter_by(email=email).first()

        if not user:
            # User not in whitelist - reject
            return jsonify({
                'authenticated': False,
                'error': 'Not authorized. Contact admin to request access.'
            }), 403

        # Update user info from Google
        user.display_name = google_info.get('name', user.display_name)
        user.avatar_url = google_info.get('picture', user.avatar_url)
        user.last_login_at = func.current_timestamp()
        db_session.commit()

        return jsonify({
            'authenticated': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'display_name': user.display_name,
                'avatar_url': user.avatar_url,
                'role': user.role
            }
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

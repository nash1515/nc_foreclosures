"""Google OAuth configuration."""

import os
from flask import redirect, url_for, session, jsonify
from flask_dance.contrib.google import make_google_blueprint, google


def create_google_blueprint():
    """Create Google OAuth blueprint."""
    blueprint = make_google_blueprint(
        client_id=os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
        scope=['openid', 'email', 'profile'],
        redirect_url='/api/auth/callback'
    )
    return blueprint


def get_google_user_info():
    """Get user info from Google."""
    if not google.authorized:
        return None

    resp = google.get('/oauth2/v2/userinfo')
    if resp.ok:
        return resp.json()
    return None

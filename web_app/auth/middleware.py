"""Authentication middleware for Flask API."""

import os
from functools import wraps
from flask import jsonify

# Check if auth is disabled at module load time
AUTH_DISABLED = os.getenv('AUTH_DISABLED', 'false').lower() == 'true'


def require_auth(f):
    """Decorator to require authentication for API endpoints.

    If AUTH_DISABLED=true in environment, this decorator does nothing.
    Otherwise, it checks if user is authenticated via Google OAuth.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # Skip auth check if disabled
        if AUTH_DISABLED:
            return f(*args, **kwargs)

        # Import here to avoid circular imports and handle case where google might not be available
        try:
            from flask_dance.contrib.google import google
        except ImportError:
            return jsonify({'error': 'OAuth not configured'}), 500

        # Check if authenticated
        if not google.authorized:
            return jsonify({'error': 'Not authenticated'}), 401

        return f(*args, **kwargs)

    return decorated

"""Main API routes."""

from flask import Blueprint, jsonify

api_bp = Blueprint('api', __name__)


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})


@api_bp.route('/auth/me', methods=['GET'])
def get_current_user():
    """Get current authenticated user.

    For now, returns 401 until Google OAuth is set up.
    """
    # TODO: Implement actual auth check
    return jsonify({'error': 'Not authenticated'}), 401


@api_bp.route('/auth/logout', methods=['POST', 'GET'])
def logout():
    """Log out current user."""
    # TODO: Implement actual logout
    return jsonify({'message': 'Logged out'})

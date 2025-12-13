"""Admin API endpoints for user management and manual scraping."""

from flask import Blueprint, jsonify, request
from flask_dance.contrib.google import google
from functools import wraps

from database.connection import get_session
from database.models import User
from web_app.auth.google import get_google_user_info

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def get_current_user_role():
    """Get the role of the currently authenticated user."""
    if not google.authorized:
        return None

    user_info = get_google_user_info()
    if not user_info:
        return None

    with get_session() as db_session:
        user = db_session.query(User).filter_by(email=user_info.get('email')).first()
        return user.role if user else None


def require_admin(f):
    """Decorator to require admin role for endpoint."""
    @wraps(f)
    def decorated(*args, **kwargs):
        role = get_current_user_role()
        if role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users', methods=['GET'])
@require_admin
def list_users():
    """List all users."""
    with get_session() as db_session:
        users = db_session.query(User).order_by(User.email).all()
        return jsonify([
            {
                'id': u.id,
                'email': u.email,
                'role': u.role
            }
            for u in users
        ])


@admin_bp.route('/users', methods=['POST'])
@require_admin
def add_user():
    """Add a new user to the whitelist."""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    role = data.get('role', 'user')

    if not email:
        return jsonify({'error': 'Email is required'}), 400

    if role not in ('admin', 'user'):
        return jsonify({'error': 'Role must be admin or user'}), 400

    with get_session() as db_session:
        # Check if user already exists
        existing = db_session.query(User).filter_by(email=email).first()
        if existing:
            return jsonify({'error': 'User already exists'}), 409

        user = User(email=email, role=role)
        db_session.add(user)
        db_session.commit()

        return jsonify({
            'id': user.id,
            'email': user.email,
            'role': user.role
        }), 201


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@require_admin
def update_user(user_id):
    """Update a user's role."""
    data = request.get_json()
    role = data.get('role')

    if role not in ('admin', 'user'):
        return jsonify({'error': 'Role must be admin or user'}), 400

    # Get current user to prevent self-modification
    current_user_info = get_google_user_info()

    with get_session() as db_session:
        user = db_session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Prevent changing own role
        if current_user_info and user.email == current_user_info.get('email'):
            return jsonify({'error': 'Cannot change your own role'}), 400

        user.role = role
        db_session.commit()

        return jsonify({
            'id': user.id,
            'email': user.email,
            'role': user.role
        })


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    """Remove a user from the whitelist."""
    # Get current user to prevent self-deletion
    current_user_info = get_google_user_info()

    with get_session() as db_session:
        user = db_session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Prevent deleting self
        if current_user_info and user.email == current_user_info.get('email'):
            return jsonify({'error': 'Cannot delete yourself'}), 400

        db_session.delete(user)
        db_session.commit()

        return jsonify({'success': True})

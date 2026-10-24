import functools
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from app.models.db import get_db, log_network_event

bp = Blueprint('auth', __name__, url_prefix='/auth')

def generate_csrf_token():
    """Generates or retrieves CSRF token for the session."""
    if '_csrf_token' not in session:
        session['_csrf_token'] = secrets.token_hex(16)
    return session['_csrf_token']

def verify_csrf_token():
    """Validates the CSRF token from form or header."""
    token = request.form.get('csrf_token') or request.headers.get('X-CSRFToken')
    if not token or token != session.get('_csrf_token'):
        return False
    return True

def login_required(view):
    """Decorator to require an authenticated session."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('auth.login', next=request.path))
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    """Decorator to require admin privileges."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            flash("Please log in as an administrator.", "warning")
            return redirect(url_for('auth.login', next=request.path))
        if session.get('role') != 'admin':
            flash("Access denied: Administrator privileges required.", "danger")
            log_network_event("UNAUTHORIZED_ACCESS", request.remote_addr, f"Unauthorized access attempt to {request.path} by user {session.get('username')}", 403)
            return redirect(url_for('student.dashboard'))
        return view(**kwargs)
    return wrapped_view

def student_required(view):
    """Decorator to ensure user is logged in as student."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            flash("Please log in as a student.", "warning")
            return redirect(url_for('auth.login', next=request.path))
        if session.get('role') != 'student':
            return redirect(url_for('admin.dashboard'))
        return view(**kwargs)
    return wrapped_view

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Unified Authentication Route.
    Supports students and administrators with secure password hashing.
    """
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('admin.dashboard'))
        return redirect(url_for('student.dashboard'))

    if request.method == 'POST':
        if not verify_csrf_token():
            flash("Security validation (CSRF) failed. Please try again.", "danger")
            return redirect(url_for('auth.login'))

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?",
            (username,)
        ).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['_csrf_token'] = secrets.token_hex(16)

            log_network_event(
                "AUTH_SUCCESS",
                request.remote_addr,
                f"User '{username}' logged in successfully as {user['role']}.",
                200
            )

            flash(f"Welcome back, {user['full_name']}!", "success")
            next_url = request.args.get('next')
            if next_url and next_url.startswith('/'):
                return redirect(next_url)

            if user['role'] == 'admin':
                return redirect(url_for('admin.dashboard'))
            return redirect(url_for('student.dashboard'))
        else:
            log_network_event(
                "AUTH_FAILURE",
                request.remote_addr,
                f"Failed login attempt for username '{username}'.",
                401
            )
            flash("Invalid username or password. Please check credentials.", "danger")

    return render_template('login.html', csrf_token=generate_csrf_token())

@bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """Terminate current user session."""
    username = session.get('username', 'Anonymous')
    log_network_event("AUTH_LOGOUT", request.remote_addr, f"User '{username}' logged out.", 200)
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for('auth.login'))

import os
from flask import Flask, render_template, request, session, redirect, url_for
from config import Config
from app.models.db import get_db, close_db, log_network_event
from app.networking.monitoring import get_server_network_interfaces, get_application_health

def create_app(config_class=Config):
    """Application Factory for Online Examination Network."""
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Ensure instance directory exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # Database teardown hook
    app.teardown_appcontext(close_db)

    # Register Blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from app.student import bp as student_bp
    app.register_blueprint(student_bp)

    from app.admin import bp as admin_bp
    app.register_blueprint(admin_bp)

    from app.networking.routes import bp as networking_bp
    app.register_blueprint(networking_bp)

    # Global Template Context Processor (available across all Jinja templates)
    @app.context_processor
    def inject_global_network_context():
        interfaces = get_server_network_interfaces()
        return {
            'project_title': 'Online Examination Network',
            'server_ip': interfaces['primary_lan_ip'],
            'server_hostname': interfaces['hostname'],
            'server_port': app.config.get('PORT', 5000),
            'current_user': {
                'id': session.get('user_id'),
                'username': session.get('username'),
                'full_name': session.get('full_name'),
                'role': session.get('role')
            } if 'user_id' in session else None
        }

    # Root Home Route
    @app.route('/')
    def index():
        db = get_db()
        exam = db.execute("SELECT * FROM examinations WHERE is_active = 1 LIMIT 1").fetchone()
        health = get_application_health(db, port=app.config.get('PORT', 5000))
        interfaces = get_server_network_interfaces()
        return render_template('index.html', exam=exam, health=health, interfaces=interfaces)

    # Error Handlers
    @app.errorhandler(404)
    def page_not_found(e):
        log_network_event("HTTP_404", request.remote_addr, f"Route not found: {request.path}", 404)
        return render_template('errors/404.html', path=request.path), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        log_network_event("HTTP_500", request.remote_addr, f"Internal server error: {e}", 500)
        return render_template('errors/500.html'), 500

    return app

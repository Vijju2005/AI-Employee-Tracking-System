"""
EBT System — Application Factory
"""

import os
from flask import Flask
from config import get_config
from app.extensions import db, login_manager, csrf, mail


def create_app(config_class=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    # Load config
    if config_class is None:
        config_class = get_config()
    app.config.from_object(config_class)

    # Ensure reports directory exists
    os.makedirs(app.config.get("REPORTS_DIR", "app/static/reports"), exist_ok=True)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    # User loader
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.dashboard.routes import dashboard_bp
    from app.employees.routes import employees_bp
    from app.attendance.routes import attendance_bp
    from app.breaks.routes import breaks_bp
    from app.leave.routes import leave_bp
    from app.reports.routes import reports_bp
    from app.ml.routes import ml_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(breaks_bp)
    app.register_blueprint(leave_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(ml_bp)

    # Health check endpoint for cloud deployment (e.g., Render, Railway, K8s)
    @app.route("/health")
    def health():
        from flask import jsonify
        from sqlalchemy import text, inspect
        db_status = "healthy"
        tables = []
        try:
            db.session.execute(text("SELECT 1"))
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
        except Exception as e:
            app.logger.error("Health check database probe failed: %s", e)
            db_status = f"unhealthy: {str(e)}"
        return jsonify({
            "status": "ok" if db_status == "healthy" else "degraded",
            "database": db_status,
            "table_count": len(tables),
            "tables_initialized": len(tables) >= 5,
        }), (200 if db_status == "healthy" else 503)

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        app.logger.error("Internal Server Error (500) caught: %s", getattr(e, "description", e), exc_info=True)
        from flask import render_template
        return render_template("errors/500.html"), 500

    # Template globals
    @app.context_processor
    def inject_globals():
        from flask_login import current_user
        return {
            "app_name": app.config.get("APP_NAME", "EBT System"),
            "current_user": current_user,
        }

    return app

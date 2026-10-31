"""
EBT System — Application Factory
"""

import os
from flask import Flask
from config import get_config
from app.extensions import db, login_manager, csrf, mail


def create_app(config_class=None):
    flask_app = Flask(__name__, template_folder="templates", static_folder="static")

    # Load config (instantiate if a class is provided to evaluate dynamic __init__)
    if config_class is None:
        config_class = get_config()
    if isinstance(config_class, type):
        config_obj = config_class()
    else:
        config_obj = config_class
    flask_app.config.from_object(config_obj)

    # Ensure reports directory exists
    os.makedirs(flask_app.config.get("REPORTS_DIR", "app/static/reports"), exist_ok=True)

    # Init extensions
    db.init_app(flask_app)
    login_manager.init_app(flask_app)
    csrf.init_app(flask_app)
    mail.init_app(flask_app)

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
    from app.holidays.routes import holidays_bp

    flask_app.register_blueprint(auth_bp)
    flask_app.register_blueprint(dashboard_bp)
    flask_app.register_blueprint(employees_bp)
    flask_app.register_blueprint(attendance_bp)
    flask_app.register_blueprint(breaks_bp)
    flask_app.register_blueprint(leave_bp)
    flask_app.register_blueprint(reports_bp)
    flask_app.register_blueprint(ml_bp)
    flask_app.register_blueprint(holidays_bp)

    # Lightweight idempotent database table check on first boot
    if not flask_app.config.get("TESTING", False):
        try:
            with flask_app.app_context():
                # Ensure all defined model tables exist (e.g. holidays)
                from app.models import Holiday, Employee  # Explicitly import models to register with metadata
                from sqlalchemy import inspect
                inspector = inspect(db.engine)
                existing_tables = inspector.get_table_names()
                if "holidays" not in existing_tables or len(existing_tables) < 5:
                    flask_app.logger.info("Creating any missing database tables (tables found: %s)...", existing_tables)
                    db.create_all()
                    if len(existing_tables) < 5:
                        try:
                            import bootstrap
                            bootstrap.bootstrap_database()
                        except Exception as bs_err:
                            flask_app.logger.warning("Startup bootstrap error: %s", bs_err)

                # Seed Karnataka 2026 holidays idempotently if missing
                try:
                    from app.holidays.seeder import seed_karnataka_holidays_2026
                    seed_karnataka_holidays_2026()
                except Exception as seed_err:
                    flask_app.logger.warning("Auto holiday seed error: %s", seed_err)

                # Safe idempotent column migration for existing tables
                inspector = inspect(db.engine)
                existing_tables = inspector.get_table_names()
                if "employees" in existing_tables:
                    cols = [c["name"] for c in inspector.get_columns("employees")]
                    if "company_name" not in cols:
                        try:
                            from sqlalchemy import text
                            db.session.execute(text("ALTER TABLE employees ADD COLUMN company_name VARCHAR(150) DEFAULT 'EBT System'"))
                            db.session.commit()
                            flask_app.logger.info("Migrated employees table: added company_name column.")
                        except Exception as mig_err:
                            db.session.rollback()
                            flask_app.logger.warning("Column migration skipped or failed: %s", mig_err)
        except Exception as init_err:
            flask_app.logger.warning("Auto db table creation skipped on startup: %s", init_err)

    # Health check endpoint for cloud deployment (e.g., Render, Railway, K8s)
    @flask_app.route("/health")
    def health():
        from flask import jsonify, request
        from sqlalchemy import text, inspect
        db_status = "healthy"
        tables = []
        migration_result = None
        try:
            db.session.execute(text("SELECT 1"))
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()

            # Ensure all model tables exist, or run on demand via query param or if missing
            if "holidays" not in tables:
                from app.models import Holiday
                Holiday.__table__.create(db.engine, checkfirst=True)
                inspector = inspect(db.engine)
                tables = inspector.get_table_names()
                migration_result = "Created holidays table"

            # Ensure 2026 Karnataka holidays are seeded
            from app.holidays.seeder import seed_karnataka_holidays_2026
            inserted, existing = seed_karnataka_holidays_2026()
            if inserted > 0:
                migration_result = (migration_result or "") + f" Seeded {inserted} holidays."
        except Exception as e:
            flask_app.logger.error("Health check database probe failed: %s", e)
            db_status = f"unhealthy: {str(e)}"
            migration_result = f"Error: {str(e)}"

        return jsonify({
            "status": "ok" if db_status == "healthy" else "degraded",
            "database": db_status,
            "table_count": len(tables),
            "tables": tables,
            "tables_initialized": len(tables) >= 5,
            "migration": migration_result,
        }), (200 if db_status == "healthy" else 503)

    # Error handlers
    @flask_app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template("errors/403.html"), 403

    @flask_app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template("errors/404.html"), 404

    @flask_app.errorhandler(500)
    def server_error(e):
        flask_app.logger.error("Internal Server Error (500) caught: %s", getattr(e, "description", e), exc_info=True)
        from flask import render_template
        return render_template("errors/500.html"), 500

    # Security headers
    @flask_app.after_request
    def set_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # Template globals and filters
    from app.time_utils import (
        format_local_time, format_local_date, to_local,
        format_hours_mins, format_mins
    )

    flask_app.jinja_env.filters["local_time"] = format_local_time
    flask_app.jinja_env.filters["local_date"] = format_local_date
    flask_app.jinja_env.filters["hours_mins"] = format_hours_mins
    flask_app.jinja_env.filters["mins"] = format_mins

    @flask_app.context_processor
    def inject_globals():
        from flask_login import current_user
        return {
            "app_name": flask_app.config.get("APP_NAME", "EBT System"),
            "current_user": current_user,
            "format_local_time": format_local_time,
            "format_local_date": format_local_date,
            "format_hours_mins": format_hours_mins,
            "format_mins": format_mins,
        }

    return flask_app

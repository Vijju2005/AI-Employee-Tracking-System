"""
EBT System — Production Bootstrapper (Render Startup)
Runs idempotent database initialization and optional demo data seeding
before handing control to the Gunicorn WSGI master process.
"""

import logging
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.extensions import db
from app.models import Department, WorkSchedule, User, UserRole, Employee, Attendance

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("bootstrap")


def bootstrap_database():
    """
    Idempotent database initializer:
    1. Runs db.create_all() so all missing tables exist.
    2. Seeds standard departments and schedules if empty.
    3. If AUTO_SEED_DEMO=true (or by default if no users exist), creates admin + demo employees
       and seeds 30-day historical attendance/breaks for ML prediction.
    """
    app = create_app()
    with app.app_context():
        # Check if tables exist
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        existing_tables = inspector.get_table_names()
        logger.info("Current tables in database: %s", existing_tables)

        if len(existing_tables) < 5:
            logger.info("Missing tables detected. Creating all database tables...")
            db.create_all()
            logger.info("All tables created successfully.")

        # Seed departments & work schedules
        from datetime import time
        default_depts = [
            ("Information Technology", "IT & Software Development"),
            ("Human Resources", "HR & People Management"),
            ("Finance", "Accounting & Finance"),
            ("Operations", "Business Operations"),
            ("Marketing", "Marketing & Communications"),
            ("Sales", "Sales & Business Development"),
        ]
        for name, desc in default_depts:
            if not Department.query.filter_by(name=name).first():
                db.session.add(Department(name=name, description=desc))

        default_schedules = [
            ("Standard 9-5", time(9, 0), time(17, 0), 8.0),
            ("Morning Shift", time(8, 0), time(16, 0), 8.0),
            ("Evening Shift", time(14, 0), time(22, 0), 8.0),
            ("Part Time Morning", time(9, 0), time(13, 0), 4.0),
        ]
        for name, st, et, th in default_schedules:
            if not WorkSchedule.query.filter_by(name=name).first():
                db.session.add(WorkSchedule(name=name, start_time=st, end_time=et, total_hours=th))

        db.session.commit()
        logger.info("Standard departments and work schedules verified.")

        # Seed Karnataka 2026 holidays if missing
        try:
            from app.holidays.seeder import seed_karnataka_holidays_2026
            ins, ex = seed_karnataka_holidays_2026()
            logger.info("Karnataka 2026 holidays verified (%d added, %d existing).", ins, ex)
        except Exception as h_err:
            logger.warning("Holiday bootstrap error: %s", h_err)

        # Check if demo data should be seeded
        auto_seed = os.environ.get("AUTO_SEED_DEMO", "true").lower() in ("true", "1", "yes")
        user_count = User.query.count()

        if auto_seed and user_count == 0:
            logger.info("No users found. Running idempotent demo setup...")
            try:
                from scripts.setup_demo import main as setup_demo_main
                setup_demo_main()
                logger.info("Admin account and demo employees seeded.")
            except Exception as e:
                logger.warning("setup_demo error: %s", e)

            try:
                attendance_count = Attendance.query.count()
                if attendance_count == 0:
                    logger.info("Seeding 30-day historical records for ML predictions...")
                    from scripts.seed_history import seed as seed_history_main
                    seed_history_main()
                    logger.info("Historical attendance and break records seeded.")
            except Exception as e:
                logger.warning("seed_history error: %s", e)

        logger.info("Bootstrap complete. Database is healthy and ready.")


if __name__ == "__main__":
    bootstrap_database()

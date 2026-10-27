"""
EBT System — Database initialization script.
Run once: python scripts/init_db.py
Creates tables and seeds default departments, schedules, and sample data.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models import (
    Department, WorkSchedule, User, Employee,
    UserRole, AccountStatus
)
from datetime import time, datetime, timezone
from werkzeug.security import generate_password_hash


def init_db():
    app = create_app()
    with app.app_context():
        print("Creating all tables...")
        db.create_all()
        print("Tables created successfully.")

        # Seed departments
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
        db.session.commit()
        print(f"Seeded {len(default_depts)} departments.")

        # Seed work schedules
        default_schedules = [
            ("Standard 9-5", time(9, 0), time(17, 0), 8.0),
            ("Morning Shift 7-3", time(7, 0), time(15, 0), 8.0),
            ("Evening Shift 3-11", time(15, 0), time(23, 0), 8.0),
            ("Flexible 10-6", time(10, 0), time(18, 0), 8.0),
            ("Part-time 9-1", time(9, 0), time(13, 0), 4.0),
        ]
        for name, start_t, end_t, total in default_schedules:
            if not WorkSchedule.query.filter_by(name=name).first():
                db.session.add(WorkSchedule(
                    name=name, start_time=start_t, end_time=end_t, total_hours=total
                ))
        db.session.commit()
        print(f"Seeded {len(default_schedules)} work schedules.")

        # Check if admin exists
        if not User.query.filter_by(role=UserRole.ADMIN).first():
            print("\nNo admin account found.")
            print("Visit http://localhost:5000/auth/setup to create the first admin account.")
            print("(Or run this script with --create-admin to create one interactively)")
        else:
            print("Admin account already exists.")

        # Seed sample employees (for demo / testing only)
        if "--seed-demo" in sys.argv:
            _seed_demo_data()

        print("\nDatabase initialization complete!")


def _seed_demo_data():
    """Create sample employees for demo purposes."""
    it_dept = Department.query.filter_by(name="Information Technology").first()
    hr_dept = Department.query.filter_by(name="Human Resources").first()
    fin_dept = Department.query.filter_by(name="Finance").first()
    std_schedule = WorkSchedule.query.filter_by(name="Standard 9-5").first()

    sample_employees = [
        {
            "emp_id": "EMP001", "name": "Rahul Sharma", "email": "rahul@company.com",
            "username": "rahul.sharma", "dept": it_dept, "designation": "Developer",
        },
        {
            "emp_id": "EMP002", "name": "Pooja Nair", "email": "pooja@company.com",
            "username": "pooja.nair", "dept": hr_dept, "designation": "HR Executive",
        },
        {
            "emp_id": "EMP003", "name": "Sneha Patil", "email": "sneha@company.com",
            "username": "sneha.patil", "dept": fin_dept, "designation": "Accountant",
        },
    ]

    created = 0
    for s in sample_employees:
        if Employee.query.filter_by(employee_id=s["emp_id"]).first():
            continue
        user = User(
            username=s["username"], email=s["email"],
            password_hash=generate_password_hash("Employee@123"),
            role=UserRole.EMPLOYEE, is_active=True,
        )
        db.session.add(user)
        db.session.flush()

        emp = Employee(
            employee_id=s["emp_id"], full_name=s["name"],
            email=s["email"], department_id=s["dept"].id if s["dept"] else None,
            designation=s["designation"], work_schedule_id=std_schedule.id if std_schedule else None,
            user_id=user.id, status=AccountStatus.ACTIVE,
        )
        db.session.add(emp)
        created += 1

    db.session.commit()
    print(f"Created {created} demo employees. Default password: Employee@123")


if __name__ == "__main__":
    init_db()

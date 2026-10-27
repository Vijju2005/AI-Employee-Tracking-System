"""
EBT System — Setup script: creates admin account + seeds demo employees.
Run from project root: python scripts/setup_demo.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')  # handle Windows console encoding

from dotenv import load_dotenv
load_dotenv()

from app import create_app
from app.extensions import db
from app.models import (
    User, UserRole, Employee, Department, WorkSchedule, AccountStatus
)
from werkzeug.security import generate_password_hash


def main():
    app = create_app()
    with app.app_context():
        # ── Admin ──────────────────────────────────────────────────────────
        if not User.query.filter_by(role=UserRole.ADMIN).first():
            admin = User(
                username="admin",
                email="admin@ebt.local",
                password_hash=generate_password_hash("Admin@123"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.session.add(admin)
            db.session.commit()
            print("✓ Admin created  |  username: admin  |  password: Admin@123")
        else:
            print("• Admin already exists — skipping.")

        # ── Extra demo employees ───────────────────────────────────────────
        sched = WorkSchedule.query.filter_by(name="Standard 9-5").first()
        dept_map = {
            d.name: d for d in Department.query.all()
        }

        demo_employees = [
            ("EMP002", "Pooja Nair",   "pooja@company.com",  "pooja.nair",
             dept_map.get("Human Resources"),    "HR Executive"),
            ("EMP003", "Sneha Patil",  "sneha@company.com",  "sneha.patil",
             dept_map.get("Finance"),            "Accountant"),
            ("EMP004", "Arjun Mehta",  "arjun@company.com",  "arjun.mehta",
             dept_map.get("Operations"),         "Operations Lead"),
            ("EMP005", "Kavya Reddy",  "kavya@company.com",  "kavya.reddy",
             dept_map.get("Marketing"),          "Marketing Executive"),
        ]

        added = 0
        for emp_id, name, email, uname, dept, designation in demo_employees:
            if Employee.query.filter_by(employee_id=emp_id).first():
                continue
            if User.query.filter_by(username=uname).first():
                continue
            u = User(
                username=uname, email=email,
                password_hash=generate_password_hash("Employee@123"),
                role=UserRole.EMPLOYEE, is_active=True,
            )
            db.session.add(u)
            db.session.flush()
            e = Employee(
                employee_id=emp_id, full_name=name, email=email,
                department_id=dept.id if dept else None,
                designation=designation,
                work_schedule_id=sched.id if sched else None,
                user_id=u.id, status=AccountStatus.ACTIVE,
            )
            db.session.add(e)
            added += 1

        db.session.commit()
        if added:
            print(f"✓ Added {added} demo employees  |  password: Employee@123")
        else:
            print("• Demo employees already present.")

        print(f"\n📊 Database summary:")
        print(f"   Users:     {User.query.count()}")
        print(f"   Employees: {Employee.query.count()}")
        print(f"   Depts:     {Department.query.count()}")
        print(f"   Schedules: {WorkSchedule.query.count()}")
        print("\n🟢 Setup complete! Start the server with: python run.py")
        print("   Login at: http://127.0.0.1:5000/auth/login")
        print("   Admin:    admin / Admin@123")
        print("   Employee: rahul.sharma / Employee@123  (or pooja.nair etc.)")


if __name__ == "__main__":
    main()

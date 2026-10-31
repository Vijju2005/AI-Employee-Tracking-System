"""
EBT System — Automated Tests
Run with: pytest tests/ -v
Uses a separate test database. Never runs against production data.
"""

import pytest
import os
from datetime import date, datetime, timezone, timedelta


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    """Create test Flask application with SQLite in-memory test database."""
    os.environ["FLASK_ENV"] = "testing"
    from app import create_app
    from config import TestingConfig
    application = create_app(TestingConfig)
    return application


@pytest.fixture(scope="session")
def db(app):
    """Initialize test database."""
    from app.extensions import db as _db
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(scope="function")
def session(db, app):
    """Provide a clean transactional test session that rolls back after each test."""
    with app.app_context():
        connection = db.engine.connect()
        transaction = connection.begin()
        # Bind a session to this connection
        from sqlalchemy.orm import Session
        test_session = Session(bind=connection)
        old_session = db.session
        db.session = test_session
        yield test_session
        test_session.close()
        transaction.rollback()
        connection.close()
        db.session = old_session


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def runner(app):
    return app.test_cli_runner()


def _make_user(db, role="employee", username="testuser", email="test@test.com"):
    from app.models import User, UserRole
    from werkzeug.security import generate_password_hash
    import uuid
    # Add random suffix to prevent unique-constraint collisions across tests
    suffix = uuid.uuid4().hex[:6]
    user = User(
        username=f"{username}_{suffix}",
        email=f"{suffix}_{email}",
        password_hash=generate_password_hash("Test@1234"),
        role=UserRole.ADMIN if role == "admin" else UserRole.EMPLOYEE,
        is_active=True,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _make_employee(db, user, emp_id="TEST001", name="Test Employee"):
    from app.models import Employee, AccountStatus
    import uuid
    suffix = uuid.uuid4().hex[:6]
    emp = Employee(
        employee_id=f"{emp_id}_{suffix}",
        full_name=name,
        email=user.email,
        user_id=user.id,
        status=AccountStatus.ACTIVE,
    )
    db.session.add(emp)
    db.session.flush()
    return emp


# ── App Startup Tests ─────────────────────────────────────────────────────────

class TestAppStartup:
    def test_app_creates(self, app):
        assert app is not None

    def test_app_is_testing(self, app):
        assert app.config["TESTING"] is True

    def test_blueprints_registered(self, app):
        blueprint_names = [bp for bp in app.blueprints]
        assert "auth" in blueprint_names
        assert "dashboard" in blueprint_names
        assert "employees" in blueprint_names
        assert "attendance" in blueprint_names
        assert "breaks" in blueprint_names
        assert "leave" in blueprint_names
        assert "reports" in blueprint_names
        assert "ml" in blueprint_names
        assert "holidays" in blueprint_names

    def test_create_app_in_production_mode_handles_database_operational_error_cleanly(self):
        """
        Regression test: When create_app() runs in non-testing mode and encounters a database
        connection failure on startup, it must not raise AttributeError (module 'app' has no attribute 'logger').
        """
        from app import create_app
        from config import Config

        class UnreachableDbConfig(Config):
            TESTING = False
            SQLALCHEMY_DATABASE_URI = "mysql+pymysql://invalid_user:invalid_pwd@127.0.0.1:9999/invalid_db?connect_timeout=1"
            def __init__(self):
                super().__init__()
                self.TESTING = False
                self.SQLALCHEMY_DATABASE_URI = "mysql+pymysql://invalid_user:invalid_pwd@127.0.0.1:9999/invalid_db?connect_timeout=1"

        # Calling create_app should catch DB connection failure and log a warning without crashing
        app_instance = create_app(UnreachableDbConfig)
        assert app_instance is not None
        assert hasattr(app_instance, "logger")



# ── Database Tests ────────────────────────────────────────────────────────────

class TestDatabase:
    def test_db_tables_created(self, db, app):
        with app.app_context():
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            assert "users" in tables
            assert "employees" in tables
            assert "attendance" in tables
            assert "breaks" in tables
            assert "leave_requests" in tables

    def test_db_connectivity(self, db, app):
        with app.app_context():
            result = db.session.execute(db.text("SELECT 1")).fetchone()
            assert result[0] == 1


# ── Authentication Tests ──────────────────────────────────────────────────────

class TestAuthentication:
    def test_login_page_loads(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code == 200

    def test_setup_page_loads(self, client, db, app):
        with app.app_context():
            from app.models import User
            # Only test if no admin exists
            if not User.query.filter_by(role="admin").first():
                resp = client.get("/auth/setup")
                assert resp.status_code == 200

    def test_login_invalid_credentials(self, client):
        resp = client.post("/auth/login", data={
            "identifier": "nonexistent@test.com",
            "password": "wrongpassword",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Invalid" in resp.data or b"invalid" in resp.data

    def test_protected_route_redirects(self, client):
        resp = client.get("/dashboard/admin", follow_redirects=False)
        assert resp.status_code in (302, 401)

    def test_password_hashing(self, app):
        from werkzeug.security import generate_password_hash, check_password_hash
        pw = "SecurePass@123"
        hashed = generate_password_hash(pw)
        assert hashed != pw
        assert check_password_hash(hashed, pw) is True
        assert check_password_hash(hashed, "wrong") is False


# ── Employee Management Tests ─────────────────────────────────────────────────

class TestEmployeeManagement:
    def test_create_employee(self, db, app):
        with app.app_context():
            import uuid
            uid = uuid.uuid4().hex[:8]
            user = _make_user(db, username=f"emptest_{uid}", email=f"emptest_{uid}@test.com")
            emp = _make_employee(db, user, emp_id=f"ETEST_{uid}", name="Emp Test")
            db.session.commit()
            from app.models import Employee
            found = Employee.query.filter_by(employee_id=emp.employee_id).first()
            assert found is not None
            assert found.full_name == "Emp Test"

    def test_duplicate_employee_id_rejected(self, db, app):
        with app.app_context():
            from sqlalchemy.exc import IntegrityError
            import uuid
            uid = uuid.uuid4().hex[:8]
            user1 = _make_user(db, username=f"dup1_{uid}", email=f"dup1_{uid}@test.com")
            user2 = _make_user(db, username=f"dup2_{uid}", email=f"dup2_{uid}@test.com")
            dup_emp_id = f"DUP_{uid}"
            from app.models import Employee, AccountStatus
            emp1 = Employee(
                employee_id=dup_emp_id, full_name="Dup1",
                email=user1.email, user_id=user1.id, status=AccountStatus.ACTIVE,
            )
            db.session.add(emp1)
            db.session.commit()

            emp2 = Employee(
                employee_id=dup_emp_id,  # same — must fail
                full_name="Dup2",
                email=user2.email, user_id=user2.id, status=AccountStatus.ACTIVE,
            )
            db.session.add(emp2)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_employee_to_dict(self, db, app):
        with app.app_context():
            import uuid
            uid = uuid.uuid4().hex[:8]
            user = _make_user(db, username=f"dicttest_{uid}", email=f"dicttest_{uid}@test.com")
            emp = _make_employee(db, user, emp_id=f"DICT_{uid}", name="Dict Test")
            db.session.commit()
            d = emp.to_dict()
            assert "employee_id" in d
            assert "full_name" in d
            assert d["employee_id"] == emp.employee_id

    def test_admin_edit_employee_details(self, app, db):
        with app.app_context():
            from app.models import User, Employee, Department, WorkSchedule, AccountStatus
            from datetime import time
            import uuid
            uid = uuid.uuid4().hex[:6]
            admin = _make_user(db, role="admin", username=f"admin_ed_{uid}", email=f"admin_ed_{uid}@test.com")
            emp_user = _make_user(db, role="employee", username=f"emp_ed_{uid}", email=f"emp_ed_{uid}@test.com")
            dept = Department(name=f"Engineering_{uid}")
            sched = WorkSchedule(name=f"General_{uid}", start_time=time(9, 0), end_time=time(17, 0), total_hours=8.0)
            db.session.add_all([dept, sched])
            db.session.commit()

            emp = _make_employee(db, emp_user, emp_id=f"ED_{uid}", name="Initial Name")
            emp.department_id = dept.id
            emp.work_schedule_id = sched.id
            db.session.commit()
            emp_id_db = emp.id
            admin_username = admin.username
            dept_id_val = dept.id
            sched_id_val = sched.id

        client = app.test_client()
        # Log in as admin
        client.post("/auth/login", data={"identifier": admin_username, "password": "Test@1234"})

        # Submit edit update
        new_email = f"updated_{uid}@test.com"
        resp = client.post(f"/employees/{emp_id_db}/edit", data={
            "employee_id": f"NEWID_{uid}",
            "full_name": "Updated Employee Name",
            "email": new_email,
            "phone": "+91 98765 43210",
            "department_id": str(dept_id_val),
            "designation": "Lead Engineer",
            "work_schedule_id": str(sched_id_val),
            "status": "active",
            "date_joined": "2024-01-15",
        }, follow_redirects=True)
        assert resp.status_code == 200

        # Log out admin so subsequent tests start unauthenticated
        client.get("/auth/logout")

        with app.app_context():
            from app.models import Employee, User
            updated_emp = Employee.query.get(emp_id_db)
            assert updated_emp.full_name == "Updated Employee Name"
            assert updated_emp.employee_id == f"NEWID_{uid}"
            assert updated_emp.email == new_email
            assert updated_emp.phone == "+91 98765 43210"
            assert updated_emp.designation == "Lead Engineer"
            assert updated_emp.date_joined.strftime("%Y-%m-%d") == "2024-01-15"
            # Ensure linked user's email was synced for login
            assert updated_emp.user.email == new_email

    def test_admin_add_employee_auto_id_and_role_and_company(self, app, db):
        with app.app_context():
            from app.models import User, Employee, Department, WorkSchedule, UserRole
            import uuid
            uid = uuid.uuid4().hex[:6]
            admin = _make_user(db, role="admin", username=f"adm_add_{uid}", email=f"adm_add_{uid}@test.com")
            dept = Department(name=f"Design_{uid}")
            db.session.add(dept)
            db.session.commit()
            admin_username = admin.username
            dept_id_val = dept.id

        client = app.test_client()
        client.post("/auth/login", data={"identifier": admin_username, "password": "Test@1234"})

        # GET Add form: verify auto_emp_id is in response
        get_resp = client.get("/employees/add")
        assert get_resp.status_code == 200
        assert b"EMP" in get_resp.data

        # 1. Add employee with standard designation and custom company
        emp_email = f"emp_auto_{uid}@test.com"
        resp1 = client.post("/employees/add", data={
            "full_name": "Sequential Emp One",
            "email": emp_email,
            "company_name": "Acme Corp",
            "role": "Employee",
            "phone": "+91 12345 67890",
            "department_id": str(dept_id_val),
            "designation_choice": "Software Developer",
            "custom_designation": "",
            "status": "active",
            "date_joined": "2025-01-10",
            "username": f"user_auto_{uid}",
            "password": "Password@123",
        }, follow_redirects=True)
        assert resp1.status_code == 200

        with app.app_context():
            from app.models import Employee, User
            e1 = Employee.query.filter_by(email=emp_email).first()
            assert e1 is not None
            assert e1.employee_id.startswith("EMP")
            assert e1.designation == "Software Developer"
            assert e1.company_name == "Acme Corp"
            assert e1.user.role == UserRole.EMPLOYEE

        # 2. Add second employee with "Other" custom designation and Admin role
        admin_email2 = f"adm_auto2_{uid}@test.com"
        resp2 = client.post("/employees/add", data={
            "full_name": "Custom Desig Admin",
            "email": admin_email2,
            "company_name": "Initech Global",
            "role": "Admin",
            "phone": "+91 99999 88888",
            "department_id": str(dept_id_val),
            "designation_choice": "Other",
            "custom_designation": "Chief Happiness Officer",
            "status": "active",
            "date_joined": "2025-02-01",
            "username": f"user_adm2_{uid}",
            "password": "Password@123",
        }, follow_redirects=True)
        assert resp2.status_code == 200

        with app.app_context():
            from app.models import Employee, User
            e2 = Employee.query.filter_by(email=admin_email2).first()
            assert e2 is not None
            assert e2.designation == "Chief Happiness Officer"
            assert e2.company_name == "Initech Global"
            assert e2.user.role == UserRole.ADMIN

        client.get("/auth/logout")

    def test_public_registration_disabled(self, app):
        client = app.test_client()
        resp = client.get("/auth/register", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

        # POST should also redirect to login with message
        resp_post = client.post("/auth/register", data={
            "username": "selfreg",
            "full_name": "Self Reg",
            "email": "selfreg@test.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
        }, follow_redirects=True)
        assert resp_post.status_code == 200
        assert b"Public registration is disabled" in resp_post.data


# ── Attendance Tests ──────────────────────────────────────────────────────────

class TestAttendance:
    def _setup(self, db, app):
        import uuid
        uid = uuid.uuid4().hex[:8]
        user = _make_user(db, username=f"attest_{uid}", email=f"attest_{uid}@test.com")
        emp = _make_employee(db, user, emp_id=f"ATT_{uid}", name="Att Test")
        db.session.commit()
        return emp

    def test_check_in_creates_record(self, db, app):
        with app.app_context():
            from app.models import Attendance, AttendanceStatus
            emp = self._setup(db, app)
            today = date.today()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            att = Attendance(
                employee_id=emp.id,
                date=today,
                check_in=now,
                status=AttendanceStatus.PRESENT,
            )
            db.session.add(att)
            db.session.commit()
            found = Attendance.query.filter_by(employee_id=emp.id, date=today).first()
            assert found is not None
            assert found.check_in is not None

    def test_checkout_calculates_duration(self, db, app):
        with app.app_context():
            from app.models import Attendance, AttendanceStatus
            emp = self._setup(db, app)
            ci = datetime(2025, 1, 10, 9, 0, 0)
            co = datetime(2025, 1, 10, 17, 0, 0)
            att = Attendance(
                employee_id=emp.id,
                date=date(2025, 1, 10),
                check_in=ci,
                check_out=co,
                status=AttendanceStatus.PRESENT,
            )
            db.session.add(att)
            db.session.commit()
            att.recalculate()
            assert att.total_duration_minutes == 480.0  # 8 hours

    def test_net_work_time_subtracts_breaks(self, db, app):
        with app.app_context():
            from app.models import Attendance, AttendanceStatus
            emp = self._setup(db, app)
            ci = datetime(2025, 1, 11, 9, 0, 0)
            co = datetime(2025, 1, 11, 17, 0, 0)
            att = Attendance(
                employee_id=emp.id,
                date=date(2025, 1, 11),
                check_in=ci,
                check_out=co,
                status=AttendanceStatus.PRESENT,
            )
            db.session.add(att)
            db.session.commit()

            from app.models import Break, BreakCategory
            brk = Break(
                attendance_id=att.id,
                employee_id=emp.id,
                category=BreakCategory.LUNCH,
                start_time=datetime(2025, 1, 11, 13, 0, 0),
            )
            brk.close(datetime(2025, 1, 11, 13, 30, 0))
            db.session.add(brk)
            db.session.commit()

            att.recalculate()
            assert att.break_duration_minutes == 30.0
            assert att.net_working_minutes == 450.0  # 480 - 30

    def test_dynamic_break_and_working_hours_calculation(self, db, app):
        """
        Verify the exact user scenario:
        Check-In: 2:00 PM (14:00)
        Break: 3:00 PM (15:00) to 3:17 PM (15:17) -> 17 minutes
        Check-Out: 6:00 PM (18:00)
        Total Working Period: 4 hours (240 min)
        Break Duration: 17 min
        Net Working Hours: 3 hours 43 min (223 min)
        """
        with app.app_context():
            from app.models import Attendance, Break, BreakCategory, AttendanceStatus
            emp = self._setup(db, app)
            d = date(2025, 2, 10)

            ci = datetime(2025, 2, 10, 14, 0, 0)
            co = datetime(2025, 2, 10, 18, 0, 0)

            att = Attendance(employee_id=emp.id, date=d, status=AttendanceStatus.PRESENT, check_in=ci, check_out=co)
            db.session.add(att)
            db.session.flush()

            # 17-minute break
            brk = Break(
                attendance_id=att.id, employee_id=emp.id,
                category=BreakCategory.TEA,
                start_time=datetime(2025, 2, 10, 15, 0, 0)
            )
            brk.close(datetime(2025, 2, 10, 15, 17, 0))
            db.session.add(brk)
            db.session.commit()

            att.recalculate()
            assert brk.duration_minutes == 17.0
            assert att.total_duration_minutes == 240.0  # 4 hours
            assert att.break_duration_minutes == 17.0
            assert att.net_working_minutes == 223.0    # 3 hours 43 minutes

    def test_live_elapsed_working_time_during_active_session(self, db, app):
        """
        Verify that an active employee (checked in, not yet checked out)
        has live gross and net working minutes calculated dynamically.
        """
        with app.app_context():
            from app.models import Attendance, Break, BreakCategory, AttendanceStatus
            emp = self._setup(db, app)
            d = date(2025, 2, 11)

            # Checked in at 14:00 (2:00 PM)
            ci = datetime(2025, 2, 11, 14, 0, 0)
            att = Attendance(employee_id=emp.id, date=d, status=AttendanceStatus.PRESENT, check_in=ci)
            db.session.add(att)
            db.session.flush()

            # 1. At 15:00 (3:00 PM) with no breaks: exactly 60m gross & net
            t1 = datetime(2025, 2, 11, 15, 0, 0)
            assert att.get_elapsed_working_minutes(t1) == 60.0
            assert att.get_total_break_minutes(t1) == 0.0
            assert att.get_net_working_minutes(t1) == 60.0

            # 2. Start a break at 15:00
            brk = Break(
                attendance_id=att.id, employee_id=emp.id,
                category=BreakCategory.LUNCH,
                start_time=t1
            )
            db.session.add(brk)
            db.session.commit()

            # At 15:17 (active break in progress for 17m):
            t2 = datetime(2025, 2, 11, 15, 17, 0)
            assert round(att.get_elapsed_working_minutes(t2)) == 77.0
            assert round(att.get_total_break_minutes(t2)) == 17.0
            assert round(att.get_net_working_minutes(t2)) == 60.0

            # End break at 15:17
            brk.close(t2)
            db.session.commit()

            # At 16:00: total elapsed 120m, break 17m, net 103m (1h 43m)
            t3 = datetime(2025, 2, 11, 16, 0, 0)
            assert att.get_elapsed_working_minutes(t3) == 120.0
            assert att.get_total_break_minutes(t3) == 17.0
            assert att.get_net_working_minutes(t3) == 103.0

    def test_duplicate_checkin_prevented(self, db, app):
        with app.app_context():
            from app.models import Attendance, AttendanceStatus
            from sqlalchemy.exc import IntegrityError
            emp = self._setup(db, app)
            d = date(2025, 2, 1)
            att1 = Attendance(employee_id=emp.id, date=d, status=AttendanceStatus.PRESENT,
                              check_in=datetime(2025, 2, 1, 9, 0))
            db.session.add(att1)
            db.session.commit()

            att2 = Attendance(employee_id=emp.id, date=d, status=AttendanceStatus.PRESENT,
                              check_in=datetime(2025, 2, 1, 9, 5))
            db.session.add(att2)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_no_negative_duration(self, db, app):
        with app.app_context():
            from app.models import Attendance, AttendanceStatus
            emp = self._setup(db, app)
            # checkout before checkin — should yield 0
            ci = datetime(2025, 1, 15, 17, 0, 0)
            co = datetime(2025, 1, 15, 9, 0, 0)
            att = Attendance(employee_id=emp.id, date=date(2025, 1, 15),
                             check_in=ci, check_out=co, status=AttendanceStatus.PRESENT)
            db.session.add(att)
            db.session.commit()
            att.recalculate()
            assert att.total_duration_minutes == 0.0


# ── Break Tests ───────────────────────────────────────────────────────────────

class TestBreaks:
    def test_break_duration_calculated(self, app):
        from app.models import Break, BreakCategory
        brk = Break(
            attendance_id=1, employee_id=1,
            category=BreakCategory.TEA,
            start_time=datetime(2025, 1, 10, 10, 0, 0),
        )
        brk.close(datetime(2025, 1, 10, 10, 15, 0))
        assert brk.duration_minutes == 15.0

    def test_break_no_negative_duration(self, app):
        from app.models import Break, BreakCategory
        brk = Break(
            attendance_id=1, employee_id=1,
            category=BreakCategory.COFFEE,
            start_time=datetime(2025, 1, 10, 11, 30, 0),
        )
        brk.close(datetime(2025, 1, 10, 11, 15, 0))  # end before start
        assert brk.duration_minutes == 0.0


# ── Leave Tests ───────────────────────────────────────────────────────────────

class TestLeave:
    def test_leave_request_created(self, db, app):
        with app.app_context():
            import uuid
            uid = uuid.uuid4().hex[:8]
            user = _make_user(db, username=f"leavetest_{uid}", email=f"leavetest_{uid}@test.com")
            emp = _make_employee(db, user, emp_id=f"LV_{uid}", name="Leave Test")
            db.session.commit()

            from app.models import LeaveRequest, LeaveType, LeaveStatus, LeaveDayType
            lr = LeaveRequest(
                employee_id=emp.id,
                leave_type=LeaveType.ANNUAL,
                day_type=LeaveDayType.FULL_DAY,
                start_date=date(2025, 3, 10),
                end_date=date(2025, 3, 12),
                reason="Vacation",
                status=LeaveStatus.PENDING,
            )
            db.session.add(lr)
            db.session.commit()
            assert lr.id is not None
            assert lr.status == LeaveStatus.PENDING

    def test_leave_approval_changes_status(self, db, app):
        with app.app_context():
            import uuid
            uid = uuid.uuid4().hex[:8]
            user = _make_user(db, username=f"leaveapprove_{uid}", email=f"leaveapprove_{uid}@test.com")
            emp = _make_employee(db, user, emp_id=f"LV2_{uid}", name="Leave Approve")
            db.session.commit()

            from app.models import LeaveRequest, LeaveType, LeaveStatus, LeaveDayType
            lr = LeaveRequest(
                employee_id=emp.id,
                leave_type=LeaveType.SICK,
                day_type=LeaveDayType.FULL_DAY,
                start_date=date(2025, 4, 1),
                end_date=date(2025, 4, 2),
                reason="Illness",
                status=LeaveStatus.PENDING,
            )
            db.session.add(lr)
            db.session.commit()

            lr.status = LeaveStatus.APPROVED
            db.session.commit()
            assert lr.status == LeaveStatus.APPROVED

    def test_leave_status_email_notification(self, db, app):
        with app.app_context():
            from app.email import send_leave_status_email
            from app.extensions import mail
            from app.models import LeaveRequest, LeaveType, LeaveStatus, LeaveDayType
            import uuid

            uid = uuid.uuid4().hex[:8]
            user = _make_user(db, username=f"mailuser_{uid}", email=f"mailuser_{uid}@test.local")
            emp = _make_employee(db, user, emp_id=f"MAIL_{uid}", name="Mail Test User")
            db.session.commit()

            lr = LeaveRequest(
                employee_id=emp.id,
                leave_type=LeaveType.CASUAL,
                day_type=LeaveDayType.FULL_DAY,
                start_date=date(2025, 5, 1),
                end_date=date(2025, 5, 2),
                reason="Family Event",
                status=LeaveStatus.APPROVED,
            )
            db.session.add(lr)
            db.session.commit()

            with mail.record_messages() as outbox:
                success = send_leave_status_email(lr)
                assert success is True
                assert len(outbox) == 1
                msg = outbox[0]
                assert msg.recipients == [emp.email]
                assert "APPROVED" in msg.subject or "Approved" in msg.subject
                assert "Family Event" not in msg.subject
                assert emp.full_name in msg.body
                assert "Approved" in msg.body or "APPROVED" in msg.body

    def test_admin_approve_and_reject_leave_routes(self, app, db):
        with app.app_context():
            from app.models import User, Employee, LeaveRequest, LeaveType, LeaveStatus, LeaveDayType
            import uuid
            uid = uuid.uuid4().hex[:6]
            admin = _make_user(db, role="admin", username=f"adm_lr_{uid}", email=f"adm_lr_{uid}@test.com")
            emp_user = _make_user(db, role="employee", username=f"emp_lr_{uid}", email=f"emp_lr_{uid}@test.com")
            emp = _make_employee(db, emp_user, emp_id=f"ELR_{uid}", name="Leave Emp")
            db.session.commit()

            lr1 = LeaveRequest(
                employee_id=emp.id,
                leave_type=LeaveType.CASUAL,
                day_type=LeaveDayType.FULL_DAY,
                start_date=date(2025, 6, 1),
                end_date=date(2025, 6, 2),
                reason="Medical appointment",
                status=LeaveStatus.PENDING,
            )
            lr2 = LeaveRequest(
                employee_id=emp.id,
                leave_type=LeaveType.SICK,
                day_type=LeaveDayType.HALF_DAY,
                start_date=date(2025, 6, 10),
                end_date=date(2025, 6, 10),
                reason="Doctor Visit",
                status=LeaveStatus.PENDING,
            )
            db.session.add_all([lr1, lr2])
            db.session.commit()
            lr1_id = lr1.id
            lr2_id = lr2.id
            admin_username = admin.username

        client = app.test_client()
        client.post("/auth/login", data={"identifier": admin_username, "password": "Test@1234"})

        # Test Approve
        resp_approve = client.post(f"/leave/{lr1_id}/review", data={
            "action": "approve",
            "admin_notes": "Approved by manager",
        }, follow_redirects=True)
        assert resp_approve.status_code == 200

        with app.app_context():
            from app.models import LeaveRequest, LeaveStatus
            req1 = db.session.get(LeaveRequest, lr1_id)
            assert req1.status == LeaveStatus.APPROVED
            assert req1.admin_notes == "Approved by manager"

        # Test Reject
        resp_reject = client.post(f"/leave/{lr2_id}/review", data={
            "action": "reject",
            "admin_notes": "Coverage not available",
        }, follow_redirects=True)
        assert resp_reject.status_code == 200

        with app.app_context():
            from app.models import LeaveRequest, LeaveStatus
            req2 = db.session.get(LeaveRequest, lr2_id)
            assert req2.status == LeaveStatus.REJECTED
            assert req2.admin_notes == "Coverage not available"

        client.get("/auth/logout")


# ── ML Preprocessing Tests ────────────────────────────────────────────────────

class TestMLPreprocessing:
    def test_empty_data_returns_empty_df(self):
        from app.ml.preprocessing import build_feature_dataframe
        df = build_feature_dataframe([])
        assert df.empty

    def test_feature_columns_present(self, db, app):
        from app.ml.preprocessing import build_feature_dataframe, FEATURE_COLS
        from app.models import Break, Attendance, Employee, BreakCategory, AttendanceStatus
        from unittest.mock import MagicMock

        # Create mock objects
        brk = MagicMock(spec=Break)
        brk.end_time = datetime(2025, 1, 10, 13, 30)
        brk.duration_minutes = 30.0
        brk.start_time = datetime(2025, 1, 10, 13, 0)
        brk.category = BreakCategory.LUNCH
        brk.id = 1

        att = MagicMock(spec=Attendance)
        att.date = date(2025, 1, 10)
        att.id = 1

        emp = MagicMock(spec=Employee)
        emp.id = 1
        emp.work_schedule = None

        df = build_feature_dataframe([(brk, att, emp)])
        if not df.empty:
            for col in FEATURE_COLS:
                assert col in df.columns

    def test_train_with_empty_data(self):
        from app.ml.train import train_and_evaluate
        result = train_and_evaluate([])
        assert result["model"] is None
        assert result["n_samples"] == 0

    def test_predict_returns_positive_value(self):
        from app.ml.predict import predict_break_duration
        train_result = {
            "model": None,
            "category_averages": {"Lunch": 30.0, "Tea": 10.0},
            "n_samples": 3,
            "baseline_mae": None,
            "baseline_rmse": None,
            "rf_mae": None,
            "rf_rmse": None,
            "status": "Test",
        }
        result = predict_break_duration(
            train_result=train_result,
            category="Lunch",
            weekday=0, hour_of_day=13,
            scheduled_hours=8.0,
            prior_breaks_today=0,
            rolling_avg=30.0,
        )
        assert result["predicted_break_minutes"] > 0

    def test_available_time_calculation(self):
        from app.ml.predict import calculate_available_time
        scheduled_end = datetime(2025, 1, 10, 17, 0, 0)
        current = datetime(2025, 1, 10, 14, 0, 0)
        # 3 hours remaining, 20 min predicted break
        avail = calculate_available_time(scheduled_end, current, 60.0, 20.0)
        assert avail == 160.0  # 180 - 20

    def test_available_time_past_shift(self):
        from app.ml.predict import calculate_available_time
        scheduled_end = datetime(2025, 1, 10, 17, 0, 0)
        current = datetime(2025, 1, 10, 18, 0, 0)  # past shift end
        avail = calculate_available_time(scheduled_end, current, 0.0, 0.0)
        assert avail == 0.0


# ── Security & Authorization Tests ──────────────────────────────────────────

class TestSecurityAndAuthorization:
    """Security tests verifying RBAC, secure headers, safe redirect, and access control."""

    def test_security_headers_present(self, app):
        client = app.test_client()
        resp = client.get("/auth/login")
        assert resp.status_code == 200
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"

    def test_unauthenticated_user_cannot_access_employee_dashboard(self, app):
        client = app.test_client()
        resp = client.get("/dashboard/employee", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_unauthenticated_user_cannot_access_admin_dashboard(self, app):
        client = app.test_client()
        resp = client.get("/dashboard/admin", follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

    def test_employee_cannot_access_admin_dashboard(self, app, db):
        with app.app_context():
            from app.models import User, UserRole
            from werkzeug.security import generate_password_hash
            emp_user = User(
                username="test_emp_sec_x",
                email="emp_sec_x@example.com",
                password_hash=generate_password_hash("EmpPass@123"),
                role=UserRole.EMPLOYEE,
                is_active=True,
            )
            db.session.add(emp_user)
            db.session.commit()

        client = app.test_client()
        client.post("/auth/login", data={"identifier": "test_emp_sec_x", "password": "EmpPass@123"})

        resp = client.get("/dashboard/admin")
        assert resp.status_code == 403

    def test_employee_cannot_access_employee_management(self, app, db):
        with app.app_context():
            from app.models import User, UserRole
            from werkzeug.security import generate_password_hash
            emp_user = User(
                username="test_emp_sec2_x",
                email="emp_sec2_x@example.com",
                password_hash=generate_password_hash("EmpPass@123"),
                role=UserRole.EMPLOYEE,
                is_active=True,
            )
            db.session.add(emp_user)
            db.session.commit()

        client = app.test_client()
        client.post("/auth/login", data={"identifier": "test_emp_sec2_x", "password": "EmpPass@123"})

        resp = client.get("/employees/")
        assert resp.status_code == 403

    def test_open_redirect_protection_on_login(self, app, db):
        with app.app_context():
            from app.models import User, UserRole
            from werkzeug.security import generate_password_hash
            user = User(
                username="test_login_redir_x",
                email="redir_x@example.com",
                password_hash=generate_password_hash("Redir@123"),
                role=UserRole.EMPLOYEE,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()

        client = app.test_client()
        # Malicious next URL trying open redirect
        resp = client.post(
            "/auth/login?next=//evil.com",
            data={"identifier": "test_login_redir_x", "password": "Redir@123"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "//evil.com" not in resp.headers["Location"]
        assert "/dashboard/employee" in resp.headers["Location"]


class TestHolidayManagement:
    """Tests for the Holiday Management System with 2026 Interactive Calendar."""

    def test_holiday_model_and_to_dict(self, app, db):
        with app.app_context():
            from app.models import Holiday
            from datetime import date
            h = Holiday(
                holiday_name="New Year Day",
                holiday_date=date(2026, 1, 1),
                description="Global New Year celebration",
            )
            db.session.add(h)
            db.session.commit()

            assert h.id is not None
            d = h.to_dict()
            assert d["holiday_name"] == "New Year Day"
            assert d["holiday_date"] == "2026-01-01"
            assert d["description"] == "Global New Year celebration"

    def test_admin_can_access_and_add_holiday(self, app, db):
        with app.app_context():
            from app.models import User, UserRole, Holiday
            from werkzeug.security import generate_password_hash
            from datetime import date
            admin_user = User(
                username="test_admin_h1",
                email="admin_h1@example.com",
                password_hash=generate_password_hash("AdminPass@123"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.session.add(admin_user)
            db.session.commit()

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": "test_admin_h1", "password": "AdminPass@123"})

        # Access Holiday Management page
        resp = client.get("/holidays/")
        assert resp.status_code == 200
        assert b"Holiday Management" in resp.data or b"2026 Calendar" in resp.data

        # Add holiday
        add_resp = client.post("/holidays/add", data={
            "holiday_name": "Republic Day",
            "holiday_date": "2026-01-26",
            "description": "National holiday in India",
        }, follow_redirects=True)
        assert add_resp.status_code == 200
        assert b"Republic Day" in add_resp.data

        # Verify duplicate date rejection
        dup_resp = client.post("/holidays/add", data={
            "holiday_name": "Another Republic Day",
            "holiday_date": "2026-01-26",
            "description": "Duplicate should fail",
        }, follow_redirects=True)
        assert dup_resp.status_code == 200
        assert b"already exists on" in dup_resp.data

    def test_admin_can_edit_and_delete_holiday(self, app, db):
        with app.app_context():
            from app.models import Holiday, User, UserRole
            from datetime import date
            from werkzeug.security import generate_password_hash
            admin_user = User(
                username="test_admin_h2",
                email="admin_h2@example.com",
                password_hash=generate_password_hash("AdminPass@123"),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.session.add(admin_user)
            db.session.commit()

            h = Holiday(
                holiday_name="Independence Day",
                holiday_date=date(2026, 8, 15),
                description="Original description",
            )
            db.session.add(h)
            db.session.commit()
            hid = h.id

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": "test_admin_h2", "password": "AdminPass@123"})

        # Edit holiday
        edit_resp = client.post(f"/holidays/{hid}/edit", data={
            "holiday_name": "Independence Day India",
            "holiday_date": "2026-08-15",
            "description": "Updated national celebration description",
        }, follow_redirects=True)
        assert edit_resp.status_code == 200
        assert b"Independence Day India" in edit_resp.data

        # Delete holiday
        del_resp = client.post(f"/holidays/{hid}/delete", follow_redirects=True)
        assert del_resp.status_code == 200
        assert b"deleted successfully" in del_resp.data

        with app.app_context():
            from app.models import Holiday
            assert db.session.get(Holiday, hid) is None

    def test_employee_can_view_calendar_but_cannot_mutate(self, app, db):
        with app.app_context():
            from app.models import User, UserRole
            from werkzeug.security import generate_password_hash
            emp_user = User(
                username="test_emp_h1",
                email="emp_h1@example.com",
                password_hash=generate_password_hash("EmpPass@123"),
                role=UserRole.EMPLOYEE,
                is_active=True,
            )
            db.session.add(emp_user)
            db.session.commit()

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": "test_emp_h1", "password": "EmpPass@123"})

        # Employee can view calendar
        view_resp = client.get("/holidays/")
        assert view_resp.status_code == 200
        assert b"2026 Calendar" in view_resp.data

        # Employee JSON API
        api_resp = client.get("/holidays/api/events?year=2026")
        assert api_resp.status_code == 200
        assert "holidays" in api_resp.get_json()

        # Employee cannot add holiday (redirects with flash)
        add_resp = client.post("/holidays/add", data={
            "holiday_name": "Unauthorized Holiday",
            "holiday_date": "2026-05-01",
        }, follow_redirects=True)
        assert add_resp.status_code == 200
        assert b"Access denied" in add_resp.data

    def test_today_holiday_detection_on_employee_dashboard(self, app, db):
        with app.app_context():
            from app.models import User, UserRole, Employee, Department, Holiday
            from werkzeug.security import generate_password_hash
            from app.time_utils import local_today
            
            dept = Department.query.first()
            if not dept:
                dept = Department(name="IT Dept")
                db.session.add(dept)
                db.session.commit()

            user = User(
                username="test_holiday_user",
                email="holiday_tester@example.com",
                password_hash=generate_password_hash("Pass@123"),
                role=UserRole.EMPLOYEE,
                is_active=True,
            )
            db.session.add(user)
            db.session.flush()

            emp = Employee(
                employee_id="EMP-H99",
                full_name="Holiday Tester",
                email="holiday_tester@example.com",
                department_id=dept.id,
                user_id=user.id,
            )
            db.session.add(emp)

            # Insert holiday for today
            today = local_today()
            h_today = Holiday(
                holiday_name="Company Founders Day",
                holiday_date=today,
                description="Annual company celebration",
            )
            db.session.add(h_today)
            db.session.commit()

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": "test_holiday_user", "password": "Pass@123"})

        resp = client.get("/dashboard/employee")
        assert resp.status_code == 200
        assert b"TODAY IS A HOLIDAY!" in resp.data
        assert b"Company Founders Day" in resp.data



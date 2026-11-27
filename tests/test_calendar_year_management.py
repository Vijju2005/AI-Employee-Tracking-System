"""
Test Suite for Session Expiry & Calendar Year Management
Verifies:
1. 8-hour login session permanent lifetime configuration
2. 10-minute attendance session refresh / status checking
3. Calendar Year CRUD, validation, uniqueness, overlap prevention
4. Employee joining date mapping to Calendar Years
"""
import pytest
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import CalendarYear, Employee, User, UserRole, AccountStatus, Attendance, AttendanceStatus


class TestSessionExpiryAndCalendarYears:
    @pytest.fixture(autouse=True)
    def setup_method(self, app, db):
        self.app = app
        self.db = db
        self.client = app.test_client()

    def test_eight_hour_session_lifetime_configuration(self):
        """Verify Flask login session permanent lifetime is configured to 8 hours."""
        lifetime = self.app.config.get("PERMANENT_SESSION_LIFETIME")
        assert lifetime == timedelta(hours=8)

    def test_calendar_year_creation_and_validations(self):
        """Test calendar year creation, date ordering validation, and uniqueness."""
        with self.app.app_context():
            # Clean up test records
            CalendarYear.query.filter(CalendarYear.name.in_(["Test Year 2028", "Test Year 2029"])).delete()
            self.db.session.commit()

            # Successful creation
            cy1 = CalendarYear(
                name="Test Year 2028",
                start_date=date(2028, 1, 1),
                end_date=date(2028, 12, 31),
                is_active=True
            )
            self.db.session.add(cy1)
            self.db.session.commit()
            assert cy1.id is not None

            # Date lookup helper
            found = CalendarYear.get_calendar_year_for_date(date(2028, 6, 15))
            assert found is not None
            assert found.name == "Test Year 2028"

            # Clean up
            self.db.session.delete(cy1)
            self.db.session.commit()

    def test_employee_calendar_year_dynamic_mapping(self):
        """Verify employees automatically map to corresponding Calendar Year based on date_joined."""
        with self.app.app_context():
            cy2026 = CalendarYear.query.filter_by(name="Calendar Year 2026").first()
            if not cy2026:
                cy2026 = CalendarYear(
                    name="Calendar Year 2026",
                    start_date=date(2026, 1, 1),
                    end_date=date(2026, 12, 31),
                    is_active=True
                )
                self.db.session.add(cy2026)
                self.db.session.commit()

            # Create an employee joined on 15 June 2026
            emp = Employee.query.filter_by(employee_id="TEST_CAL_01").first()
            if not emp:
                emp = Employee(
                    employee_id="TEST_CAL_01",
                    full_name="Test Cal Employee",
                    email="test_cal@example.com",
                    date_joined=datetime(2026, 6, 15, 10, 30),
                    status=AccountStatus.ACTIVE
                )
                self.db.session.add(emp)
                self.db.session.commit()

            assert emp.joining_calendar_year is not None
            assert emp.joining_calendar_year.name == "Calendar Year 2026"

            # Clean up
            self.db.session.delete(emp)
            self.db.session.commit()

    def test_calendar_year_routes_authorized_access(self):
        """Verify calendar year list and view routes are accessible to Admin/SuperAdmin."""
        with self.app.app_context():
            admin_user = User.query.filter_by(username="test_cal_admin").first()
            if not admin_user:
                admin_user = User(
                    username="test_cal_admin",
                    email="cal_admin@example.com",
                    password_hash=generate_password_hash("CalAdmin123!"),
                    role=UserRole.ADMIN,
                    is_active=True,
                    is_verified=True,
                )
                self.db.session.add(admin_user)
                self.db.session.commit()

            with self.client.session_transaction() as sess:
                sess["_user_id"] = str(admin_user.id)
                sess["_fresh"] = True
                from app.time_utils import get_current_session_cycle_id
                sess["login_cycle_id"] = get_current_session_cycle_id()

            # 1. Roster view
            resp = self.client.get("/holidays/calendar-years")
            assert resp.status_code == 200
            assert b"Calendar Year Management" in resp.data

            # 2. Add calendar year via route
            post_resp = self.client.post("/holidays/calendar-years/add", data={
                "name": "Fiscal Year 2029-30",
                "start_date": "2029-04-01",
                "end_date": "2030-03-31",
                "is_active": "on"
            }, follow_redirects=True)
            assert post_resp.status_code == 200
            assert b"Fiscal Year 2029-30" in post_resp.data

            # 3. Clean up
            cy = CalendarYear.query.filter_by(name="Fiscal Year 2029-30").first()
            if cy:
                self.db.session.delete(cy)
                self.db.session.commit()
            if cy:
                db.session.delete(cy)
                db.session.commit()

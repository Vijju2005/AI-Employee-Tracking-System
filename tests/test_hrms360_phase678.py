import pytest
import uuid
from datetime import date
from werkzeug.security import generate_password_hash
from app.models import (
    User, UserRole, Department, Designation, LeaveTypePolicy, WorkSchedule,
    JobOpening, JobCandidate, Employee, AccountStatus
)

class TestHRMS360Phase678Suite:
    """Automated integration tests for Phases 6, 7 and 8."""

    def test_employee_grid_view_and_details_page(self, app, db):
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            admin = User(
                username=f"adm_grid_{uid}",
                email=f"adm_grid_{uid}@test.com",
                password_hash=generate_password_hash("AdminPass123!"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            emp = Employee(
                employee_id=f"EMP{uid}".upper()[:10],
                full_name=f"Employee {uid}",
                email=f"emp_{uid}@test.com",
                status=AccountStatus.ACTIVE,
            )
            db.session.add_all([admin, emp])
            db.session.commit()
            emp_id = emp.id

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"adm_grid_{uid}", "password": "AdminPass123!"}, follow_redirects=True)

        # 1. Test Grid View
        resp = client.get("/employees/?view=grid")
        assert resp.status_code == 200
        assert b"Employee Directory" in resp.data

        # 2. Test Employee Details View
        view_resp = client.get(f"/employees/{emp_id}/view")
        assert view_resp.status_code == 200
        assert b"Personnel &amp; Job Record" in view_resp.data or b"Personnel & Job Record" in view_resp.data

    def test_department_and_designation_crud(self, app, db):
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            admin = User(
                username=f"adm_dept_{uid}",
                email=f"adm_dept_{uid}@test.com",
                password_hash=generate_password_hash("AdminPass123!"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.session.add(admin)
            db.session.commit()

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"adm_dept_{uid}", "password": "AdminPass123!"}, follow_redirects=True)

        # 1. Add Department
        dept_name = f"Dept_{uid}"
        d_resp = client.post("/employees/departments/add", data={
            "name": dept_name,
            "description": "Department test"
        }, follow_redirects=True)
        assert d_resp.status_code == 200

        with app.app_context():
            dept = Department.query.filter_by(name=dept_name).first()
            assert dept is not None
            dept_id = dept.id

        # 2. Add Designation
        desig_name = f"Desig_{uid}"
        desig_resp = client.post("/employees/designations/add", data={
            "name": desig_name,
            "department_id": str(dept_id),
            "description": "Designation test"
        }, follow_redirects=True)
        assert desig_resp.status_code == 200

        with app.app_context():
            desig = Designation.query.filter_by(name=desig_name).first()
            assert desig is not None

    def test_schedules_and_leave_policies(self, app, db):
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            admin = User(
                username=f"adm_sched_{uid}",
                email=f"adm_sched_{uid}@test.com",
                password_hash=generate_password_hash("AdminPass123!"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.session.add(admin)
            db.session.commit()

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"adm_sched_{uid}", "password": "AdminPass123!"}, follow_redirects=True)

        # 1. Add Shift Schedule
        sched_name = f"Shift_{uid}"
        s_resp = client.post("/attendance/schedules/add", data={
            "name": sched_name,
            "start_time": "08:00",
            "end_time": "16:00",
            "description": "Morning 8-4"
        }, follow_redirects=True)
        assert s_resp.status_code == 200

        with app.app_context():
            sched = WorkSchedule.query.filter_by(name=sched_name).first()
            assert sched is not None

        # 2. Add Leave Policy
        pol_name = f"Policy_{uid}"
        pol_code = f"POL_{uid.upper()}"
        p_resp = client.post("/leave/policies/add", data={
            "name": pol_name,
            "code": pol_code,
            "annual_allocation_days": "15",
            "carry_forward_max_days": "5",
            "is_paid": "on",
            "description": "Test policy"
        }, follow_redirects=True)
        assert p_resp.status_code == 200

        with app.app_context():
            pol = LeaveTypePolicy.query.filter_by(code=pol_code).first()
            assert pol is not None

    def test_dedicated_dashboards_and_recruitment_crud(self, app, db):
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            admin = User(
                username=f"adm_dash_{uid}",
                email=f"adm_dash_{uid}@test.com",
                password_hash=generate_password_hash("AdminPass123!"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            db.session.add(admin)
            db.session.commit()

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"adm_dash_{uid}", "password": "AdminPass123!"}, follow_redirects=True)

        # 1. HR Dashboard
        hr_resp = client.get("/dashboard/hr")
        assert hr_resp.status_code == 200
        assert b"HR Analytics Dashboard" in hr_resp.data

        # 2. Attendance Dashboard
        att_resp = client.get("/dashboard/attendance")
        assert att_resp.status_code == 200
        assert b"Attendance &amp; Punctuality Dashboard" in att_resp.data or b"Attendance & Punctuality Dashboard" in att_resp.data

        # 3. Recruitment Dashboard & CRUD
        rec_resp = client.get("/dashboard/recruitment")
        assert rec_resp.status_code == 200

        # Add Job Opening
        job_title = f"Role_{uid}"
        j_resp = client.post("/dashboard/recruitment/openings/add", data={
            "title": job_title,
            "positions": "1",
            "job_type": "Full-Time",
            "experience_level": "Senior",
            "description": "Recruitment test"
        }, follow_redirects=True)
        assert j_resp.status_code == 200

        with app.app_context():
            job = JobOpening.query.filter_by(title=job_title).first()
            assert job is not None
            job_id = job.id

        # Add Candidate
        cand_resp = client.post("/dashboard/recruitment/candidates/add", data={
            "job_opening_id": str(job_id),
            "full_name": f"Candidate_{uid}",
            "email": f"cand_{uid}@example.com",
            "phone": "+91 99999 88888",
            "status": "screening"
        }, follow_redirects=True)
        assert cand_resp.status_code == 200

        with app.app_context():
            cand = JobCandidate.query.filter_by(email=f"cand_{uid}@example.com").first()
            assert cand is not None
            cand_id = cand.id

        # Update Candidate Status
        u_resp = client.post(f"/dashboard/recruitment/candidates/{cand_id}/status", data={
            "status": "interviewing"
        }, follow_redirects=True)
        assert u_resp.status_code == 200

        with app.app_context():
            cand_after = db.session.get(JobCandidate, cand_id)
            assert cand_after.status == "interviewing"

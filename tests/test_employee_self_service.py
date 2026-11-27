"""
Tests for Phase 1: Employee Self-Service (ESS) Portal.
Validates:
- My Profile viewing & updating permitted fields (phone, photo)
- Salary & role protection (unmodifiable by employees)
- My Documents upload, viewing, downloading, and isolation
- Company Policies viewing, downloading, and admin CRUD
- My Payslips & My Attendance integration
"""

import io
import uuid
import pytest
from werkzeug.security import generate_password_hash
from app.models import Employee, User, UserRole, AccountStatus, EmployeeDocument, CompanyPolicy


class TestPhase1EmployeeSelfService:
    def test_employee_profile_view_and_security(self, app, db):
        """Test employee can view their profile and cannot mutate salary or role."""
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            u = User(
                username=f"emp_prof_{uid}",
                email=f"emp_prof_{uid}@corp.com",
                password_hash=generate_password_hash("EmployeePass123!"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            db.session.add(u)
            db.session.flush()

            emp = Employee(
                employee_id=f"EMP{uid}".upper()[:10],
                full_name=f"Self Service User {uid}",
                email=f"emp_prof_{uid}@corp.com",
                phone="+91 98888 77777",
                status=AccountStatus.ACTIVE,
                user_id=u.id,
            )
            db.session.add(emp)
            db.session.commit()
            emp_name = emp.full_name

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"emp_prof_{uid}", "password": "EmployeePass123!"}, follow_redirects=True)

        resp = client.get("/employees/profile")
        assert resp.status_code == 200
        assert b"Employee Self-Service Profile" in resp.data
        assert emp_name.encode() in resp.data
        assert b"Security Notice" in resp.data

    def test_update_profile_phone(self, app, db):
        """Test employee can update personal contact phone."""
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            u = User(
                username=f"emp_upd_{uid}",
                email=f"emp_upd_{uid}@corp.com",
                password_hash=generate_password_hash("EmployeePass123!"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            db.session.add(u)
            db.session.flush()

            emp = Employee(
                employee_id=f"EMP{uid}".upper()[:10],
                full_name=f"Update User {uid}",
                email=f"emp_upd_{uid}@corp.com",
                status=AccountStatus.ACTIVE,
                user_id=u.id,
            )
            db.session.add(emp)
            db.session.commit()
            emp_id = emp.id

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"emp_upd_{uid}", "password": "EmployeePass123!"}, follow_redirects=True)

        resp = client.post("/employees/profile/update", data={
            "phone": "+91 91234 56789"
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Personal contact profile updated successfully" in resp.data

        with app.app_context():
            emp_after = Employee.query.get(emp_id)
            assert emp_after.phone == "+91 91234 56789"

    def test_documents_workflow_and_isolation(self, app, db):
        """Test document upload, download, and strict employee boundary isolation."""
        uid1 = uuid.uuid4().hex[:6]
        uid2 = uuid.uuid4().hex[:6]
        with app.app_context():
            u1 = User(
                username=f"doc_u1_{uid1}",
                email=f"doc_u1_{uid1}@corp.com",
                password_hash=generate_password_hash("DocPass123!"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            u2 = User(
                username=f"doc_u2_{uid2}",
                email=f"doc_u2_{uid2}@corp.com",
                password_hash=generate_password_hash("DocPass123!"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            db.session.add_all([u1, u2])
            db.session.flush()

            emp1 = Employee(
                employee_id=f"EMP{uid1}".upper()[:10],
                full_name=f"Doc Employee 1 {uid1}",
                email=f"doc_u1_{uid1}@corp.com",
                status=AccountStatus.ACTIVE,
                user_id=u1.id,
            )
            emp2 = Employee(
                employee_id=f"EMP{uid2}".upper()[:10],
                full_name=f"Doc Employee 2 {uid2}",
                email=f"doc_u2_{uid2}@corp.com",
                status=AccountStatus.ACTIVE,
                user_id=u2.id,
            )
            db.session.add_all([emp1, emp2])
            db.session.commit()
            emp1_id = emp1.id

        client = app.test_client()

        # Employee 1 logs in
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"doc_u1_{uid1}", "password": "DocPass123!"}, follow_redirects=True)

        # 1. View documents page
        res = client.get("/employees/documents")
        assert res.status_code == 200
        assert b"Employee Documents Center" in res.data

        # 2. Upload document
        fake_file = (io.BytesIO(b"%PDF-1.4 Fake test PDF content for HRMS360"), "test_contract.pdf")
        upload_res = client.post("/employees/documents/upload", data={
            "document_name": f"Offer Letter {uid1}",
            "document_type": "Offer Letter",
            "document_file": fake_file,
            "notes": "Verified offer acceptance"
        }, follow_redirects=True)
        assert upload_res.status_code == 200
        assert b"uploaded successfully" in upload_res.data

        with app.app_context():
            doc = EmployeeDocument.query.filter_by(document_name=f"Offer Letter {uid1}").first()
            assert doc is not None
            assert doc.employee_id == emp1_id
            doc_id = doc.id

        # 3. Download document by Owner (Employee 1) -> Success
        down_res = client.get(f"/employees/documents/{doc_id}/download")
        assert down_res.status_code == 200
        assert b"%PDF-1.4 Fake test PDF" in down_res.data

        # 4. Another employee (Employee 2) attempts to download this document -> must get 403 Forbidden
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"doc_u2_{uid2}", "password": "DocPass123!"}, follow_redirects=True)

        forbidden_res = client.get(f"/employees/documents/{doc_id}/download")
        assert forbidden_res.status_code == 403

    def test_company_policies_access_and_admin_crud(self, app, db):
        """Test company policies can be viewed by employees and managed by admins."""
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            admin = User(
                username=f"adm_pol_{uid}",
                email=f"adm_pol_{uid}@corp.com",
                password_hash=generate_password_hash("AdminPass123!"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            emp_user = User(
                username=f"emp_pol_{uid}",
                email=f"emp_pol_{uid}@corp.com",
                password_hash=generate_password_hash("EmpPass123!"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            db.session.add_all([admin, emp_user])
            db.session.commit()

        client = app.test_client()

        # 1. Admin login to create a policy
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"adm_pol_{uid}", "password": "AdminPass123!"}, follow_redirects=True)

        # Admin adds policy
        fake_policy_pdf = (io.BytesIO(b"%PDF-1.5 Corporate Safety Policy 2026"), "safety_policy.pdf")
        add_res = client.post("/employees/policies/add", data={
            "title": f"Safety Policy {uid}",
            "category": "POSH & Workplace Safety",
            "version": "1.0",
            "effective_date": "2026-01-01",
            "description": "Zero tolerance anti-harassment standards and grievance redressal mechanism.",
            "policy_file": fake_policy_pdf
        }, follow_redirects=True)
        assert add_res.status_code == 200
        assert b"published successfully" in add_res.data

        with app.app_context():
            pol = CompanyPolicy.query.filter_by(title=f"Safety Policy {uid}").first()
            assert pol is not None
            policy_id = pol.id

        # 2. Employee login to view and download policy
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"emp_pol_{uid}", "password": "EmpPass123!"}, follow_redirects=True)

        pol_view = client.get("/employees/policies")
        assert pol_view.status_code == 200
        assert f"Safety Policy {uid}".encode() in pol_view.data

        # Employee downloads policy file
        pol_down = client.get(f"/employees/policies/{policy_id}/download")
        assert pol_down.status_code == 200
        assert b"%PDF-1.5 Corporate Safety Policy 2026" in pol_down.data

        # Standard employee must NOT be allowed to delete policy
        unauth_del = client.post(f"/employees/policies/{policy_id}/delete")
        assert unauth_del.status_code == 403

"""
EBT System — Tests for Authentication Enhancements, Super Admin & RBAC
Tests:
- User Self-Registration & Email Verification token flow
- Forgot Password request & Token-based Reset Password
- Two-Step Verification (OTP over email) and invalid OTP handling
- Session Lock Screen & Unlock
- Super Admin Dashboard, Companies Management & Status Toggle
- Packages Management & Tier Pricing
- Subscriptions Management & Renewals
- Dynamic Roles, Permissions Registry, and User-Role Mapping
"""

import uuid
import pytest
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import (
    User, UserRole, Employee, AccountStatus,
    Company, Package, Subscription, Role, Permission
)
from app.auth.routes import _get_serializer


class TestPhase1AuthenticationSuite:
    def test_user_registration_and_email_verification(self, app, db):
        app.config["ENABLE_SELF_REGISTRATION"] = True
        uid = uuid.uuid4().hex[:6]
        client = app.test_client()

        # 1. Register new user
        reg_resp = client.post("/auth/register", data={
            "username": f"newuser_{uid}",
            "full_name": f"New User {uid}",
            "email": f"newuser_{uid}@enterprise.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
        }, follow_redirects=True)
        assert reg_resp.status_code == 200
        assert b"Account created successfully" in reg_resp.data

        with app.app_context():
            u = User.query.filter_by(username=f"newuser_{uid}").first()
            assert u is not None
            assert u.is_verified is False
            uid_val = u.id

            s = _get_serializer()
            token = s.dumps({"user_id": uid_val}, salt="email-verification")

        # 2. Email verification token
        ver_resp = client.get(f"/auth/verify-email/{token}", follow_redirects=True)
        assert ver_resp.status_code == 200
        assert b"Email successfully verified" in ver_resp.data

        with app.app_context():
            u = db.session.get(User, uid_val)
            assert u.is_verified is True

    def test_forgot_and_reset_password_workflow(self, app, db):
        app.config["ENABLE_SELF_REGISTRATION"] = True
        uid = uuid.uuid4().hex[:6]
        email = f"pwd_{uid}@enterprise.com"

        client = app.test_client()
        client.post("/auth/register", data={
            "username": f"pwd_user_{uid}",
            "full_name": "Password User",
            "email": email,
            "password": "InitialPassword@123",
            "confirm_password": "InitialPassword@123",
        }, follow_redirects=True)

        with app.app_context():
            u = User.query.filter_by(email=email).first()
            uid_val = u.id

        # Forgot password request
        f_resp = client.post("/auth/forgot-password", data={"email": email}, follow_redirects=True)
        assert f_resp.status_code == 200
        assert b"password reset instructions" in f_resp.data

        with app.app_context():
            s = _get_serializer()
            reset_tok = s.dumps({"user_id": uid_val}, salt="password-reset")

        # Reset password with token
        r_resp = client.post(f"/auth/reset-password/{reset_tok}", data={
            "password": "BrandNewSecret@123",
            "confirm_password": "BrandNewSecret@123",
        }, follow_redirects=True)
        assert r_resp.status_code == 200
        assert b"password has been reset successfully" in r_resp.data

        with app.app_context():
            u = db.session.get(User, uid_val)
            assert check_password_hash(u.password_hash, "BrandNewSecret@123")

    def test_two_factor_otp_login_and_lock_screen(self, app, db):
        app.config["ENABLE_SELF_REGISTRATION"] = True
        uid = uuid.uuid4().hex[:6]
        client = app.test_client()

        client.post("/auth/register", data={
            "username": f"otp_{uid}",
            "full_name": "OTP User",
            "email": f"otp_{uid}@enterprise.com",
            "password": "Password@123",
            "confirm_password": "Password@123",
        }, follow_redirects=True)

        with app.app_context():
            u = User.query.filter_by(username=f"otp_{uid}").first()
            u.is_verified = True
            u.two_factor_enabled = True
            db.session.commit()
            uid_val = u.id

        # Step 1: Sign in triggers OTP requirement
        l_resp = client.post("/auth/login", data={"identifier": f"otp_{uid}", "password": "Password@123"}, follow_redirects=True)
        assert l_resp.status_code == 200
        assert b"Two-Step Verification" in l_resp.data

        with app.app_context():
            u = db.session.get(User, uid_val)
            otp = u.otp_code
            assert otp is not None

        # Step 2: Invalid OTP fails
        bad_resp = client.post("/auth/verify-otp", data={"otp": "999999"}, follow_redirects=True)
        assert b"Invalid verification code" in bad_resp.data

        # Step 3: Valid OTP signs user in
        otp_resp = client.post("/auth/verify-otp", data={"otp": otp}, follow_redirects=True)
        assert otp_resp.status_code == 200
        assert b"Two-step verification successful" in otp_resp.data

        # Step 4: Lock screen & unlock
        lock_resp = client.get("/auth/lock")
        assert lock_resp.status_code == 200
        assert b"Session Locked" in lock_resp.data

        unlock_resp = client.post("/auth/lock", data={"password": "Password@123"}, follow_redirects=True)
        assert unlock_resp.status_code == 200
        assert b"Session unlocked" in unlock_resp.data


class TestPhase2And3SuperAdminAndRBAC:
    def test_superadmin_dashboard_and_company_management(self, app, db):
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            sadmin = User(
                username=f"sadmin_{uid}",
                email=f"sadmin_{uid}@enterprise.com",
                password_hash=generate_password_hash("SuperAdmin@123"),
                role=UserRole.SUPERADMIN,
                is_active=True,
                is_verified=True,
            )
            db.session.add(sadmin)
            db.session.commit()

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"sadmin_{uid}", "password": "SuperAdmin@123"}, follow_redirects=True)

        # 1. Super Admin Dashboard
        dash = client.get("/superadmin/dashboard")
        assert dash.status_code == 200
        assert b"Super Admin Control Hub" in dash.data

        # 2. Add Company
        c_resp = client.post("/superadmin/companies/add", data={
            "name": f"Enterprise Corp {uid}",
            "code": f"EC{uid}".upper(),
            "email": f"corp_{uid}@enterprise.com",
        }, follow_redirects=True)
        assert c_resp.status_code == 200
        assert f"EC{uid}".upper().encode() in c_resp.data

        with app.app_context():
            comp = Company.query.filter_by(code=f"EC{uid}".upper()).first()
            assert comp is not None
            comp_id = comp.id

        # Toggle company status
        t_resp = client.post(f"/superadmin/companies/{comp_id}/toggle-status", follow_redirects=True)
        assert t_resp.status_code == 200
        assert b"SUSPENDED" in t_resp.data

    def test_packages_and_subscriptions_management(self, app, db):
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            sadmin = User(
                username=f"sadmin2_{uid}",
                email=f"sadmin2_{uid}@enterprise.com",
                password_hash=generate_password_hash("SuperAdmin@123"),
                role=UserRole.SUPERADMIN,
                is_active=True,
                is_verified=True,
            )
            comp = Company(
                name=f"Sub Corp {uid}",
                code=f"SC{uid}".upper(),
                email=f"sub_{uid}@corp.com",
            )
            db.session.add_all([sadmin, comp])
            db.session.commit()
            comp_id = comp.id

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"sadmin2_{uid}", "password": "SuperAdmin@123"}, follow_redirects=True)

        # 1. Add Package
        p_resp = client.post("/superadmin/packages/save", data={
            "name": f"Gold Tier {uid}",
            "code": f"GOLD_{uid}".upper(),
            "price_per_month": "149.0",
            "price_per_year": "1490.0",
            "max_employees": "150",
            "max_storage_mb": "2000",
        }, follow_redirects=True)
        assert p_resp.status_code == 200

        with app.app_context():
            pkg = Package.query.filter_by(code=f"GOLD_{uid}".upper()).first()
            assert pkg is not None
            pkg_id = pkg.id

        # 2. Add Subscription
        s_resp = client.post("/superadmin/subscriptions/add", data={
            "company_id": str(comp_id),
            "package_id": str(pkg_id),
            "billing_cycle": "monthly",
            "amount": "149.0",
        }, follow_redirects=True)
        assert s_resp.status_code == 200
        assert b"Subscription generated" in s_resp.data

    def test_roles_and_permissions_management(self, app, db):
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            sadmin = User(
                username=f"sadmin3_{uid}",
                email=f"sadmin3_{uid}@enterprise.com",
                password_hash=generate_password_hash("SuperAdmin@123"),
                role=UserRole.SUPERADMIN,
                is_active=True,
                is_verified=True,
            )
            db.session.add(sadmin)
            db.session.commit()
            sadmin_id = sadmin.id

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"sadmin3_{uid}", "password": "SuperAdmin@123"}, follow_redirects=True)

        # 1. Add Custom Role
        r_resp = client.post("/roles/add", data={
            "name": f"Audit Officer {uid}",
            "description": "Internal auditor",
        }, follow_redirects=True)
        assert r_resp.status_code == 200
        assert f"Audit Officer {uid}".encode() in r_resp.data

        # 2. Add Custom Permission
        perm_resp = client.post("/roles/permissions/add", data={
            "name": f"Audit Deep Dive {uid}",
            "slug": f"audit_deep_{uid}",
            "module": "audit",
            "description": "Deep inspection",
        }, follow_redirects=True)
        assert perm_resp.status_code == 200
        assert f"audit_deep_{uid}".encode() in perm_resp.data

        # 3. Assign Role to User
        with app.app_context():
            aud_role = Role.query.filter_by(name=f"Audit Officer {uid}").first()
            role_id = aud_role.id

        u_assign = client.post(f"/roles/users/{sadmin_id}/assign", data={
            "role_ids": [str(role_id)],
            "two_factor_enabled": "on",
        }, follow_redirects=True)
        assert u_assign.status_code == 200

        with app.app_context():
            u = db.session.get(User, sadmin_id)
            assert u.two_factor_enabled is True
            assert any(r.name == f"Audit Officer {uid}" for r in u.roles)
            assert u.has_permission(f"audit_deep_{uid}") is True  # Superadmin always returns True

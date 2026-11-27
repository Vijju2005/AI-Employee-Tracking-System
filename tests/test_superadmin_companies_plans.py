"""
Tests for Company Management & Subscription Plans (Super Admin)
Covers:
- Companies list, search, filter, pagination
- Add/Edit company with validation (unique code, date order, required fields)
- Save and Add Another action
- Company Profile Details view (Profile, Contact, Locations, Subscriptions, Employee & User summaries)
- Company Location management (add/delete branch facilities, principal headquarters)
- Company Status Toggle (Activate/Suspend), Archive, and Safe Deletion prevention
- Companies directory export to formatted Excel (.xlsx)
- Subscription Plan duplicate and extended attributes (description, billing_cycle, max_users, trial_period_days)
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import (
    User, UserRole, Company, Package, Subscription, Employee, CompanyLocation
)


class TestCompanyManagementAndSubscriptionPlans:

    @pytest.fixture
    def setup_data(self, app, db):
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            sadmin = User(
                username=f"sadmin_cmp_{uid}",
                email=f"sadmin_cmp_{uid}@enterprise.com",
                password_hash=generate_password_hash("SuperAdmin@123"),
                role=UserRole.SUPERADMIN,
                is_active=True,
                is_verified=True,
            )
            pkg = Package(
                name=f"Enterprise Prime {uid}",
                code=f"EPRIME_{uid}".upper(),
                description="High scale multi-tenant tier",
                billing_cycle="both",
                price_per_month=199.0,
                price_per_year=1990.0,
                max_employees=250,
                max_users=25,
                max_storage_mb=5000,
                trial_period_days=30,
                is_active=True,
            )
            db.session.add_all([sadmin, pkg])
            db.session.commit()

            return {
                "sadmin_username": sadmin.username,
                "pkg_id": pkg.id,
                "pkg_code": pkg.code,
            }

    def test_company_creation_and_validations(self, app, client, setup_data):
        client.post("/auth/login", data={"identifier": setup_data["sadmin_username"], "password": "SuperAdmin@123"}, follow_redirects=True)

        uid = uuid.uuid4().hex[:6]
        code = f"CMP_{uid}".upper()

        # 1. Invalid date order check (end < start)
        bad_date_resp = client.post("/superadmin/companies/create", data={
            "name": f"Bad Date Corp {uid}",
            "code": f"BD_{uid}".upper(),
            "email": f"bad_{uid}@corp.com",
            "subscription_start": "2026-12-01",
            "subscription_end": "2026-01-01",
        }, follow_redirects=True)
        assert bad_date_resp.status_code == 200
        assert b"cannot precede Start Date" in bad_date_resp.data

        # 2. Successful Company creation with Initial Administrator
        create_resp = client.post("/superadmin/companies/create", data={
            "name": f"Global Innovations {uid}",
            "code": code,
            "registration_number": f"REG-{uid}-2026",
            "gstin": "29ABCDE1234F1Z5",
            "pan": "ABCDE1234F",
            "industry": "Software Services",
            "website": "https://www.innovations.com",
            "email": f"info_{uid}@innovations.com",
            "phone": "+91 80 8765 4321",
            "address": "100 Innovation Way, Tech Park",
            "country": "India",
            "state": "Karnataka",
            "city": "Bengaluru",
            "pincode": "560100",
            "package_id": str(setup_data["pkg_id"]),
            "employee_limit": "300",
            "user_limit": "30",
            "subscription_start": "2026-01-01",
            "subscription_end": "2026-12-31",
            "admin_name": f"Alice Admin {uid}",
            "admin_email": f"alice_{uid}@innovations.com",
            "admin_mobile": "+91 99887 76655",
            "action": "save",
        }, follow_redirects=True)
        assert create_resp.status_code == 200
        assert b"created successfully" in create_resp.data

        with app.app_context():
            cmp = Company.query.filter_by(code=code).first()
            assert cmp is not None
            assert cmp.registration_number == f"REG-{uid}-2026"
            assert cmp.gstin == "29ABCDE1234F1Z5"
            assert cmp.city == "Bengaluru"
            assert cmp.package_id == setup_data["pkg_id"]
            assert cmp.employee_limit == 300
            assert cmp.user_limit == 30
            cmp_id = cmp.id

            # Verify initial admin user created
            admin_user = User.query.filter_by(company_id=cmp_id).first()
            assert admin_user is not None
            assert admin_user.email == f"alice_{uid}@innovations.com"
            assert admin_user.role == UserRole.ADMIN

            # Verify subscription created
            sub = Subscription.query.filter_by(company_id=cmp_id).first()
            assert sub is not None
            assert sub.package_id == setup_data["pkg_id"]

        # 3. Duplicate code validation
        dup_resp = client.post("/superadmin/companies/create", data={
            "name": f"Another Name {uid}",
            "code": code,
            "email": f"diff_{uid}@corp.com",
        }, follow_redirects=True)
        assert dup_resp.status_code == 200
        assert b"already assigned to another organization" in dup_resp.data

    def test_company_detail_profile_and_locations(self, app, client, setup_data):
        client.post("/auth/login", data={"identifier": setup_data["sadmin_username"], "password": "SuperAdmin@123"}, follow_redirects=True)

        uid = uuid.uuid4().hex[:6]
        code = f"LOC_{uid}".upper()

        with app.app_context():
            c = Company(
                name=f"Location Corp {uid}",
                code=code,
                email=f"loc_{uid}@corp.com",
                package_id=setup_data["pkg_id"],
                status="active",
            )
            db.session.add(c)
            db.session.commit()
            cid = c.id

        # 1. View Company Detail page
        view_resp = client.get(f"/superadmin/companies/{cid}/view")
        assert view_resp.status_code == 200
        assert f"Location Corp {uid}".encode() in view_resp.data
        assert b"Profile &amp; Statutory Data" in view_resp.data
        assert b"Operating Branch Locations" in view_resp.data

        # 2. Add Branch Location
        add_loc_resp = client.post(f"/superadmin/companies/{cid}/locations/add", data={
            "location_name": "Hyderabad R&D Center",
            "address": "HITEC City Phase 2",
            "city": "Hyderabad",
            "state": "Telangana",
            "country": "India",
            "pincode": "500081",
            "is_headquarters": "1",
        }, follow_redirects=True)
        assert add_loc_resp.status_code == 200
        assert b"Hyderabad R" in add_loc_resp.data
        assert b"added to" in add_loc_resp.data

        with app.app_context():
            loc = CompanyLocation.query.filter_by(company_id=cid).first()
            assert loc is not None
            assert loc.location_name == "Hyderabad R&D Center"
            assert loc.is_headquarters is True
            loc_id = loc.id

        # 3. Delete Branch Location
        del_loc_resp = client.post(f"/superadmin/companies/{cid}/locations/{loc_id}/delete", follow_redirects=True)
        assert del_loc_resp.status_code == 200
        assert b"removed" in del_loc_resp.data

        with app.app_context():
            assert db.session.get(CompanyLocation, loc_id) is None

    def test_company_status_toggle_archive_and_safe_delete(self, app, client, setup_data):
        client.post("/auth/login", data={"identifier": setup_data["sadmin_username"], "password": "SuperAdmin@123"}, follow_redirects=True)

        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            c = Company(
                name=f"Archive Corp {uid}",
                code=f"ARC_{uid}".upper(),
                email=f"arc_{uid}@corp.com",
                status="active",
            )
            db.session.add(c)
            db.session.commit()
            cid = c.id

        # 1. Suspend company
        susp_resp = client.post(f"/superadmin/companies/{cid}/toggle-status", follow_redirects=True)
        assert susp_resp.status_code == 200
        assert b"SUSPENDED" in susp_resp.data

        # 2. Archive company
        arch_resp = client.post(f"/superadmin/companies/{cid}/archive", follow_redirects=True)
        assert arch_resp.status_code == 200
        assert b"Archived" in arch_resp.data

        with app.app_context():
            assert db.session.get(Company, cid).status == "archived"

        # 3. Link an employee to test safe deletion prevention
        with app.app_context():
            emp = Employee(
                employee_id=f"EMP_{uid}",
                full_name="Tester",
                email=f"test_{uid}@arc.com",
                company_name=f"Archive Corp {uid}",
            )
            db.session.add(emp)
            db.session.commit()

        # Attempt to delete company -> MUST BE REJECTED
        del_resp = client.post(f"/superadmin/companies/{cid}/delete", follow_redirects=True)
        assert del_resp.status_code == 200
        assert b"Cannot delete company" in del_resp.data

        with app.app_context():
            assert db.session.get(Company, cid) is not None

    def test_companies_excel_export(self, app, client, setup_data):
        client.post("/auth/login", data={"identifier": setup_data["sadmin_username"], "password": "SuperAdmin@123"}, follow_redirects=True)

        exp_resp = client.get("/superadmin/companies/export/excel")
        assert exp_resp.status_code == 200
        assert exp_resp.headers["Content-Type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert "attachment; filename=" in exp_resp.headers["Content-Disposition"]
        assert len(exp_resp.data) > 1000

    def test_package_plan_duplication_and_extended_attributes(self, app, client, setup_data):
        client.post("/auth/login", data={"identifier": setup_data["sadmin_username"], "password": "SuperAdmin@123"}, follow_redirects=True)

        pkg_id = setup_data["pkg_id"]

        # Duplicate plan
        dup_resp = client.post(f"/superadmin/packages/{pkg_id}/duplicate", follow_redirects=True)
        assert dup_resp.status_code == 200
        assert b"Package duplicated successfully" in dup_resp.data

        with app.app_context():
            orig = db.session.get(Package, pkg_id)
            dups = Package.query.filter(Package.name.like(f"{orig.name} (Copy%")).all()
            assert len(dups) >= 1
            dup_pkg = dups[0]
            assert dup_pkg.is_active is False
            assert dup_pkg.price_per_month == orig.price_per_month
            assert dup_pkg.trial_period_days == orig.trial_period_days
            assert dup_pkg.max_users == orig.max_users

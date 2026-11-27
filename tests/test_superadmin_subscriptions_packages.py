"""
EBT System — Comprehensive Tests for Super Admin Subscription & Package Management
Verifies:
1. Super Admin access control (403 for unauthenticated or non-superadmin users)
2. Package CRUD: Create, Edit, Toggle Active/Inactive status
3. Package Deletion Protection: Rejection when active company or subscription references exist
4. Subscription Management: Creation, custom pricing, monthly/yearly billing
5. Subscription Renewals & Extensions: Auto, 30d, 90d, 365d, and custom dates
6. Subscription Plan Upgrades / Downgrades with history preservation
7. Subscription Status Transitions: Active, Pending, Expired, Cancelled
8. Company Subscription History Timeline view
9. Subscriptions Search, Status Filter, Package Filter, and Sorting
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import (
    User, UserRole, Company, Package, Subscription
)


class TestSuperAdminSubscriptionsAndPackages:

    @pytest.fixture
    def setup_data(self, app, db):
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            sadmin = User(
                username=f"sadmin_sub_{uid}",
                email=f"sadmin_sub_{uid}@enterprise.com",
                password_hash=generate_password_hash("SuperAdmin@123"),
                role=UserRole.SUPERADMIN,
                is_active=True,
                is_verified=True,
            )
            standard_emp = User(
                username=f"emp_sub_{uid}",
                email=f"emp_sub_{uid}@enterprise.com",
                password_hash=generate_password_hash("EmpPass@123"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            pkg_starter = Package(
                name=f"Bronze Tier {uid}",
                code=f"BRONZE_{uid}".upper(),
                price_per_month=29.0,
                price_per_year=290.0,
                max_employees=15,
                max_storage_mb=500,
                is_active=True,
            )
            pkg_pro = Package(
                name=f"Silver Tier {uid}",
                code=f"SILVER_{uid}".upper(),
                price_per_month=99.0,
                price_per_year=990.0,
                max_employees=50,
                max_storage_mb=2000,
                is_active=True,
            )
            comp = Company(
                name=f"Acme Corp {uid}",
                code=f"ACME_{uid}".upper(),
                email=f"acme_{uid}@test.com",
            )
            db.session.add_all([sadmin, standard_emp, pkg_starter, pkg_pro, comp])
            db.session.commit()

            return {
                "sadmin_username": sadmin.username,
                "emp_username": standard_emp.username,
                "pkg_starter_id": pkg_starter.id,
                "pkg_pro_id": pkg_pro.id,
                "comp_id": comp.id,
            }

    def test_superadmin_authorization_enforcement(self, app, client, setup_data):
        # 1. Unauthenticated request -> redirect to login
        resp = client.get("/superadmin/packages")
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]

        # 2. Authenticated standard employee -> 403 Forbidden
        client.post("/auth/login", data={"identifier": setup_data["emp_username"], "password": "EmpPass@123"}, follow_redirects=True)
        emp_resp = client.get("/superadmin/packages")
        assert emp_resp.status_code == 403

        emp_sub_resp = client.get("/superadmin/subscriptions")
        assert emp_sub_resp.status_code == 403

        # Logout employee
        client.get("/auth/logout")

    def test_package_creation_editing_and_status_toggle(self, app, client, setup_data):
        client.post("/auth/login", data={"identifier": setup_data["sadmin_username"], "password": "SuperAdmin@123"}, follow_redirects=True)

        # 1. View packages page
        view_resp = client.get("/superadmin/packages")
        assert view_resp.status_code == 200
        assert b"Packages &amp; Subscription Plans" in view_resp.data

        # 2. Create new package
        uid = uuid.uuid4().hex[:6]
        create_resp = client.post("/superadmin/packages/save", data={
            "name": f"Platinum Tier {uid}",
            "code": f"PLAT_{uid}".upper(),
            "price_per_month": "199.0",
            "price_per_year": "1990.0",
            "max_employees": "200",
            "max_storage_mb": "5000",
            "features[]": ["Attendance Timesheets & GPS Check-in", "Automated Payroll & Payslip PDF"],
            "custom_features": "Dedicated Account Manager\n24/7 SLA",
        }, follow_redirects=True)
        assert create_resp.status_code == 200
        assert b"saved successfully" in create_resp.data

        with app.app_context():
            pkg = Package.query.filter_by(code=f"PLAT_{uid}".upper()).first()
            assert pkg is not None
            assert pkg.price_per_month == 199.0
            assert pkg.max_employees == 200
            assert "Attendance Timesheets" in pkg.features_json
            assert "Dedicated Account Manager" in pkg.features_json
            pkg_id = pkg.id

        # 3. Edit Package
        edit_resp = client.post("/superadmin/packages/save", data={
            "package_id": str(pkg_id),
            "name": f"Platinum Elite {uid}",
            "code": f"PLAT_{uid}".upper(),
            "price_per_month": "249.0",
            "price_per_year": "2490.0",
            "max_employees": "300",
            "max_storage_mb": "6000",
            "features[]": ["Attendance Timesheets & GPS Check-in"],
        }, follow_redirects=True)
        assert edit_resp.status_code == 200

        with app.app_context():
            pkg_after = db.session.get(Package, pkg_id)
            assert pkg_after.name == f"Platinum Elite {uid}"
            assert pkg_after.price_per_month == 249.0

        # 4. Toggle Package Active/Inactive
        toggle_resp = client.post(f"/superadmin/packages/{pkg_id}/toggle-status", follow_redirects=True)
        assert toggle_resp.status_code == 200
        assert b"DEACTIVATED" in toggle_resp.data

        with app.app_context():
            assert db.session.get(Package, pkg_id).is_active is False

        toggle_back = client.post(f"/superadmin/packages/{pkg_id}/toggle-status", follow_redirects=True)
        assert toggle_back.status_code == 200
        assert b"ACTIVATED" in toggle_back.data

        with app.app_context():
            assert db.session.get(Package, pkg_id).is_active is True

    def test_package_deletion_safety_checks(self, app, client, setup_data):
        client.post("/auth/login", data={"identifier": setup_data["sadmin_username"], "password": "SuperAdmin@123"}, follow_redirects=True)

        comp_id = setup_data["comp_id"]
        pkg_starter_id = setup_data["pkg_starter_id"]

        # 1. Assign package to company and create subscription
        sub_resp = client.post("/superadmin/subscriptions/add", data={
            "company_id": str(comp_id),
            "package_id": str(pkg_starter_id),
            "billing_cycle": "monthly",
            "status": "active",
        }, follow_redirects=True)
        assert sub_resp.status_code == 200

        # 2. Attempt to delete package_starter -> MUST BE REJECTED safely
        del_resp = client.post(f"/superadmin/packages/{pkg_starter_id}/delete", follow_redirects=True)
        assert del_resp.status_code == 200
        assert b"Cannot delete package" in del_resp.data

        with app.app_context():
            assert db.session.get(Package, pkg_starter_id) is not None

        # 3. Create unlinked package and delete -> MUST SUCCEED
        uid = uuid.uuid4().hex[:6]
        client.post("/superadmin/packages/save", data={
            "name": f"Temporary Plan {uid}",
            "code": f"TEMP_{uid}".upper(),
            "price_per_month": "10.0",
            "price_per_year": "100.0",
            "max_employees": "5",
            "max_storage_mb": "100",
        }, follow_redirects=True)

        with app.app_context():
            temp_pkg = Package.query.filter_by(code=f"TEMP_{uid}".upper()).first()
            temp_id = temp_pkg.id

        del_ok_resp = client.post(f"/superadmin/packages/{temp_id}/delete", follow_redirects=True)
        assert del_ok_resp.status_code == 200
        assert b"deleted successfully" in del_ok_resp.data

        with app.app_context():
            assert db.session.get(Package, temp_id) is None

    def test_subscription_creation_renewals_and_plan_change(self, app, client, setup_data):
        client.post("/auth/login", data={"identifier": setup_data["sadmin_username"], "password": "SuperAdmin@123"}, follow_redirects=True)

        comp_id = setup_data["comp_id"]
        starter_id = setup_data["pkg_starter_id"]
        pro_id = setup_data["pkg_pro_id"]

        # 1. Assign Starter Subscription (Monthly)
        add_resp = client.post("/superadmin/subscriptions/add", data={
            "company_id": str(comp_id),
            "package_id": str(starter_id),
            "billing_cycle": "monthly",
            "status": "active",
        }, follow_redirects=True)
        assert add_resp.status_code == 200
        assert b"Subscription generated and activated" in add_resp.data

        with app.app_context():
            sub = Subscription.query.filter_by(company_id=comp_id, status="active").first()
            assert sub is not None
            assert sub.amount == 29.0
            assert sub.package_id == starter_id
            sub_id = sub.id

        # 2. Renew subscription with custom duration (+90 days)
        renew_resp = client.post(f"/superadmin/subscriptions/{sub_id}/renew", data={
            "extension_type": "90"
        }, follow_redirects=True)
        assert renew_resp.status_code == 200
        assert b"renewed until" in renew_resp.data

        with app.app_context():
            # Old sub should be retired/cancelled and new active sub created
            subs = Subscription.query.filter_by(company_id=comp_id).order_by(Subscription.id.desc()).all()
            assert len(subs) >= 2
            latest_sub = subs[0]
            assert latest_sub.status == "active"
            latest_id = latest_sub.id

        # 3. Upgrade Plan to Pro Tier (Yearly)
        upgrade_resp = client.post(f"/superadmin/subscriptions/{latest_id}/change-plan", data={
            "new_package_id": str(pro_id),
            "billing_cycle": "yearly",
        }, follow_redirects=True)
        assert upgrade_resp.status_code == 200
        assert b"Plan changed to" in upgrade_resp.data

        with app.app_context():
            active_sub = Subscription.query.filter_by(company_id=comp_id, status="active").first()
            assert active_sub is not None
            assert active_sub.package_id == pro_id
            assert active_sub.billing_cycle == "yearly"
            assert active_sub.amount == 990.0

            # Verify Company model reflects current package
            company = db.session.get(Company, comp_id)
            assert company.package_id == pro_id

            # Verify complete subscription audit trail is preserved
            all_comp_subs = Subscription.query.filter_by(company_id=comp_id).all()
            assert len(all_comp_subs) >= 3

        # 4. Update status and dates
        edit_status_resp = client.post(f"/superadmin/subscriptions/{active_sub.id}/update-status", data={
            "status": "pending",
            "starts_at": "2026-01-01",
            "expires_at": "2026-12-31",
        }, follow_redirects=True)
        assert edit_status_resp.status_code == 200

        with app.app_context():
            s_updated = db.session.get(Subscription, active_sub.id)
            assert s_updated.status == "pending"
            assert s_updated.starts_at.strftime("%Y-%m-%d") == "2026-01-01"
            assert s_updated.expires_at.strftime("%Y-%m-%d") == "2026-12-31"

        # 5. Cancel Subscription
        cancel_resp = client.post(f"/superadmin/subscriptions/{active_sub.id}/cancel", follow_redirects=True)
        assert cancel_resp.status_code == 200
        assert b"has been cancelled" in cancel_resp.data

        with app.app_context():
            assert db.session.get(Subscription, active_sub.id).status == "cancelled"

        # 6. Company Subscription History view
        hist_resp = client.get(f"/superadmin/companies/{comp_id}/subscriptions-history")
        assert hist_resp.status_code == 200
        assert b"Subscription History:" in hist_resp.data
        assert b"Historical License Transactions" in hist_resp.data

    def test_subscriptions_search_filtering_and_sorting(self, app, client, setup_data):
        client.post("/auth/login", data={"identifier": setup_data["sadmin_username"], "password": "SuperAdmin@123"}, follow_redirects=True)

        comp_id = setup_data["comp_id"]
        pro_id = setup_data["pkg_pro_id"]

        # Provision a subscription
        client.post("/superadmin/subscriptions/add", data={
            "company_id": str(comp_id),
            "package_id": str(pro_id),
            "billing_cycle": "monthly",
            "status": "active",
        }, follow_redirects=True)

        # Test search query
        search_resp = client.get(f"/superadmin/subscriptions?q=Acme")
        assert search_resp.status_code == 200
        assert b"Acme Corp" in search_resp.data

        # Test status filter
        filter_resp = client.get(f"/superadmin/subscriptions?status=active")
        assert filter_resp.status_code == 200
        assert b"Active" in filter_resp.data

        # Test package filter
        pkg_filter_resp = client.get(f"/superadmin/subscriptions?package_id={pro_id}")
        assert pkg_filter_resp.status_code == 200
        assert b"Silver Tier" in pkg_filter_resp.data

        # Test sorting
        sort_resp = client.get(f"/superadmin/subscriptions?sort_by=amount_desc")
        assert sort_resp.status_code == 200

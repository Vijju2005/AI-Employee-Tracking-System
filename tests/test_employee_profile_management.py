"""
Unit & Integration Tests for Comprehensive Employee Profile Management:
- Personal information & emergency contacts CRUD
- Encryption of Aadhaar and PAN at rest
- UI masking verification (XXXX-XXXX-1234 and ABC•••4F)
- RBAC isolation: employees cannot edit identity, salary, or other employees' profiles
- Full 7-section profile view
"""

import uuid
import pytest
from datetime import date
from werkzeug.security import generate_password_hash
from app.models import Employee, EmployeeProfile, User, UserRole, AccountStatus, EmployeeDocument, EmployeeSalary
from app.utils.crypto import encrypt_field, decrypt_field, mask_aadhaar, mask_pan, mask_bank_account


class TestEmployeeProfileManagementSuite:

    def test_crypto_encryption_and_masking_helpers(self, app):
        """Verify AES-256 field encryption and visual data masking."""
        with app.app_context():
            plain_aadhaar = "987654321098"
            plain_pan = "ABCDE1234F"
            plain_acc = "11223344556677"

            # Encrypt
            enc_aadhaar = encrypt_field(plain_aadhaar)
            enc_pan = encrypt_field(plain_pan)

            assert enc_aadhaar != plain_aadhaar
            assert enc_pan != plain_pan

            # Decrypt
            assert decrypt_field(enc_aadhaar) == plain_aadhaar
            assert decrypt_field(enc_pan) == plain_pan

            # Masking
            assert mask_aadhaar(plain_aadhaar) == "XXXX-XXXX-1098"
            assert "•••" in mask_pan(plain_pan)
            assert mask_bank_account(plain_acc) == "••••••••6677"

    def test_employee_profile_model_creation_and_properties(self, app, db):
        """Verify EmployeeProfile model relationships, properties, and dictionary exports."""
        with app.app_context():
            uid = uuid.uuid4().hex[:6]
            emp = Employee(
                employee_id=f"EMP{uid}".upper()[:10],
                full_name="Rajesh Sharma",
                email=f"rajesh_{uid}@testcompany.local",
                phone="+919876543210",
                status=AccountStatus.ACTIVE
            )
            db.session.add(emp)
            db.session.flush()

            profile = EmployeeProfile(
                employee_id=emp.id,
                date_of_birth=date(1994, 5, 15),
                gender="Male",
                marital_status="Married",
                personal_email="rajesh.personal@gmail.com",
                blood_group="O+",
                nationality="Indian",
                current_address="102, Tech Park Residency, Bengaluru",
                highest_qualification="B.Tech Computer Science",
                institution_university="VTU Karnataka",
                graduation_year=2016,
                emergency_contact_name="Sunita Sharma",
                emergency_contact_relation="Spouse",
                emergency_contact_phone="+919876500000"
            )
            profile.aadhaar_number = "123456789012"
            profile.pan_number = "BPKPS1234A"
            db.session.add(profile)
            db.session.commit()

            # Retrieve and verify encryption at rest
            prof_db = EmployeeProfile.query.filter_by(employee_id=emp.id).first()
            assert prof_db is not None
            assert prof_db.aadhaar_number_encrypted != "123456789012"
            assert prof_db.aadhaar_number == "123456789012"
            assert prof_db.aadhaar_masked == "XXXX-XXXX-9012"
            assert prof_db.pan_number == "BPKPS1234A"
            assert "BPK" in prof_db.pan_masked

            # Dictionary export masking
            d = prof_db.to_dict(mask_sensitive=True)
            assert d["aadhaar_number"] == "XXXX-XXXX-9012"
            assert "123456789012" not in str(d)

    def test_admin_view_and_update_full_profile(self, app, db):
        """Admin can access view_employee and update any section including identity and employment."""
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            admin_user = User(
                username=f"adm_{uid}",
                email=f"adm_{uid}@test.local",
                password_hash=generate_password_hash("AdminPass123!"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            emp_user = User(
                username=f"emp_{uid}",
                email=f"emp_{uid}@test.local",
                password_hash=generate_password_hash("EmpPass123!"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            db.session.add_all([admin_user, emp_user])
            db.session.flush()

            emp = Employee(
                employee_id=f"EMP{uid}".upper()[:10],
                full_name="Target Personnel",
                email=f"emp_{uid}@test.local",
                phone="+919876543210",
                status=AccountStatus.ACTIVE,
                user_id=emp_user.id,
            )
            db.session.add(emp)
            db.session.commit()
            emp_id = emp.id

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"adm_{uid}", "password": "AdminPass123!"}, follow_redirects=True)

        # GET profile view
        resp = client.get(f"/employees/{emp_id}/view")
        assert resp.status_code == 200
        assert b"Comprehensive Profile" in resp.data
        assert b"Personal Info" in resp.data
        assert b"Identity &amp; Govt" in resp.data

        # Update Personal Section
        resp_post = client.post(
            f"/employees/{emp_id}/profile/update",
            data={
                "section": "personal",
                "gender": "Female",
                "marital_status": "Single",
                "blood_group": "AB+",
                "nationality": "Indian",
                "personal_email": "updated.emp@company.local",
                "current_address": "Indiranagar, Bengaluru"
            },
            follow_redirects=True
        )
        assert resp_post.status_code == 200
        assert b"Personal" in resp_post.data

        # Update Identity Section (Admin permitted)
        resp_id = client.post(
            f"/employees/{emp_id}/profile/update",
            data={
                "section": "identity",
                "aadhaar_number": "555566667777",
                "pan_number": "ABCDE9999Z",
                "uan_number": "100998877665"
            },
            follow_redirects=True
        )
        assert resp_id.status_code == 200

        # Verify in DB
        with app.app_context():
            prof_after = EmployeeProfile.query.filter_by(employee_id=emp_id).first()
            assert prof_after.blood_group == "AB+"
            assert prof_after.aadhaar_number == "555566667777"
            assert prof_after.aadhaar_masked == "XXXX-XXXX-7777"
            assert prof_after.uan_number == "100998877665"

    def test_employee_rbac_security_boundaries(self, app, db):
        """
        Standard employee can update their own personal/emergency details,
        but is blocked (403) from mutating sensitive identity or viewing other employees' profiles.
        """
        uid = uuid.uuid4().hex[:6]
        with app.app_context():
            u1 = User(
                username=f"emp1_{uid}",
                email=f"emp1_{uid}@test.local",
                password_hash=generate_password_hash("EmpPass123!"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            u2 = User(
                username=f"emp2_{uid}",
                email=f"emp2_{uid}@test.local",
                password_hash=generate_password_hash("EmpPass123!"),
                role=UserRole.EMPLOYEE,
                is_active=True,
                is_verified=True,
            )
            db.session.add_all([u1, u2])
            db.session.flush()

            emp1 = Employee(
                employee_id=f"E1{uid}".upper()[:10],
                full_name="Employee One",
                email=f"emp1_{uid}@test.local",
                status=AccountStatus.ACTIVE,
                user_id=u1.id,
            )
            emp2 = Employee(
                employee_id=f"E2{uid}".upper()[:10],
                full_name="Employee Two",
                email=f"emp2_{uid}@test.local",
                status=AccountStatus.ACTIVE,
                user_id=u2.id,
            )
            db.session.add_all([emp1, emp2])
            db.session.commit()
            emp1_id = emp1.id
            emp2_id = emp2.id

        client = app.test_client()
        client.get("/auth/logout")
        client.post("/auth/login", data={"identifier": f"emp1_{uid}", "password": "EmpPass123!"}, follow_redirects=True)

        # 1. Employee cannot view other employee's profile
        resp_other = client.get(f"/employees/{emp2_id}/view")
        assert resp_other.status_code == 403

        # 2. Employee cannot update other employee's profile
        resp_tamper = client.post(
            f"/employees/{emp2_id}/profile/update",
            data={"section": "personal", "blood_group": "B+"}
        )
        assert resp_tamper.status_code == 403

        # 3. Employee cannot update their own Identity section (Admin only)
        resp_id_tamper = client.post(
            f"/employees/{emp1_id}/profile/update",
            data={"section": "identity", "aadhaar_number": "999900001111"}
        )
        assert resp_id_tamper.status_code == 403

        # 4. Employee CAN update their own family / emergency details
        resp_fam = client.post(
            f"/employees/{emp1_id}/profile/update",
            data={
                "section": "family",
                "father_name": "Ramesh Nair",
                "emergency_contact_name": "Anita Nair",
                "emergency_contact_relation": "Mother",
                "emergency_contact_phone": "+919876511111"
            },
            follow_redirects=True
        )
        assert resp_fam.status_code == 200

        # Verify in DB
        with app.app_context():
            prof = EmployeeProfile.query.filter_by(employee_id=emp1_id).first()
            assert prof.emergency_contact_name == "Anita Nair"
            assert prof.emergency_contact_relation == "Mother"

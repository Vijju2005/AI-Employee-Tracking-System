"""
EBT System — Default RBAC & SaaS Seeder
Seeds standard initial roles, granular permissions, and starter SaaS packages idempotently.
"""

from app.models import Role, Permission, Package

DEFAULT_PERMISSIONS = [
    # Dashboard & Analytics
    ("View Admin Dashboard", "view_admin_dashboard", "dashboard", "Access executive overview analytics"),
    ("View AI Predictions", "view_ai_predictions", "analytics", "Access ML availability predictions"),

    # Employee Management
    ("View Employees", "view_employees", "employees", "View employee roster and profiles"),
    ("Create Employees", "create_employees", "employees", "Add new employee records"),
    ("Edit Employees", "edit_employees", "employees", "Modify employee profiles and records"),
    ("Delete Employees", "delete_employees", "employees", "Deactivate or remove employee profiles"),

    # Attendance & Breaks
    ("View Attendance", "view_attendance", "attendance", "View company-wide attendance"),
    ("Manage Attendance", "manage_attendance", "attendance", "Check-in/out and edit timesheets"),
    ("View Breaks", "view_breaks", "breaks", "Monitor employee break activities"),

    # Leave Management
    ("View Leaves", "view_leaves", "leave", "View leave requests"),
    ("Approve Leaves", "approve_leaves", "leave", "Approve or reject leave applications"),

    # Payroll Management
    ("View Payroll", "view_payroll", "payroll", "Access payroll metrics and compensation"),
    ("Process Payroll", "process_payroll", "payroll", "Run monthly payroll and issue payslips"),
    ("Manage Salary Structures", "manage_salaries", "payroll", "Configure employee CTC and components"),

    # Reports
    ("View Reports", "view_reports", "reports", "Access corporate reports"),
    ("Export Reports", "export_reports", "reports", "Download PDF and Excel reports"),

    # User & Role Administration
    ("Manage Users", "manage_users", "admin", "Manage user credentials and status"),
    ("Manage Roles", "manage_roles", "admin", "Create, edit, and assign roles"),
    ("Manage Permissions", "manage_permissions", "admin", "Configure system permissions"),
]

DEFAULT_PACKAGES = [
    {
        "name": "Starter Plan",
        "code": "STARTER",
        "price_per_month": 49.0,
        "price_per_year": 490.0,
        "max_employees": 20,
        "max_storage_mb": 500,
        "features": '["Break Tracking", "Attendance Timesheets", "Standard Reports", "Email Support"]',
    },
    {
        "name": "Professional Plan",
        "code": "PRO",
        "price_per_month": 129.0,
        "price_per_year": 1290.0,
        "max_employees": 100,
        "max_storage_mb": 2000,
        "features": '["All Starter Features", "Automated Payroll", "Leave Approvals", "Export PDF/Excel", "Priority Support"]',
    },
    {
        "name": "Enterprise Suite",
        "code": "ENTERPRISE",
        "price_per_month": 299.0,
        "price_per_year": 2990.0,
        "max_employees": 1000,
        "max_storage_mb": 10000,
        "features": '["All Pro Features", "AI Availability Predictions", "Custom RBAC Roles", "Audit Logs", "24/7 Dedicated Support"]',
    },
]


def seed_rbac_and_packages(db_session):
    """
    Idempotently seeds permissions, system roles, and standard SaaS packages.
    """
    # 1. Seed Permissions
    for name, slug, module, desc in DEFAULT_PERMISSIONS:
        existing = db_session.query(Permission).filter_by(slug=slug).first()
        if not existing:
            p = Permission(name=name, slug=slug, module=module, description=desc)
            db_session.add(p)

    db_session.flush()

    # 2. Seed Default Roles
    all_perms = db_session.query(Permission).all()

    admin_role = db_session.query(Role).filter_by(name="Administrator").first()
    if not admin_role:
        admin_role = Role(
            name="Administrator",
            description="Full corporate administrative access to all modules and configurations.",
            is_system=True,
        )
        admin_role.permissions = all_perms
        db_session.add(admin_role)

    hr_role = db_session.query(Role).filter_by(name="HR Manager").first()
    if not hr_role:
        hr_perms = [p for p in all_perms if p.module in ["employees", "attendance", "leave", "payroll", "reports"]]
        hr_role = Role(
            name="HR Manager",
            description="Manages workforce directory, attendance, leaves, and payroll.",
            is_system=False,
        )
        hr_role.permissions = hr_perms
        db_session.add(hr_role)

    employee_role = db_session.query(Role).filter_by(name="Standard Employee").first()
    if not employee_role:
        emp_perms = [p for p in all_perms if p.slug in ["view_attendance", "manage_attendance", "view_breaks", "view_leaves", "view_reports"]]
        employee_role = Role(
            name="Standard Employee",
            description="Self-service employee portal: check-in, breaks, personal leaves, and payslips.",
            is_system=True,
        )
        employee_role.permissions = emp_perms
        db_session.add(employee_role)

    # 3. Seed Default Packages
    for pkg_data in DEFAULT_PACKAGES:
        existing_pkg = db_session.query(Package).filter_by(code=pkg_data["code"]).first()
        if not existing_pkg:
            pkg = Package(
                name=pkg_data["name"],
                code=pkg_data["code"],
                price_per_month=pkg_data["price_per_month"],
                price_per_year=pkg_data["price_per_year"],
                max_employees=pkg_data["max_employees"],
                max_storage_mb=pkg_data["max_storage_mb"],
                features_json=pkg_data["features"],
                is_active=True,
            )
            db_session.add(pkg)

    db_session.commit()

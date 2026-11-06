# HRMS360 – Employee Break Tracking & Availability Prediction System

**HRMS360 (EBT Enterprise System)** | *Next-Generation Workforce Intelligence & Enterprise Human Resource Management System*

A full-stack, enterprise-grade Python Flask web application designed for comprehensive workforce lifecycle management. It integrates precision attendance & dynamic working hours tracking, intelligent multi-category break monitoring, automated payroll & statutory compliance calculation, leave management & policy governance, multi-tenant Super Admin architecture, granular Role-Based Access Control (RBAC), executive HR dashboards, and predictive Scikit-Learn Machine Learning models for employee availability and break forecasting.

---

## 🌐 Live Application & Repositories

* **Live Production URL**: [https://ai-employee-tracking-system.onrender.com](https://ai-employee-tracking-system.onrender.com)
* **GitHub Repository**: [https://github.com/Vijju2005/AI-Employee-Tracking-System](https://github.com/Vijju2005/AI-Employee-Tracking-System)
* **Production Database**: Managed TiDB Cloud Serverless Cluster (MySQL 8.0 wire-compatible with SSL/TLS encryption)
* **Production Health Check**: [https://ai-employee-tracking-system.onrender.com/health](https://ai-employee-tracking-system.onrender.com/health)

---

## 🏛️ System Architecture

```
                                +-----------------------------+
                                |  Browser / Mobile Clients   |
                                +--------------+--------------+
                                               |  HTTPS (Render CDN / SSL)
                                               v
                                +-----------------------------+
                                |    Gunicorn / WSGI Server   |
                                +--------------+--------------+
                                               |
                                               v
                                +-----------------------------+
                                |      Flask Application      |
                                |  - Blueprints & Jinja2      |
                                |  - Flask-Login & CSRF       |
                                |  - Scikit-Learn ML Engine   |
                                |  - ReportLab & OpenPyXL     |
                                |  - Dynamic Working Hours    |
                                |  - Auto Schema Synchronizer |
                                +--------------+--------------+
                                               | TLS / SSL (certifi CA)
                                               v
                                +-----------------------------+
                                |   TiDB Cloud / MySQL 8.0    |
                                |   (26 Relational Tables)    |
                                +-----------------------------+
```

### Technology Stack
* **Backend Framework**: Python 3.14 / Flask 3.1, Gunicorn WSGI
* **Database & ORM**: SQLAlchemy 2.0, PyMySQL, TiDB Cloud / MySQL 8.0 (26 production relational tables)
* **Frontend**: HTML5, Vanilla JavaScript, CSS3 (Enterprise Navy-Blue Design System, Lucide Icons, Chart.js)
* **Machine Learning**: Scikit-Learn (Random Forest Regressors, Rolling Baseline Metrics, MAE/RMSE evaluation), Pandas, NumPy
* **Report Generation**: ReportLab (Vector Branded PDF), OpenPyXL (Multi-sheet styled Excel `.xlsx`)
* **Security & Auth**: Flask-Login, Flask-WTF (CSRF tokens), Werkzeug PBKDF2/SHA-256 password hashing, HTTP Security Headers, 2FA Email OTP

---

## 📦 Core Modules & Functional Highlights

### 1. 🔐 Authentication & Session Security
* **Multi-Factor Security**: Email verification upon registration, 6-digit Time-based OTP for Two-Step Verification, and quick lock-screen shortcut.
* **Credential Recovery**: Cryptographically signed password reset tokens with 1-hour expiration and account-enumeration protection.
* **Audit Defense**: Hardened session cookies (`HttpOnly`, `SameSite=Lax`, `Secure` in production), anti-clickjacking headers (`X-Frame-Options: DENY`), and open-redirect sanitization.

### 2. 👑 Super Admin & Multi-Tenancy Portal (`/superadmin`)
* **Tenant Governance**: Provision and manage enterprise client companies with tenant codes, subscription statuses, and contact details.
* **Package Tier Engine**: Configure subscription plans (Starter, Professional, Enterprise) defining employee limits and cloud storage quotas.
* **Subscriptions & Billing**: Assign and audit company subscriptions with real-time status and renewal tracking.

### 3. 🛡️ Enterprise RBAC & Security Management (`/roles`)
* **Role Management**: Configure system roles (Super Admin, Administrator, HR Manager, Standard Employee) and custom organizational roles.
* **Permission Registry**: Module-level permission matrix governing Dashboard, Employees, Attendance, Breaks, Leave, Payroll, Reports, and Security settings.
* **User Permission Assignments**: Fine-grained assignment of roles and Two-Factor Authentication policies to individual users.

### 4. 👥 Employee Lifecycle Management (`/employees`)
* **Dual Visualization**: 1-click toggle between standard List View and card-based Employee Grid View with quick search and filters.
* **Employee 360° Profile**: Dedicated view page displaying personal info, emergency contacts, active designation, salary grade, attendance stats, and recent leave logs.
* **Department & Designation Hub**: Complete CRUD for departments and job designations with relational safety guards preventing accidental deletion of populated units.

### 5. ⏱️ Attendance & Dynamic Break Tracking (`/attendance`, `/breaks`)
* **Dynamic Net Working Hours**: Real-time client-side and server-side calculation:
  $$\text{Net Working Time} = \text{Gross Elapsed Time} - \text{Total Break Duration}$$
* **Multi-Category Breaks**: Precision tracking for Tea, Coffee, Lunch, Personal, and Other breaks with overlap prevention.
* **Shift Schedules (`/attendance/schedules`)**: Define recurring shifts (Morning, General, Evening, Night) and assign workforce members with 1 click.
* **Holidays & Compliance (`/holidays`)**: Centralized company holiday calendar with automated holiday detection on dashboards.

### 6. 🌴 Leave Management & Governance (`/leave`)
* **Leave Requests**: Apply for Casual, Sick, Earned, or Maternity leave with full-day, half-day, or hourly options.
* **Leave Policy Engine (`/leave/policies`)**: Configure annual day quotas, paid vs unpaid rules, carry-forward limits, and document attachment mandates.
* **Managerial Review**: Streamlined approval/rejection workflows with administrative remarks and automated email notifications.

### 7. 💰 Automated Payroll & Statutory Compliance (`/payroll`)
* **Salary Structure Engine**: Define employee CTC, Basic Pay, HRA, Special Allowance, and customized allowances.
* **Statutory Calculations**: Automated deductions for Provident Fund (PF), Employee State Insurance (ESI), Professional Tax (PT), and Tax Deducted at Source (TDS).
* **Pay Components Management (`/payroll/components`)**: Enterprise responsive interface to govern earnings and statutory deduction items.
* **One-Click Payslips**: Automated generation and instant branded PDF download of itemized employee payslips.

### 8. 📊 Dedicated Executive Dashboards
* **HR Analytics Dashboard (`/dashboard/hr`)**: Workforce headcount, department distribution, turnover metrics, and active employee status breakdown.
* **Attendance & Punctuality Dashboard (`/dashboard/attendance`)**: Today's presence rate, late check-in tracking, active break counters, and 7-day attendance trends.
* **Recruitment & Applicant Pipeline (`/dashboard/recruitment`)**: Job opening management, applicant pipeline tracking across stages (Applied, Screening, Interviewing, Offered, Hired), and fast status updates.

### 9. 📑 Audit & Enterprise Reporting (`/reports`)
* 7 Dedicated Report Types: Attendance Audit, Break Log Analysis, Leave History, Payroll Register, Department Summary, Punctuality Log, and System Audit.
* Export Formats: Vector PDF with company branding and ReportLab styling, and multi-sheet formatted Excel `.xlsx` spreadsheets via OpenPyXL.

### 10. 🤖 Machine Learning Availability Engine
* Multi-tier prediction engine utilizing Random Forest Regressors and rolling category baselines to predict break duration and forecast remaining daily availability.

---

## 💻 Local Installation & Setup Instructions

### 1. Prerequisites
* Python 3.9+ (Python 3.11 to 3.14 fully supported)
* MySQL 8.0+ or local SQLite fallback
* Git

### 2. Clone Repository
```bash
git clone https://github.com/Vijju2005/AI-Employee-Tracking-System.git
cd AI-Employee-Tracking-System
```

### 3. Create & Activate Virtual Environment
```bash
# Create virtual environment
python -m venv venv

# Windows (Command Prompt / PowerShell)
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to create your local `.env`:
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Configure your local `.env` file (use safe credentials; never commit actual production secrets):
```env
FLASK_ENV=development
SECRET_KEY=replace-with-a-secure-random-32-byte-hex-string
WTF_CSRF_SECRET_KEY=replace-with-a-secure-random-32-byte-hex-string
TIMEZONE=Asia/Kolkata

# Local Database (MySQL)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ebt_system
DB_USER=root
DB_PASSWORD=your_local_password
DB_SSL=false

# Optional: To use zero-configuration SQLite locally, uncomment:
# DB_USE_SQLITE=1
```

### 6. Initialize Database & Seed Demo Data
```bash
# Automatically creates all 26 relational tables and initial superadmin/roles
python scripts/init_db.py

# Seeds comprehensive sample employees, departments, schedules, and payroll
python scripts/setup_demo.py
```

### 7. Run the Application
```bash
python run.py
```
Open your web browser and navigate to: `http://127.0.0.1:5000`

---

## 🔑 Demo Login Credentials for Evaluation

For examiner, faculty, or evaluator testing:

| Role | Username | Password | Key Permissions & Capabilities |
|---|---|---|---|
| **Super Admin** | `superadmin` | `SuperAdmin@123` | Global tenant management, subscription packages, and system RBAC |
| **Administrator** | `admin` | `Admin@123` | Full enterprise HR management, payroll, leave reviews, and reports |
| **Standard Employee** | `sneha.patil` | `Employee@123` | Self-service check-in, dynamic break tracker, leave application, payslips |
| **Standard Employee** | `rahul.sharma` | `Employee@123` | Attendance tracking, break logging, availability predictions |

*(Note: In production environments, passwords can be changed securely at `/auth/reset-password` or by administrators via the user management console).*

---

## 🧪 Comprehensive Automated Test Suite

The project includes an extensive test suite verifying 68 test cases across all blueprints and functional modules:

```bash
# Run all tests with verbose output
pytest -v

# Run Phase 6-8 enhancements test suite
pytest tests/test_hrms360_phase678.py -v

# Run authentication and RBAC security suite
pytest tests/test_auth_superadmin_rbac.py -v
```

### Test Suite Summary:
* **68 / 68 Passed (100% Pass Rate)**
* **Categories Tested**:
  - Application startup, configuration, and blueprint registration
  - Database connectivity, SSL initialization, and table schemas
  - Authentication, email verification, 2FA OTP, password reset, and session lock
  - Super Admin tenant management and subscription tiers
  - RBAC permission enforcement and route isolation
  - Employee list vs grid view, profile view, department & designation CRUD
  - Attendance check-in/out, live elapsed time, and break math
  - Shift schedules and leave policy management
  - Dedicated HR, Attendance, and Recruitment dashboards
  - Payroll calculation, pay components configuration, and PDF payslips
  - ReportLab PDF and OpenPyXL Excel report exports
  - Scikit-Learn ML preprocessing and Random Forest prediction

---

## 📁 Project Directory Structure & Submission Checklist

```
AI-Employee-Tracking-System/
├── app/
│   ├── __init__.py                # App factory, DB init, and table synchronizer
│   ├── models.py                  # 26 SQLAlchemy ORM models
│   ├── forms.py                   # Form definitions and validation
│   ├── auth/                      # Authentication, OTP, and password reset routes
│   ├── attendance/                # Check-in/out, schedules, and shift routes
│   ├── breaks/                    # Break start/stop and session tracking
│   ├── employees/                 # Employee directory, grid view, depts & designations
│   ├── leave/                     # Leave requests, review, and policy settings
│   ├── payroll/                   # Salary structures, components, and payslips
│   ├── reports/                   # PDF & Excel export routes
│   ├── dashboard/                 # HR, Attendance, and Recruitment dashboards
│   ├── holidays/                  # Holiday calendar management
│   ├── superadmin/                # Multi-tenancy and subscription management
│   ├── ml/                        # Scikit-Learn Random Forest prediction engine
│   ├── static/                    # CSS stylesheets, JS scripts, and brand assets
│   └── templates/                 # Jinja2 enterprise templates
├── tests/
│   ├── test_ebt.py                # Core attendance, breaks, leave, payroll tests
│   ├── test_auth_superadmin_rbac.py # Auth, Super Admin, and RBAC test suite
│   └── test_hrms360_phase678.py   # Employee grid, shifts, policies, dashboards
├── scripts/
│   ├── init_db.py                 # Database initialization script
│   ├── setup_demo.py              # Sample data population script
│   └── backup_db.py               # Safe database JSON backup utility
├── Procfile                       # Render production deployment configuration
├── requirements.txt               # Locked production dependencies
├── pytest.ini                     # Pytest testing configuration
├── run.py                         # Local development runner
└── wsgi_prod.py                   # Production WSGI entry point
```

### 📋 Clean Google Drive Submission Checklist
When packaging this repository for college submission or archiving, **DO NOT INCLUDE** sensitive or generated files:

* [x] **Exclude**: `.env` (Never share database credentials or secret keys; use `.env.example`)
* [x] **Exclude**: `venv/` (Virtual environment folder; examiners install via `requirements.txt`)
* [x] **Exclude**: `.git/` (Hidden version control folder)
* [x] **Exclude**: `__pycache__/` and `*.pyc` (Generated Python bytecode)
* [x] **Exclude**: `.pytest_cache/` (Generated testing cache)
* [x] **Include**: Complete `app/` source directory (models, routes, templates, static)
* [x] **Include**: Complete `tests/` test suite
* [x] **Include**: Complete `scripts/` setup and backup utilities
* [x] **Include**: `requirements.txt`, `run.py`, `wsgi_prod.py`, `Procfile`, `pytest.ini`
* [x] **Include**: `.env.example` (Template with safe placeholders)
* [x] **Include**: Updated `README.md`

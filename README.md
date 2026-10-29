# Employee Break Tracking & Availability Prediction System (EBT System)

**EBT System** | *Work Smarter. Track Better. Improve Productivity.*

A full-stack, enterprise-ready Python Flask application for tracking employee attendance, monitoring multiple break categories, managing leave requests, exporting PDF/Excel audit reports, and predicting break duration and availability using Scikit-Learn Machine Learning (Random Forest).

---

## 🌐 Live Application & Repository

* **Production URL**: [https://ai-employee-tracking-system.onrender.com](https://ai-employee-tracking-system.onrender.com)
* **GitHub Repository**: [https://github.com/Vijju2005/AI-Employee-Tracking-System](https://github.com/Vijju2005/AI-Employee-Tracking-System)
* **Production Database**: TiDB Cloud Starter (Managed MySQL-compatible cluster with TLS/SSL encryption)

---

## 📋 Problem Statement & Objectives

### The Problem
Traditional attendance systems only capture punch-in and punch-out times, obscuring actual break habits, active availability, and real net working hours. In modern hybrid or office settings, managers struggle to assess team availability, anticipate when employees will return from breaks, and process leaves without manual spreadsheets.

### Objectives
1. **Accurate Time Tracking**: Record precise server timestamps (stored in UTC, rendered in IST: `Asia/Kolkata`).
2. **Dynamic Working Hours**: Continuously calculate elapsed and net working hours while employees are checked in ($Working\,Hours = Gross\,Elapsed - Total\,Breaks$).
3. **Multi-Category Break Management**: Track Tea, Lunch, Coffee, Personal, and Other breaks with overlap and duplication prevention.
4. **Machine Learning Predictions**: Forecast break duration and available working time using historical averages and Random Forest regression.
5. **Role-Based Access Control (RBAC)**: Enforce isolated views for Administrators and Employees.
6. **Audit & Compliance Reporting**: Generate branded PDF and formatted Excel reports on demand.

---

## 🛠️ Technology Stack & Architecture

```
                      +-----------------------------+
                      |   Browser / Client Devices  |
                      +--------------+--------------+
                                     |  HTTPS (Render)
                                     v
                      +-----------------------------+
                      |       Gunicorn / WSGI       |
                      +--------------+--------------+
                                     |
                                     v
                      +-----------------------------+
                      |      Flask Application      |
                      |  - Blueprints & Jinja2      |
                      |  - Flask-Login & CSRF       |
                      |  - Scikit-Learn ML Engine   |
                      |  - ReportLab & OpenPyXL     |
                      +--------------+--------------+
                                     | TLS / SSL (certifi)
                                     v
                      +-----------------------------+
                      |   TiDB Cloud / MySQL 8.0    |
                      |   (ebt_system cluster)      |
                      +-----------------------------+
```

* **Backend**: Python 3.14, Flask 3.1, Gunicorn
* **Database & ORM**: SQLAlchemy 2.0, PyMySQL, TiDB Cloud / MySQL 8.0
* **Frontend**: HTML5, Vanilla JavaScript, CSS3 (Enterprise Navy-Blue Design System), Chart.js
* **Machine Learning**: Scikit-Learn (Random Forest Regressor, MAE/RMSE metrics), NumPy, Pandas
* **Report Generation**: ReportLab (PDF), OpenPyXL (Excel `.xlsx`)
* **Security & Auth**: Flask-Login, Flask-WTF (CSRF), Werkzeug bcrypt hashing, HTTP security headers

---

## 👥 Features by Role

### 👨‍💼 Administrator Portal
* **Dashboard Overview**: Real-time KPI metric cards (Total Employees, Present Today, Pending Leaves, Active Breaks).
* **Visual Analytics**: 7-day attendance trend charts (Present vs Absent) and Department employee distribution charts via Chart.js.
* **Employee Management**: Create, edit, search, and toggle active/inactive status for staff members.
* **Attendance & Break Auditing**: Inspect timestamps, check-in statuses, and break durations across all departments.
* **Leave Review**: Review pending leave applications with one-click Approve/Reject, admin remarks, and automated email notifications.
* **Organization-Wide ML Predictions**: Run availability predictions for any employee and break type.
* **Enterprise Reporting**: Export custom-filtered PDF and Excel reports for attendance, breaks, leaves, and working hours.

### 👩‍💻 Employee Portal
* **Check-In / Check-Out**: One-click check-in with duplicate session prevention and automated IST timestamping.
* **Live Dynamic Working Hours**: Real-time client-side timer calculating net working hours every second.
* **Break Management**: Start and end multiple breaks (Lunch, Tea, Coffee, Personal, Other) with active break tracking.
* **Leave Requests**: Apply for Casual, Sick, or Annual leaves with Full Day, Half Day, or Partial options.
* **Smart Break Predictions**: View personalized machine learning predictions of expected break duration and remaining daily availability.
* **Personal History**: Access personal attendance, break, and leave records anytime.

---

## 🤖 Machine Learning Model: Availability & Break Prediction

The system implements a tiered prediction architecture:

1. **Cold Start / Global Baseline**:
   - For employees with fewer than 5 records, the system calculates the category average duration across all completed records.
2. **Personal Historical Baseline**:
   - For employees with between 5 and 19 historical records, the model computes their personalized rolling category average.
3. **Random Forest Regressor ($\ge 20$ records)**:
   - When 20 or more category break records exist for an employee, a `RandomForestRegressor` (50 estimators) is trained dynamically on:
     - Day of the week (`weekday`)
     - Hour of the day (`hour_of_day`)
     - Encoded break category (`category_encoded`)
     - Total scheduled daily hours (`scheduled_hours`)
   - Returns predicted break duration along with validation metrics:
     - **MAE** (Mean Absolute Error)
     - **RMSE** (Root Mean Squared Error)
   - Computes estimated net available working minutes remaining in the shift:
     $$\text{Available Minutes} = \max\Big(0,\; (\text{Scheduled Hours} \times 60) - \text{Predicted Break Duration}\Big)$$

---

## 💻 Local Installation & Setup

### 1. Prerequisites
* Python 3.9+ (Python 3.11–3.14 supported)
* MySQL 8.0+ or local SQLite fallback
* Git

### 2. Clone Repository
```bash
git clone https://github.com/Vijju2005/AI-Employee-Tracking-System.git
cd AI-Employee-Tracking-System
```

### 3. Create & Activate Virtual Environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env`:
```bash
copy .env.example .env    # Windows
cp .env.example .env      # Linux/macOS
```

Fill in required settings (generate random secret keys using `python -c "import secrets; print(secrets.token_hex(32))"`):
```env
FLASK_ENV=development
SECRET_KEY=replace-with-a-secure-random-string
WTF_CSRF_SECRET_KEY=replace-with-a-secure-random-string
TIMEZONE=Asia/Kolkata

# Local Database Configuration:
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ebt_system
DB_USER=ebt_app
DB_PASSWORD=your_local_mysql_password
DB_SSL=false
```

*(Note: To run locally with zero-configuration SQLite instead of MySQL, set `DB_USE_SQLITE=1` in your `.env`)*

### 6. Run Database Migrations & Seed Demo Data
```bash
python scripts/init_db.py
python scripts/setup_demo.py
```

### 7. Run Local Development Server
```bash
python run.py
```
Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in your web browser.

---

## 🔒 Security & Data Protection Review

The application underwent a comprehensive Day 7 security audit:
* **CSRF Protection**: All state-changing POST requests require a valid CSRF token verified via `Flask-WTF`.
* **Password Hashing**: Passwords stored using Werkzeug secure password hashing (PBKDF2/SHA256).
* **Session Security**: Session cookies configured with `HttpOnly`, `SameSite=Lax`, and `Secure` flag in production.
* **HTTP Security Headers**: Injected on all responses:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY` (anti-clickjacking)
  - `X-XSS-Protection: 1; mode=block`
  - `Referrer-Policy: strict-origin-when-cross-origin`
* **Open Redirect Defense**: Sanitized `next` parameter validation preventing `//evil.com` or `/\evil.com` redirection exploits.
* **Role-Based Access Control**: `@admin_required` decorators strictly isolate administrator endpoints; employees attempting unauthorized access receive HTTP 403.
* **SQL Injection Prevention**: All database interactions use SQLAlchemy parameterized queries and ORM objects.

---

## 💾 Database Backup & Recovery Procedure

### Automated TiDB Cloud Backups
The cloud production cluster `ebt-cluster` on TiDB Cloud Starter features automated cloud backups and multi-zone AWS replication.

### Manual / Local JSON Dump Utility
A custom non-destructive backup utility is provided in `scripts/backup_db.py`:
```bash
python scripts/backup_db.py
```
This utility:
1. Connects using the configured database environment variables.
2. Extracts all 8 system tables (`users`, `employees`, `departments`, `work_schedules`, `attendance`, `breaks`, `leave_requests`, `break_predictions`).
3. Serializes dates and decimals safely into `backups/ebt_backup_<TIMESTAMP>.json`.
4. Never modifies, deletes, or overwrites existing records.

---

## 🧪 Automated Testing

Run the complete 37-test automated verification suite:
```bash
pytest tests/ -v
```
**Test Coverage Includes:**
* Application factory and blueprint registration
* Database table creation and schema connectivity
* Authentication, setup, and password hashing
* Employee management and duplicate ID rejection
* Attendance check-in, check-out, and live working-hour calculations
* Break tracking, duration math, and non-overlapping constraints
* Leave request creation and admin approval workflows
* ML preprocessing, baseline evaluation, and Random Forest regressors
* Security headers, RBAC route isolation, and open redirect defenses

---

## 📖 User Guide & Demo Accounts

### Demo Accounts for Testing & Evaluation:
| Role | Username | Default Password | Features Accessible |
|---|---|---|---|
| **Administrator** | `admin` | `Admin@123` | Full dashboard, employee management, leave reviews, report export |
| **Employee** | `sneha.patil` | `Employee@123` | Personal dashboard, check-in/out, start/end breaks, apply leave |
| **Employee** | `rahul.sharma` | `Employee@123` | Personal dashboard, attendance tracking, leave requests |

*(Note: In production environments, administrators can immediately reset credentials via the employee edit panel).*

### Workflow Guide:
1. **Login**: Visit `/auth/login`, enter credentials, and select "Sign In".
2. **Attendance**: On the Employee Dashboard, click `Check In`. The card changes to `Checked In` and the live timer begins tracking working time.
3. **Breaks**: Select a category (e.g. *Tea*, *Lunch*) and click `Start Break`. The card highlights the active break. Click `End Break` once finished.
4. **Checkout**: Click `Check Out`. The system calculates final gross and net working hours.
5. **Leave**: Navigate to `Leave Management` $\rightarrow$ `Apply Leave`. Fill in the dates, type, and reason. The administrator reviews this under `/leave`.
6. **Reports**: Go to `Reports`, choose the report type (Attendance, Breaks, Leave, Working Hours), select PDF or Excel, and click `Generate Report`.

---

## 🔧 Troubleshooting Guide

| Issue | Root Cause | Solution |
|---|---|---|
| **HTTP 500 on Login** | Cloud database credentials out of sync | Verify `DB_PASSWORD` or `DATABASE_URL` in Render environment settings. |
| **"Application Loading" Timeout** | Blocking initialization scripts during Gunicorn boot | Ensure Procfile runs `web: gunicorn wsgi_prod:app` directly without long blocking commands. |
| **Working Hours Shows 0h 0m** | Database check-in time missing or uncalculated | Trigger check-in; client-side JS and backend `get_net_working_minutes()` will calculate elapsed time. |
| **PDF/Excel Export Fails** | Missing ReportLab/OpenPyXL libraries | Verify dependencies with `pip install -r requirements.txt`. |

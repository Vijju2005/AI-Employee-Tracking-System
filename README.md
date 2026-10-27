# Employee Break Tracking & Availability Prediction System

**EBT System** | *Work Smarter. Track Better. Improve Productivity.*

A full-stack Flask web application for managing employee attendance, breaks, leave requests, and predicting break duration using machine learning.

---

## 📋 Project Overview

The EBT System is a browser-based HR management application with:
- **Admin Portal** — Manage employees, view all attendance/breaks, approve leaves, generate reports, and view AI predictions
- **Employee Portal** — Check in/out, manage breaks, apply for leave, view personal history and predictions

---

## ✨ Features

| Category | Features |
|---|---|
| **Authentication** | Role-based login (Admin/Employee), secure password hashing, session management, CSRF protection |
| **Employee Management** | Add, view, edit employees; departments; work schedules |
| **Attendance** | Check-in/out with server timestamps, duplicate prevention, net working time calculation |
| **Break Tracking** | Lunch, Tea, Coffee, Personal, Other categories; overlap prevention; multiple breaks per session |
| **Leave Management** | Full/half/partial day leave; Pending/Approved/Rejected workflow |
| **Dashboards** | Admin stats + charts; Employee daily summary |
| **Reports** | PDF (ReportLab) and Excel (openpyxl) for attendance, breaks, leave, working hours |
| **ML Prediction** | Historical average baseline + Random Forest (when ≥20 samples); MAE/RMSE evaluation |
| **Responsive UI** | Navy-blue corporate design; mobile-friendly |

---

## 🛠️ Technology Stack

- **Backend**: Python 3.14, Flask 3.1
- **Database**: MySQL 8.0, Flask-SQLAlchemy, PyMySQL
- **Frontend**: HTML5, CSS3, JavaScript, Chart.js
- **ML**: Pandas, NumPy, Scikit-learn (Random Forest)
- **Reports**: ReportLab (PDF), openpyxl (Excel)
- **Auth**: Flask-Login, Flask-WTF (CSRF), bcrypt
- **Testing**: pytest, pytest-flask

---

## 📦 Requirements

- Python 3.9+
- MySQL 8.0+
- pip

---

## 🚀 Setup Instructions

### 1. Clone / Navigate to Project

```bash
cd "EMPLOYEE BREAK TRACKING & AVAILABILITY PREDICTION SYSTEM"
```

### 2. Create Virtual Environment (recommended)

```bash
python -m venv venv
venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/macOS
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

```bash
copy .env.example .env
```

Edit `.env` and fill in your MySQL credentials:

```env
SECRET_KEY=your-random-secret-key-here
WTF_CSRF_SECRET_KEY=another-random-key
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ebt_system
DB_USER=ebt_app
DB_PASSWORD=your-password-here
FLASK_ENV=development
TIMEZONE=Asia/Kolkata
```

Generate a secret key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. MySQL Setup

The database and user must already exist. Run in MySQL Workbench or CLI:

```sql
CREATE DATABASE ebt_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'ebt_app'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON ebt_system.* TO 'ebt_app'@'localhost';
FLUSH PRIVILEGES;
```

### 6. Test Database Connection

```bash
python scripts/test_connection.py
```

### 7. Initialize Database (create tables)

```bash
python scripts/init_db.py
```

### 8. Seed Demo Data (Admin + Employees + 30 days history)

```bash
# Creates admin user + 3 demo employees with departments & schedules
python scripts/setup_demo.py

# Seeds 30 days of attendance + break records for ML training
python scripts/seed_history.py
```

### 9. Create Admin Account (alternative — UI setup)

If you prefer the browser setup, visit: `http://localhost:5000/auth/setup`

> This one-time setup page is only available before any admin account exists.

### 10. Run the Application

```bash
python run.py
```

Open: **http://localhost:5000**

---

## 🔑 Demo Credentials

After running `scripts/setup_demo.py` and `scripts/seed_history.py`:

| Role | Username | Password |
|------|----------|----------|
| **Admin** | `admin` | `Admin@123` |
| **Employee** | `sneha.patil` | `Employee@123` |
| **Employee** | `arjun.mehta` | `Employee@123` |
| **Employee** | `kavya.reddy` | `Employee@123` |

> **Note**: The system starts with 84 seeded attendance records and 191 break records across 5 employees, providing enough data for Random Forest training (≥20 samples threshold).

---

## 🧪 Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test class
pytest tests/test_ebt.py::TestAttendance -v

# Run with coverage
pip install pytest-cov
pytest tests/ --cov=app --cov-report=html
```

> **Note**: Unit tests use **SQLite in-memory** — no MySQL setup required for testing.
> Run `FLASK_ENV=testing pytest tests/ -v` to skip MySQL entirely.

---

## 🤖 ML Training & Evaluation

The ML prediction module runs automatically when you visit `/ml/`:

1. **Historical Average Baseline** — Always computed from break records grouped by category
2. **Random Forest** — Trained when ≥20 completed break records exist
3. **Evaluation** — Chronological train/test split (80%/20%), MAE and RMSE reported

To generate demo data for ML testing:
```bash
python scripts/init_db.py --seed-demo
```
Then add break records through the employee portal for several days.

**Features used** (no target leakage):
- Weekday (0=Mon, 6=Sun)
- Hour of day
- Break category (encoded)
- Scheduled working hours
- Prior breaks today
- Rolling 7-day average duration per employee+category

---

## 📄 Report Export

1. Login as Admin or Employee
2. Go to **Reports** in the sidebar
3. Select report type, format (PDF/Excel), date range, and optional filters
4. Click **Generate & Download**

Available reports: Attendance, Breaks, Leave, Working Hours Summary

---

## 🎯 Demo Steps

### Quick Demo (with seeded data)
1. Run `python scripts/setup_demo.py` and `python scripts/seed_history.py`
2. Start Flask: `python run.py`
3. Open http://localhost:5000

### Admin walkthrough
1. Login: `admin` / `Admin@123`
2. Dashboard → view employee count, attendance stats, break activity
3. **Employees** → view list, add new employee, toggle active/inactive status
4. **Attendance** → view all employees' check-in/out history and filter by date
5. **Reports** → select type (Attendance/Breaks/Leave/Working Hours), format (PDF/Excel) → **Generate & Download**
6. **Leave** → view pending requests, approve or reject
7. **ML Prediction** → select employee + break category → Predict → see estimated duration

### Employee walkthrough
1. Login: `sneha.patil` / `Employee@123`
2. **Attendance** → Click **Check In** → clock in recorded
3. **Breaks** → Click **Start Break** → select Lunch → **End Break**
4. **Attendance** → Click **Check Out** → net working time shown
5. **Leave** → Apply for leave (select dates + type + reason)
6. **ML Prediction** → predict break duration for the week

---

## ⚠️ Known Limitations

1. **ML accuracy** — Predictions improve significantly with more historical data (≥50 records recommended for meaningful RF training)
2. **No email notifications** — Leave approvals/rejections don't send emails (Flask-Mail configured but not triggered)
3. **No file attachments** — Leave requests don't support document uploads
4. **Single timezone** — The system uses server timezone; multi-timezone support would require additional configuration
5. **No real-time updates** — Dashboard doesn't auto-refresh; manual page reload required

---

## 📁 Project Structure

```
EMPLOYEE BREAK TRACKING & AVAILABILITY PREDICTION SYSTEM/
├── app/
│   ├── __init__.py          # Application factory
│   ├── extensions.py        # SQLAlchemy, LoginManager, CSRF
│   ├── models.py            # All SQLAlchemy models
│   ├── auth/routes.py       # Login, logout, setup
│   ├── dashboard/routes.py  # Admin + employee dashboards
│   ├── employees/routes.py  # Employee CRUD (admin)
│   ├── attendance/routes.py # Check-in/out
│   ├── breaks/routes.py     # Break start/end
│   ├── leave/routes.py      # Leave requests
│   ├── reports/routes.py    # PDF + Excel generation
│   ├── ml/
│   │   ├── preprocessing.py # Feature engineering
│   │   ├── train.py         # Model training + evaluation
│   │   ├── predict.py       # Inference + availability
│   │   └── routes.py        # ML prediction page
│   ├── templates/           # Jinja2 HTML templates
│   └── static/
│       ├── css/main.css     # Corporate design system
│       └── js/main.js       # Frontend interactions
├── tests/test_ebt.py        # pytest test suite
├── scripts/
│   ├── init_db.py           # DB initialization (create tables)
│   ├── setup_demo.py        # Create admin + demo employees (idempotent)
│   ├── seed_history.py      # Seed 30 days of attendance + break records
│   └── test_connection.py   # MySQL connectivity test
├── config.py                # Environment-based configuration
├── run.py                   # Application entry point
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## 🔐 Security Notes

- Passwords are hashed with Werkzeug's `generate_password_hash` (PBKDF2/scrypt)
- CSRF tokens protect all state-changing forms
- Role-based access enforced server-side (not just frontend)
- Employees cannot access other employees' records
- `.env` file is in `.gitignore` — never commit real credentials
- Use a strong `SECRET_KEY` in production
- Set `FLASK_ENV=production` and `FLASK_DEBUG=0` in production

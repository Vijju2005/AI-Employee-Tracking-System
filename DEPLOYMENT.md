# EBT System — Production Deployment Guide (Windows)

This document describes how to deploy the **Employee Break Tracking & Availability Prediction System** in a production environment on Windows Server or Windows 10/11 using **Waitress** WSGI server and **MySQL 8.0+**.

---

## 1. Prerequisites

1. **Python 3.9+** (64-bit) installed with "Add Python to PATH" enabled.
2. **MySQL Server 8.0+** running as a Windows service on port 3306.
3. Dedicated database user and database with utf8mb4 collation:
   ```sql
   CREATE DATABASE ebt_system CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'ebt_app'@'localhost' IDENTIFIED BY 'StrongProductionPassword!';
   GRANT ALL PRIVILEGES ON ebt_system.* TO 'ebt_app'@'localhost';
   FLUSH PRIVILEGES;
   ```

---

## 2. Environment Configuration (`.env`)

Create or update `.env` in the project root:

```env
# ── Core Security ────────────────────────────────────────────────
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=947493a0bfa7d530869aef0266...
WTF_CSRF_SECRET_KEY=38fae83bc489...

# ── Flask Environment ────────────────────────────────────────────
FLASK_ENV=production
FLASK_DEBUG=0

# ── Database (MySQL) ─────────────────────────────────────────────
DB_HOST=localhost
DB_PORT=3306
DB_NAME=ebt_system
DB_USER=ebt_app
DB_PASSWORD=StrongProductionPassword!

# ── Application Settings ─────────────────────────────────────────
APP_NAME=EBT System
TIMEZONE=Asia/Kolkata

# ── Email / SMTP (Flask-Mail) ────────────────────────────────────
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=notifications@company.com
MAIL_PASSWORD=AppSpecificPasswordOrSecret
MAIL_DEFAULT_SENDER="EBT HR Portal" <notifications@company.com>
MAIL_SUPPRESS_SEND=false
```

---

## 3. Dependency Installation

Open PowerShell as Administrator / standard deployment user:

```powershell
cd "c:\path\to\EMPLOYEE BREAK TRACKING & AVAILABILITY PREDICTION SYSTEM"

# Create / activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install production dependencies
pip install -r requirements.txt
```

---

## 4. Database Initialization & Verification

Run the connectivity check and table initializer:

```powershell
python scripts/test_connection.py
python scripts/init_db.py
```

Optional demo seed (only if staging/demo environment):
```powershell
python scripts/setup_demo.py
python scripts/seed_history.py
```

---

## 5. Running with Production WSGI Server (Waitress)

### Direct Execution
Waitress is a production-quality, multi-threaded pure Python WSGI server designed and tested specifically for Windows:

```powershell
python wsgi_prod.py
```

Or using the CLI runner:
```powershell
waitress-serve --host=0.0.0.0 --port=5000 --threads=6 wsgi_prod:app
```

The application will bind to `http://0.0.0.0:5000` with:
- 6 concurrent worker threads
- Connection pooling and auto pre-ping for MySQL
- Secure session cookies (`SESSION_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True`, `SameSite=Lax`)
- Strict CSRF validation

---

## 6. Reverse Proxy Setup (Recommended for Windows)

In enterprise production deployments, place IIS (with URL Rewrite + ARR) or NGINX for Windows in front of Waitress:

- **SSL/TLS Termination**: Install your corporate certificate on IIS/NGINX (Port 443 HTTPS).
- **Reverse Proxy**: Forward HTTPS traffic to `http://127.0.0.1:5000`.
- **Static Assets**: Serve `/static/` files directly through IIS/NGINX for maximum performance.

---

## 7. Windows Service Configuration (NSSM - Optional)

To run Waitress automatically on Windows startup in the background:

1. Download **NSSM** (Non-Sucking Service Manager) from `https://nssm.cc/`.
2. Open Administrator Command Prompt:
   ```cmd
   nssm install EBT_Service "C:\path\to\EMPLOYEE BREAK TRACKING & AVAILABILITY PREDICTION SYSTEM\venv\Scripts\python.exe" "C:\path\to\EMPLOYEE BREAK TRACKING & AVAILABILITY PREDICTION SYSTEM\wsgi_prod.py"
   nssm set EBT_Service AppDirectory "C:\path\to\EMPLOYEE BREAK TRACKING & AVAILABILITY PREDICTION SYSTEM"
   nssm start EBT_Service
   ```
3. The service can then be monitored via `services.msc`.

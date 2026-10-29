# EMPLOYEE BREAK TRACKING & AVAILABILITY PREDICTION SYSTEM
## Comprehensive Final Project Technical Report

**Author / Developer**: Vijju2005  
**Technologies**: Python 3.14, Flask 3.1, MySQL / TiDB Cloud, Scikit-Learn, HTML5, CSS3, JavaScript, Chart.js  
**Hosting Platform**: Render Cloud Web Services (HTTPS)  
**Live Production URL**: [https://ai-employee-tracking-system.onrender.com](https://ai-employee-tracking-system.onrender.com)  
**GitHub Repository**: [https://github.com/Vijju2005/AI-Employee-Tracking-System](https://github.com/Vijju2005/AI-Employee-Tracking-System)  

---

### 1. Abstract
The **Employee Break Tracking & Availability Prediction System (EBT System)** is a web-based human resource management solution designed to provide transparent, accurate, and predictive insights into employee work cycles. Traditional attendance platforms record check-in and check-out events but fail to measure micro-break durations, net working time, and real-time team availability. This system addresses those gaps by combining server-side UTC timestamping with localized Indian Standard Time (IST) presentation, dynamic working hours calculation, multi-category break tracking (Tea, Lunch, Coffee, Personal, Other), leave request management, on-demand PDF/Excel report exports, and machine learning availability predictions driven by Random Forest regression. Deployed on Render with a TLS-secured TiDB Cloud database, the platform satisfies enterprise performance, security, and auditing standards.

---

### 2. Problem Statement
In modern hybrid and in-office workplaces, productivity measurement suffers from significant blind spots:
1. **Gross vs. Net Discrepancies**: Basic biometric or punch-card systems only register arrival and departure times, ignoring intermediate breaks that often exceed allotted limits.
2. **Unpredictable Availability**: Team leads and project managers frequently do not know when a team member on break will return, leading to delayed meetings and misallocated urgent tasks.
3. **Manual Overhead**: Tracking break times and leaves using disparate spreadsheets leads to human error, missed leave balances, and payroll disputes.
4. **Data Isolation**: Organizations lack historical analytics and predictive tools that correlate shift durations, days of the week, and break categories.

---

### 3. Objectives
* Build an automated, web-accessible attendance platform with zero manual spreadsheet reliance.
* Enforce server-side timestamp recording in UTC, converted and displayed in Indian Standard Time (IST).
* Dynamically calculate live net working hours ($Working\,Hours = Elapsed\,Session\,Duration - Completed\,Breaks$).
* Support multi-category breaks with overlap prevention and automatic break closure upon shift check-out.
* Integrate a tiered machine learning model using baseline averages and Random Forest Regressors to predict break durations and available work time.
* Implement strict Role-Based Access Control (RBAC) isolating Administrative controls from Employee self-service functions.
* Provide one-click audit report generation in branded PDF (ReportLab) and formatted Excel (OpenPyXL) formats.
* Deploy on a cloud infrastructure using Render and a managed TiDB Cloud MySQL database with automated schema creation.

---

### 4. Existing System Limitations
| Feature | Conventional Systems | EBT System (Proposed) |
|---|---|---|
| **Punch Tracking** | Check-in / Check-out only | Check-in, Check-out, and continuous Live Working Hours |
| **Break Monitoring** | Untracked or honor-system logs | Real-time multi-category tracking with active timer |
| **Timezone Consistency** | Prone to client device clock tampering | Strict server UTC storage with localized IST formatting |
| **Predictive AI** | None | Random Forest break and availability forecasting |
| **Audit Reporting** | Static or limited CSV exports | Branded PDF tables and styled Excel workbooks |
| **Security & RBAC** | Basic password checks | CSRF protection, secure hashing, RBAC, and security headers |

---

### 5. Proposed Solution & System Architecture
The application follows a clean 3-tier architectural model:

1. **Client / Presentation Layer**:
   - Modern, responsive HTML5/CSS3 frontend using an enterprise Navy-Blue design system.
   - Dynamic client-side JavaScript executing real-time second-by-second countdown and working-hour counters.
   - Interactive Chart.js visual analytics rendering 7-day attendance trends and departmental headcounts.
2. **Application / Logic Layer**:
   - Python Flask 3.1 web framework structured via modular Blueprints (`auth`, `dashboard`, `employees`, `attendance`, `breaks`, `leave`, `reports`, `ml`).
   - Flask-Login managing user sessions and `@admin_required` decorators enforcing role separation.
   - Scikit-Learn machine learning engine evaluating feature sets and running regressions.
   - ReportLab and OpenPyXL modules formatting binary document streams in-memory without temporary file exposure.
3. **Data / Storage Layer**:
   - TiDB Cloud Starter managed MySQL-compatible cluster.
   - TLS 1.2/1.3 encryption using `certifi` CA verification.
   - SQLAlchemy 2.0 ORM managing connection pooling (`pool_pre_ping`, `pool_recycle=300`).

---

### 6. Database Design & Schema
The relational database `ebt_system` contains 8 relational tables:

```
  +------------------+         +------------------+
  |      users       |1 ----- 1|    employees     |
  +------------------+         +--------+---------+
                                        | 1
                                        |
       +--------------------------------+-------------------------------+
       | 1                              | 1                             | 1
       v *                              v *                             v *
+--------------+                +---------------+               +-----------------+
|  attendance  |1             * |     breaks    |               |  leave_requests |
+-------+------+                +---------------+               +-----------------+
        | 1
        |
        v *
+--------------+
|    breaks    |
+--------------+
```

1. **`users`**: Authentication credentials, role (`ADMIN`, `EMPLOYEE`), active state, password hashes, and last login timestamps.
2. **`departments`**: Organizational departments (Engineering, HR, Sales, Marketing, Support, Operations).
3. **`work_schedules`**: Shift templates detailing start times, end times, and expected daily hours.
4. **`employees`**: Employee master records, unique employee IDs (`EMP001`), contact info, department foreign keys, and user links.
5. **`attendance`**: Daily session records, date, check-in, check-out, gross duration, total break duration, net working hours, and status (`Present`, `Half Day`, `On Leave`, `Absent`).
6. **`breaks`**: Individual break events, linked to attendance and employee, category (`Lunch`, `Tea`, `Coffee`, `Personal`, `Other`), start time, end time, and duration in minutes.
7. **`leave_requests`**: Employee leave requests, leave type (`Casual`, `Sick`, `Annual`), day type (`Full Day`, `Half Day`, `Partial`), date ranges, status (`Pending`, `Approved`, `Rejected`), and admin review notes.
8. **`break_predictions`**: Logged prediction events recording features, predicted minutes, available time, and evaluation errors.

---

### 7. Module Descriptions

#### A. Authentication & Security Module (`app.auth`)
* Enforces secure credentials validation with Werkzeug password hashing.
* Handles user login with persistent sessions and safe relative redirection (blocking open redirect vulnerabilities like `//evil.com`).
* Enforces HTTP response headers (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `X-XSS-Protection`, `Referrer-Policy`).

#### B. Dashboard Module (`app.dashboard`)
* **Admin Dashboard**: Aggregates top-level KPI metrics (Total Employees, Present Today, Pending Leaves, Active Breaks), renders 7-day attendance trends, department distribution charts, and lists recent pending leave submissions.
* **Employee Dashboard**: Displays personal shift summary, hero status card with action buttons, live working-hour timers, quick links, and mini AI availability cards.

#### C. Attendance Tracking Module (`app.attendance`)
* Validates check-in requests against active sessions and current calendar date.
* Automatically records UTC naive timestamps.
* Upon check-out, automatically closes any dangling open break and runs `recalculate()` to persist accurate gross, break, and net minutes.

#### D. Break Management Module (`app.breaks`)
* Supports multiple breaks per day across standard corporate categories.
* Checks for any existing active break before allowing a new break to start, eliminating overlapping break conflicts.
* Recalculates parent attendance records on completion.

#### E. Leave Management Module (`app.leave`)
* Self-service portal for employees to submit leave requests with date validation (`end_date >= start_date`).
* Administrative review portal with one-click approval or rejection and optional review notes.
* Asynchronous/integrated email notification dispatch via Flask-Mail to notify employees of decision outcomes.

#### F. Reporting Module (`app.reports`)
* Dynamic filtering by date range, department, and employee.
* Generates landscape A4 PDF documents via ReportLab with corporate branding, custom headers, and clean table wrapping.
* Generates formatted Excel `.xlsx` workbooks via OpenPyXL with auto-fitted column dimensions.

#### G. Machine Learning Module (`app.ml`)
* Predicts expected break durations and remaining productive hours based on contextual features.

---

### 8. Machine Learning Methodology
The machine learning pipeline predicts break duration ($y$) to forecast remaining available shift time.

#### Feature Engineering
Each completed break record extracts:
1. `weekday`: Day of the week (0 = Monday, 6 = Sunday).
2. `hour_of_day`: Hour when the break was initiated (0 to 23).
3. `category_encoded`: Categorical encoding of break type (Lunch: 0, Tea: 1, Coffee: 2, Personal: 3, Other: 4).
4. `scheduled_hours`: Standard scheduled shift duration (e.g. 8.0 hours).

#### Tiered Model Selection
* **Tier 1 (Cold Start: $N < 5$)**: Returns global average for the category.
* **Tier 2 (Personal Baseline: $5 \le N < 20$)**: Returns personal historical rolling average.
* **Tier 3 (Random Forest Regressor: $N \ge 20$)**:
  - Algorithm: `RandomForestRegressor(n_estimators=50, random_state=42)`
  - Data split: 80% training, 20% validation.
  - Evaluation Metrics:
    $$\text{MAE} = \frac{1}{n}\sum_{i=1}^{n}|y_i - \hat{y}_i|$$
    $$\text{RMSE} = \sqrt{\frac{1}{n}\sum_{i=1}^{n}(y_i - \hat{y}_i)^2}$$

#### Availability Calculation
$$\text{Available Working Minutes} = \max\Big(0,\; (\text{Scheduled Shift Hours} \times 60) - \text{Predicted Break Duration}\Big)$$

---

### 9. Testing & Quality Assurance
The system includes a 37-test automated verification suite built using `pytest` and `pytest-flask`.

#### Verification Summary:
```text
tests/test_ebt.py::TestAppStartup (3 tests) ...................... PASSED
tests/test_ebt.py::TestDatabase (2 tests) ........................ PASSED
tests/test_ebt.py::TestAuthentication (5 tests) .................. PASSED
tests/test_ebt.py::TestEmployeeManagement (3 tests) .............. PASSED
tests/test_ebt.py::TestAttendance (7 tests) ...................... PASSED
tests/test_ebt.py::TestBreaks (2 tests) .......................... PASSED
tests/test_ebt.py::TestLeave (3 tests) ........................... PASSED
tests/test_ebt.py::TestMLPreprocessing (6 tests) ................. PASSED
tests/test_ebt.py::TestSecurityAndAuthorization (6 tests) ........ PASSED

============================= 37 passed in 5.07s =============================
```

#### Key Test Scenarios:
1. **Dynamic Working Hours Calculation**: Verified that gross elapsed minutes minus completed break minutes equals exact net working time.
2. **Duplicate Check-in Prevention**: Verified that attempting multiple check-ins during an active shift is blocked.
3. **Role-Based Access Control**: Verified that an employee session attempting to view `/dashboard/admin` or `/employees/` receives an HTTP 403 Forbidden.
4. **Open Redirect Defenses**: Verified that login requests with malicious `next=//evil.com` safely redirect to internal dashboard routes.
5. **Report Generation**: Verified byte streams for PDF and Excel generation.

---

### 10. Challenges & Technical Solutions
1. **Challenge: Timezone Inconsistencies between UTC and Local Display**
   - *Solution*: Built [`app/time_utils.py`](file:///c:/Users/keert/Downloads/EMPLOYEE%20BREAK%20TRACKING%20&%20AVAILABILITY%20PREDICTION%20SYSTEM/app/time_utils.py) ensuring all database storage is naive UTC while Jinja2 template filters (`|local_time`, `|local_date`) and client JavaScript handle `Asia/Kolkata` presentation.
2. **Challenge: Render Free Web Service Boot Timeouts**
   - *Solution*: Removed blocking database migration scripts from `Procfile` command chains; implemented non-blocking idempotent startup checks in [`app/__init__.py`](file:///c:/Users/keert/Downloads/EMPLOYEE%20BREAK%20TRACKING%20&%20AVAILABILITY%20PREDICTION%20SYSTEM/app/__init__.py).
3. **Challenge: TiDB Cloud Public TLS Verification**
   - *Solution*: Configured `connect_args` in [`config.py`](file:///c:/Users/keert/Downloads/EMPLOYEE%20BREAK%20TRACKING%20&%20AVAILABILITY%20PREDICTION%20SYSTEM/config.py) using `certifi.where()` and hostname verification.
4. **Challenge: Unclosed Breaks on Shift Check-out**
   - *Solution*: Updated checkout route to detect open breaks and automatically close them with accurate duration accounting.

---

### 11. Future Enhancements
* **Mobile Geofencing**: GPS validation restricting check-ins to approved office premises or client sites.
* **Facial Recognition**: Biometric photo capture on punch-in to eliminate proxy attendance.
* **Calendar Integration**: Synchronization with Microsoft 365 and Google Calendar to mark break schedules automatically.
* **Slack / Teams Bot**: Quick `/break start` and `/checkin` chat commands.

---

### 12. Conclusion
The **Employee Break Tracking & Availability Prediction System** successfully modernizes workplace time tracking. By unifying attendance, multi-category break monitoring, leave management, automated audit reporting, and machine learning intelligence into a secure, responsive web application, the system delivers high accuracy, transparent reporting, and actionable operational insights.

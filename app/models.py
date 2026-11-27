"""
EBT System — SQLAlchemy Models
All database tables defined here.
"""

from datetime import datetime, timezone
from enum import Enum as PyEnum

from flask_login import UserMixin
from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, Time, UniqueConstraint, Index,
)
from sqlalchemy.orm import relationship

from app.extensions import db


# ── Helpers ───────────────────────────────────────────────────────────────────

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Enumerations ──────────────────────────────────────────────────────────────

class UserRole(str, PyEnum):
    SUPERADMIN = "superadmin"
    ADMIN = "admin"
    EMPLOYEE = "employee"


class AccountStatus(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class LeaveType(str, PyEnum):
    ANNUAL = "Annual"
    SICK = "Sick"
    CASUAL = "Casual"
    MATERNITY = "Maternity"
    PATERNITY = "Paternity"
    UNPAID = "Unpaid"
    OTHER = "Other"


class LeaveStatus(str, PyEnum):
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"


class LeaveDayType(str, PyEnum):
    FULL_DAY = "Full Day"
    HALF_DAY = "Half Day"
    PARTIAL = "Partial"


class BreakCategory(str, PyEnum):
    LUNCH = "Lunch"
    TEA = "Tea"
    COFFEE = "Coffee"
    PERSONAL = "Personal"
    OTHER = "Other"


class AttendanceStatus(str, PyEnum):
    PRESENT = "Present"
    ABSENT = "Absent"
    HALF_DAY = "Half Day"
    ON_LEAVE = "On Leave"


# ── Models ────────────────────────────────────────────────────────────────────

class Department(db.Model):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    employees = relationship("Employee", back_populates="department", lazy="dynamic")

    def __repr__(self):
        return f"<Department {self.name}>"

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description}


class WorkSchedule(db.Model):
    __tablename__ = "work_schedules"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    total_hours = Column(Float, nullable=False, default=8.0)
    description = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    employees = relationship("Employee", back_populates="work_schedule", lazy="dynamic")

    def __repr__(self):
        return f"<WorkSchedule {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "start_time": str(self.start_time),
            "end_time": str(self.end_time),
            "total_hours": self.total_hours,
        }


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False, unique=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.EMPLOYEE)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    last_login = Column(DateTime)

    # Core authentication & security extensions
    is_verified = Column(Boolean, default=True, nullable=False)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    otp_code = Column(String(6), nullable=True)
    otp_expires_at = Column(DateTime, nullable=True)

    # Multi-tenant Company linkage (optional for Super Admin)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True)

    employee = relationship("Employee", back_populates="user", uselist=False)
    company = relationship("Company", back_populates="users", foreign_keys=[company_id])
    roles = relationship("Role", secondary="user_roles", back_populates="users")

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

    @property
    def is_superadmin(self):
        return self.role == UserRole.SUPERADMIN

    @property
    def is_admin(self):
        return self.role in [UserRole.ADMIN, UserRole.SUPERADMIN]

    def has_role(self, role_name: str) -> bool:
        if self.is_superadmin:
            return True
        role_lower = role_name.lower()
        if self.role.value.lower() == role_lower:
            return True
        return any(r.name.lower() == role_lower for r in self.roles)

    def has_permission(self, permission_slug: str) -> bool:
        if self.is_superadmin:
            return True
        perm_lower = permission_slug.lower()
        for r in self.roles:
            for p in r.permissions:
                if p.slug.lower() == perm_lower:
                    return True
        # Admins by default have access to enterprise management modules
        if self.role == UserRole.ADMIN:
            return True
        return False

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "is_active": self.is_active,
        }


class Employee(db.Model):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True)
    employee_id = Column(String(20), nullable=False, unique=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(20))
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    designation = Column(String(100))
    company_name = Column(String(150), default="EBT System")
    work_schedule_id = Column(Integer, ForeignKey("work_schedules.id"), nullable=True)
    status = Column(Enum(AccountStatus), default=AccountStatus.ACTIVE, nullable=False)
    date_joined = Column(DateTime, default=utcnow)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    department = relationship("Department", back_populates="employees")
    work_schedule = relationship("WorkSchedule", back_populates="employees")
    user = relationship("User", back_populates="employee")
    manager = relationship("Employee", remote_side=[id], backref=db.backref("subordinates", lazy="dynamic"))
    attendance_records = relationship("Attendance", back_populates="employee", lazy="dynamic", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="employee", lazy="dynamic", cascade="all, delete-orphan")
    documents = relationship("EmployeeDocument", back_populates="employee", lazy="dynamic", cascade="all, delete-orphan")
    profile = relationship("EmployeeProfile", uselist=False, back_populates="employee", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Employee {self.employee_id} {self.full_name}>"

    @property
    def joining_calendar_year(self):
        """
        Dynamically returns the matching CalendarYear instance based on the employee's date_joined.
        """
        if not self.date_joined:
            return None
        return CalendarYear.get_calendar_year_for_date(self.date_joined)

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "department": self.department.name if self.department else None,
            "department_id": self.department_id,
            "designation": self.designation,
            "company_name": self.company_name,
            "work_schedule": self.work_schedule.name if self.work_schedule else None,
            "work_schedule_id": self.work_schedule_id,
            "status": self.status.value,
            "date_joined": self.date_joined.isoformat() if self.date_joined else None,
        }


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    date = Column(db.Date, nullable=False)
    check_in = Column(DateTime, nullable=True)
    check_out = Column(DateTime, nullable=True)
    total_duration_minutes = Column(Float, default=0.0)   # Gross time (check_in → check_out)
    break_duration_minutes = Column(Float, default=0.0)   # Sum of all break durations
    net_working_minutes = Column(Float, default=0.0)      # Gross − breaks
    status = Column(Enum(AttendanceStatus), default=AttendanceStatus.PRESENT)
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    employee = relationship("Employee", back_populates="attendance_records")
    breaks = relationship("Break", back_populates="attendance", lazy="dynamic", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_attendance_employee_date"),
        Index("ix_attendance_date", "date"),
        Index("ix_attendance_employee_date", "employee_id", "date"),
    )

    def __repr__(self):
        return f"<Attendance emp={self.employee_id} date={self.date}>"

    def get_elapsed_working_minutes(self, now: datetime | None = None) -> float:
        """
        Calculate gross elapsed working time up to check_out or current time.
        """
        if not self.check_in:
            return 0.0
        end_ref = self.check_out or (now or utcnow())
        if end_ref < self.check_in:
            return 0.0
        delta = end_ref - self.check_in
        return max(0.0, delta.total_seconds() / 60)

    def get_total_break_minutes(self, now: datetime | None = None) -> float:
        """
        Calculate total break time including completed breaks and any currently active break.
        """
        total = 0.0
        ref_time = now or utcnow()
        for b in self.breaks:
            if b.end_time and b.duration_minutes is not None:
                total += b.duration_minutes
            elif b.start_time and not b.end_time:
                # Active break
                if ref_time > b.start_time:
                    total += (ref_time - b.start_time).total_seconds() / 60
        return max(0.0, total)

    def get_net_working_minutes(self, now: datetime | None = None) -> float:
        """
        Calculate net working minutes (gross elapsed working time minus total break time).
        """
        ref_time = now or utcnow()
        gross = self.get_elapsed_working_minutes(ref_time)
        breaks = self.get_total_break_minutes(ref_time)
        return max(0.0, gross - breaks)

    def recalculate(self):
        """Recalculate durations from timestamps and completed breaks."""
        if self.check_in and self.check_out:
            delta = self.check_out - self.check_in
            self.total_duration_minutes = max(0.0, delta.total_seconds() / 60)
        else:
            self.total_duration_minutes = 0.0

        # Only query breaks relationship when instance is bound to a session
        from sqlalchemy import inspect as sa_inspect
        try:
            state = sa_inspect(self)
            if state.session is not None:
                completed_breaks = self.breaks.filter(
                    Break.end_time.isnot(None)
                ).all()
                self.break_duration_minutes = sum(
                    b.duration_minutes for b in completed_breaks if b.duration_minutes
                )
            # else: leave break_duration_minutes at its current value (0.0 default)
        except Exception:
            pass  # Detached or uninspectable — skip break recalculation

        self.net_working_minutes = max(
            0.0, self.total_duration_minutes - self.break_duration_minutes
        )

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "date": self.date.isoformat() if self.date else None,
            "check_in": self.check_in.isoformat() if self.check_in else None,
            "check_out": self.check_out.isoformat() if self.check_out else None,
            "total_duration_minutes": self.total_duration_minutes,
            "break_duration_minutes": self.break_duration_minutes,
            "net_working_minutes": self.net_working_minutes,
            "status": self.status.value if self.status else None,
        }


class Break(db.Model):
    __tablename__ = "breaks"

    id = Column(Integer, primary_key=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    category = Column(Enum(BreakCategory), nullable=False, default=BreakCategory.OTHER)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    duration_minutes = Column(Float, default=0.0)
    notes = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    attendance = relationship("Attendance", back_populates="breaks")
    employee = relationship("Employee")

    __table_args__ = (
        Index("ix_breaks_attendance", "attendance_id"),
        Index("ix_breaks_employee", "employee_id"),
    )

    def __repr__(self):
        return f"<Break {self.category} emp={self.employee_id}>"

    def get_elapsed_minutes(self, now: datetime | None = None) -> float:
        """Calculate elapsed minutes of this break."""
        if not self.start_time:
            return 0.0
        end_ref = self.end_time or (now or utcnow())
        if end_ref < self.start_time:
            return 0.0
        delta = end_ref - self.start_time
        return max(0.0, delta.total_seconds() / 60)

    def close(self, end_time: datetime):
        """End the break and calculate duration."""
        self.end_time = end_time
        delta = end_time - self.start_time
        self.duration_minutes = max(0.0, delta.total_seconds() / 60)

    def to_dict(self):
        return {
            "id": self.id,
            "attendance_id": self.attendance_id,
            "employee_id": self.employee_id,
            "category": self.category.value if self.category else None,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_minutes": self.duration_minutes,
        }


class LeaveRequest(db.Model):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    leave_type = Column(Enum(LeaveType), nullable=False)
    day_type = Column(Enum(LeaveDayType), nullable=False, default=LeaveDayType.FULL_DAY)
    start_date = Column(db.Date, nullable=False)
    end_date = Column(db.Date, nullable=False)
    partial_start_time = Column(Time, nullable=True)
    partial_end_time = Column(Time, nullable=True)
    reason = Column(Text, nullable=False)
    status = Column(Enum(LeaveStatus), default=LeaveStatus.PENDING, nullable=False)
    reviewed_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    admin_notes = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    employee = relationship("Employee", back_populates="leave_requests")
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])

    __table_args__ = (
        Index("ix_leave_employee", "employee_id"),
        Index("ix_leave_status", "status"),
        Index("ix_leave_dates", "start_date", "end_date"),
    )

    def __repr__(self):
        return f"<LeaveRequest emp={self.employee_id} {self.leave_type} {self.status}>"

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "leave_type": self.leave_type.value if self.leave_type else None,
            "day_type": self.day_type.value if self.day_type else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "reason": self.reason,
            "status": self.status.value if self.status else None,
            "admin_notes": self.admin_notes,
        }


class PredictionHistory(db.Model):
    __tablename__ = "prediction_history"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    prediction_date = Column(DateTime, default=utcnow, nullable=False)
    break_category = Column(Enum(BreakCategory), nullable=True)
    predicted_break_minutes = Column(Float)
    predicted_available_minutes = Column(Float)
    model_used = Column(String(50))
    mae = Column(Float)
    rmse = Column(Float)
    features_used = Column(Text)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    employee = relationship("Employee")

    def __repr__(self):
        return f"<PredictionHistory emp={self.employee_id} {self.prediction_date}>"

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "prediction_date": self.prediction_date.isoformat() if self.prediction_date else None,
            "break_category": self.break_category.value if self.break_category else None,
            "predicted_break_minutes": self.predicted_break_minutes,
            "predicted_available_minutes": self.predicted_available_minutes,
            "model_used": self.model_used,
            "mae": self.mae,
            "rmse": self.rmse,
        }


class Holiday(db.Model):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True)
    holiday_name = Column(String(150), nullable=False)
    holiday_date = Column(db.Date, nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    creator = relationship("User")

    def __repr__(self):
        return f"<Holiday {self.holiday_name} on {self.holiday_date}>"

    def to_dict(self):
        return {
            "id": self.id,
            "holiday_name": self.holiday_name,
            "holiday_date": self.holiday_date.isoformat() if self.holiday_date else None,
            "description": self.description,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ── Calendar Year Management ───────────────────────────────────────────────────

class CalendarYear(db.Model):
    """
    Fiscal or statutory calendar year defining official organizational dates.
    Enables automatic mapping with employee joining dates.
    """
    __tablename__ = "calendar_years"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True, index=True) # e.g. 'Calendar Year 2026'
    start_date = Column(db.Date, nullable=False)
    end_date = Column(db.Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self):
        return f"<CalendarYear {self.name} ({self.start_date} to {self.end_date})>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def get_calendar_year_for_date(cls, target_date):
        """
        Find the matching calendar year for a given date.
        Accepts datetime or date.
        """
        if not target_date:
            return None
        if hasattr(target_date, "date"):
            d = target_date.date()
        else:
            d = target_date
        return cls.query.filter(cls.start_date <= d, cls.end_date >= d).first()


# ── Payroll Models ─────────────────────────────────────────────────────────────

class PayrollItemType(str, PyEnum):
    EARNING = "earning"
    DEDUCTION = "deduction"


class PayrollItem(db.Model):
    """
    Configurable components for earnings and deductions
    (e.g., Basic Pay, HRA, Special Allowance, PF, ESI, TDS, Professional Tax, LWF).
    """
    __tablename__ = "payroll_items"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    item_type = Column(Enum(PayrollItemType), nullable=False)
    description = Column(String(255), nullable=True)
    is_statutory = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    def __repr__(self):
        return f"<PayrollItem {self.code} ({self.item_type.value})>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "item_type": self.item_type.value,
            "description": self.description,
            "is_statutory": self.is_statutory,
            "is_active": self.is_active,
        }


class EmployeeSalary(db.Model):
    """
    Salary structure for an employee:
    Basic, HRA, Special Allowance, Other Allowances, Bonus,
    Employer Contributions, PF, ESI, TDS, Professional Tax, LWF, Other Deductions.
    """
    __tablename__ = "employee_salaries"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, unique=True, index=True)

    # Earnings
    basic_salary = Column(Float, default=0.0, nullable=False)
    hra = Column(Float, default=0.0, nullable=False)
    special_allowance = Column(Float, default=0.0, nullable=False)
    other_allowances = Column(Float, default=0.0, nullable=False)
    bonus = Column(Float, default=0.0, nullable=False)
    employer_contributions = Column(Float, default=0.0, nullable=False)
    other_payments = Column(Float, default=0.0, nullable=False)

    # Deductions
    pf_deduction = Column(Float, default=0.0, nullable=False)
    esi_deduction = Column(Float, default=0.0, nullable=False)
    tds_deduction = Column(Float, default=0.0, nullable=False)
    prof_tax = Column(Float, default=0.0, nullable=False)
    lwf_deduction = Column(Float, default=0.0, nullable=False)
    other_deductions = Column(Float, default=0.0, nullable=False)

    # Computed figures cached for fast reporting
    gross_salary = Column(Float, default=0.0, nullable=False)
    total_deductions = Column(Float, default=0.0, nullable=False)
    net_salary = Column(Float, default=0.0, nullable=False)
    ctc = Column(Float, default=0.0, nullable=False)

    effective_date = Column(db.Date, nullable=True)
    payment_mode = Column(String(50), default="Bank Transfer", nullable=False)
    bank_name = Column(String(100), nullable=True)
    account_number = Column(String(50), nullable=True)
    ifsc_code = Column(String(20), nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    employee = relationship("Employee", backref=db.backref("salary_structure", uselist=False))

    def compute_totals(self):
        """Recalculate gross, total deductions, net salary and annual CTC."""
        self.gross_salary = round(
            (self.basic_salary or 0.0) +
            (self.hra or 0.0) +
            (self.special_allowance or 0.0) +
            (self.other_allowances or 0.0) +
            (self.bonus or 0.0) +
            (self.other_payments or 0.0), 2
        )
        self.total_deductions = round(
            (self.pf_deduction or 0.0) +
            (self.esi_deduction or 0.0) +
            (self.tds_deduction or 0.0) +
            (self.prof_tax or 0.0) +
            (self.lwf_deduction or 0.0) +
            (self.other_deductions or 0.0), 2
        )
        self.net_salary = max(0.0, round(self.gross_salary - self.total_deductions, 2))
        monthly_ctc = self.gross_salary + (self.employer_contributions or 0.0)
        self.ctc = round(monthly_ctc * 12.0, 2)
        return self.net_salary

    def __repr__(self):
        return f"<EmployeeSalary emp={self.employee_id} Net={self.net_salary}>"


class PayrollRun(db.Model):
    """
    A payroll run cycle for a given month (e.g. 'May 2025' or '2025-05').
    Stores aggregate metrics and status.
    """
    __tablename__ = "payroll_runs"

    id = Column(Integer, primary_key=True)
    payroll_month = Column(String(20), nullable=False, unique=True, index=True)  # e.g., "May 2025"
    month_code = Column(String(10), nullable=False, unique=True, index=True)     # e.g., "2025-05"
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)

    total_employees = Column(Integer, default=0, nullable=False)
    total_salary_cost = Column(Float, default=0.0, nullable=False)  # CTC / Total cost
    gross_payout = Column(Float, default=0.0, nullable=False)
    total_deductions = Column(Float, default=0.0, nullable=False)
    net_payout = Column(Float, default=0.0, nullable=False)
    average_ctc = Column(Float, default=0.0, nullable=False)

    # Component aggregates
    total_basic = Column(Float, default=0.0, nullable=False)
    total_hra = Column(Float, default=0.0, nullable=False)
    total_special = Column(Float, default=0.0, nullable=False)
    total_other_allowances = Column(Float, default=0.0, nullable=False)
    total_employer_contributions = Column(Float, default=0.0, nullable=False)
    total_other_payments = Column(Float, default=0.0, nullable=False)

    # Deductions breakdown
    total_pf = Column(Float, default=0.0, nullable=False)
    total_tds = Column(Float, default=0.0, nullable=False)
    total_esi = Column(Float, default=0.0, nullable=False)
    total_prof_tax = Column(Float, default=0.0, nullable=False)
    total_lwf = Column(Float, default=0.0, nullable=False)
    total_other_deductions = Column(Float, default=0.0, nullable=False)

    status = Column(String(30), default="Completed", nullable=False)  # "Completed", "Processing", "Draft"
    completed_on = Column(db.Date, nullable=True)

    # Payslip progress counters
    payslips_generated = Column(Integer, default=0, nullable=False)
    payslips_in_progress = Column(Integer, default=0, nullable=False)
    payslips_yet_to_start = Column(Integer, default=0, nullable=False)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    creator = relationship("User")
    payslips = relationship("Payslip", back_populates="payroll_run", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PayrollRun {self.payroll_month} Net={self.net_payout}>"


class StatutoryCompliance(db.Model):
    """
    Statutory compliance tracking for PF, ESI, TDS, Professional Tax, LWF.
    Displays actual recorded status (Paid, Pending, Not Applicable).
    """
    __tablename__ = "statutory_compliances"

    id = Column(Integer, primary_key=True)
    component_name = Column(String(50), nullable=False)   # PF, ESI, TDS, Professional Tax, LWF
    period = Column(String(50), nullable=False)           # "May 2025" or "Apr - Jun 2025"
    amount = Column(Float, default=0.0, nullable=False)
    status = Column(String(30), default="Pending", nullable=False)  # "Paid", "Pending", "Not Applicable"
    due_date = Column(db.Date, nullable=True)
    paid_date = Column(db.Date, nullable=True)
    challan_number = Column(String(100), nullable=True)
    notes = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("component_name", "period", name="uq_statutory_component_period"),
    )

    def __repr__(self):
        return f"<StatutoryCompliance {self.component_name} {self.period} [{self.status}]>"


class Payslip(db.Model):
    """
    Payslip record for an employee for a specific payroll cycle.
    """
    __tablename__ = "payslips"

    id = Column(Integer, primary_key=True)
    payslip_number = Column(String(50), nullable=False, unique=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    payroll_run_id = Column(Integer, ForeignKey("payroll_runs.id"), nullable=True, index=True)

    payroll_month = Column(String(20), nullable=False)  # e.g., "May 2025"
    month_code = Column(String(10), nullable=False)     # e.g., "2025-05"

    # Attendance/work days summary
    working_days = Column(Integer, default=30, nullable=False)
    days_present = Column(Float, default=30.0, nullable=False)
    days_absent = Column(Float, default=0.0, nullable=False)

    # Earnings breakdown
    basic_salary = Column(Float, default=0.0, nullable=False)
    hra = Column(Float, default=0.0, nullable=False)
    special_allowance = Column(Float, default=0.0, nullable=False)
    other_allowances = Column(Float, default=0.0, nullable=False)
    bonus = Column(Float, default=0.0, nullable=False)
    gross_earnings = Column(Float, default=0.0, nullable=False)

    # Deductions breakdown
    pf_deduction = Column(Float, default=0.0, nullable=False)
    esi_deduction = Column(Float, default=0.0, nullable=False)
    tds_deduction = Column(Float, default=0.0, nullable=False)
    prof_tax = Column(Float, default=0.0, nullable=False)
    lwf_deduction = Column(Float, default=0.0, nullable=False)
    other_deductions = Column(Float, default=0.0, nullable=False)
    total_deductions = Column(Float, default=0.0, nullable=False)

    net_salary = Column(Float, default=0.0, nullable=False)

    status = Column(String(30), default="Generated", nullable=False)  # "Generated", "In Progress", "Draft"
    generated_at = Column(DateTime, default=utcnow, nullable=False)

    employee = relationship("Employee", backref=db.backref("payslips", lazy="dynamic"))
    payroll_run = relationship("PayrollRun", back_populates="payslips")

    __table_args__ = (
        UniqueConstraint("employee_id", "month_code", name="uq_emp_month_payslip"),
    )

    def __repr__(self):
        return f"<Payslip {self.payslip_number} emp={self.employee_id} {self.payroll_month}>"


class ExpenseStatus(str, PyEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REIMBURSED = "reimbursed"


class ExpenseCategory(str, PyEnum):
    TRAVEL = "travel"
    MEALS = "meals"
    EQUIPMENT = "equipment"
    OFFICE_SUPPLIES = "office_supplies"
    INTERNET_PHONE = "internet_phone"
    TRAINING = "training"
    CLIENT_ENTERTAINMENT = "client_entertainment"
    OTHER = "other"


class Expense(db.Model):
    """
    Employee Expense and Reimbursement records.
    Tracks expenses, category, amounts, receipts, approval status, and dates.
    """
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    expense_number = Column(String(50), nullable=False, unique=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    category = Column(Enum(ExpenseCategory), default=ExpenseCategory.TRAVEL, nullable=False)
    amount = Column(Float, default=0.0, nullable=False)
    expense_date = Column(db.Date, nullable=False)
    merchant = Column(String(150), nullable=True)
    description = Column(String(500), nullable=True)
    status = Column(Enum(ExpenseStatus), default=ExpenseStatus.PENDING, nullable=False)

    approved_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    reimbursed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    employee = relationship("Employee", backref=db.backref("expenses", lazy="dynamic"))
    approver = relationship("User", foreign_keys=[approved_by_id])

    def __repr__(self):
        return f"<Expense {self.expense_number} emp={self.employee_id} amount={self.amount}>"


# ── RBAC & Super Admin Enterprise Models ────────────────────────────────────

# Association table for User <-> Role (Many-to-Many)
user_roles = db.Table(
    "user_roles",
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

# Association table for Role <-> Permission (Many-to-Many)
role_permissions = db.Table(
    "role_permissions",
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(db.Model):
    """
    Granular permission items (e.g. view_employees, manage_payroll, review_leaves, view_reports)
    """
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    module = Column(String(50), nullable=False, default="general")
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    roles = relationship("Role", secondary=role_permissions, back_populates="permissions")

    def __repr__(self):
        return f"<Permission {self.slug}>"


class Role(db.Model):
    """
    Dynamic enterprise roles (e.g. Super Admin, HR Manager, Team Lead, Accountant, Employee)
    """
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)  # System roles cannot be deleted
    created_at = Column(DateTime, default=utcnow, nullable=False)

    users = relationship("User", secondary=user_roles, back_populates="roles")
    permissions = relationship("Permission", secondary=role_permissions, back_populates="roles")

    def __repr__(self):
        return f"<Role {self.name}>"


class Package(db.Model):
    """
    SaaS Subscription Packages (e.g. Starter, Professional, Enterprise)
    """
    __tablename__ = "packages"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    description = Column(String(255), nullable=True)
    billing_cycle = Column(String(20), default="monthly", nullable=False)  # monthly, yearly, both
    price_per_month = Column(Float, nullable=False, default=0.0)
    price_per_year = Column(Float, nullable=False, default=0.0)
    max_employees = Column(Integer, nullable=False, default=25)
    max_users = Column(Integer, nullable=False, default=5)
    max_storage_mb = Column(Integer, nullable=False, default=500)
    trial_period_days = Column(Integer, default=14, nullable=False)
    features_json = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    subscriptions = relationship("Subscription", back_populates="package", lazy="dynamic")

    def __repr__(self):
        return f"<Package {self.name} (${self.price_per_month}/mo)>"


# Alias for requirement compatibility
SubscriptionPlan = Package


class Company(db.Model):
    """
    Multi-tenant enterprise company entity.
    """
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    logo = Column(String(255), nullable=True)
    registration_number = Column(String(100), nullable=True)
    gstin = Column(String(50), nullable=True)
    pan = Column(String(50), nullable=True)
    industry = Column(String(100), nullable=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=True)
    address = Column(String(255), nullable=True)
    country = Column(String(100), default="India", nullable=True)
    state = Column(String(100), nullable=True)
    city = Column(String(100), nullable=True)
    pincode = Column(String(20), nullable=True)
    website = Column(String(200), nullable=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=True)
    employee_limit = Column(Integer, nullable=True)
    user_limit = Column(Integer, nullable=True)
    status = Column(String(30), default="active", nullable=False)  # active, suspended, pending, archived
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    package = relationship("Package", foreign_keys=[package_id])
    users = relationship("User", back_populates="company", foreign_keys="User.company_id", lazy="dynamic")
    subscriptions = relationship("Subscription", back_populates="company", lazy="dynamic")
    locations = relationship("CompanyLocation", back_populates="company", cascade="all, delete-orphan", lazy="dynamic")

    def __repr__(self):
        return f"<Company {self.name} ({self.code})>"


class CompanyLocation(db.Model):
    """
    Multiple office branches, facilities and geographic locations per company tenant.
    """
    __tablename__ = "company_locations"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    location_name = Column(String(100), nullable=False)
    address = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    country = Column(String(100), default="India", nullable=True)
    pincode = Column(String(20), nullable=True)
    phone = Column(String(30), nullable=True)
    email = Column(String(150), nullable=True)
    is_headquarters = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    company = relationship("Company", back_populates="locations")

    def __repr__(self):
        return f"<CompanyLocation {self.location_name} (Company #{self.company_id})>"


# Alias for backward/spec compatibility
CompanyAddress = CompanyLocation


class Subscription(db.Model):
    """
    Company SaaS Subscriptions tracking billing cycle, status, and renewals.
    """
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    package_id = Column(Integer, ForeignKey("packages.id"), nullable=False)
    billing_cycle = Column(String(20), default="monthly", nullable=False)  # monthly, yearly
    amount = Column(Float, default=0.0, nullable=False)
    status = Column(String(30), default="active", nullable=False)  # active, expired, cancelled, trial
    starts_at = Column(DateTime, default=utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    company = relationship("Company", back_populates="subscriptions")
    package = relationship("Package", back_populates="subscriptions")

    def __repr__(self):
        return f"<Subscription company={self.company_id} pkg={self.package_id} status={self.status}>"


class Designation(db.Model):
    """
    Job designations mapped within the organization, optionally associated with a department.
    """
    __tablename__ = "designations"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    department = relationship("Department")

    def __repr__(self):
        return f"<Designation {self.name}>"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "department_id": self.department_id,
            "department_name": self.department.name if self.department else None,
            "description": self.description,
        }


class LeaveTypePolicy(db.Model):
    """
    Leave types and annual allocations with carry forward rules.
    """
    __tablename__ = "leave_type_policies"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(30), nullable=False, unique=True)
    annual_allocation_days = Column(Integer, default=12, nullable=False)
    carry_forward_max_days = Column(Integer, default=0, nullable=False)
    is_paid = Column(Boolean, default=True, nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    def __repr__(self):
        return f"<LeaveTypePolicy {self.name} ({self.code})>"


class JobOpening(db.Model):
    """
    Recruitment Job Postings and Openings.
    """
    __tablename__ = "job_openings"

    id = Column(Integer, primary_key=True)
    title = Column(String(150), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    positions = Column(Integer, default=1, nullable=False)
    status = Column(String(30), default="open", nullable=False)  # open, closed, on_hold
    job_type = Column(String(50), default="Full-Time")  # Full-Time, Part-Time, Contract
    experience_level = Column(String(50), default="Mid-Level")
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    department = relationship("Department")
    candidates = relationship("JobCandidate", back_populates="job_opening", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<JobOpening {self.title} ({self.status})>"


class JobCandidate(db.Model):
    """
    Recruitment Candidates / Applicants pipeline and interview tracking.
    """
    __tablename__ = "job_candidates"

    id = Column(Integer, primary_key=True)
    job_opening_id = Column(Integer, ForeignKey("job_openings.id"), nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(30), nullable=True)
    status = Column(String(40), default="applied", nullable=False)  # applied, screening, interviewing, offered, hired, rejected
    interview_date = Column(DateTime, nullable=True)
    interview_notes = Column(Text, nullable=True)
    rating = Column(Integer, default=0)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    job_opening = relationship("JobOpening", back_populates="candidates")

    def __repr__(self):
        return f"<JobCandidate {self.full_name} ({self.status})>"


class EmployeeDocument(db.Model):
    __tablename__ = "employee_documents"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    document_name = Column(String(200), nullable=False)
    document_type = Column(String(80), nullable=False, default="Other")  # Offer Letter, Experience Letter, ID Proof, Address Proof, Certification, Other
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)  # bytes
    mime_type = Column(String(100), default="application/octet-stream")
    status = Column(String(40), default="Approved", nullable=False)  # Pending, Approved, Rejected
    notes = Column(Text, nullable=True)
    uploaded_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    employee = relationship("Employee", back_populates="documents")
    uploader = relationship("User", foreign_keys=[uploaded_by_id])

    def __repr__(self):
        return f"<EmployeeDocument {self.document_name} ({self.document_type})>"

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "document_name": self.document_name,
            "document_type": self.document_type,
            "file_size": self.file_size,
            "mime_type": self.mime_type,
            "status": self.status,
            "uploaded_at": self.created_at.strftime("%Y-%m-%d %H:%M") if self.created_at else None,
        }


class CompanyPolicy(db.Model):
    __tablename__ = "company_policies"

    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False, default="General")  # General, Leave & Attendance, IT & Security, Code of Conduct, POSH, HR Guidelines
    description = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)
    version = Column(String(30), default="1.0", nullable=False)
    effective_date = Column(db.Date, nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    creator = relationship("User", foreign_keys=[created_by_id])

    def __repr__(self):
        return f"<CompanyPolicy {self.title} (v{self.version})>"

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "has_file": bool(self.file_path),
            "version": self.version,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "created_at": self.created_at.strftime("%Y-%m-%d") if self.created_at else None,
        }


class EmployeeProfile(db.Model):
    """
    Comprehensive Employee Profile Extension
    Stores personal, government/identity, family/emergency contacts,
    education/experience, and extended employment attributes.
    Sensitive identity fields are encrypted at rest with Fernet AES-256.
    """
    __tablename__ = "employee_profiles"

    id = Column(Integer, primary_key=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, unique=True, index=True)

    # 1. Personal Information
    date_of_birth = Column(db.Date, nullable=True)
    gender = Column(String(20), nullable=True)  # Male, Female, Other
    marital_status = Column(String(30), nullable=True)  # Single, Married, Divorced, Widowed
    personal_email = Column(String(255), nullable=True)
    personal_phone = Column(String(30), nullable=True)
    blood_group = Column(String(10), nullable=True)  # O+, A+, B+, AB-, etc.
    nationality = Column(String(80), default="Indian", nullable=True)
    current_address = Column(Text, nullable=True)
    permanent_address = Column(Text, nullable=True)

    # 2. Identity & Government Details (Encrypted at rest)
    aadhaar_number_encrypted = Column(String(255), nullable=True)
    pan_number_encrypted = Column(String(255), nullable=True)
    passport_number = Column(String(100), nullable=True)
    passport_expiry = Column(db.Date, nullable=True)
    driving_licence = Column(String(100), nullable=True)
    uan_number = Column(String(50), nullable=True)
    pf_account_number = Column(String(50), nullable=True)
    esic_number = Column(String(50), nullable=True)

    # 3. Family & Emergency Contacts
    father_name = Column(String(150), nullable=True)
    mother_name = Column(String(150), nullable=True)
    spouse_name = Column(String(150), nullable=True)
    dependents_info = Column(Text, nullable=True)
    emergency_contact_name = Column(String(150), nullable=True)
    emergency_contact_relation = Column(String(80), nullable=True)
    emergency_contact_phone = Column(String(30), nullable=True)
    emergency_contact_address = Column(Text, nullable=True)

    # 4. Education & Experience
    highest_qualification = Column(String(150), nullable=True)
    institution_university = Column(String(200), nullable=True)
    graduation_year = Column(Integer, nullable=True)
    previous_company = Column(String(200), nullable=True)
    previous_designation = Column(String(150), nullable=True)
    total_experience_years = Column(Float, default=0.0, nullable=True)

    # 5. Extended Employment Attributes
    employment_type = Column(String(50), default="Full-Time", nullable=True)  # Full-Time, Part-Time, Contract, Intern
    work_location = Column(String(100), default="Bengaluru", nullable=True)
    probation_end_date = Column(db.Date, nullable=True)
    confirmation_date = Column(db.Date, nullable=True)

    # 6. Banking Detail Overrides (Encrypted at rest)
    account_holder_name = Column(String(150), nullable=True)
    bank_branch = Column(String(150), nullable=True)
    bank_account_encrypted = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    employee = relationship("Employee", back_populates="profile")

    def __repr__(self):
        return f"<EmployeeProfile emp_id={self.employee_id}>"

    # Properties for encrypted fields
    @property
    def aadhaar_number(self):
        from app.utils.crypto import decrypt_field
        return decrypt_field(self.aadhaar_number_encrypted) if self.aadhaar_number_encrypted else ""

    @aadhaar_number.setter
    def aadhaar_number(self, val):
        from app.utils.crypto import encrypt_field
        self.aadhaar_number_encrypted = encrypt_field(val) if val else None

    @property
    def pan_number(self):
        from app.utils.crypto import decrypt_field
        return decrypt_field(self.pan_number_encrypted) if self.pan_number_encrypted else ""

    @pan_number.setter
    def pan_number(self, val):
        from app.utils.crypto import encrypt_field
        self.pan_number_encrypted = encrypt_field(val) if val else None

    @property
    def bank_account_number(self):
        from app.utils.crypto import decrypt_field
        return decrypt_field(self.bank_account_encrypted) if self.bank_account_encrypted else ""

    @bank_account_number.setter
    def bank_account_number(self, val):
        from app.utils.crypto import encrypt_field
        self.bank_account_encrypted = encrypt_field(val) if val else None

    # Masked representations for safe display
    @property
    def aadhaar_masked(self):
        from app.utils.crypto import mask_aadhaar
        return mask_aadhaar(self.aadhaar_number)

    @property
    def pan_masked(self):
        from app.utils.crypto import mask_pan
        return mask_pan(self.pan_number)

    @property
    def bank_account_masked(self):
        from app.utils.crypto import mask_bank_account
        return mask_bank_account(self.bank_account_number)

    def to_dict(self, mask_sensitive=True):
        """Export dictionary representation; masks sensitive government identifiers by default."""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "date_of_birth": self.date_of_birth.isoformat() if self.date_of_birth else None,
            "gender": self.gender,
            "marital_status": self.marital_status,
            "personal_email": self.personal_email,
            "personal_phone": self.personal_phone,
            "blood_group": self.blood_group,
            "nationality": self.nationality,
            "current_address": self.current_address,
            "permanent_address": self.permanent_address,
            "aadhaar_number": self.aadhaar_masked if mask_sensitive else self.aadhaar_number,
            "pan_number": self.pan_masked if mask_sensitive else self.pan_number,
            "passport_number": self.passport_number,
            "uan_number": self.uan_number,
            "pf_account_number": self.pf_account_number,
            "esic_number": self.esic_number,
            "highest_qualification": self.highest_qualification,
            "institution_university": self.institution_university,
            "graduation_year": self.graduation_year,
            "previous_company": self.previous_company,
            "previous_designation": self.previous_designation,
            "total_experience_years": self.total_experience_years,
            "employment_type": self.employment_type,
            "work_location": self.work_location,
            "emergency_contact_name": self.emergency_contact_name,
            "emergency_contact_phone": self.emergency_contact_phone,
            "emergency_contact_relation": self.emergency_contact_relation,
        }








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

    employee = relationship("Employee", back_populates="user", uselist=False)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

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
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    department = relationship("Department", back_populates="employees")
    work_schedule = relationship("WorkSchedule", back_populates="employees")
    user = relationship("User", back_populates="employee")
    attendance_records = relationship("Attendance", back_populates="employee", lazy="dynamic", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="employee", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Employee {self.employee_id} {self.full_name}>"

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



"""
EBT System — Seed historical attendance and break data (last 30 days).
Run: python scripts/seed_history.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

import random
from datetime import date, datetime, timedelta, time

from app import create_app
from app.extensions import db
from app.models import (
    Employee, Attendance, Break, LeaveRequest,
    AttendanceStatus, BreakCategory, LeaveType, LeaveDayType, LeaveStatus,
)

random.seed(42)

BREAK_TEMPLATES = {
    BreakCategory.LUNCH:    (30, 15),   # (mean_min, std_min)
    BreakCategory.TEA:      (10,  5),
    BreakCategory.COFFEE:   ( 8,  4),
    BreakCategory.PERSONAL: (12,  6),
    BreakCategory.OTHER:    (15,  7),
}

DAILY_BREAK_PLANS = [
    [BreakCategory.LUNCH, BreakCategory.TEA],
    [BreakCategory.LUNCH, BreakCategory.COFFEE, BreakCategory.PERSONAL],
    [BreakCategory.LUNCH, BreakCategory.TEA, BreakCategory.TEA],
    [BreakCategory.LUNCH],
    [BreakCategory.LUNCH, BreakCategory.COFFEE],
]


def _rand_dur(cat):
    mean, std = BREAK_TEMPLATES[cat]
    return max(1, round(random.gauss(mean, std), 1))


def seed():
    app = create_app()
    with app.app_context():
        employees = Employee.query.all()
        if not employees:
            print("No employees found — run setup_demo.py first.")
            return

        today = date.today()
        att_added = 0
        brk_added = 0

        for emp in employees:
            checkin_hour   = random.randint(8, 10)
            checkout_hour  = random.randint(17, 19)

            for days_ago in range(1, 31):       # last 30 working days
                d = today - timedelta(days=days_ago)
                if d.weekday() >= 5:            # skip weekends
                    continue

                # Skip ~15% of days (absent / leave)
                if random.random() < 0.12:
                    continue

                # Skip if already exists
                if Attendance.query.filter_by(employee_id=emp.id, date=d).first():
                    continue

                ci_min = random.randint(0, 20)
                co_min = random.randint(0, 20)
                check_in  = datetime(d.year, d.month, d.day,
                                     checkin_hour, ci_min)
                check_out = datetime(d.year, d.month, d.day,
                                     checkout_hour, co_min)

                att = Attendance(
                    employee_id=emp.id,
                    date=d,
                    check_in=check_in,
                    check_out=check_out,
                    status=AttendanceStatus.PRESENT,
                )
                db.session.add(att)
                db.session.flush()   # get att.id

                # Add breaks for this day
                plan = random.choice(DAILY_BREAK_PLANS)
                cursor = check_in + timedelta(hours=1)
                for cat in plan:
                    dur = _rand_dur(cat)
                    # Advance cursor a little between breaks
                    gap = random.randint(30, 90)
                    brk_start = cursor + timedelta(minutes=gap)
                    brk_end   = brk_start + timedelta(minutes=dur)

                    if brk_end >= check_out:
                        break

                    brk = Break(
                        attendance_id=att.id,
                        employee_id=emp.id,
                        category=cat,
                        start_time=brk_start,
                        end_time=brk_end,
                        duration_minutes=dur,
                    )
                    db.session.add(brk)
                    brk_added += 1
                    cursor = brk_end

                att.recalculate()
                att_added += 1

        db.session.commit()

        # Add a few sample leave requests
        leave_added = 0
        emp = employees[0] if employees else None
        if emp:
            future_start = today + timedelta(days=5)
            future_end   = today + timedelta(days=7)
            if not LeaveRequest.query.filter_by(employee_id=emp.id,
                                                start_date=future_start).first():
                lr = LeaveRequest(
                    employee_id=emp.id,
                    leave_type=LeaveType.ANNUAL,
                    day_type=LeaveDayType.FULL_DAY,
                    start_date=future_start,
                    end_date=future_end,
                    reason="Annual vacation",
                    status=LeaveStatus.PENDING,
                )
                db.session.add(lr)
                leave_added += 1

        db.session.commit()
        print(f"Seeded {att_added} attendance records, "
              f"{brk_added} breaks, {leave_added} leave requests.")


if __name__ == "__main__":
    seed()

"""
Payroll Seeder for default payroll components and sample realistic salary structures.
Idempotent and safe: never overwrites existing employee salary or payroll data.
"""

from datetime import date
from app.extensions import db
from app.models import PayrollItem, PayrollItemType, StatutoryCompliance


DEFAULT_PAYROLL_ITEMS = [
    # Earnings
    {"name": "Basic Pay", "code": "BASIC", "item_type": PayrollItemType.EARNING, "is_statutory": True, "description": "Core fixed salary component (typically 40-50% of CTC)"},
    {"name": "House Rent Allowance (HRA)", "code": "HRA", "item_type": PayrollItemType.EARNING, "is_statutory": True, "description": "Allowance for housing costs"},
    {"name": "Special Allowance", "code": "SPECIAL", "item_type": PayrollItemType.EARNING, "is_statutory": False, "description": "Supplementary performance or role allowance"},
    {"name": "Other Allowances", "code": "OTHER_ALLOW", "item_type": PayrollItemType.EARNING, "is_statutory": False, "description": "Transport, medical, books, and telecommunication reimbursements"},
    {"name": "Performance Bonus", "code": "BONUS", "item_type": PayrollItemType.EARNING, "is_statutory": False, "description": "Periodic incentive or bonus"},
    {"name": "Employer PF Contribution", "code": "EMPLOYER_PF", "item_type": PayrollItemType.EARNING, "is_statutory": True, "description": "Employer statutory provident fund contribution"},
    {"name": "Other Payments", "code": "OTHER_PAY", "item_type": PayrollItemType.EARNING, "is_statutory": False, "description": "Ad-hoc, arrears, or one-off awards"},

    # Deductions
    {"name": "Provident Fund (Employee PF)", "code": "PF", "item_type": PayrollItemType.DEDUCTION, "is_statutory": True, "description": "Statutory employee PF contribution (12% of basic)"},
    {"name": "Employee State Insurance (ESI)", "code": "ESI", "item_type": PayrollItemType.DEDUCTION, "is_statutory": True, "description": "ESI medical insurance deduction where applicable"},
    {"name": "Tax Deducted at Source (TDS)", "code": "TDS", "item_type": PayrollItemType.DEDUCTION, "is_statutory": True, "description": "Income tax deducted at source"},
    {"name": "Professional Tax (PT)", "code": "PROF_TAX", "item_type": PayrollItemType.DEDUCTION, "is_statutory": True, "description": "State statutory professional tax deduction"},
    {"name": "Labour Welfare Fund (LWF)", "code": "LWF", "item_type": PayrollItemType.DEDUCTION, "is_statutory": True, "description": "Statutory state labour welfare fund contribution"},
    {"name": "Other Deductions", "code": "OTHER_DED", "item_type": PayrollItemType.DEDUCTION, "is_statutory": False, "description": "Notice pay, company advances, or miscellaneous deductions"},
]


def seed_default_payroll_items(session=None):
    """Seed initial payroll components idempotently."""
    sess = session or db.session
    inserted = 0
    for item in DEFAULT_PAYROLL_ITEMS:
        existing = sess.query(PayrollItem).filter_by(code=item["code"]).first()
        if not existing:
            p_item = PayrollItem(
                name=item["name"],
                code=item["code"],
                item_type=item["item_type"],
                description=item["description"],
                is_statutory=item["is_statutory"],
                is_active=True,
            )
            sess.add(p_item)
            inserted += 1

    if inserted > 0:
        sess.commit()
    return inserted

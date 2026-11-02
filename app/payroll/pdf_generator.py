"""
PDF Payslip Generator using ReportLab.
Produces a crisp, professional enterprise payslip document matching standard HR payroll formats.
"""

import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_payslip_pdf(payslip, employee, company_name="EBT Enterprise System"):
    """
    Generate an in-memory PDF buffer for an employee's payslip.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CompanyTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0B192C"),
        alignment=0,
    )
    sub_style = ParagraphStyle(
        "SubTitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748B"),
        alignment=0,
    )
    slip_title_style = ParagraphStyle(
        "SlipTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#2563EB"),
        alignment=2,
    )
    header_lbl = ParagraphStyle(
        "HeaderLabel",
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.HexColor("#475569"),
        leading=10,
    )
    header_val = ParagraphStyle(
        "HeaderVal",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=colors.HexColor("#0F172A"),
        leading=11,
    )
    table_hdr = ParagraphStyle(
        "TableHdr",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.white,
        leading=12,
    )
    table_cell_lbl = ParagraphStyle(
        "TableCellLbl",
        fontName="Helvetica",
        fontSize=8.5,
        textColor=colors.HexColor("#1E293B"),
        leading=11,
    )
    table_cell_val = ParagraphStyle(
        "TableCellVal",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=colors.HexColor("#0F172A"),
        leading=11,
        alignment=2,
    )
    total_lbl = ParagraphStyle(
        "TotalLbl",
        fontName="Helvetica-Bold",
        fontSize=9,
        textColor=colors.HexColor("#0B192C"),
        leading=12,
    )
    total_val = ParagraphStyle(
        "TotalVal",
        fontName="Helvetica-Bold",
        fontSize=9.5,
        textColor=colors.HexColor("#0B192C"),
        leading=12,
        alignment=2,
    )
    net_style = ParagraphStyle(
        "NetStyle",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.HexColor("#2563EB"),
        leading=18,
        alignment=2,
    )

    story = []

    # 1. Top Header: Company Name & Payslip Title
    emp_company = (employee.company_name if employee and employee.company_name else company_name)
    top_table_data = [
        [
            Paragraph(f"<b>{emp_company}</b>", title_style),
            Paragraph(f"<b>PAYSLIP FOR {payslip.payroll_month.upper()}</b>", slip_title_style)
        ],
        [
            Paragraph("Workforce Management &amp; Payroll Division", sub_style),
            Paragraph(f"Reference No: <b>{payslip.payslip_number}</b>", sub_style)
        ]
    ]
    top_table = Table(top_table_data, colWidths=[320, 220])
    top_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(top_table)
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceBefore=2, spaceAfter=12))

    # 2. Employee & Payroll Metadata Table
    dept_name = employee.department.name if employee and employee.department else "General"
    desig_name = employee.designation if employee and employee.designation else "Employee"
    salary_record = employee.salary_structure if hasattr(employee, "salary_structure") else None

    info_data = [
        [
            Paragraph("Employee Name:", header_lbl),
            Paragraph(f"<b>{employee.full_name}</b>", header_val),
            Paragraph("Payroll Period:", header_lbl),
            Paragraph(payslip.payroll_month, header_val),
        ],
        [
            Paragraph("Employee ID:", header_lbl),
            Paragraph(f"<code>{employee.employee_id}</code>", header_val),
            Paragraph("Days in Month:", header_lbl),
            Paragraph(str(payslip.working_days), header_val),
        ],
        [
            Paragraph("Department:", header_lbl),
            Paragraph(dept_name, header_val),
            Paragraph("Days Worked:", header_lbl),
            Paragraph(f"{payslip.days_present:.1f}", header_val),
        ],
        [
            Paragraph("Designation:", header_lbl),
            Paragraph(desig_name, header_val),
            Paragraph("Days Absent/Loss:", header_lbl),
            Paragraph(f"{payslip.days_absent:.1f}", header_val),
        ],
        [
            Paragraph("Bank Name:", header_lbl),
            Paragraph(salary_record.bank_name if salary_record and salary_record.bank_name else "Direct Deposit", header_val),
            Paragraph("Payment Status:", header_lbl),
            Paragraph(f"<b>{payslip.status}</b>", header_val),
        ],
        [
            Paragraph("A/C Number:", header_lbl),
            Paragraph(f"XXXX-{salary_record.account_number[-4:]}" if salary_record and salary_record.account_number else "On File", header_val),
            Paragraph("Generated Date:", header_lbl),
            Paragraph(payslip.generated_at.strftime("%d %b %Y") if payslip.generated_at else "-", header_val),
        ],
    ]
    info_table = Table(info_data, colWidths=[90, 180, 100, 170])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 14))

    # 3. Two-Column Table: Earnings vs Deductions
    earnings_rows = [
        ("Basic Salary", payslip.basic_salary),
        ("House Rent Allowance (HRA)", payslip.hra),
        ("Special Allowance", payslip.special_allowance),
        ("Other Allowances", payslip.other_allowances),
        ("Bonus / Incentives", payslip.bonus),
    ]

    deductions_rows = [
        ("Provident Fund (PF)", payslip.pf_deduction),
        ("Employee State Insurance (ESI)", payslip.esi_deduction),
        ("Tax Deducted at Source (TDS)", payslip.tds_deduction),
        ("Professional Tax (PT)", payslip.prof_tax),
        ("Labour Welfare Fund (LWF)", payslip.lwf_deduction),
        ("Other Deductions", payslip.other_deductions),
    ]

    # Equalize row lengths
    max_len = max(len(earnings_rows), len(deductions_rows))
    breakdown_data = [
        [
            Paragraph("EARNINGS", table_hdr),
            Paragraph("AMOUNT (INR)", table_hdr),
            Paragraph("DEDUCTIONS", table_hdr),
            Paragraph("AMOUNT (INR)", table_hdr),
        ]
    ]

    for i in range(max_len):
        e_lbl, e_val = earnings_rows[i] if i < len(earnings_rows) else ("", 0.0)
        d_lbl, d_val = deductions_rows[i] if i < len(deductions_rows) else ("", 0.0)

        breakdown_data.append([
            Paragraph(e_lbl, table_cell_lbl) if e_lbl else "",
            Paragraph(f"INR {e_val:,.2f}", table_cell_val) if e_lbl else "",
            Paragraph(d_lbl, table_cell_lbl) if d_lbl else "",
            Paragraph(f"INR {d_val:,.2f}", table_cell_val) if d_lbl else "",
        ])

    # Totals row
    breakdown_data.append([
        Paragraph("<b>Total Gross Earnings</b>", total_lbl),
        Paragraph(f"<b>INR {payslip.gross_earnings:,.2f}</b>", total_val),
        Paragraph("<b>Total Deductions</b>", total_lbl),
        Paragraph(f"<b>INR {payslip.total_deductions:,.2f}</b>", total_val),
    ])

    breakdown_table = Table(breakdown_data, colWidths=[180, 90, 180, 90])
    breakdown_table.setStyle(TableStyle([
        # Headers
        ("BACKGROUND", (0, 0), (1, 0), colors.HexColor("#2563EB")),
        ("BACKGROUND", (2, 0), (3, 0), colors.HexColor("#0B192C")),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("ALIGN", (3, 0), (3, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        # Body
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        # Totals row
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F1F5F9")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(breakdown_table)
    story.append(Spacer(1, 14))

    # 4. Net Payout Highlight Box
    net_data = [
        [
            Paragraph("<b>NET SALARY PAYABLE:</b><br/><font size=7.5 color='#64748B'>(Total Gross Earnings minus Total Statutory &amp; Voluntary Deductions)</font>", ParagraphStyle(
                "NetLabel", fontName="Helvetica", fontSize=10, textColor=colors.HexColor("#0B192C"), leading=13
            )),
            Paragraph(f"INR {payslip.net_salary:,.2f}", net_style)
        ]
    ]
    net_table = Table(net_data, colWidths=[360, 180])
    net_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#EFF6FF")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#2563EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(net_table)
    story.append(Spacer(1, 24))

    # 5. Authorization & Verification Notes
    footer_data = [
        [
            Paragraph("<b>Employee Signature:</b> ___________________", header_lbl),
            Paragraph("<b>Authorized Signatory:</b> ___________________", ParagraphStyle("RightLbl", parent=header_lbl, alignment=2))
        ],
        [
            Paragraph("<font size=7 color='#94A3B8'>* This document is a computer-generated official enterprise pay advice.</font>", header_lbl),
            Paragraph(f"<font size=7 color='#94A3B8'>Generated on {payslip.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC') if payslip.generated_at else ''}</font>", ParagraphStyle("RightTime", parent=header_lbl, alignment=2))
        ]
    ]
    footer_table = Table(footer_data, colWidths=[270, 270])
    footer_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(footer_table)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

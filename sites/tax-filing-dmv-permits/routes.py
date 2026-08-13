"""Lakeport Government Services Portal -- tax filing, DMV, and permits.

Serves a government services portal similar to state DMV / tax filing sites.
Data is loaded from DATA_SOURCES_DIR / "tax-dmv" containing pre-built JSON
files for users, tax filings, vehicles, permits, and payments.

Supports 28 macros: navigate_by_dropdown, navigate_by_route, search_by_query,
search_by_semantic, filter_by_dropdown, filter_by_date_range, extract_by_query,
extract_by_semantic, extract_by_dropdown, extract_from_table, extract_by_route,
compute_from_table, compute_by_extremum, compute_by_slider, verify_by_toggle,
submit_by_query, submit_by_form, edit_by_query, apply_by_form, sign_by_signature,
select_by_dropdown, select_by_date_range, export_by_dropdown, upload_by_upload,
book_by_date_range, pay_by_form, authenticate_by_form, verify_identity_by_code
"""
import csv
import hashlib
import io
import json
import pathlib
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db
from app.events import emit
from helpers.auth import current_user, browsing_user

SITE = "tax-filing-dmv-permits"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "tax-filing-dmv-permits",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _load_filings():
    return db.query(SITE, "tax_filings")


def _save_filings(data):
    db.save_collection(SITE, "tax_filings", data)


def _load_vehicles():
    return db.query(SITE, "vehicles")


def _save_vehicles(data):
    db.save_collection(SITE, "vehicles", data)


def _load_permits():
    return db.query(SITE, "permits")


def _save_permits(data):
    db.save_collection(SITE, "permits", data)


def _load_payments():
    return db.query(SITE, "payments")


def _save_payments(data):
    db.save_collection(SITE, "payments", data)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


def _get_current_user():
    return current_user(_get_user)


def _get_browsing_user():
    """Return logged-in user, or fall back to user 1 for browse-only mode."""
    return browsing_user(_get_user, fallback=1)


def _search_text(record, query):
    """Check whether query words appear in common text fields of a record."""
    q = query.lower()
    searchable = " ".join(str(v) for v in record.values() if isinstance(v, (str, int, float))).lower()
    return q in searchable


def _semantic_score(record, query):
    """Simple keyword overlap scoring for semantic-style search."""
    words = set(query.lower().split())
    text = " ".join(str(v) for v in record.values() if isinstance(v, (str, int, float))).lower()
    matches = sum(1 for w in words if w in text)
    return matches / max(len(words), 1)


def _generate_verification_code(user_id):
    """Generate a deterministic 6-digit verification code for a user."""
    seed = f"lakeport-verify-{user_id}-2026"
    h = hashlib.sha256(seed.encode()).hexdigest()
    return str(int(h[:8], 16) % 900000 + 100000)


# ---------------------------------------------------------------------------
# Forms library — IRS / DMV / permit forms with PDF generation
# ---------------------------------------------------------------------------

GOV_FORMS = [
    # Tax forms
    {"id": "form-1040", "form_number": "Form 1040", "title": "U.S. Individual Income Tax Return",
     "description": "Standard federal income tax return for individuals. Use this form to report wages, salary, tips, interest, dividends, capital gains, and other income.",
     "category": "tax", "revised": "2025", "pages": 2, "has_instructions": True},
    {"id": "form-1040-sr", "form_number": "Form 1040-SR", "title": "U.S. Tax Return for Seniors",
     "description": "Simplified tax return for taxpayers age 65 and older. Same as Form 1040 but with larger print and a standard deduction chart.",
     "category": "tax", "revised": "2025", "pages": 2, "has_instructions": True},
    {"id": "form-w2", "form_number": "Form W-2", "title": "Wage and Tax Statement",
     "description": "Reports wages paid and taxes withheld for each employee. Employers must furnish by January 31.",
     "category": "tax", "revised": "2025", "pages": 1, "has_instructions": False},
    {"id": "form-w4", "form_number": "Form W-4", "title": "Employee's Withholding Certificate",
     "description": "Complete this form so your employer can withhold the correct federal income tax from your pay.",
     "category": "tax", "revised": "2025", "pages": 2, "has_instructions": True},
    {"id": "form-1099-misc", "form_number": "Form 1099-MISC", "title": "Miscellaneous Information",
     "description": "Reports payments of $600 or more for rents, royalties, prizes, awards, and other miscellaneous income.",
     "category": "tax", "revised": "2025", "pages": 1, "has_instructions": False},
    {"id": "form-1099-int", "form_number": "Form 1099-INT", "title": "Interest Income",
     "description": "Reports interest income of $10 or more paid by banks, savings institutions, and other payers.",
     "category": "tax", "revised": "2025", "pages": 1, "has_instructions": False},
    {"id": "schedule-a", "form_number": "Schedule A (Form 1040)", "title": "Itemized Deductions",
     "description": "Use to claim itemized deductions including medical expenses, state/local taxes, mortgage interest, and charitable contributions.",
     "category": "tax", "revised": "2025", "pages": 1, "has_instructions": True},
    {"id": "schedule-b", "form_number": "Schedule B (Form 1040)", "title": "Interest and Ordinary Dividends",
     "description": "Report interest and ordinary dividends exceeding $1,500. Also report foreign accounts and trusts.",
     "category": "tax", "revised": "2025", "pages": 1, "has_instructions": False},
    {"id": "schedule-c", "form_number": "Schedule C (Form 1040)", "title": "Profit or Loss From Business",
     "description": "Report income or loss from a business you operated as a sole proprietor. Includes business expenses.",
     "category": "tax", "revised": "2025", "pages": 2, "has_instructions": True},
    {"id": "schedule-se", "form_number": "Schedule SE (Form 1040)", "title": "Self-Employment Tax",
     "description": "Calculate self-employment tax for individuals with net self-employment earnings of $400 or more.",
     "category": "tax", "revised": "2025", "pages": 1, "has_instructions": True},
    {"id": "form-4868", "form_number": "Form 4868", "title": "Application for Automatic Extension of Time to File",
     "description": "Request an automatic 6-month extension to file your individual income tax return.",
     "category": "tax", "revised": "2025", "pages": 1, "has_instructions": True},
    {"id": "form-8879", "form_number": "Form 8879", "title": "IRS e-file Signature Authorization",
     "description": "Authorize an ERO to enter your PIN as your electronic signature on your e-filed return.",
     "category": "tax", "revised": "2025", "pages": 1, "has_instructions": False},
    {"id": "lp-property-tax", "form_number": "LP-PT-100", "title": "Lakeport Property Tax Return",
     "description": "Annual property tax return for real property within Lakeport city limits. Due April 15.",
     "category": "tax", "revised": "2026", "pages": 2, "has_instructions": True},
    {"id": "lp-business-tax", "form_number": "LP-BT-200", "title": "Lakeport Business Tax Return",
     "description": "Annual business tax return for businesses operating within Lakeport. Report gross revenue and calculate tax liability.",
     "category": "tax", "revised": "2026", "pages": 2, "has_instructions": True},

    # DMV forms
    {"id": "mv-1", "form_number": "MV-1", "title": "Vehicle Registration Application",
     "description": "Apply for initial vehicle registration in Lakeport. Requires proof of ownership, insurance, and emissions test.",
     "category": "dmv", "revised": "2026", "pages": 2, "has_instructions": True},
    {"id": "mv-2", "form_number": "MV-2", "title": "Vehicle Registration Renewal",
     "description": "Renew an existing vehicle registration. Valid for one year from the date of renewal.",
     "category": "dmv", "revised": "2026", "pages": 1, "has_instructions": False},
    {"id": "mv-3", "form_number": "MV-3", "title": "Certificate of Title Application",
     "description": "Apply for a certificate of title for a motor vehicle, trailer, or vessel.",
     "category": "dmv", "revised": "2026", "pages": 2, "has_instructions": True},
    {"id": "mv-4", "form_number": "MV-4", "title": "Title Transfer / Bill of Sale",
     "description": "Transfer vehicle ownership from seller to buyer. Both parties must sign. Requires odometer disclosure.",
     "category": "dmv", "revised": "2026", "pages": 1, "has_instructions": False},
    {"id": "mv-5", "form_number": "MV-5", "title": "Change of Address Notification",
     "description": "Notify the DMV of a change in your residential address. Must be filed within 30 days of moving.",
     "category": "dmv", "revised": "2026", "pages": 1, "has_instructions": False},
    {"id": "dl-1", "form_number": "DL-1", "title": "Driver's License Application / Renewal",
     "description": "Apply for or renew a Lakeport driver's license. Requires vision screening and knowledge test for new applicants.",
     "category": "dmv", "revised": "2026", "pages": 2, "has_instructions": True},
    {"id": "mv-emissions", "form_number": "MV-EM-100", "title": "Vehicle Emissions Inspection Report",
     "description": "Emissions test results form completed by authorized inspection stations. Required for registration.",
     "category": "dmv", "revised": "2026", "pages": 1, "has_instructions": False},

    # Permit forms
    {"id": "bp-100", "form_number": "BP-100", "title": "Building Permit Application",
     "description": "Application for new construction, additions, or structural modifications. Requires site plan and contractor info.",
     "category": "permits", "revised": "2026", "pages": 3, "has_instructions": True},
    {"id": "bp-200", "form_number": "BP-200", "title": "Renovation / Remodel Permit",
     "description": "Permit for interior or exterior renovations not involving structural changes.",
     "category": "permits", "revised": "2026", "pages": 2, "has_instructions": False},
    {"id": "bp-300", "form_number": "BP-300", "title": "Electrical Permit Application",
     "description": "Required for all electrical installations, alterations, or repairs. Must be filed by a licensed electrician.",
     "category": "permits", "revised": "2026", "pages": 1, "has_instructions": False},
    {"id": "bp-400", "form_number": "BP-400", "title": "Plumbing Permit Application",
     "description": "Required for plumbing installations, alterations, or repairs. Includes water heater replacements.",
     "category": "permits", "revised": "2026", "pages": 1, "has_instructions": False},
    {"id": "pk-100", "form_number": "PK-100", "title": "Residential Parking Permit",
     "description": "Apply for a residential parking permit for designated permit-only zones. Valid for one year.",
     "category": "permits", "revised": "2026", "pages": 1, "has_instructions": False},
    {"id": "ep-100", "form_number": "EP-100", "title": "Special Event Permit Application",
     "description": "Required for public events, gatherings, or festivals with 50+ expected attendees.",
     "category": "permits", "revised": "2026", "pages": 2, "has_instructions": True},
    {"id": "fp-100", "form_number": "FP-100", "title": "Fence Permit Application",
     "description": "Required for installation of fences over 4 feet in height. Includes setback and material requirements.",
     "category": "permits", "revised": "2026", "pages": 1, "has_instructions": False},
]

_FORMS_BY_ID = {f["id"]: f for f in GOV_FORMS}


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user, logged_in = _get_browsing_user()
    filings = [f for f in _load_filings() if f["user_id"] == user["id"]]
    vehicles = [v for v in _load_vehicles() if v["user_id"] == user["id"]]
    permits = [p for p in _load_permits() if p["user_id"] == user["id"]]
    payments = [p for p in _load_payments() if p["user_id"] == user["id"]]
    # Documents awaiting the user's signature — surfaced up front (DocuSign-style)
    awaiting_signature = [f for f in filings if _needs_signature(f)]
    services = ["Tax Filings", "Vehicles & DMV", "Permits", "Payments", "Appointments"]
    return render_template(
        "tax-filing-dmv-permits/index.html",
        user=user, logged_in=logged_in,
        filings=filings, vehicles=vehicles,
        permits=permits, payments=payments,
        awaiting_signature=awaiting_signature,
        services=services,
    )


@blueprint.route("/forms")
def forms_page():
    user, logged_in = _get_browsing_user()
    category = request.args.get("category", "").strip()

    cat_labels = {"tax": "Tax Forms & Schedules", "dmv": "Motor Vehicle Forms", "permits": "Permit Applications"}
    form_categories = {}
    for cat_key, cat_label in cat_labels.items():
        forms = [f for f in GOV_FORMS if f["category"] == cat_key]
        if forms:
            form_categories[cat_label] = forms

    return render_template(
        "tax-filing-dmv-permits/forms.html",
        user=user, logged_in=logged_in,
        form_categories=form_categories, category=category,
    )


@blueprint.route("/forms/<form_id>/pdf")
def form_pdf(form_id):
    form = _FORMS_BY_ID.get(form_id)
    if not form:
        abort(404)

    show_instructions = request.args.get("instructions", "") == "1"
    pdf_bytes = _generate_form_pdf(form, instructions=show_instructions)
    filename = f"{form['form_number'].replace(' ', '_').replace('/', '-')}"
    if show_instructions:
        filename += "_Instructions"
    filename += ".pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f"inline; filename={filename}"},
    )


@blueprint.route("/api/forms")
def api_forms():
    category = request.args.get("category", "").strip()
    q = request.args.get("q", "").strip().lower()
    results = GOV_FORMS
    if category:
        results = [f for f in results if f["category"] == category]
    if q:
        results = [f for f in results if q in f["form_number"].lower() or q in f["title"].lower() or q in f["description"].lower()]
    return jsonify(results)


@blueprint.route("/api/forms/<form_id>")
def api_form_detail(form_id):
    form = _FORMS_BY_ID.get(form_id)
    if not form:
        abort(404)
    return jsonify(form)


def _generate_form_pdf(form, instructions=False):
    """Generate a realistic-looking government PDF form."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from io import BytesIO

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch)
    styles = getSampleStyleSheet()
    story = []

    # Header styles
    header_style = ParagraphStyle('FormHeader', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#333333'), leading=10)
    title_style = ParagraphStyle('FormTitle', parent=styles['Normal'],
        fontSize=16, textColor=colors.black, fontName='Helvetica-Bold', leading=20,
        spaceAfter=4)
    subtitle_style = ParagraphStyle('FormSubtitle', parent=styles['Normal'],
        fontSize=10, textColor=colors.HexColor('#444444'), leading=13, spaceAfter=8)
    label_style = ParagraphStyle('FieldLabel', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#555555'), leading=10, spaceBefore=6)
    field_style = ParagraphStyle('FieldBox', parent=styles['Normal'],
        fontSize=10, leading=14, spaceBefore=2, spaceAfter=4)
    small_style = ParagraphStyle('Small', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor('#666666'), leading=9)
    inst_style = ParagraphStyle('Instructions', parent=styles['Normal'],
        fontSize=9, textColor=colors.HexColor('#333333'), leading=13, spaceAfter=6)

    is_federal = form["category"] == "tax" and not form["form_number"].startswith("LP-")

    # Top header bar
    if is_federal:
        header_data = [
            [Paragraph("Department of the Treasury<br/>Internal Revenue Service", header_style),
             Paragraph(f"<b>{form['form_number']}</b>", ParagraphStyle('', parent=title_style, fontSize=20, alignment=2)),
             Paragraph(f"OMB No. 1545-0074<br/>{form['revised']}", ParagraphStyle('', parent=header_style, alignment=2))],
        ]
    else:
        dept = "Lakeport Revenue Department" if form["category"] == "tax" else (
            "Lakeport Department of Motor Vehicles" if form["category"] == "dmv" else
            "Lakeport Permits & Inspections")
        header_data = [
            [Paragraph(f"City of Lakeport<br/>{dept}", header_style),
             Paragraph(f"<b>{form['form_number']}</b>", ParagraphStyle('', parent=title_style, fontSize=18, alignment=2)),
             Paragraph(f"Rev. {form['revised']}", ParagraphStyle('', parent=header_style, alignment=2))],
        ]

    header_table = Table(header_data, colWidths=[2.5 * inch, 3 * inch, 1.5 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6))

    # Title
    story.append(Paragraph(form['title'], title_style))
    if not instructions:
        story.append(Paragraph(form['description'], subtitle_style))

    if instructions:
        # Instructions page
        story.append(Paragraph(f"<b>Instructions for {form['form_number']}</b>", ParagraphStyle('', parent=title_style, fontSize=14, spaceAfter=12)))
        story.append(Paragraph("<b>General Instructions</b>", ParagraphStyle('', parent=styles['Normal'], fontSize=11, fontName='Helvetica-Bold', spaceAfter=6)))

        _add_instructions(story, form, inst_style, small_style)
    else:
        # Form fields
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Spacer(1, 8))

        _add_form_fields(story, form, label_style, field_style, small_style, styles)

    # Footer
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    if is_federal:
        story.append(Paragraph(f"Cat. No. {abs(hash(form['id'])) % 90000 + 10000} &nbsp;&nbsp; {form['form_number']} ({form['revised']})", small_style))
    else:
        story.append(Paragraph(f"{form['form_number']} (Rev. {form['revised']}) &mdash; City of Lakeport", small_style))

    doc.build(story)
    return buf.getvalue()


def _add_form_fields(story, form, label_style, field_style, small_style, styles):
    """Add form-specific fields based on form type."""
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import inch

    fid = form["id"]

    # Common header fields for tax forms
    if form["category"] == "tax":
        story.append(Paragraph("Your first name and middle initial", label_style))
        story.append(Paragraph("_" * 50, field_style))
        story.append(Paragraph("Last name", label_style))
        story.append(Paragraph("_" * 50, field_style))
        story.append(Paragraph("Social security number", label_style))
        story.append(Paragraph("___ ___ - ___ ___ - ___ ___ ___ ___", field_style))

        if fid in ("form-1040", "form-1040-sr"):
            story.append(Paragraph("Home address (number, street, and apt. no.)", label_style))
            story.append(Paragraph("_" * 70, field_style))
            story.append(Paragraph("City, town, or post office. If foreign address, see instructions.", label_style))
            story.append(Paragraph("_" * 40 + " &nbsp; State: _____ &nbsp; ZIP: ____________", field_style))
            story.append(Spacer(1, 10))

            story.append(Paragraph("<b>Filing Status</b> &mdash; Check only one box", label_style))
            for status in ["Single", "Married filing jointly", "Married filing separately", "Head of household", "Qualifying surviving spouse"]:
                story.append(Paragraph(f"&#9744; {status}", field_style))

            story.append(Spacer(1, 10))
            story.append(Paragraph("<b>Income</b>", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
            lines = [
                ("1", "Wages, salaries, tips (Form W-2)", "1"),
                ("2a", "Tax-exempt interest", "2a"),
                ("2b", "Taxable interest", "2b"),
                ("3a", "Qualified dividends", "3a"),
                ("3b", "Ordinary dividends", "3b"),
                ("4a", "IRA distributions", "4a"),
                ("4b", "Taxable amount", "4b"),
                ("5a", "Pensions and annuities", "5a"),
                ("5b", "Taxable amount", "5b"),
                ("6", "Social Security benefits", "6"),
                ("7", "Capital gain or (loss)", "7"),
                ("8", "Other income from Schedule 1, line 10", "8"),
                ("9", "Total income. Add lines 1 through 8", "9"),
            ]
            for num, desc, _ in lines:
                row = [[Paragraph(f"<b>{num}</b>", small_style),
                        Paragraph(desc, field_style),
                        Paragraph("____________", field_style)]]
                t = Table(row, colWidths=[0.5 * inch, 5 * inch, 1.5 * inch])
                t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
                story.append(t)

            story.append(Spacer(1, 10))
            story.append(Paragraph("<b>Tax and Credits</b>", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
            for num, desc in [("10", "Adjustments to income (Schedule 1, line 26)"),
                              ("11", "Adjusted gross income"),
                              ("12", "Standard deduction or itemized deductions (Schedule A)"),
                              ("13", "Qualified business income deduction"),
                              ("14", "Total deductions"),
                              ("15", "Taxable income")]:
                row = [[Paragraph(f"<b>{num}</b>", small_style),
                        Paragraph(desc, field_style),
                        Paragraph("____________", field_style)]]
                t = Table(row, colWidths=[0.5 * inch, 5 * inch, 1.5 * inch])
                t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
                story.append(t)

        elif fid in ("form-w4",):
            story.append(Spacer(1, 8))
            story.append(Paragraph("<b>Step 1: Enter Personal Information</b>", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
            story.append(Paragraph("Address: _" * 40, field_style))
            story.append(Paragraph("Filing status:  &#9744; Single &nbsp; &#9744; Married filing jointly &nbsp; &#9744; Head of household", field_style))
            story.append(Spacer(1, 8))
            story.append(Paragraph("<b>Step 2: Multiple Jobs or Spouse Works</b>", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
            story.append(Paragraph("&#9744; Use the estimator at www.irs.gov/W4App for the most accurate withholding", field_style))
            story.append(Spacer(1, 8))
            story.append(Paragraph("<b>Step 3: Claim Dependents</b>", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
            story.append(Paragraph("Number of qualifying children under age 17: _________ &times; $2,000 = ____________", field_style))
            story.append(Paragraph("Number of other dependents: _________ &times; $500 = ____________", field_style))

        elif fid in ("schedule-c",):
            story.append(Paragraph("Principal business or profession", label_style))
            story.append(Paragraph("_" * 50, field_style))
            story.append(Paragraph("Business name (if different from above)", label_style))
            story.append(Paragraph("_" * 50, field_style))
            story.append(Paragraph("Employer ID number (EIN)", label_style))
            story.append(Paragraph("___ ___ - ___ ___ ___ ___ ___ ___ ___", field_style))
            story.append(Paragraph("Business address: _" * 40, field_style))
            story.append(Spacer(1, 8))
            story.append(Paragraph("<b>Part I &mdash; Income</b>", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
            for num, desc in [("1", "Gross receipts or sales"), ("2", "Returns and allowances"), ("3", "Cost of goods sold (from Part III)"), ("5", "Gross income")]:
                row = [[Paragraph(f"<b>{num}</b>", small_style), Paragraph(desc, field_style), Paragraph("____________", field_style)]]
                t = Table(row, colWidths=[0.5 * inch, 5 * inch, 1.5 * inch])
                t.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
                story.append(t)

        else:
            # Generic tax form fields
            story.append(Paragraph("Tax period: From ____________ To ____________", field_style))
            story.append(Paragraph("Amount: $ ____________", field_style))

    elif form["category"] == "dmv":
        story.append(Paragraph("Owner Information", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
        story.append(Paragraph("Full legal name: _" * 40, field_style))
        story.append(Paragraph("Date of birth: ___/___/______ &nbsp;&nbsp; Driver's license #: ____________", field_style))
        story.append(Paragraph("Address: _" * 40, field_style))
        story.append(Paragraph("City: _________________ State: _____ ZIP: ____________", field_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Vehicle Information", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
        story.append(Paragraph("Year: ________ Make: _________________ Model: _________________", field_style))
        story.append(Paragraph("Body type: ____________ Color: ____________", field_style))
        story.append(Paragraph("VIN: _" * 30, field_style))
        story.append(Paragraph("Plate number (if existing): ____________ State: _____", field_style))
        story.append(Paragraph("Odometer reading: ____________ miles", field_style))
        if fid in ("mv-1", "mv-3"):
            story.append(Spacer(1, 6))
            story.append(Paragraph("Proof of Insurance: &#9744; Attached &nbsp; Policy #: ____________ Carrier: ____________", field_style))
            story.append(Paragraph("Emissions Test: &#9744; Passed &nbsp; &#9744; Exempt &nbsp; Test Date: ___/___/______", field_style))
        if fid == "mv-4":
            story.append(Spacer(1, 8))
            story.append(Paragraph("Seller Information", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
            story.append(Paragraph("Seller name: _" * 30, field_style))
            story.append(Paragraph("Seller signature: _________________________ Date: ___/___/______", field_style))
            story.append(Paragraph("Sale price: $ ____________", field_style))

    elif form["category"] == "permits":
        story.append(Paragraph("Applicant Information", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
        story.append(Paragraph("Name: _" * 40, field_style))
        story.append(Paragraph("Phone: ____________ Email: ________________________", field_style))
        story.append(Paragraph("Property address: _" * 40, field_style))
        story.append(Spacer(1, 8))
        story.append(Paragraph("Project Description", ParagraphStyle('', parent=label_style, fontSize=10, fontName='Helvetica-Bold')))
        story.append(Paragraph("Type of work: _" * 40, field_style))
        story.append(Paragraph("Estimated cost: $ ____________", field_style))
        story.append(Paragraph("Estimated start date: ___/___/______ Completion date: ___/___/______", field_style))
        story.append(Paragraph("Description of work:", label_style))
        for _ in range(4):
            story.append(Paragraph("_" * 80, field_style))
        if fid in ("bp-100", "bp-200"):
            story.append(Spacer(1, 6))
            story.append(Paragraph("Contractor: _" * 30 + " License #: ____________", field_style))

    # Signature block
    story.append(Spacer(1, 16))
    story.append(Paragraph("Under penalties of perjury, I declare that I have examined this form and the information is true, correct, and complete.", small_style))
    story.append(Spacer(1, 8))
    story.append(Paragraph("Signature: _________________________________ &nbsp; Date: ___/___/______", field_style))
    story.append(Paragraph("Print name: ________________________________", field_style))


def _add_instructions(story, form, inst_style, small_style):
    """Add instructions content for a form."""
    from reportlab.platypus import Paragraph, Spacer

    story.append(Paragraph(f"These instructions are for {form['form_number']}, {form['title']}.", inst_style))
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>Who Must File</b>", inst_style))
    if form["category"] == "tax":
        story.append(Paragraph("You must file a return if your gross income exceeds the filing threshold for your filing status and age. See the filing requirements chart in the Form 1040 instructions for details.", inst_style))
    elif form["category"] == "dmv":
        story.append(Paragraph("All motor vehicles operated on public roads within the City of Lakeport must be registered. New residents must register within 30 days of establishing residency.", inst_style))
    else:
        story.append(Paragraph("A permit is required before beginning any construction, renovation, or modification project. Failure to obtain a permit may result in fines and required removal of unauthorized work.", inst_style))

    story.append(Paragraph("<b>When and Where to File</b>", inst_style))
    if form["category"] == "tax":
        story.append(Paragraph("File by April 15 of the year following the tax year. If the due date falls on a weekend or holiday, the deadline is extended to the next business day. File online at lakeport.gov or mail to: Lakeport Revenue Department, PO Box 1040, Lakeport, WA 98000.", inst_style))
    elif form["category"] == "dmv":
        story.append(Paragraph("Submit in person at any Lakeport DMV office, or online at lakeport.gov/dmv. Processing time is 5-10 business days.", inst_style))
    else:
        story.append(Paragraph("Submit to the Lakeport Permits & Inspections office or online at lakeport.gov/permits. Applications are reviewed within 15 business days.", inst_style))

    story.append(Paragraph("<b>Required Documentation</b>", inst_style))
    if form["category"] == "tax":
        story.append(Paragraph("Attach all W-2 forms, 1099 forms, and supporting schedules. Keep a copy of your completed return for your records.", inst_style))
    elif form["category"] == "dmv":
        story.append(Paragraph("Bring valid photo ID, proof of insurance, proof of ownership (title or bill of sale), and emissions inspection report (if applicable).", inst_style))
    else:
        story.append(Paragraph("Include a site plan, project drawings (if applicable), contractor license information, and proof of property ownership or authorization from the property owner.", inst_style))

    story.append(Paragraph("<b>Fees</b>", inst_style))
    if form["category"] == "tax":
        story.append(Paragraph("There is no fee to file a tax return. Late filing penalties may apply: 5% of unpaid tax per month, up to 25%. Interest accrues on unpaid balances.", inst_style))
    elif form["category"] == "dmv":
        story.append(Paragraph("Registration fee: $45. Title fee: $15. Late renewal penalty: $25. Specialty plate surcharge: varies. Emissions test: $15-25 at authorized stations.", inst_style))
    else:
        story.append(Paragraph("Building permit: $50 base + $10 per $1,000 of project value. Electrical/Plumbing: $35. Parking permit: $75/year. Event permit: $100-500 based on size.", inst_style))

    story.append(Paragraph("<b>Need Help?</b>", inst_style))
    story.append(Paragraph("Contact the Lakeport Government Services helpline at (555) 867-5309 or visit lakeport.gov/help.", inst_style))


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("tax-filing-dmv-permits/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return render_template("tax-filing-dmv-permits/login.html",
                               error="Invalid username or password")
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return render_template("tax-filing-dmv-permits/login.html", error="Invalid password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="tax-filing-dmv-permits", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("tax-filing-dmv-permits.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("identity_verified", None)
    return redirect(url_for("tax-filing-dmv-permits.index"))


@blueprint.route("/tax-filings")
def tax_filings_page():
    user, logged_in = _get_browsing_user()
    filings = _load_filings()

    q = request.args.get("q", "").strip()
    tax_year = request.args.get("tax_year")
    filing_type = request.args.get("type")
    status = request.args.get("status")
    user_filter = request.args.get("user_id")

    if user_filter:
        filings = [f for f in filings if f["user_id"] == int(user_filter)]
    else:
        filings = [f for f in filings if f["user_id"] == user["id"]]

    if q:
        filings = [f for f in filings if _search_text(f, q)]
    if tax_year:
        filings = [f for f in filings if f["tax_year"] == int(tax_year)]
    if filing_type:
        filings = [f for f in filings if f["type"] == filing_type]
    if status:
        filings = [f for f in filings if f["status"] == status]

    tax_years = sorted(set(f["tax_year"] for f in _load_filings()))
    filing_types = sorted(set(f["type"] for f in _load_filings()))

    return render_template(
        "tax-filing-dmv-permits/tax_filings.html",
        user=user, logged_in=logged_in, filings=filings,
        tax_years=tax_years, filing_types=filing_types,
        selected_year=tax_year, selected_type=filing_type,
        selected_status=status, search_q=q,
    )


@blueprint.route("/tax-filing/<int:filing_id>")
def tax_filing_detail(filing_id):
    user, logged_in = _get_browsing_user()
    filings = _load_filings()
    filing = next((f for f in filings if f["id"] == filing_id), None)
    if not filing:
        abort(404)
    payments = [p for p in _load_payments()
                if p.get("related_filing_id") == filing["filing_id"]]
    return render_template(
        "tax-filing-dmv-permits/tax_filing_detail.html",
        user=user, logged_in=logged_in, filing=filing, payments=payments,
    )


# ---------------------------------------------------------------------------
# File a Form 1040 income-tax return (create_by_form, carries the compute op:
# line 9 = sum of lines 1-8). Plain HTML form POST so the entered line values
# land in the request body captured by /_admin/log -> gradeable by the verifier.
# ---------------------------------------------------------------------------

# 1040 income lines that sum into line 9 (Total income)
_F1040_INCOME_LINES = ["line_1", "line_2b", "line_3b", "line_4b",
                       "line_5b", "line_6", "line_7", "line_8"]


def _needs_signature(filing):
    """A newly-created filing that requires the user's signature and hasn't been
    signed yet. Pre-existing seed filings (no requires_signature flag) are left
    alone so we don't nag about historical records."""
    return bool(filing.get("requires_signature")) and not filing.get("signed")


def _money(raw):
    """Parse a currency-ish string ('$1,234.50', '1234', '') to float; blank -> 0.0."""
    s = str(raw or "").strip().replace("$", "").replace(",", "").replace("(", "-").replace(")", "")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


@blueprint.route("/file-1040", methods=["GET"])
def file_1040_page():
    user, logged_in = _get_browsing_user()
    default_year = max((f["tax_year"] for f in _load_filings()), default=2024)
    return render_template(
        "tax-filing-dmv-permits/file_1040.html",
        user=user, logged_in=logged_in, default_year=default_year,
    )


@blueprint.route("/file-1040", methods=["POST"])
def file_1040_submit():
    """Persist a filed 1040. Stores each entered line plus the entered line 9 so
    a verifier can gate on the transcribed values AND recompute the total itself."""
    user, logged_in = _get_browsing_user()
    lines = {k: _money(request.form.get(k)) for k in _F1040_INCOME_LINES}
    entered_total = _money(request.form.get("line_9"))
    computed_total = round(sum(lines.values()), 2)

    filings = _load_filings()
    new_id = db.next_id(SITE, "tax_filings")
    tax_year = request.form.get("tax_year", type=int) or 2024
    filing_id = f"TAX-{tax_year}-INC-{new_id:05d}"
    filing = {
        "id": new_id,
        "filing_id": filing_id,
        "user_id": user["id"],
        "root_user_id": user.get("root_user_id", user["id"]),
        "taxpayer_name": request.form.get("taxpayer_name", user.get("display_name", "")).strip(),
        "type": "income_tax",
        "tax_year": tax_year,
        "filing_date": datetime.now().strftime("%Y-%m-%d"),
        "due_date": f"{tax_year + 1}-04-15",
        # every newly-filed form must be signed before it is complete
        "status": "awaiting_signature",
        "requires_signature": True,
        "signed": False,
        "gross_income": entered_total,
        "taxable_income": entered_total,
        "tax_owed": 0.0, "tax_paid": 0.0, "refund_amount": 0.0,
        "filing_method": "online",
        "processed_by": "", "notes": "",
        "property_address": "", "parcel_number": "", "assessed_value": 0.0,
        "tax_rate": 0.0, "gross_revenue": 0.0, "taxable_revenue": 0.0,
        # 1040-specific detail (for grading + the detail page)
        "form_1040": {
            "filing_status": request.form.get("filing_status", ""),
            "ssn": request.form.get("ssn", "").strip(),
            **lines,
            "line_9": entered_total,
            "computed_total_income": computed_total,
        },
    }
    filings.append(filing)
    _save_filings(filings)
    # filing isn't complete until it's signed — take the user straight to signing
    return redirect(url_for("tax-filing-dmv-permits.sign_document_page", filing_id=new_id))


@blueprint.route("/vehicles")
def vehicles_page():
    user, logged_in = _get_browsing_user()
    vehicles = _load_vehicles()

    body_type = request.args.get("body_type")
    renewal_status = request.args.get("renewal_status")
    user_filter = request.args.get("user_id")

    if user_filter:
        vehicles = [v for v in vehicles if v["user_id"] == int(user_filter)]
    else:
        vehicles = [v for v in vehicles if v["user_id"] == user["id"]]

    if body_type:
        vehicles = [v for v in vehicles if v["vehicle"]["body_type"] == body_type]
    if renewal_status:
        vehicles = [v for v in vehicles if v["renewal_status"] == renewal_status]

    body_types = sorted(set(v["vehicle"]["body_type"] for v in _load_vehicles()))

    return render_template(
        "tax-filing-dmv-permits/vehicles.html",
        user=user, logged_in=logged_in, vehicles=vehicles,
        show_register_form=False, body_types=body_types,
        selected_body_type=body_type, selected_renewal=renewal_status,
    )


@blueprint.route("/vehicle/<int:vehicle_id>")
def vehicle_detail(vehicle_id):
    user, logged_in = _get_browsing_user()
    vehicles = _load_vehicles()
    vehicle = next((v for v in vehicles if v["id"] == vehicle_id), None)
    if not vehicle:
        abort(404)
    payments = [p for p in _load_payments()
                if p.get("related_registration_id") == vehicle["registration_id"]]
    return render_template(
        "tax-filing-dmv-permits/vehicle_detail.html",
        user=user, logged_in=logged_in, vehicle=vehicle, payments=payments,
    )


@blueprint.route("/register-vehicle", methods=["GET"])
def register_vehicle_page():
    user, logged_in = _get_browsing_user()
    return render_template(
        "tax-filing-dmv-permits/register_vehicle.html",
        user=user, logged_in=logged_in,
    )


@blueprint.route("/permits")
def permits_page():
    user, logged_in = _get_browsing_user()
    permits = _load_permits()

    permit_type = request.args.get("type")
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    user_filter = request.args.get("user_id")

    if user_filter:
        permits = [p for p in permits if p["user_id"] == int(user_filter)]
    else:
        permits = [p for p in permits if p["user_id"] == user["id"]]

    if permit_type:
        permits = [p for p in permits if p["type"] == permit_type]
    if status:
        permits = [p for p in permits if p["status"] == status]
    if date_from:
        permits = [p for p in permits if p["date_submitted"] and p["date_submitted"] >= date_from]
    if date_to:
        permits = [p for p in permits if p["date_submitted"] and p["date_submitted"] <= date_to]

    permit_types = sorted(set(p["type"] for p in _load_permits()))

    return render_template(
        "tax-filing-dmv-permits/permits.html",
        user=user, logged_in=logged_in, permits=permits,
        show_apply_form=False, permit_types=permit_types,
        selected_type=permit_type, selected_status=status,
        date_from=date_from, date_to=date_to,
    )


@blueprint.route("/permit/<int:permit_id>")
def permit_detail(permit_id):
    user, logged_in = _get_browsing_user()
    permits = _load_permits()
    permit = next((p for p in permits if p["id"] == permit_id), None)
    if not permit:
        abort(404)
    payments = [p for p in _load_payments()
                if p.get("related_permit_id") == permit["permit_id"]]
    return render_template(
        "tax-filing-dmv-permits/permit_detail.html",
        user=user, logged_in=logged_in, permit=permit, payments=payments,
    )


@blueprint.route("/apply-permit", methods=["GET"])
def apply_permit_page():
    user, logged_in = _get_browsing_user()
    return render_template(
        "tax-filing-dmv-permits/apply_permit.html",
        user=user, logged_in=logged_in,
    )


@blueprint.route("/payments")
def payments_page():
    user, logged_in = _get_browsing_user()
    payments = _load_payments()

    payment_type = request.args.get("type")
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    user_filter = request.args.get("user_id")

    if user_filter:
        payments = [p for p in payments if p["user_id"] == int(user_filter)]
    else:
        payments = [p for p in payments if p["user_id"] == user["id"]]

    if payment_type:
        payments = [p for p in payments if p["type"] == payment_type]
    if status:
        payments = [p for p in payments if p["status"] == status]
    if date_from:
        payments = [p for p in payments if p["payment_date"] and p["payment_date"] >= date_from]
    if date_to:
        payments = [p for p in payments if p["payment_date"] and p["payment_date"] <= date_to]

    payment_types = sorted(set(p["type"] for p in _load_payments()))

    return render_template(
        "tax-filing-dmv-permits/payments.html",
        user=user, logged_in=logged_in, payments=payments,
        payment_types=payment_types,
        selected_type=payment_type, selected_status=status,
        date_from=date_from, date_to=date_to,
    )


@blueprint.route("/make-payment")
def make_payment_page():
    user, logged_in = _get_browsing_user()
    filings = [f for f in _load_filings() if f["user_id"] == user["id"]]
    vehicles = [v for v in _load_vehicles() if v["user_id"] == user["id"]]
    permits = [p for p in _load_permits() if p["user_id"] == user["id"]]
    return render_template(
        "tax-filing-dmv-permits/make_payment.html",
        user=user, logged_in=logged_in,
        filings=filings, vehicles=vehicles, permits=permits,
    )


@blueprint.route("/search")
def search_page():
    user, logged_in = _get_browsing_user()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "all")
    results = {"filings": [], "vehicles": [], "permits": [], "payments": []}

    if q:
        # FTS/BM25 search (multi-word queries work; results ranked + capped)
        # instead of the old whole-table Python substring scan, which failed
        # every multi-word query and dumped entire tables on common tokens
        if category in ("all", "filings"):
            results["filings"] = db.search(SITE, "tax_filings", q, limit=50)
        if category in ("all", "vehicles"):
            results["vehicles"] = db.search(SITE, "vehicles", q, limit=50)
        if category in ("all", "permits"):
            results["permits"] = db.search(SITE, "permits", q, limit=50)
        if category in ("all", "payments"):
            results["payments"] = db.search(SITE, "payments", q, limit=50)

    total = sum(len(v) for v in results.values())
    return render_template(
        "tax-filing-dmv-permits/search.html",
        user=user, logged_in=logged_in, query=q, category=category,
        results=results, total=total,
    )


@blueprint.route("/appointments")
def appointments_page():
    user, logged_in = _get_browsing_user()
    return render_template(
        "tax-filing-dmv-permits/appointments.html",
        user=user, logged_in=logged_in,
    )


@blueprint.route("/verify-identity", methods=["GET"])
def verify_identity_page():
    user, logged_in = _get_browsing_user()
    code = _generate_verification_code(user["id"])
    return render_template(
        "tax-filing-dmv-permits/verify_identity.html",
        user=user, logged_in=logged_in,
        verification_code=code,
        verified=session.get("identity_verified", False),
    )


@blueprint.route("/sign-document/<int:filing_id>")
def sign_document_page(filing_id):
    user, logged_in = _get_browsing_user()
    filing = next((f for f in _load_filings() if f["id"] == filing_id), None)
    if not filing:
        abort(404)
    return render_template(
        "tax-filing-dmv-permits/sign_document.html",
        user=user, logged_in=logged_in, filing=filing,
    )


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/tax-filings")
def api_tax_filings():
    filings = _load_filings()
    user_id = request.args.get("user_id", type=int)
    tax_year = request.args.get("tax_year", type=int)
    filing_type = request.args.get("type")
    status = request.args.get("status")
    q = request.args.get("q", "").strip()
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    if user_id:
        filings = [f for f in filings if f["user_id"] == user_id]
    if tax_year:
        filings = [f for f in filings if f["tax_year"] == tax_year]
    if filing_type:
        filings = [f for f in filings if f["type"] == filing_type]
    if status:
        filings = [f for f in filings if f["status"] == status]
    if q:
        filings = [f for f in filings if _search_text(f, q)]
    if date_from:
        filings = [f for f in filings if f.get("filing_date") and f["filing_date"] >= date_from]
    if date_to:
        filings = [f for f in filings if f.get("filing_date") and f["filing_date"] <= date_to]

    return jsonify(filings)


@blueprint.route("/api/tax-filings/<int:filing_id>")
def api_tax_filing(filing_id):
    filing = next((f for f in _load_filings() if f["id"] == filing_id), None)
    if not filing:
        return jsonify({"error": "Filing not found"}), 404
    return jsonify(filing)


@blueprint.route("/api/tax-filings/<int:filing_id>", methods=["PUT"])
def api_tax_filing_update(filing_id):
    filings = _load_filings()
    filing = next((f for f in filings if f["id"] == filing_id), None)
    if not filing:
        return jsonify({"error": "Filing not found"}), 404
    data = request.get_json(force=True)
    for key in ["status", "notes", "filing_method", "tax_paid", "filing_date"]:
        if key in data:
            filing[key] = data[key]
    if "signed" in data:
        filing["signed"] = data["signed"]
        filing["signed_date"] = datetime.now().strftime("%Y-%m-%d")
    _save_filings(filings)
    if data.get("status") == "filed" or data.get("signed"):
        emit("file_created", user_id=filing.get("user_id", 1), filename=f"Tax Return {filing.get('tax_year', '')}", file_type="document", source_site="tax-filing-dmv-permits", source_id=str(filing_id))
    return jsonify(filing)


@blueprint.route("/api/tax-filings/search")
def api_tax_filings_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    filings = _load_filings()
    results = [f for f in filings if _search_text(f, q)]
    return jsonify(results)


@blueprint.route("/api/tax-filings/semantic")
def api_tax_filings_semantic():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])
    filings = _load_filings()
    scored = [(f, _semantic_score(f, q)) for f in filings]
    scored = [(f, s) for f, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)
    return jsonify([f for f, _ in scored])


@blueprint.route("/api/vehicles", methods=["GET"])
def api_vehicles_get():
    vehicles = _load_vehicles()
    user_id = request.args.get("user_id", type=int)
    body_type = request.args.get("body_type")
    renewal_status = request.args.get("renewal_status")
    fuel_type = request.args.get("fuel_type")

    if user_id:
        vehicles = [v for v in vehicles if v["user_id"] == user_id]
    if body_type:
        vehicles = [v for v in vehicles if v["vehicle"]["body_type"] == body_type]
    if renewal_status:
        vehicles = [v for v in vehicles if v["renewal_status"] == renewal_status]
    if fuel_type:
        vehicles = [v for v in vehicles if v["vehicle"]["fuel_type"] == fuel_type]

    return jsonify(vehicles)


@blueprint.route("/api/vehicles", methods=["POST"])
def api_vehicles_post():
    data = request.get_json(force=True)
    vehicles = _load_vehicles()
    new_id = max((v["id"] for v in vehicles), default=0) + 1
    today = datetime.now().strftime("%Y-%m-%d")
    reg_num = f"VEH-{datetime.now().year}-{new_id:05d}"

    new_vehicle = {
        "id": new_id,
        "registration_id": reg_num,
        "user_id": data.get("user_id", 1),
        "root_user_id": data.get("root_user_id", 1),
        "owner_name": data.get("owner_name", ""),
        "vehicle": {
            "year": data.get("year"),
            "make": data.get("make", ""),
            "model": data.get("model", ""),
            "trim": data.get("trim", ""),
            "color": data.get("color", ""),
            "body_type": data.get("body_type", "sedan"),
            "vin": data.get("vin", ""),
            "engine": data.get("engine", ""),
            "fuel_type": data.get("fuel_type", "gasoline"),
        },
        "plate_number": data.get("plate_number", ""),
        "plate_state": data.get("plate_state", "WA"),
        "registration_date": today,
        "expiration_date": f"{datetime.now().year + 1}-{today[5:]}",
        "renewal_status": "current",
        "renewal_due_date": f"{datetime.now().year + 1}-{today[5:]}",
        "renewal_fee": data.get("renewal_fee", 85.00),
        "late_penalty": 0.00,
        "title_number": f"WA-TTL-{today.replace('-', '')}-{str(data.get('vin', ''))[-4:]}",
        "lien_holder": data.get("lien_holder"),
        "insurance_verified": data.get("insurance_verified", False),
        "emissions_test": None,
        "address_on_file": data.get("address_on_file", ""),
    }
    vehicles.append(new_vehicle)
    _save_vehicles(vehicles)
    return jsonify(new_vehicle), 201


@blueprint.route("/api/vehicles/<int:vehicle_id>", methods=["GET"])
def api_vehicle_get(vehicle_id):
    vehicle = next((v for v in _load_vehicles() if v["id"] == vehicle_id), None)
    if not vehicle:
        return jsonify({"error": "Vehicle not found"}), 404
    return jsonify(vehicle)


@blueprint.route("/api/vehicles/<int:vehicle_id>", methods=["PUT"])
def api_vehicle_put(vehicle_id):
    vehicles = _load_vehicles()
    vehicle = next((v for v in vehicles if v["id"] == vehicle_id), None)
    if not vehicle:
        return jsonify({"error": "Vehicle not found"}), 404
    data = request.get_json(force=True)
    for key in ["plate_number", "plate_state", "renewal_status",
                "insurance_verified", "lien_holder", "address_on_file"]:
        if key in data:
            vehicle[key] = data[key]
    if "vehicle" in data:
        for key in ["color", "trim", "engine", "fuel_type"]:
            if key in data["vehicle"]:
                vehicle["vehicle"][key] = data["vehicle"][key]
    _save_vehicles(vehicles)
    return jsonify(vehicle)


@blueprint.route("/api/vehicles/<int:vehicle_id>", methods=["DELETE"])
def api_vehicle_delete(vehicle_id):
    vehicles = _load_vehicles()
    vehicle = next((v for v in vehicles if v["id"] == vehicle_id), None)
    if not vehicle:
        return jsonify({"error": "Vehicle not found"}), 404
    vehicles = [v for v in vehicles if v["id"] != vehicle_id]
    _save_vehicles(vehicles)
    return jsonify({"deleted": vehicle_id})


@blueprint.route("/api/permits", methods=["GET"])
def api_permits_get():
    permits = _load_permits()
    user_id = request.args.get("user_id", type=int)
    permit_type = request.args.get("type")
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    if user_id:
        permits = [p for p in permits if p["user_id"] == user_id]
    if permit_type:
        permits = [p for p in permits if p["type"] == permit_type]
    if status:
        permits = [p for p in permits if p["status"] == status]
    if date_from:
        permits = [p for p in permits if p["date_submitted"] and p["date_submitted"] >= date_from]
    if date_to:
        permits = [p for p in permits if p["date_submitted"] and p["date_submitted"] <= date_to]

    return jsonify(permits)


@blueprint.route("/api/permits", methods=["POST"])
def api_permits_post():
    data = request.get_json(force=True)
    permits = _load_permits()
    new_id = max((p["id"] for p in permits), default=0) + 1
    today = datetime.now().strftime("%Y-%m-%d")
    permit_num = f"PRM-{datetime.now().year}-{new_id:04d}"

    new_permit = {
        "id": new_id,
        "permit_id": permit_num,
        "agency_portal_permit_id": None,
        "user_id": data.get("user_id", 1),
        "root_user_id": data.get("root_user_id", 1),
        "applicant_name": data.get("applicant_name", ""),
        "type": data.get("type", "Building"),
        "address": data.get("address", ""),
        "status": "pending",
        "date_submitted": today,
        "date_approved": None,
        "valid_from": None,
        "valid_to": None,
        "fee": data.get("fee", 0.00),
        "fee_paid": data.get("fee_paid", False),
        "reviewed_by": None,
        "description": data.get("description", ""),
        "notes": None,
    }
    permits.append(new_permit)
    _save_permits(permits)
    return jsonify(new_permit), 201


@blueprint.route("/api/permits/<int:permit_id>")
def api_permit(permit_id):
    permit = next((p for p in _load_permits() if p["id"] == permit_id), None)
    if not permit:
        return jsonify({"error": "Permit not found"}), 404
    return jsonify(permit)


@blueprint.route("/api/permits/<int:permit_id>", methods=["PUT"])
def api_permit_update(permit_id):
    permits = _load_permits()
    permit = next((p for p in permits if p["id"] == permit_id), None)
    if not permit:
        return jsonify({"error": "Permit not found"}), 404
    data = request.get_json(force=True)
    for key in ["status", "notes", "date_approved", "valid_from", "valid_to",
                "fee_paid", "reviewed_by", "description"]:
        if key in data:
            permit[key] = data[key]
    _save_permits(permits)
    return jsonify(permit)


@blueprint.route("/api/payments", methods=["GET"])
def api_payments_get():
    payments = _load_payments()
    user_id = request.args.get("user_id", type=int)
    payment_type = request.args.get("type")
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    if user_id:
        payments = [p for p in payments if p["user_id"] == user_id]
    if payment_type:
        payments = [p for p in payments if p["type"] == payment_type]
    if status:
        payments = [p for p in payments if p["status"] == status]
    if date_from:
        payments = [p for p in payments if p["payment_date"] and p["payment_date"] >= date_from]
    if date_to:
        payments = [p for p in payments if p["payment_date"] and p["payment_date"] <= date_to]

    return jsonify(payments)


@blueprint.route("/api/payments", methods=["POST"])
def api_payments_post():
    data = request.get_json(force=True)
    payments = _load_payments()
    new_id = max((p["id"] for p in payments), default=0) + 1
    today = datetime.now().strftime("%Y-%m-%d")
    pay_num = f"TDPAY-{datetime.now().year}-{new_id:04d}"
    conf_num = f"CFM-{today.replace('-', '')}-{new_id * 11111 % 99999:05d}"

    new_payment = {
        "id": new_id,
        "payment_id": pay_num,
        "user_id": data.get("user_id", 1),
        "root_user_id": data.get("root_user_id", 1),
        "payer_name": data.get("payer_name", ""),
        "type": data.get("type", ""),
        "related_filing_id": data.get("related_filing_id"),
        "related_registration_id": data.get("related_registration_id"),
        "related_permit_id": data.get("related_permit_id"),
        "amount": data.get("amount", 0.00),
        "method": data.get("method", "credit_card"),
        "payment_date": today,
        "due_date": data.get("due_date", today),
        "status": "completed",
        "confirmation_number": conf_num,
        "processed_by": None,
        "notes": data.get("notes"),
    }
    if data.get("method") == "credit_card":
        new_payment["card_last_four"] = data.get("card_last_four", "0000")
    elif data.get("method") == "ach_debit":
        new_payment["account_last_four"] = data.get("account_last_four", "0000")
    elif data.get("method") == "check":
        new_payment["check_number"] = data.get("check_number", "")

    payments.append(new_payment)
    _save_payments(payments)

    account_type = data.get("account_type", "checking")
    emit("payment", user_id=new_payment["user_id"], amount=new_payment["amount"], recipient="City of Lakeport", category="Government", account_type=account_type)

    return jsonify(new_payment), 201


@blueprint.route("/api/search")
def api_search():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "all")
    results = {"filings": [], "vehicles": [], "permits": [], "payments": []}

    if q:
        if category in ("all", "filings"):
            results["filings"] = [f for f in _load_filings() if _search_text(f, q)]
        if category in ("all", "vehicles"):
            results["vehicles"] = [v for v in _load_vehicles()
                                   if _search_text(v, q) or q.lower() in json.dumps(v["vehicle"]).lower()]
        if category in ("all", "permits"):
            results["permits"] = [p for p in _load_permits() if _search_text(p, q)]
        if category in ("all", "payments"):
            results["payments"] = [p for p in _load_payments() if _search_text(p, q)]

    total = sum(len(v) for v in results.values())
    return jsonify({"query": q, "category": category, "total": total, "results": results})


@blueprint.route("/api/search/semantic")
def api_search_semantic():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": [], "count": 0})
    all_items = []
    for f in _load_filings():
        s = _semantic_score(f, q)
        if s > 0:
            all_items.append({"type": "filing", "data": f, "score": s})
    for v in _load_vehicles():
        combined = dict(v)
        combined.update(v["vehicle"])
        s = _semantic_score(combined, q)
        if s > 0:
            all_items.append({"type": "vehicle", "data": v, "score": s})
    for p in _load_permits():
        s = _semantic_score(p, q)
        if s > 0:
            all_items.append({"type": "permit", "data": p, "score": s})
    all_items.sort(key=lambda x: x["score"], reverse=True)
    return jsonify({"results": all_items, "count": len(all_items)})


@blueprint.route("/api/stats")
def api_stats():
    filings = _load_filings()
    vehicles = _load_vehicles()
    permits = _load_permits()
    payments = _load_payments()

    total_tax_owed = sum(f.get("tax_owed", 0) for f in filings)
    total_tax_paid = sum(f.get("tax_paid", 0) for f in filings)
    total_payments = sum(p.get("amount", 0) for p in payments)

    filing_statuses = {}
    for f in filings:
        s = f["status"]
        filing_statuses[s] = filing_statuses.get(s, 0) + 1

    permit_statuses = {}
    for p in permits:
        s = p["status"]
        permit_statuses[s] = permit_statuses.get(s, 0) + 1

    renewal_statuses = {}
    for v in vehicles:
        s = v["renewal_status"]
        renewal_statuses[s] = renewal_statuses.get(s, 0) + 1

    tax_years = sorted(set(f["tax_year"] for f in filings))

    highest_filing = max(filings, key=lambda f: f.get("tax_owed", 0)) if filings else None
    lowest_filing = min(filings, key=lambda f: f.get("tax_owed", 0)) if filings else None
    highest_fee_permit = max(permits, key=lambda p: p.get("fee", 0)) if permits else None
    highest_renewal_fee = max(vehicles, key=lambda v: v.get("renewal_fee", 0)) if vehicles else None

    return jsonify({
        "total_filings": len(filings),
        "total_vehicles": len(vehicles),
        "total_permits": len(permits),
        "total_payments": len(payments),
        "total_tax_owed": total_tax_owed,
        "total_tax_paid": total_tax_paid,
        "outstanding_tax": total_tax_owed - total_tax_paid,
        "total_payment_amount": total_payments,
        "filing_statuses": filing_statuses,
        "permit_statuses": permit_statuses,
        "vehicle_renewal_statuses": renewal_statuses,
        "tax_years": tax_years,
        "highest_tax_owed_filing": highest_filing,
        "lowest_tax_owed_filing": lowest_filing,
        "highest_fee_permit": highest_fee_permit,
        "highest_renewal_fee_vehicle": highest_renewal_fee,
    })


@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json")
    category = request.args.get("category", "filings")

    if category == "filings":
        data = _load_filings()
    elif category == "vehicles":
        data = _load_vehicles()
    elif category == "permits":
        data = _load_permits()
    elif category == "payments":
        data = _load_payments()
    else:
        return jsonify({"error": "Invalid category"}), 400

    if fmt == "csv":
        if not data:
            return Response("", mimetype="text/csv")
        output = io.StringIO()
        flat_data = []
        all_keys = set()
        for item in data:
            flat = {}
            for k, v in item.items():
                if isinstance(v, dict):
                    for kk, vv in v.items():
                        flat[f"{k}_{kk}"] = vv
                elif isinstance(v, list):
                    flat[k] = json.dumps(v)
                else:
                    flat[k] = v
            flat_data.append(flat)
            all_keys.update(flat.keys())
        fieldnames = sorted(all_keys)
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in flat_data:
            writer.writerow(row)
        return Response(output.getvalue(), mimetype="text/csv",
                       headers={"Content-Disposition": f"attachment; filename={category}.csv"})

    return jsonify(data)


@blueprint.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload a document file (for upload_by_upload macro)."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "No file selected"}), 400
    filename = f.filename
    content_length = 0
    content = f.read()
    content_length = len(content)
    return jsonify({
        "status": "uploaded",
        "filename": filename,
        "size": content_length,
        "upload_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


@blueprint.route("/api/appointments", methods=["POST"])
def api_book_appointment():
    """Book a DMV appointment (book_by_date_range macro)."""
    data = request.get_json(force=True)
    date = data.get("date")
    time_slot = data.get("time_slot", "10:00 AM")
    service = data.get("service", "General")
    location = data.get("location", "Lakeport DMV Office")

    if not date:
        return jsonify({"error": "Date is required"}), 400

    appt_id = f"APT-{date.replace('-', '')}-{hash(date + time_slot) % 9999:04d}"
    user, _ = _get_browsing_user()
    emit("booking", user_id=user["id"], title=f"DMV Appt: {service}", start=date, location=location)
    return jsonify({
        "status": "booked",
        "appointment_id": appt_id,
        "date": date,
        "time_slot": time_slot,
        "service": service,
        "location": location,
    })


@blueprint.route("/api/verify-identity", methods=["POST"])
def api_verify_identity():
    """Verify identity by code (verify_identity_by_code macro)."""
    data = request.get_json(force=True)
    code = data.get("code", "")
    user_id = data.get("user_id")

    if not user_id:
        user, _ = _get_browsing_user()
        user_id = user["id"]

    expected = _generate_verification_code(user_id)
    if str(code) == expected:
        session["identity_verified"] = True
        return jsonify({"status": "verified", "user_id": user_id})
    return jsonify({"status": "failed", "error": "Invalid verification code"}), 400


def _valid_signature_drawing(drawing, points):
    """A drawn signature counts when it's a PNG data URL of plausible size backed
    by enough stroke points that a stray dot doesn't pass as a signature."""
    if not (isinstance(drawing, str) and drawing.startswith("data:image/png;base64,")):
        return False
    if len(points or []) < 8:
        return False
    import base64
    try:
        return len(base64.b64decode(drawing.split(",", 1)[1])) > 500
    except Exception:
        return False


@blueprint.route("/api/sign", methods=["POST"])
def api_sign_document():
    """Electronically sign a document (sign_by_freeformdrawing).

    DocuSign-style single "Sign here" field: the taxpayer draws their signature
    in one clearly-labeled box. A valid drawn signature marks the filing signed
    and completes it (status -> filed). The response + saved filing carry the
    signed flag so the trajectory network log makes the action gradeable.
    """
    data = request.get_json(force=True)
    filing_id = data.get("filing_id")

    if not filing_id:
        return jsonify({"error": "Filing ID is required"}), 400

    filings = _load_filings()
    filing = next((f for f in filings if f["id"] == filing_id), None)
    if not filing:
        return jsonify({"error": "Filing not found"}), 404

    drawing = data.get("signature_drawing") or ""
    points = data.get("signature_points") or []
    typed_name = (data.get("typed_name") or "").strip()
    valid_drawing = _valid_signature_drawing(drawing, points)
    # sign by DRAWING (sign_by_freeformdrawing) or by TYPING your name (sign_by_text)
    if not valid_drawing and not typed_name:
        return jsonify({"error": "Draw your signature, or type your full legal name, to continue."}), 400
    method = "drawn" if valid_drawing else "typed"

    filing["signed"] = True
    filing["signed_date"] = datetime.now().strftime("%Y-%m-%d")
    filing["signature"] = typed_name or data.get("signature", filing.get("taxpayer_name", ""))
    filing["signed_method"] = method
    filing["signed_with_drawing"] = valid_drawing
    filing["signature_drawing"] = drawing if valid_drawing else ""
    # signing completes a document that was awaiting signature
    if filing.get("requires_signature") or filing.get("status") == "awaiting_signature":
        filing["status"] = "filed"
    _save_filings(filings)

    return jsonify({
        "status": "signed",
        "filing_id": filing_id,
        "signed_date": filing["signed_date"],
        "signed_method": method,
        "signed_with_drawing": valid_drawing,
    })


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """API login endpoint."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    # Match the form login behavior: default password is "password"
    stored_pw = user.get("password", "password")
    if password and password != stored_pw:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/users")
def api_users():
    return jsonify(_load_users())


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user)


@blueprint.route("/api/tax-filings/compute")
def api_compute():
    """Compute aggregates over tax filings for compute_from_table/compute_by_slider."""
    filings = _load_filings()
    user_id = request.args.get("user_id", type=int)
    min_amount = request.args.get("min_amount", type=float, default=0)
    max_amount = request.args.get("max_amount", type=float, default=999999999)

    if user_id:
        filings = [f for f in filings if f["user_id"] == user_id]

    filings = [f for f in filings if min_amount <= f.get("tax_owed", 0) <= max_amount]

    total_owed = sum(f.get("tax_owed", 0) for f in filings)
    total_paid = sum(f.get("tax_paid", 0) for f in filings)

    return jsonify({
        "count": len(filings),
        "total_tax_owed": total_owed,
        "total_tax_paid": total_paid,
        "outstanding": total_owed - total_paid,
        "average_tax_owed": total_owed / max(len(filings), 1),
        "min_amount_filter": min_amount,
        "max_amount_filter": max_amount,
    })

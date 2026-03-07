"""
Professional PDF builder for HR forms — Injaaz application theme.
Native ReportLab generation, no DOCX conversion.
"""
import os
import base64
import io
import tempfile
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm, mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image,
    KeepTogether, PageBreak,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas

# ── Modern minimal: black & white only ─────────────────────────────────────
C_BLACK = colors.black
C_GRAY = colors.HexColor("#666666")
C_LIGHT = colors.HexColor("#cccccc")
C_WHITE = colors.white

_W, _H = A4
_LM = 1.4 * cm
_RM = 1.4 * cm
CONTENT_W = _W - _LM - _RM

LOGO_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "static", "logo.png",
)


def _fmt(v):
    if not v:
        return "-"
    try:
        d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return d.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        s = str(v)
        return s if s not in ("", "-") else "-"


def _fd(fd, key, default="-"):
    v = (fd or {}).get(key)
    if v in (None, "", "-"):
        return default
    return str(v)


def _sig_to_image(data_url, w_mm=36, h_mm=12):
    """Load signature image and make white background transparent."""
    if not data_url or not isinstance(data_url, str) or not data_url.startswith("data:image"):
        return None
    try:
        _, b64 = data_url.split(",", 1)
        raw = io.BytesIO(base64.b64decode(b64))
        try:
            from PIL import Image as PILImage
            pil = PILImage.open(raw).convert("RGBA")
            data = pil.load()
            w, h = pil.size
            for y in range(h):
                for x in range(w):
                    r, g, b, a = data[x, y]
                    if r >= 250 and g >= 250 and b >= 250:
                        data[x, y] = (r, g, b, 0)
            out = io.BytesIO()
            pil.save(out, "PNG")
            out.seek(0)
            raw = out
        except Exception:
            raw.seek(0)
        return Image(raw, width=w_mm * mm, height=h_mm * mm)
    except Exception:
        return None


# ── Canvas: top accent bar + footer ──────────────────────────────────────────
class HRPDFCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        self._saved = []
        self._form_title = kwargs.pop("form_title", "HR Form")
        super().__init__(*args, **kwargs)

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        n = len(self._saved)
        for s in self._saved:
            self.__dict__.update(s)
            self._draw_decorations(n)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def _draw_decorations(self, total):
        w, h = _W, _H
        self.setStrokeColor(C_BLACK)
        self.setLineWidth(0.3)
        self.line(0, h - 0.08 * cm, w, h - 0.08 * cm)
        self.setStrokeColor(C_LIGHT)
        self.setLineWidth(0.3)
        self.line(_LM, 1.3 * cm, w - _RM, 1.3 * cm)
        self.setFont("Helvetica", 5)
        self.setFillColor(C_GRAY)
        self.drawString(_LM, 0.85 * cm, "INJAAZ")
        self.drawRightString(w - _RM, 0.85 * cm, f"Page {self._pageNumber} of {total}")


# ── Paragraph styles ─────────────────────────────────────────────────────────
def _get_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "HRTitle", parent=base["Normal"],
            fontSize=14, textColor=C_BLACK, fontName="Helvetica-Bold",
            alignment=TA_LEFT, spaceAfter=0, spaceBefore=0,
        ),
        "section": ParagraphStyle(
            "HRSec", parent=base["Normal"],
            fontSize=9, textColor=C_BLACK, fontName="Helvetica-Bold",
            alignment=TA_LEFT, spaceAfter=2, spaceBefore=10, leftIndent=0,
        ),
        "body": ParagraphStyle(
            "HRBody", parent=base["Normal"],
            fontSize=9, textColor=C_BLACK, fontName="Helvetica",
            alignment=TA_LEFT, spaceAfter=1, spaceBefore=0, leading=13,
        ),
        "label": ParagraphStyle(
            "HRLbl", parent=base["Normal"],
            fontSize=8, textColor=C_GRAY, fontName="Helvetica-Bold",
            alignment=TA_LEFT, spaceAfter=0, spaceBefore=0,
        ),
        "small": ParagraphStyle(
            "HRSm", parent=base["Normal"],
            fontSize=7, textColor=C_GRAY, fontName="Helvetica",
            alignment=TA_LEFT, spaceAfter=0, spaceBefore=0,
        ),
    }


# ── Reusable layout components ───────────────────────────────────────────────

def _header_table(form_name, styles):
    """Logo right, headline: Injaaz Facility Management's + form name (centered)."""
    logo_cell = ""
    if os.path.exists(LOGO_PATH):
        try:
            logo_cell = Image(LOGO_PATH, width=0.65 * inch, height=0.65 * inch, kind="proportional")
        except Exception:
            pass
    if not logo_cell:
        logo_cell = Paragraph(
            "<b>INJAAZ</b>",
            ParagraphStyle("HL", fontSize=10, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_RIGHT),
        )
    sub = Paragraph(
        '<font size="7" color="#666666">Injaaz Facility Management\'s</font>',
        ParagraphStyle("HSub", fontSize=7, textColor=C_GRAY, alignment=TA_LEFT, spaceAfter=2),
    )
    ttl = Paragraph(
        f'<font size="14" color="#000000"><b>{form_name}</b></font>',
        ParagraphStyle("HT", fontSize=14, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_LEFT, spaceAfter=0),
    )
    title_block = Table([[sub], [ttl]], colWidths=[CONTENT_W * 0.72])
    title_block.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    t = Table([[title_block, logo_cell]], colWidths=[CONTENT_W * 0.72, CONTENT_W * 0.28])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), 12),
        ("LEFTPADDING", (1, 0), (1, -1), 16),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, C_BLACK),
    ]))
    return t


def _instruction_line(text, styles=None):
    p = Paragraph(
        f'<font size="6" color="#666666">{text}</font>',
        ParagraphStyle("Inst", fontSize=6, textColor=C_GRAY, fontName="Helvetica", alignment=TA_LEFT, spaceAfter=0, spaceBefore=10),
    )
    return p


def _info_box(text, styles=None):
    inner = Paragraph(
        f'<font size="7" color="#000000"><b>Note</b> {text}</font>',
        ParagraphStyle("Info", fontSize=7, textColor=C_BLACK, fontName="Helvetica", alignment=TA_LEFT, spaceAfter=0, spaceBefore=0),
    )
    t = Table([[inner]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("BOX", (0, 0), (-1, -1), 0.5, C_LIGHT),
    ]))
    return t


def _section_bar(title, styles):
    """Section header without number."""
    return _section_bar_numbered(None, title, styles)


def _section_bar_numbered(num, title, styles=None):
    """Compact: number + title, thin underline."""
    styles = styles or _get_styles()
    if num:
        txt = f"<b>{num}. {title}</b>"
        inner = Paragraph(txt, ParagraphStyle("Sec", fontSize=9, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_LEFT))
        t = Table([[inner]], colWidths=[CONTENT_W])
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, C_BLACK),
        ]))
    else:
        t = Table(
            [[Paragraph(f"<b>{title.upper()}</b>", styles["section"])]],
            colWidths=[CONTENT_W],
        )
        t.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
    return t


def _data_table(pairs, cols=2, styles=None):
    """Modern minimal: label | value, horizontal lines only."""
    if not pairs:
        return Spacer(1, 0.05 * inch)
    lbl_style = ParagraphStyle("DTL", fontSize=7, textColor=C_GRAY, fontName="Helvetica-Bold", alignment=TA_LEFT)
    val_style = ParagraphStyle("DTV", fontSize=8, textColor=C_BLACK, fontName="Helvetica", alignment=TA_LEFT, leading=11)
    if cols == 4:
        rows = []
        for i in range(0, len(pairs), 2):
            r = []
            for j in range(2):
                if i + j < len(pairs):
                    lbl, val = pairs[i + j]
                    r.append(Paragraph(f"{lbl.upper()}", lbl_style))
                    r.append(Paragraph(str(val)[:800] if val else "—", val_style))
                else:
                    r.extend(["", ""])
            rows.append(r)
        lw, vw = CONTENT_W * 0.22, CONTENT_W * 0.28
        cw = [lw, vw, lw, vw]
    else:
        rows = [
            [Paragraph(l.upper(), lbl_style), Paragraph(str(v)[:800] if v else "—", val_style)]
            for l, v in pairs
        ]
        cw = [CONTENT_W * 0.28, CONTENT_W * 0.72]
    t = Table(rows, colWidths=cw)
    style_cmds = [
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, C_LIGHT),
    ]
    if cols == 4:
        style_cmds.extend([
            ("LINEAFTER", (0, 0), (0, -1), 0.25, C_LIGHT),
            ("LINEAFTER", (2, 0), (2, -1), 0.25, C_LIGHT),
        ])
    else:
        style_cmds.append(("LINEAFTER", (0, 0), (0, -1), 0.25, C_LIGHT))
    t.setStyle(TableStyle(style_cmds))
    return t


def _form_fields(pairs, styles=None):
    """Form fields: label | value (same as data table)."""
    return _data_table(pairs, cols=2, styles=styles)


def _long_field(label, value, styles=None):
    lbl_style = ParagraphStyle("LFL", fontSize=7, textColor=C_GRAY, fontName="Helvetica-Bold", alignment=TA_LEFT)
    val_style = ParagraphStyle("LFV", fontSize=8, textColor=C_BLACK, fontName="Helvetica", alignment=TA_LEFT, leading=11)
    t = Table([
        [Paragraph(label.upper(), lbl_style)],
        [Paragraph(str(value)[:4000] if value else "—", val_style)],
    ], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, C_LIGHT),
    ]))
    return t


def _rating_table(rows_data, styles=None):
    styles = styles or _get_styles()
    hdr_s = ParagraphStyle("RTH", fontSize=8, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_LEFT)
    hdr = [Paragraph("<b>Criterion</b>", hdr_s), Paragraph("<b>Score</b>", hdr_s), Paragraph("<b>Max</b>", hdr_s)]
    data = [hdr]
    for crit, score, mx in rows_data:
        sv = str(score) if score not in (None, "", "-") else "-"
        data.append([
            Paragraph(crit[:120], styles["body"]),
            Paragraph(sv, styles["body"]),
            Paragraph(str(mx), styles["small"]),
        ])
    t = Table(data, colWidths=[CONTENT_W * 0.60, CONTENT_W * 0.20, CONTENT_W * 0.20])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, C_BLACK),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (2, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, C_LIGHT),
    ]))
    return t


def _checklist_table(items, styles=None, with_date=False):
    """Premium checklist: clean header, horizontal rules only."""
    styles = styles or _get_styles()
    hdr_s = ParagraphStyle("CTH", fontSize=8, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_LEFT)
    if with_date:
        hdr = [Paragraph("<b>Item</b>", hdr_s), Paragraph("<b>Status</b>", hdr_s), Paragraph("<b>Date</b>", hdr_s)]
        cw = [CONTENT_W * 0.60, CONTENT_W * 0.20, CONTENT_W * 0.20]
    else:
        hdr = [Paragraph("<b>Item</b>", hdr_s), Paragraph("<b>Status</b>", hdr_s)]
        cw = [CONTENT_W * 0.75, CONTENT_W * 0.25]
    data = [hdr]
    for row in items:
        label = row[0]
        status = row[1] if len(row) > 1 else None
        date_val = row[2] if len(row) > 2 and with_date else None
        done = str(status).lower() in ("on", "completed", "yes", "true", "1") if status else False
        if with_date and date_val is not None:
            data.append([
                Paragraph(label[:90], styles["body"]),
                Paragraph("Done" if done else "-", styles["body"]),
                Paragraph(_fmt(date_val), styles["small"]),
            ])
        elif with_date:
            data.append([
                Paragraph(label[:90], styles["body"]),
                Paragraph("Done" if done else "-", styles["body"]),
                Paragraph("-", styles["small"]),
            ])
        else:
            data.append([
                Paragraph(label[:90], styles["body"]),
                Paragraph("Done" if done else "-", styles["body"]),
            ])
    t = Table(data, colWidths=cw)
    cmds = [
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, C_BLACK),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, C_LIGHT),
    ]
    if with_date:
        cmds.append(("ALIGN", (2, 0), (2, -1), "CENTER"))
    t.setStyle(TableStyle(cmds))
    return t


def _signature_block(signatures, styles=None):
    """Compact: transparent signature only, no box or background."""
    n = len(signatures)
    sig_w = min(40 * mm, CONTENT_W / max(n, 1))
    cw = [sig_w] * n
    lbl_row, sig_row, dt_row = [], [], []
    for label, img_data, date_val in signatures:
        lbl_row.append(Paragraph(
            f"<b>{label}</b>",
            ParagraphStyle("SL", fontSize=7, textColor=C_BLACK, fontName="Helvetica-Bold", alignment=TA_LEFT),
        ))
        img = _sig_to_image(img_data)
        if img:
            sig_cell = img
        else:
            sig_cell = Paragraph(
                '<font color="#999999">Sign</font>',
                ParagraphStyle("SH", fontSize=7, textColor=C_GRAY, fontName="Helvetica", alignment=TA_LEFT),
            )
        sig_row.append(sig_cell)
        dt_row.append(Paragraph(
            _fmt(date_val) if date_val else "Date",
            ParagraphStyle("SD", fontSize=6, textColor=C_GRAY, fontName="Helvetica", alignment=TA_LEFT),
        ))
    t = Table([lbl_row, sig_row, dt_row], colWidths=cw, rowHeights=[10, 28, 8])
    t.hAlign = "LEFT"
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _footer_block(styles=None):
    return Paragraph(
        f'<font color="#666666" size="6">Generated {datetime.now().strftime("%d/%m/%Y %H:%M")}</font>',
        ParagraphStyle("Ftr", fontSize=6, textColor=C_GRAY, alignment=TA_CENTER, fontName="Helvetica", spaceBefore=4),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Form builders
# ═══════════════════════════════════════════════════════════════════════════════

def _build_leave(story, fd, styles):
    story.append(_header_table("Leave Application Form", styles))
    story.append(Spacer(1, 0.08 * inch))
    story.append(_section_bar_numbered("01", "Employee Information", styles))
    story.append(_data_table([
        ("Employee Name", _fd(fd, "employee_name")),
        ("Employee ID", _fd(fd, "employee_id")),
        ("Job Title", _fd(fd, "job_title")),
        ("Department", _fd(fd, "department")),
        ("Date of Joining", _fmt(fd.get("date_of_joining"))),
        ("Mobile No.", _fd(fd, "mobile_no")),
        ("Last Leave Date", _fmt(fd.get("last_leave_date"))),
        ("Today's Date", _fmt(fd.get("today_date"))),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Leave Details", styles))
    lt = _fd(fd, "leave_type_display") or _fd(fd, "leave_type")
    if lt == "other":
        lt = _fd(fd, "leave_type_other", "Other")
    story.append(_data_table([
        ("Leave Type", lt),
        ("Salary Advance", _fd(fd, "salary_advance", "No").upper()),
        ("First Day of Leave", _fmt(fd.get("first_day_of_leave"))),
        ("Last Day of Leave", _fmt(fd.get("last_day_of_leave"))),
        ("Total Days", _fd(fd, "total_days_requested")),
        ("Date Returning", _fmt(fd.get("date_returning_to_work"))),
        ("Reachable Telephone", _fd(fd, "telephone_reachable")),
        ("Replacement Name", _fd(fd, "replacement_name")),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("03", "Signatures", styles))
    story.append(_signature_block([
        ("Employee", fd.get("employee_signature"), fd.get("today_date")),
        ("Replacement", fd.get("replacement_signature"), None),
        ("GM Approval", fd.get("gm_signature"), None),
    ], styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("04", "HR Use Only", styles))
    story.append(_data_table([
        ("HR Checked", _fd(fd, "hr_checked")),
        ("Balance C/F", _fd(fd, "hr_balance_cf")),
        ("Contract Year", _fd(fd, "hr_contract_year")),
        ("Paid", _fd(fd, "hr_paid")),
        ("Unpaid", _fd(fd, "hr_unpaid")),
    ], cols=4, styles=styles))
    if fd.get("hr_comments"):
        story.append(Spacer(1, 0.05 * inch))
        story.append(_long_field("HR Comments", fd.get("hr_comments"), styles))
    story.append(_signature_block([("HR Signature", fd.get("hr_signature"), fd.get("hr_date"))], styles))


def _build_commencement(story, fd, styles):
    story.append(_header_table("Commencement Form", styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_instruction_line(
        "Complete this form within 5 days of joining and submit to HR.",
        styles,
    ))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "Personal Details", styles))
    story.append(_form_fields([
        ("Full Name", _fd(fd, "employee_name")),
        ("Position / Title", _fd(fd, "position")),
        ("Department", _fd(fd, "department")),
        ("Organization", _fd(fd, "organization", "INJAAZ")),
        ("Contact Number", _fd(fd, "contacts")),
        ("Date of Joining (DD/MM/YYYY)", _fmt(fd.get("date_of_joining"))),
    ], styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Bank Account Details", styles))
    story.append(_form_fields([
        ("Bank Name", _fd(fd, "bank_name")),
        ("Branch", _fd(fd, "bank_branch")),
        ("Account Number", _fd(fd, "account_number")),
    ], styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("03", "Employee Declaration", styles))
    story.append(_signature_block([
        ("Employee Signature", fd.get("employee_signature"), fd.get("employee_sign_date")),
    ], styles))
    story.append(Spacer(1, 0.08 * inch))
    story.append(_section_bar_numbered("04", "Reporting Manager", styles))
    story.append(_form_fields([
        ("Manager Name", _fd(fd, "reporting_to_name")),
        ("Designation / Title", _fd(fd, "reporting_to_designation")),
        ("Contact Number", _fd(fd, "reporting_to_contact")),
    ], styles))
    story.append(Spacer(1, 0.08 * inch))
    story.append(_signature_block([
        ("Reporting Officer Signature", fd.get("reporting_to_signature"), fd.get("reporting_sign_date")),
    ], styles))
    story.append(Spacer(1, 0.08 * inch))
    story.append(_info_box(
        "Need a Salary Letter? If you require assistance with a salary letter to open a new bank account, "
        "please forward your request to the HR Department.",
        styles,
    ))


def _build_duty_resumption(story, fd, styles):
    story.append(_header_table("Duty Resumption Form", styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "Employee Details", styles))
    story.append(_data_table([
        ("Requester", _fd(fd, "requester")),
        ("Employee Name", _fd(fd, "employee_name")),
        ("Employee ID", _fd(fd, "employee_id")),
        ("Job Title", _fd(fd, "job_title")),
        ("Company", _fd(fd, "company", "INJAAZ LLC")),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Leave & Resumption Dates", styles))
    story.append(_data_table([
        ("Leave Started", _fmt(fd.get("leave_started"))),
        ("Leave Ended", _fmt(fd.get("leave_ended"))),
        ("Planned Resumption", _fmt(fd.get("planned_resumption_date"))),
        ("Actual Resumption", _fmt(fd.get("actual_resumption_date"))),
        ("Note", _fd(fd, "note")),
    ], cols=4, styles=styles))
    if fd.get("line_manager_remarks"):
        story.append(Spacer(1, 0.05 * inch))
        story.append(_long_field("Line Manager Remarks", fd.get("line_manager_remarks"), styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("03", "Signatures", styles))
    sigs = [("Employee", fd.get("employee_signature"), fd.get("sign_date"))]
    if fd.get("gm_signature"):
        sigs.append(("GM Approval", fd.get("gm_signature"), None))
    if fd.get("hr_signature"):
        sigs.append(("HR", fd.get("hr_signature"), None))
    story.append(_signature_block(sigs, styles))


def _build_passport_release(story, fd, styles):
    ft = _fd(fd, "passport_form_type", "release").replace("_", " ").title()
    story.append(_header_table(f"Passport {ft} Form", styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "Request Details", styles))
    story.append(_data_table([
        ("Form Type", ft),
        ("Date", _fmt(fd.get("form_date"))),
        ("Requester", _fd(fd, "requester")),
        ("Employee Name", _fd(fd, "employee_name")),
        ("Employee ID", _fd(fd, "employee_id")),
        ("Job Title", _fd(fd, "job_title")),
        ("Project", _fd(fd, "project")),
        ("Release Date", _fmt(fd.get("release_date"))),
    ], cols=4, styles=styles))
    if fd.get("purpose_of_release"):
        story.append(Spacer(1, 0.05 * inch))
        story.append(_long_field("Purpose of Release", fd.get("purpose_of_release"), styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Signatures", styles))
    sigs = [("Employee", fd.get("employee_signature"), fd.get("form_date"))]
    if fd.get("gm_signature"):
        sigs.append(("GM Approval", fd.get("gm_signature"), None))
    if fd.get("hr_signature"):
        sigs.append(("HR", fd.get("hr_signature"), None))
    story.append(_signature_block(sigs, styles))


def _build_grievance(story, fd, styles):
    story.append(_header_table("Employee Grievance / Disciplinary Action Form", styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "First Party (Complainant)", styles))
    story.append(_data_table([
        ("Employee Name", _fd(fd, "complainant_name")),
        ("Employee ID", _fd(fd, "complainant_id")),
        ("Designation", _fd(fd, "complainant_designation")),
        ("Contact No.", _fd(fd, "complainant_contact")),
        ("Date of Incident", _fmt(fd.get("date_of_incident"))),
        ("Shift / Time", _fd(fd, "shift_time")),
        ("Location", _fd(fd, "issue_location", "").replace("_", " ").title()),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Second Party", styles))
    story.append(_data_table([
        ("Employee Name", _fd(fd, "second_party_name")),
        ("Staff ID", _fd(fd, "second_party_id")),
        ("Department", _fd(fd, "second_party_department")),
        ("Place of Incident", _fd(fd, "place_of_incident")),
        ("Shift / Time", _fd(fd, "second_party_shift")),
        ("Contact No.", _fd(fd, "second_party_contact")),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("03", "Complaint Details", styles))
    story.append(_long_field("Description of Complaint", fd.get("complaint_description") or fd.get("complaint"), styles))
    story.append(_data_table([
        ("Witnesses", _fd(fd, "witnesses")),
        ("Who Informed", _fd(fd, "who_informed")),
        ("Attachment", _fd(fd, "attachment")),
    ], cols=2, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("04", "HR Review", styles))
    story.append(_data_table([
        ("Statement 2nd Party", _fd(fd, "statement_2nd_party")),
        ("Statement Verified", _fd(fd, "hr_statement_verified")),
        ("1st / Recurring", _fd(fd, "hr_first_recurring")),
    ], cols=4, styles=styles))
    if fd.get("hr_remarks"):
        story.append(_long_field("HR Remarks", fd.get("hr_remarks"), styles))
    if fd.get("gm_remarks"):
        story.append(_long_field("GM Remarks", fd.get("gm_remarks"), styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("05", "Signatures", styles))
    sigs = [("Complainant", fd.get("complainant_signature"), fd.get("date_of_incident"))]
    if fd.get("hr_signature"):
        sigs.append(("HR", fd.get("hr_signature"), None))
    if fd.get("gm_signature"):
        sigs.append(("GM", fd.get("gm_signature"), None))
    story.append(_signature_block(sigs, styles))


def _build_visa_renewal(story, fd, styles):
    story.append(_header_table("Visa Renewal Form", styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "Employee Information", styles))
    dec = _fd(fd, "decision_display") or _fd(fd, "decision", "").replace("_", " ").title()
    story.append(_data_table([
        ("Date", _fmt(fd.get("form_date"))),
        ("Employee Name", _fd(fd, "employee_name")),
        ("Employee ID", _fd(fd, "employee_id")),
        ("Employer", _fd(fd, "employer", "INJAAZ")),
        ("Position", _fd(fd, "position")),
        ("Years Completed", _fd(fd, "years_completed")),
        ("Decision", dec),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Signature", styles))
    story.append(_signature_block([("Employee", fd.get("employee_signature"), fd.get("form_date"))], styles))


def _build_interview_assessment(story, fd, styles):
    story.append(_header_table("Interview Assessment Form", styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "Candidate Information", styles))
    story.append(_data_table([
        ("Candidate Name", _fd(fd, "candidate_name")),
        ("Position Title", _fd(fd, "position_title")),
        ("Academic Qualification", _fd(fd, "academic_qualification")),
        ("Age", _fd(fd, "age")),
        ("Gender", _fd(fd, "gender")),
        ("Marital Status", _fd(fd, "marital_status")),
        ("No. of Dependents", _fd(fd, "dependents")),
        ("Nationality", _fd(fd, "nationality")),
        ("Current Job Title", _fd(fd, "current_job_title")),
        ("Years of Experience", _fd(fd, "years_experience")),
        ("Current Salary", _fd(fd, "current_salary")),
        ("Expected Salary", _fd(fd, "expected_salary")),
        ("Interview Date", _fmt(fd.get("interview_date"))),
        ("Interview By", _fd(fd, "interview_by")),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Assessment Ratings", styles))
    rating_map = {"outstanding": "Outstanding", "v_good": "V. Good", "good": "Good", "fair": "Fair", "low": "Low"}
    rows = [
        ("Turn-out & Appearance", rating_map.get(_fd(fd, "rating_turnout"), _fd(fd, "rating_turnout")), "Outstanding\u2192Low"),
        ("Confidence", rating_map.get(_fd(fd, "rating_confidence"), _fd(fd, "rating_confidence")), "Outstanding\u2192Low"),
        ("Mental Alertness", rating_map.get(_fd(fd, "rating_mental_alertness"), _fd(fd, "rating_mental_alertness")), "Outstanding\u2192Low"),
        ("Maturity & Emotional Stability", rating_map.get(_fd(fd, "rating_maturity"), _fd(fd, "rating_maturity")), "Outstanding\u2192Low"),
        ("Communication Skills", rating_map.get(_fd(fd, "rating_communication"), _fd(fd, "rating_communication")), "Outstanding\u2192Low"),
        ("Technical Knowledge", rating_map.get(_fd(fd, "rating_technical"), _fd(fd, "rating_technical")), "Outstanding\u2192Low"),
        ("Relevant Training", rating_map.get(_fd(fd, "rating_training"), _fd(fd, "rating_training")), "Outstanding\u2192Low"),
        ("Relevant Experience", rating_map.get(_fd(fd, "rating_experience"), _fd(fd, "rating_experience")), "Outstanding\u2192Low"),
        ("Overall Rating", rating_map.get(_fd(fd, "rating_overall"), _fd(fd, "rating_overall")), "Outstanding\u2192Low"),
    ]
    story.append(_rating_table(rows, styles))
    if fd.get("overall_assessment"):
        story.append(_long_field("Overall Assessment", fd.get("overall_assessment"), styles))
    story.append(_data_table([("Eligible for Employment", _fd(fd, "eligibility", "").upper())], cols=2, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("03", "Signatures", styles))
    sigs = []
    if fd.get("hr_signature"):
        sigs.append(("HR", fd.get("hr_signature"), None))
    if fd.get("gm_signature"):
        sigs.append(("GM", fd.get("gm_signature"), None))
    if sigs:
        story.append(_signature_block(sigs, styles))


def _build_staff_appraisal(story, fd, styles):
    story.append(_header_table("Staff Appraisal Form", styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "Employee Information", styles))
    story.append(_data_table([
        ("Employee Name", _fd(fd, "employee_name")),
        ("Employee ID", _fd(fd, "employee_id")),
        ("Department", _fd(fd, "department")),
        ("Position", _fd(fd, "position")),
        ("Appraisal Period", _fd(fd, "appraisal_period")),
        ("Reviewer", _fd(fd, "reviewer")),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Performance Ratings (Scale 1\u20135)", styles))
    rows = [
        ("Punctuality (15%)", _fd(fd, "rating_punctuality"), "1-5"),
        ("Job Knowledge (15%)", _fd(fd, "rating_job_knowledge"), "1-5"),
        ("Quality of Work (15%)", _fd(fd, "rating_quality"), "1-5"),
        ("Productivity (15%)", _fd(fd, "rating_productivity"), "1-5"),
        ("Communication (10%)", _fd(fd, "rating_communication"), "1-5"),
        ("Teamwork (10%)", _fd(fd, "rating_teamwork"), "1-5"),
        ("Problem-Solving (10%)", _fd(fd, "rating_problem_solving"), "1-5"),
        ("Adaptability (5%)", _fd(fd, "rating_adaptability"), "1-5"),
        ("Leadership (5%)", _fd(fd, "rating_leadership"), "1-5"),
        ("TOTAL SCORE", _fd(fd, "total_score"), "5"),
    ]
    story.append(_rating_table(rows, styles))
    comment_fields = [
        ("comments_punctuality", "Punctuality"), ("comments_job_knowledge", "Job Knowledge"),
        ("comments_quality", "Quality"), ("comments_productivity", "Productivity"),
        ("comments_communication", "Communication"), ("comments_teamwork", "Teamwork"),
        ("comments_problem_solving", "Problem-Solving"), ("comments_adaptability", "Adaptability"),
        ("comments_leadership", "Leadership"),
    ]
    comment_pairs = [(lbl, _fd(fd, key)) for key, lbl in comment_fields if fd.get(key) and fd.get(key) not in ("", "-")]
    if comment_pairs:
        story.append(Spacer(1, 0.05 * inch))
        story.append(_section_bar_numbered("03", "Evaluator Comments", styles))
        story.append(_data_table(comment_pairs, cols=2, styles=styles))
    if fd.get("employee_strengths"):
        story.append(_long_field("Employee Strengths", fd.get("employee_strengths"), styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("04", "Signatures", styles))
    sigs = [("Employee", fd.get("employee_signature"), None)]
    if fd.get("hr_signature"):
        sigs.append(("HR", fd.get("hr_signature"), None))
    if fd.get("gm_signature"):
        sigs.append(("GM", fd.get("gm_signature"), None))
    story.append(_signature_block(sigs, styles))


def _build_station_clearance(story, fd, styles):
    story.append(_header_table("Station Clearance Form", styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "Employee Information", styles))
    dep_map = {"transfer": "Transfer", "resignation": "Resignation", "termination": "Termination", "end_of_contract": "End of Contract"}
    tdep = dep_map.get(_fd(fd, "type_of_departure"), _fd(fd, "type_of_departure"))
    story.append(_data_table([
        ("Employee Name", _fd(fd, "employee_name")),
        ("Employee ID", _fd(fd, "employee_id")),
        ("Position", _fd(fd, "position")),
        ("Department", _fd(fd, "department")),
        ("Section", _fd(fd, "section")),
        ("Employment Date", _fmt(fd.get("employment_date"))),
        ("Type of Departure", tdep),
        ("Last Working Date", _fmt(fd.get("last_working_date"))),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Department Clearance", styles))
    story.append(_checklist_table([
        ("Tasks handed over", fd.get("tasks_handed_over"), fd.get("dept_date_1")),
        ("Documents handed over", fd.get("documents_handed_over"), fd.get("dept_date_2")),
        ("Files handed over", fd.get("files_handed_over"), fd.get("dept_date_3")),
        ("Keys returned", fd.get("keys_returned"), fd.get("dept_date_4")),
        ("Toolbox returned", fd.get("toolbox_returned"), fd.get("dept_date_5")),
        ("Access card", fd.get("access_card_returned"), fd.get("dept_date_6")),
    ], styles, with_date=True))
    if fd.get("dept_others"):
        story.append(_long_field("Department \u2013 Others", fd.get("dept_others"), styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("03", "IT Clearance", styles))
    story.append(_checklist_table([
        ("E-mail cancelled", fd.get("email_cancelled")),
        ("Software/hardware returned", fd.get("software_hardware_returned")),
        ("Laptop returned", fd.get("laptop_returned")),
    ], styles))
    if fd.get("it_others"):
        story.append(_long_field("IT \u2013 Others", fd.get("it_others"), styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("04", "HR Clearance", styles))
    story.append(_checklist_table([
        ("Employee file shifted", fd.get("file_shifted")),
        ("Dues paid", fd.get("dues_paid")),
        ("Medical card returned", fd.get("medical_card_returned")),
    ], styles))
    if fd.get("hr_others"):
        story.append(_long_field("HR \u2013 Others", fd.get("hr_others"), styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("05", "Finance Clearance", styles))
    story.append(_checklist_table([
        ("EOS Benefits Transfer", fd.get("eos_transfer")),
    ], styles))
    if fd.get("finance_others"):
        story.append(_long_field("Finance \u2013 Others", fd.get("finance_others"), styles))
    if fd.get("remarks"):
        story.append(_long_field("Remarks", fd.get("remarks"), styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("06", "Signatures", styles))
    sigs = [("Employee", fd.get("employee_signature"), None)]
    if fd.get("hr_signature"):
        sigs.append(("HR", fd.get("hr_signature"), None))
    story.append(_signature_block(sigs, styles))


def _build_performance_evaluation(story, fd, styles):
    story.append(_header_table("Performance Evaluation Form", styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "Employee Information", styles))
    story.append(_data_table([
        ("Employee Name", _fd(fd, "employee_name")),
        ("Employee ID", _fd(fd, "employee_id")),
        ("Department", _fd(fd, "department")),
        ("Designation", _fd(fd, "designation")),
        ("Date of Evaluation", _fmt(fd.get("date_of_evaluation"))),
        ("Date of Joining", _fmt(fd.get("date_of_joining"))),
        ("Evaluation By", _fd(fd, "evaluation_done_by")),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("02", "Performance Scores (Scale 1\u201310)", styles))
    rows = [
        ("Score 01", _fd(fd, "score_01"), "10"),
        ("Score 02", _fd(fd, "score_02"), "10"),
        ("Score 03", _fd(fd, "score_03"), "10"),
        ("Score 04", _fd(fd, "score_04"), "10"),
        ("Score 05", _fd(fd, "score_05"), "10"),
        ("Score 06", _fd(fd, "score_06"), "10"),
        ("Score 07", _fd(fd, "score_07"), "10"),
        ("Score 08", _fd(fd, "score_08"), "10"),
        ("Score 09", _fd(fd, "score_09"), "10"),
        ("Score 10", _fd(fd, "score_10"), "10"),
        ("OVERALL SCORE", _fd(fd, "overall_score"), "100"),
    ]
    story.append(_rating_table(rows, styles))
    if fd.get("evaluator_name") or fd.get("evaluator_designation"):
        story.append(Spacer(1, 0.06 * inch))
        story.append(_section_bar_numbered("03", "Evaluator Details", styles))
        story.append(_data_table([
            ("Evaluator Name", _fd(fd, "evaluator_name")),
            ("Evaluator Designation", _fd(fd, "evaluator_designation")),
        ], cols=4, styles=styles))
    for lbl, key in [
        ("Evaluator Observation", "evaluator_observation"),
        ("Area of Concern", "area_of_concern"),
        ("Training Required", "training_required"),
        ("Employee Comments", "employee_comments"),
        ("Concern In-charge", "concern_incharge_name"),
        ("In-charge Comments", "incharge_comments"),
        ("GM Remarks", "gm_remarks"),
        ("HR Remarks", "hr_remarks"),
    ]:
        if fd.get(key):
            story.append(_long_field(lbl, fd.get(key), styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("04", "Signatures", styles))
    sigs = [
        ("Employee", fd.get("employee_signature"), fd.get("employee_sign_date")),
        ("Evaluator", fd.get("evaluator_signature"), fd.get("evaluator_sign_date")),
    ]
    if fd.get("hr_signature"):
        sigs.append(("HR", fd.get("hr_signature"), None))
    if fd.get("gm_signature"):
        sigs.append(("GM", fd.get("gm_signature"), None))
    story.append(_signature_block(sigs, styles))


def _build_contract_renewal(story, fd, styles):
    sub_labels = {
        "01": [
            ("01A", "Completes assigned tasks efficiently and accurately"),
            ("01B", "Demonstrates strong understanding of job responsibilities"),
            ("01C", "Meets deadlines consistently"),
            ("01D", "Produces work of high quality"),
            ("01E", "Takes initiative to improve work processes"),
        ],
        "02": [
            ("02A", "Shows positive attitude towards work and colleagues"),
            ("02B", "Accepts feedback constructively"),
            ("02C", "Maintains professionalism"),
            ("02D", "Demonstrates adaptability"),
            ("02E", "Upholds company policies and values"),
        ],
        "03": [
            ("03A", "Communicates clearly and effectively"),
            ("03B", "Works collaboratively"),
            ("03C", "Resolves conflicts amicably"),
            ("03D", "Demonstrates good listening skills"),
            ("03E", "Keeps supervisors informed of progress"),
        ],
        "04": [
            ("04A", "Arrives on time and prepared"),
            ("04B", "Maintains consistent attendance"),
            ("04C", "Provides notice for absences"),
        ],
    }
    story.append(_header_table("Contract Renewal Assessment Form", styles))
    story.append(Spacer(1, 0.05 * inch))
    story.append(_section_bar_numbered("01", "Employee Information", styles))
    story.append(_data_table([
        ("Employee Name", _fd(fd, "employee_name")),
        ("Employee ID", _fd(fd, "employee_id")),
        ("Department", _fd(fd, "department")),
        ("Designation", _fd(fd, "designation")),
        ("Date of Joining", _fmt(fd.get("date_of_joining"))),
        ("Contract End Date", _fmt(fd.get("contract_end_date"))),
        ("Date of Evaluation", _fmt(fd.get("date_of_evaluation"))),
        ("Evaluation By", _fd(fd, "evaluation_by")),
    ], cols=4, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    for idx, (sn, title) in enumerate([
        ("01", "Job Performance"),
        ("02", "Attitude & Work Ethics"),
        ("03", "Communication & Teamwork"),
        ("04", "Punctuality & Attendance"),
    ], start=2):
        story.append(_section_bar_numbered(f"{idx:02d}", title, styles))
        sub_list = sub_labels.get(sn, [])
        rows = []
        for suffix, label in sub_list:
            key = f"rating_{sn}{suffix[-1].lower()}"
            rows.append((label, _fd(fd, key), "1\u20135"))
        rows.append((f"Section {sn} Average", _fd(fd, f"rating_{sn}"), "1\u20135"))
        story.append(_rating_table(rows, styles))
        if fd.get(f"comments_{sn}"):
            story.append(_long_field("Comments", fd.get(f"comments_{sn}"), styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("06", "Summary", styles))
    story.append(_data_table([
        ("Total Score", _fd(fd, "overall_score")),
        ("Recommendation", _fd(fd, "recommendation", "").replace("_", " ").title()),
        ("Strength", _fd(fd, "strength")),
        ("Areas for Improvement", _fd(fd, "areas_for_improvement")),
    ], cols=2, styles=styles))
    story.append(Spacer(1, 0.06 * inch))
    story.append(_section_bar_numbered("07", "Evaluator Signature", styles))
    story.append(_signature_block([
        ("Evaluator", fd.get("evaluator_signature"), fd.get("evaluator_date")),
    ], styles))


_BUILDERS = {
    "leave_application": (_build_leave, "Leave Application"),
    "leave": (_build_leave, "Leave Application"),
    "commencement": (_build_commencement, "Commencement"),
    "duty_resumption": (_build_duty_resumption, "Duty Resumption"),
    "passport_release": (_build_passport_release, "Passport Release"),
    "grievance": (_build_grievance, "Grievance"),
    "visa_renewal": (_build_visa_renewal, "Visa Renewal"),
    "interview_assessment": (_build_interview_assessment, "Interview Assessment"),
    "staff_appraisal": (_build_staff_appraisal, "Staff Appraisal"),
    "station_clearance": (_build_station_clearance, "Station Clearance"),
    "performance_evaluation": (_build_performance_evaluation, "Performance Evaluation"),
    "contract_renewal": (_build_contract_renewal, "Contract Renewal"),
}


def build_hr_pdf(form_type, form_data, output_stream, submission_id=None):
    """Build a professional PDF for the given HR form type. Returns True on success."""
    builder, title = _BUILDERS.get(form_type, (None, None))
    if not builder:
        return False

    fd = form_data or {}
    styles = _get_styles()
    story = []

    builder(story, fd, styles)
    story.append(Spacer(1, 0.12 * inch))
    story.append(_footer_block(styles))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=_LM, rightMargin=_RM,
        topMargin=0.7 * cm, bottomMargin=1.4 * cm,
    )
    doc.build(story, canvasmaker=lambda *a, **k: HRPDFCanvas(*a, form_title=title, **k))

    pdf_bytes = buf.getvalue()
    if hasattr(output_stream, "write"):
        output_stream.write(pdf_bytes)
    else:
        with open(output_stream, "wb") as f:
            f.write(pdf_bytes)
    return True


def supports_pdf(form_type):
    return form_type in _BUILDERS

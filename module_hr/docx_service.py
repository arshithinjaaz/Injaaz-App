"""
Populate HR DOCX templates with form data from the UI.
Uses docxtpl to fill placeholders in HR Documents (e.g. Commencement Form - INJAAZ.DOCX).
"""
import os
import base64
import tempfile
from datetime import datetime
from io import BytesIO


def fit_docx_to_one_page(source_stream):
    """
    Reduce margins and paragraph spacing so the document fits on one page,
    and apply a single font (Calibri) to all form text.
    """
    from docx import Document
    from docx.shared import Cm, Pt

    source_stream.seek(0)
    doc = Document(source_stream)
    margin = Cm(0.7)
    for section in doc.sections:
        section.top_margin = margin
        section.bottom_margin = margin
        section.left_margin = margin
        section.right_margin = margin
    FORM_FONT = "Calibri"
    BODY_SIZE = Pt(11)
    for para in doc.paragraphs:
        pf = para.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(2)
        for run in para.runs:
            run.font.name = FORM_FONT
            if run.font.size is None or run.font.size.pt < 14:
                run.font.size = BODY_SIZE
    # Tables (e.g. header): same font for all cell text
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.name = FORM_FONT
    out = BytesIO()
    doc.save(out)
    out.seek(0)
    return out


def _get_docxtpl():
    """Lazy import so HR module loads even if docxtpl is not installed (DOCX download will fail with clear error)."""
    try:
        from docxtpl import DocxTemplate, InlineImage
        from docx.shared import Mm
        return DocxTemplate, InlineImage, Mm
    except ImportError as e:
        raise ImportError(
            "docxtpl is required for HR DOCX download. Install with: pip install docxtpl"
        ) from e


def _get_hr_documents_path():
    """Path to HR Documents folder (project root)"""
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'HR Documents')


def _get_template_path(form_type):
    """Return template path for form type. Prefer shared file in HR Documents/ root, then templates/."""
    folder = _get_hr_documents_path()
    templates_sub = os.path.join(folder, 'templates')
    templates = {
        'commencement': 'Commencement Form - INJAAZ.DOCX',
        'leave_application': 'Leave Application Form - INJAAZ.DOCX',
        'leave': 'Leave Application Form - INJAAZ.DOCX',
        'duty_resumption': 'Duty Resumption Form - INJAAZ.DOCX',
        'passport_release': 'Passport Release & Submission Form - INJAAZ.DOCX',
        'grievance': 'Employee grievance disciplinary action-form.docx',
    }
    name = templates.get(form_type)
    if not name:
        return None
    # Prefer shared document in HR Documents/ (e.g. Commencement Form - INJAAZ.DOCX) so UI data fills your file
    for base in (folder, templates_sub):
        path = os.path.join(base, name)
        if os.path.isfile(path):
            return path
    return None


def _fmt_date(v):
    if not v:
        return '-'
    try:
        d = datetime.fromisoformat(str(v).replace('Z', '+00:00'))
        return d.strftime('%d/%m/%Y')
    except (ValueError, TypeError):
        return str(v)


def _signature_to_inline_image(tpl, data_url, width_mm=22, height_mm=10):
    """Convert base64 data URL signature to InlineImage for docxtpl.
    Returns (InlineImage, tmp_path) so caller can delete tmp_path after render/save.
    docxtpl reads the image file during render(), so the file must exist until then.
    """
    if not data_url or not isinstance(data_url, str) or not data_url.startswith('data:image'):
        return None, None
    try:
        _, InlineImage, Mm = _get_docxtpl()
        # data:image/png;base64,iVBORw0KGgo...
        header, b64 = data_url.split(',', 1)
        img_data = base64.b64decode(b64)
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(img_data)
            tmp_path = f.name
        img = InlineImage(tpl, tmp_path, width=Mm(width_mm), height=Mm(height_mm))
        return img, tmp_path
    except Exception:
        return None, None


def _build_commencement_context(form_data):
    """Build docxtpl context from Commencement form UI data."""
    fd = form_data or {}
    tpl = None  # Will be set when we have the template

    ctx = {
        'employee_name': fd.get('employee_name') or '-',
        'position': fd.get('position') or '-',
        'contacts': fd.get('contacts') or '-',
        'department': fd.get('department') or '-',
        'organization': fd.get('organization') or 'INJAAZ',
        'date_of_joining': _fmt_date(fd.get('date_of_joining')),
        'bank_name': fd.get('bank_name') or '-',
        'bank_branch': fd.get('bank_branch') or '-',
        'account_number': fd.get('account_number') or '-',
        'employee_sign_date': _fmt_date(fd.get('employee_sign_date')),
        'reporting_to_name': fd.get('reporting_to_name') or '-',
        'reporting_to_designation': fd.get('reporting_to_designation') or '-',
        'reporting_to_contact': fd.get('reporting_to_contact') or '-',
        'reporting_sign_date': _fmt_date(fd.get('reporting_sign_date')),
    }
    return ctx


def _add_commencement_signatures(tpl, ctx, form_data):
    """Add signature InlineImages to context. Returns list of temp file paths to delete after save."""
    fd = form_data or {}
    tmp_paths = []
    emp_sig, emp_path = _signature_to_inline_image(tpl, fd.get('employee_signature'))
    rep_sig, rep_path = _signature_to_inline_image(tpl, fd.get('reporting_to_signature'))
    if emp_path:
        tmp_paths.append(emp_path)
    if rep_path:
        tmp_paths.append(rep_path)
    if emp_sig:
        ctx['employee_signature'] = emp_sig
    else:
        ctx['employee_signature'] = '(Signed in original)'
    if rep_sig:
        ctx['reporting_to_signature'] = rep_sig
    else:
        ctx['reporting_to_signature'] = '(Signed in original)'
    return tmp_paths


def generate_commencement_docx(form_data, output_path_or_stream, submission_id=None):
    """
    Generate filled Commencement Form DOCX from UI form data.
    Template: HR Documents/Commencement Form - INJAAZ.DOCX
    Placeholders required in template: {{ employee_name }}, {{ position }}, {{ contacts }},
    {{ department }}, {{ organization }}, {{ date_of_joining }}, {{ bank_name }}, {{ bank_branch }},
    {{ account_number }}, {{ employee_signature }}, {{ employee_sign_date }},
    {{ reporting_to_name }}, {{ reporting_to_designation }}, {{ reporting_to_contact }},
    {{ reporting_to_signature }}, {{ reporting_sign_date }}
    """
    template_path = _get_template_path('commencement')
    if not template_path:
        raise FileNotFoundError('Commencement Form template not found in HR Documents folder')

    DocxTemplate, _, _ = _get_docxtpl()
    tpl = DocxTemplate(template_path)
    ctx = _build_commencement_context(form_data)
    tmp_paths = _add_commencement_signatures(tpl, ctx, form_data)
    if submission_id:
        ctx['submission_id'] = submission_id

    tpl.render(ctx)
    try:
        if hasattr(output_path_or_stream, 'write'):
            tpl.save(output_path_or_stream)
        else:
            tpl.save(output_path_or_stream)
    finally:
        for p in tmp_paths:
            try:
                if os.path.exists(p):
                    os.unlink(p)
            except OSError:
                pass


def generate_hr_docx(submission, output_path_or_stream):
    """
    Generate filled HR DOCX from submission. Dispatches by form type.
    Returns True if generated, False if form type has no DOCX template.
    """
    form_type = (submission.module_type or '').replace('hr_', '')
    form_data = submission.form_data or {}

    if form_type in ('commencement',):
        generate_commencement_docx(form_data, output_path_or_stream, submission.submission_id)
        return True

    # Add other form types here (leave_application, duty_resumption, etc.)
    # once templates have placeholders added
    return False


def get_supported_docx_forms():
    """Return list of form types that support DOCX download."""
    supported = []
    for ft in ('commencement', 'leave_application', 'leave', 'duty_resumption', 'passport_release', 'grievance'):
        if _get_template_path(ft):
            supported.append(ft)
    return supported

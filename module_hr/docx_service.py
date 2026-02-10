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
        'performance_evaluation': 'Employee Performance Evaluation Form - INJAAZ.DOCX',
        'interview_assessment': 'Interview Assessment Form - INJAAZ.DOCX',
        'staff_appraisal': 'Staff Appraisal Form - INJAAZ.DOCX',
        'station_clearance': 'Station Clearance Form - INJAAZ.DOCX',
        'visa_renewal': 'Visa Renewal Form - INJAAZ.DOCX',
        'contract_renewal': 'Employee Contract Renewal Assessment Form Word.docx',
    }
    name = templates.get(form_type)
    if not name:
        return None
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


def _build_generic_context(form_data, date_keys=None):
    """Build docxtpl context from form_data: all keys, dates formatted. date_keys = set of keys to format as date."""
    fd = form_data or {}
    date_keys = date_keys or set()
    if not date_keys:
        for k, v in fd.items():
            if v and ('date' in k.lower() or 'day' in k.lower() or 'start' in k.lower() or 'end' in k.lower() or 'joining' in k.lower() or 'returning' in k.lower() or 'release' in k.lower() or 'incident' in k.lower() or 'employment' in k.lower() or 'last_working' in k.lower() or 'form_date' in k.lower() or ('evaluation' in k.lower() and 'date' in k)):
                date_keys.add(k)
    skip = {'form_type', 'employee_signature', 'evaluator_signature', 'gm_signature', 'hr_signature', 'complainant_signature'}
    ctx = {}
    for k, v in fd.items():
        if k in skip:
            continue
        if k in date_keys or (v and isinstance(v, str) and len(v) >= 8 and v[:4].isdigit() and '-' in v):
            ctx[k] = _fmt_date(v)
        else:
            ctx[k] = v if v not in (None, '') else '-'
    return ctx


def _add_signatures_to_context(tpl, ctx, form_data, signature_pairs):
    """signature_pairs = [(ctx_key, form_data_key), ...]. Returns tmp_paths."""
    tmp_paths = []
    for ctx_key, data_key in signature_pairs:
        img, path = _signature_to_inline_image(tpl, (form_data or {}).get(data_key))
        if path:
            tmp_paths.append(path)
        ctx[ctx_key] = img if img else '(Signed in original)'
    return tmp_paths


def _generate_filled_docx_generic(form_type, form_data, output_path_or_stream, submission_id=None,
                                   context_extra=None, signature_pairs=None):
    """Load template, build context (generic + extra), add signatures, render, save."""
    template_path = _get_template_path(form_type)
    if not template_path:
        raise FileNotFoundError(f'Template not found for {form_type}')
    DocxTemplate, _, _ = _get_docxtpl()
    tpl = DocxTemplate(template_path)
    ctx = _build_generic_context(form_data)
    if context_extra:
        ctx.update(context_extra)
    if submission_id:
        ctx['submission_id'] = submission_id
    tmp_paths = []
    if signature_pairs:
        tmp_paths = _add_signatures_to_context(tpl, ctx, form_data, signature_pairs)
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


def _build_performance_evaluation_context(form_data):
    """Build docxtpl context from Performance Evaluation form UI data."""
    fd = form_data or {}
    ctx = {
        'employee_name': fd.get('employee_name') or '-',
        'employee_id': fd.get('employee_id') or '-',
        'department': fd.get('department') or '-',
        'designation': fd.get('designation') or '-',
        'date_of_evaluation': _fmt_date(fd.get('date_of_evaluation')),
        'date_of_joining': _fmt_date(fd.get('date_of_joining')),
        'evaluation_done_by': fd.get('evaluation_done_by') or '-',
        'score_01': fd.get('score_01') or '-',
        'score_02': fd.get('score_02') or '-',
        'score_03': fd.get('score_03') or '-',
        'score_04': fd.get('score_04') or '-',
        'score_05': fd.get('score_05') or '-',
        'score_06': fd.get('score_06') or '-',
        'score_07': fd.get('score_07') or '-',
        'score_08': fd.get('score_08') or '-',
        'score_09': fd.get('score_09') or '-',
        'score_10': fd.get('score_10') or '-',
        'overall_score': fd.get('overall_score') or '-',
        'evaluator_name': fd.get('evaluator_name') or '-',
        'evaluator_designation': fd.get('evaluator_designation') or '-',
        'evaluator_observation': fd.get('evaluator_observation') or '-',
        'area_of_concern': fd.get('area_of_concern') or '-',
        'training_required': fd.get('training_required') or '-',
        'employee_comments': fd.get('employee_comments') or '-',
        'employee_sign_date': _fmt_date(fd.get('employee_sign_date')),
        'evaluator_sign_date': _fmt_date(fd.get('evaluator_sign_date')),
        'concern_incharge_name': fd.get('concern_incharge_name') or '-',
        'incharge_comments': fd.get('incharge_comments') or '-',
        'gm_remarks': fd.get('gm_remarks') or '-',
        'hr_remarks': fd.get('hr_remarks') or '-',
    }
    return ctx


def _add_performance_evaluation_signatures(tpl, ctx, form_data):
    """Add signature InlineImages to context. Returns list of temp file paths to delete after save."""
    fd = form_data or {}
    tmp_paths = []
    for key, data_key in [
        ('employee_signature', 'employee_signature'),
        ('evaluator_signature', 'evaluator_signature'),
    ]:
        img, path = _signature_to_inline_image(tpl, fd.get(data_key))
        if path:
            tmp_paths.append(path)
        ctx[key] = img if img else '(Signed in original)'
    return tmp_paths


def generate_performance_evaluation_docx(form_data, output_path_or_stream, submission_id=None):
    """Generate filled Performance Evaluation DOCX from UI form data."""
    template_path = _get_template_path('performance_evaluation')
    if not template_path:
        raise FileNotFoundError('Performance Evaluation template not found')

    DocxTemplate, _, _ = _get_docxtpl()
    tpl = DocxTemplate(template_path)
    ctx = _build_performance_evaluation_context(form_data)
    tmp_paths = _add_performance_evaluation_signatures(tpl, ctx, form_data)
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
    Generate HR DOCX from submission. Filled for commencement and performance_evaluation;
    template copy for other forms.
    Returns (True, filled=True) if generated with data, (True, filled=False) if template only,
    (False, False) if no template.
    """
    form_type = (submission.module_type or '').replace('hr_', '')
    form_data = submission.form_data or {}

    if form_type == 'commencement':
        generate_commencement_docx(form_data, output_path_or_stream, submission.submission_id)
        return True, True
    if form_type == 'performance_evaluation':
        generate_performance_evaluation_docx(form_data, output_path_or_stream, submission.submission_id)
        return True, True

    # Generic filled DOCX for all other forms that have placeholders in template
    FILLED_FORM_SIGNATURES = {
        'leave_application': [('employee_signature', 'employee_signature')],
        'leave': [('employee_signature', 'employee_signature')],
        'duty_resumption': [('employee_signature', 'employee_signature')],
        'passport_release': [('employee_signature', 'employee_signature')],
        'grievance': [('complainant_signature', 'complainant_signature')],
        'interview_assessment': [],
        'staff_appraisal': [('employee_signature', 'employee_signature')],
        'station_clearance': [('employee_signature', 'employee_signature')],
        'visa_renewal': [('employee_signature', 'employee_signature')],
        'contract_renewal': [('evaluator_signature', 'evaluator_signature')],
    }
    if form_type in FILLED_FORM_SIGNATURES:
        try:
            _generate_filled_docx_generic(
                form_type, form_data, output_path_or_stream, submission_id=submission.submission_id,
                signature_pairs=FILLED_FORM_SIGNATURES[form_type]
            )
            return True, True
        except Exception:
            pass
    template_path = _get_template_path(form_type)
    if not template_path:
        return False, False
    with open(template_path, 'rb') as f:
        output_path_or_stream.write(f.read())
    return True, False


def get_supported_docx_forms():
    """Return list of form types that support DOCX download."""
    form_types = (
        'commencement', 'leave_application', 'leave', 'duty_resumption', 'passport_release',
        'grievance', 'performance_evaluation', 'interview_assessment', 'staff_appraisal',
        'station_clearance', 'visa_renewal', 'contract_renewal',
    )
    return [ft for ft in form_types if _get_template_path(ft)]

"""
DocHub API routes.
"""
import json
import mimetypes
import os
import re
import uuid
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, send_file
from sqlalchemy import or_
from sqlalchemy.orm.attributes import flag_modified
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.utils import secure_filename

from app.middleware import token_required
from app.models import DocHubAccess, DocHubDocument, User, db
from common.error_responses import error_response, success_response

docs_bp = Blueprint('docs_bp', __name__, url_prefix='/api/docs')

ALLOWED_DOC_EXTENSIONS = {
    'pdf', 'docx', 'xlsx', 'xls', 'pptx', 'md', 'zip',
    'png', 'jpg', 'jpeg', 'gif', 'webp',
}

# Inline images embedded in HTML content (<img src="/api/docs/inline/...">)
INLINE_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_INLINE_IMAGE_BYTES = 8 * 1024 * 1024

# Reference documents linked from tables / body (<a href="/api/docs/inline/...">)
INLINE_REFERENCE_EXT = {'pdf', 'docx', 'xlsx', 'xls', 'pptx', 'md', 'zip'}

# Only these are served inline (for <img src="...">). All other inline types are download-only.
INLINE_BROWSER_DISPLAY_EXT = INLINE_IMAGE_EXT
MAX_INLINE_REFERENCE_BYTES = 25 * 1024 * 1024

_INLINE_FILE_RE = re.compile(
    r'^[a-f0-9]{32}\.(png|jpg|jpeg|gif|webp|pdf|docx|xlsx|xls|pptx|md|zip)$',
    re.IGNORECASE,
)


def _ext_of(filename):
    return (filename.rsplit('.', 1)[1].lower() if '.' in filename else '')


def _normalize_reference_attachments(raw):
    """Validate list of reference links stored on content documents."""
    if not isinstance(raw, list):
        return None
    out = []
    for item in raw[:40]:
        if not isinstance(item, dict):
            continue
        url = (item.get('url') or '').strip()
        if url.startswith(('http://', 'https://')):
            try:
                from urllib.parse import urlparse

                path = urlparse(url).path or ''
                if path.startswith('/api/docs/inline/'):
                    url = path
            except Exception:
                pass
        if not url.startswith('/api/docs/inline/'):
            continue
        fname = (item.get('filename') or 'file').strip()[:255] or 'file'
        entry = {'url': url, 'filename': fname}
        fid = item.get('feed_document_id')
        if fid is not None:
            try:
                entry['feed_document_id'] = int(fid)
            except (TypeError, ValueError):
                pass
        out.append(entry)
    return out


def _is_allowed_file(filename):
    return _ext_of(filename) in ALLOWED_DOC_EXTENSIONS


def _get_current_user():
    user_id = get_jwt_identity()
    if not user_id:
        return None
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        uid = user_id
    return User.query.get(uid)


def _has_dochub_access(user):
    if not user:
        return False
    if user.role == 'admin':
        return True
    row = DocHubAccess.query.filter_by(user_id=user.id).first()
    if row is None:
        # Default allow for all users unless admin restricts.
        return True
    return bool(row.can_access)


@docs_bp.route('/access-check', methods=['GET'])
@jwt_required()
@token_required
def access_check():
    user = _get_current_user()
    if not user:
        return error_response('User not found', status_code=404, error_code='NOT_FOUND')
    return success_response({
        'allowed': _has_dochub_access(user),
        'is_admin': user.role == 'admin'
    })


DOC_CATEGORIES = ['onboarding', 'contracts', 'policies', 'manuals', 'reports', 'Internal', 'API', 'Guide', 'Legal', 'Spec']


@docs_bp.route('/inline-image', methods=['POST'])
@jwt_required()
@token_required
def upload_inline_editor_image():
    """Store an image for rich-text document content; returns a stable URL for <img src>."""
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    if 'file' not in request.files:
        return error_response('No file', status_code=400, error_code='VALIDATION_ERROR')
    f = request.files['file']
    if not f or not f.filename:
        return error_response('No file', status_code=400, error_code='VALIDATION_ERROR')

    ext = _ext_of(f.filename)
    if ext not in INLINE_IMAGE_EXT:
        return error_response('Only PNG, JPEG, GIF, or WebP images are allowed', status_code=400, error_code='VALIDATION_ERROR')

    generated_root = current_app.config.get('GENERATED_DIR')
    if not generated_root:
        return error_response('Generated directory not configured', status_code=500, error_code='CONFIG_ERROR')

    inline_dir = os.path.join(generated_root, 'dochub', 'inline')
    os.makedirs(inline_dir, exist_ok=True)

    name = f'{uuid.uuid4().hex}.{ext}'
    path = os.path.join(inline_dir, name)
    f.save(path)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    if size > MAX_INLINE_IMAGE_BYTES:
        try:
            os.remove(path)
        except OSError:
            pass
        return error_response('Image too large (max 8 MB)', status_code=400, error_code='VALIDATION_ERROR')

    url = f'/api/docs/inline/{name}'
    return success_response({'url': url}, message='Image uploaded', status_code=201)


@docs_bp.route('/inline-reference', methods=['POST'])
@jwt_required()
@token_required
def upload_inline_reference():
    """Store a reference file (PDF, Office, etc.) for links in document HTML; URL works without JWT."""
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    if 'file' not in request.files:
        return error_response('No file', status_code=400, error_code='VALIDATION_ERROR')
    f = request.files['file']
    if not f or not f.filename:
        return error_response('No file', status_code=400, error_code='VALIDATION_ERROR')

    ext = _ext_of(f.filename)
    if ext not in INLINE_REFERENCE_EXT:
        return error_response(
            'Allowed: PDF, Word, Excel, PowerPoint, Markdown, or ZIP',
            status_code=400,
            error_code='VALIDATION_ERROR',
        )

    generated_root = current_app.config.get('GENERATED_DIR')
    if not generated_root:
        return error_response('Generated directory not configured', status_code=500, error_code='CONFIG_ERROR')

    inline_dir = os.path.join(generated_root, 'dochub', 'inline')
    os.makedirs(inline_dir, exist_ok=True)

    safe_name = secure_filename(f.filename) or f'reference.{ext}'
    name = f'{uuid.uuid4().hex}.{ext}'
    path = os.path.join(inline_dir, name)
    f.save(path)
    size = os.path.getsize(path) if os.path.exists(path) else 0
    if size > MAX_INLINE_REFERENCE_BYTES:
        try:
            os.remove(path)
        except OSError:
            pass
        return error_response('File too large (max 25 MB)', status_code=400, error_code='VALIDATION_ERROR')

    category = (request.form.get('category') or 'Internal').strip()
    if category not in DOC_CATEGORIES:
        category = 'Internal'

    base_title = os.path.splitext(safe_name)[0].replace('_', ' ').strip() or 'Reference file'
    feed_doc = DocHubDocument(
        title=base_title,
        filename=safe_name,
        stored_path=path,
        file_type=ext.upper(),
        doc_type='upload',
        category=category,
        status='draft',
        size_bytes=size,
        author_id=user.id if user else None,
        inline_asset=True,
    )
    db.session.add(feed_doc)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        try:
            os.remove(path)
        except OSError:
            pass
        current_app.logger.exception('Could not register reference file in DocHub list')
        return error_response('Could not save file metadata', status_code=500, error_code='SERVER_ERROR')

    url = f'/api/docs/inline/{name}'
    return success_response(
        {
            'url': url,
            'filename': safe_name,
            'feed_document': feed_doc.to_dict(),
            'feed_document_id': feed_doc.id,
        },
        message='Reference file uploaded',
        status_code=201,
    )


@docs_bp.route('/inline/<filename>', methods=['GET'])
def serve_inline_editor_image(filename):
    """
    Serve inline assets without Authorization (for <img src> and reference <a href>).
    Filenames are unguessable UUIDs.
    """
    if not _INLINE_FILE_RE.match(filename or ''):
        return error_response('Not found', status_code=404, error_code='NOT_FOUND')

    generated_root = current_app.config.get('GENERATED_DIR')
    if not generated_root:
        return error_response('Not found', status_code=404, error_code='NOT_FOUND')

    path = os.path.join(generated_root, 'dochub', 'inline', filename)
    if not os.path.isfile(path):
        return error_response('Not found', status_code=404, error_code='NOT_FOUND')

    ext = _ext_of(filename)
    mime, _ = mimetypes.guess_type(path)
    if ext in INLINE_BROWSER_DISPLAY_EXT:
        return send_file(path, mimetype=mime or 'application/octet-stream', as_attachment=False)

    # Word, PDF, etc.: force download so the browser does not open or preview in-tab.
    dn = (request.args.get('dn') or '').strip()
    download_name = secure_filename(dn) if dn else None
    if not download_name:
        download_name = f'document.{ext}' if ext else filename
    return send_file(
        path,
        mimetype=mime or 'application/octet-stream',
        as_attachment=True,
        download_name=download_name,
    )


@docs_bp.route('', methods=['GET'])
@jwt_required()
@token_required
def list_documents():
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    # Omit rows created only for "additional documents" / inline reference uploads (still reachable by id for DELETE).
    docs = (
        DocHubDocument.query.filter(
            or_(DocHubDocument.inline_asset.is_(False), DocHubDocument.inline_asset.is_(None))
        )
        .order_by(DocHubDocument.updated_at.desc())
        .all()
    )
    docs_data = [d.to_dict() for d in docs]
    return success_response({'documents': docs_data, 'count': len(docs_data)})


@docs_bp.route('', methods=['POST'])
@jwt_required()
@token_required
def create_document():
    """Create a new content-based document (editable in browser)."""
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    data = request.get_json() or {}
    title = (data.get('title') or data.get('name') or '').strip()
    if not title:
        return error_response('Document title is required', status_code=400, error_code='VALIDATION_ERROR')

    category = (data.get('category') or data.get('tag') or 'Internal').strip()
    if category not in DOC_CATEGORIES:
        category = 'Internal'
    content = data.get('content') or ''
    status = (data.get('status') or 'draft').strip().lower()
    if status not in ['draft', 'review', 'published', 'archived']:
        status = 'draft'

    doc = DocHubDocument(
        title=title,
        filename='',
        stored_path='',
        file_type='',
        doc_type='content',
        content=content,
        category=category,
        status=status,
        size_bytes=0,
        author_id=user.id if user else None
    )
    db.session.add(doc)
    db.session.commit()
    return success_response({'document': doc.to_dict()}, message='Document created', status_code=201)


@docs_bp.route('/upload', methods=['POST'])
@jwt_required()
@token_required
def upload_documents():
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    incoming = []
    if 'files' in request.files:
        incoming.extend(request.files.getlist('files'))
    if 'file' in request.files:
        incoming.append(request.files.get('file'))

    incoming = [f for f in incoming if f and f.filename]
    if not incoming:
        return error_response('No file selected', status_code=400, error_code='VALIDATION_ERROR')

    category = (request.form.get('category') or 'Internal').strip()
    status = (request.form.get('status') or 'draft').strip().lower()
    if status not in ['draft', 'review', 'published', 'archived']:
        status = 'draft'

    generated_root = current_app.config.get('GENERATED_DIR')
    if not generated_root:
        return error_response('Generated directory not configured', status_code=500, error_code='CONFIG_ERROR')

    dochub_dir = os.path.join(generated_root, 'dochub')
    os.makedirs(dochub_dir, exist_ok=True)

    created = []
    for idx, f in enumerate(incoming):
        if not _is_allowed_file(f.filename):
            continue

        ext = _ext_of(f.filename)
        original_name = secure_filename(f.filename)
        base_title = os.path.splitext(original_name)[0].replace('_', ' ').strip() or 'Untitled Document'
        custom_name = (request.form.get('name') or '').strip() if idx == 0 else ''
        title = custom_name or base_title

        unique_name = f"{uuid.uuid4().hex[:12]}_{original_name}"
        path = os.path.join(dochub_dir, unique_name)
        f.save(path)
        size_bytes = os.path.getsize(path) if os.path.exists(path) else 0

        doc = DocHubDocument(
            title=title,
            filename=original_name,
            stored_path=path,
            file_type=ext.upper(),
            doc_type='upload',
            category=category,
            status=status,
            size_bytes=size_bytes,
            author_id=user.id if user else None
        )
        db.session.add(doc)
        created.append(doc)

    if not created:
        return error_response('No valid files uploaded', status_code=400, error_code='VALIDATION_ERROR')

    db.session.commit()
    return success_response({
        'documents': [d.to_dict() for d in created],
        'count': len(created)
    }, message=f'Uploaded {len(created)} document(s)', status_code=201)


@docs_bp.route('/<int:doc_id>', methods=['GET'])
@jwt_required()
@token_required
def get_document(doc_id):
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    doc = DocHubDocument.query.get_or_404(doc_id)
    return success_response({'document': doc.to_dict()})


@docs_bp.route('/<int:doc_id>/download', methods=['GET'])
@jwt_required()
@token_required
def download_document(doc_id):
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    doc = DocHubDocument.query.get_or_404(doc_id)
    if (doc.doc_type or 'upload') == 'content':
        return error_response('Content documents cannot be downloaded as files', status_code=400, error_code='INVALID_TYPE')
    if not doc.stored_path or not os.path.exists(doc.stored_path):
        return error_response('Document file not found', status_code=404, error_code='NOT_FOUND')
    mime, _ = mimetypes.guess_type(doc.filename or '')
    return send_file(
        doc.stored_path,
        as_attachment=True,
        download_name=doc.filename or 'document',
        mimetype=mime or 'application/octet-stream',
    )


@docs_bp.route('/<int:doc_id>', methods=['PATCH'])
@jwt_required()
@token_required
def update_document(doc_id):
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    doc = DocHubDocument.query.get_or_404(doc_id)
    data = request.get_json() or {}

    if 'name' in data:
        new_name = (data.get('name') or '').strip()
        if new_name:
            doc.title = new_name
    if 'status' in data:
        status = (data.get('status') or '').strip().lower()
        if status in ['draft', 'review', 'published', 'archived']:
            doc.status = status
    if 'tag' in data:
        tag = (data.get('tag') or '').strip()
        if tag:
            doc.category = tag
    if 'starred' in data:
        doc.is_starred = bool(data.get('starred'))
    if 'content' in data and doc.doc_type == 'content':
        doc.content = data.get('content') or ''
    if 'reference_attachments' in data and doc.doc_type == 'content':
        norm = _normalize_reference_attachments(data.get('reference_attachments'))
        if norm is not None:
            # Always persist JSON (including []); empty list is falsy in Python — do not skip.
            doc.reference_attachments = json.dumps(norm)
            flag_modified(doc, 'reference_attachments')

    doc.updated_at = datetime.utcnow()
    db.session.commit()
    return success_response({'document': doc.to_dict()}, message='Document updated')


@docs_bp.route('/<int:doc_id>', methods=['DELETE'])
@jwt_required()
@token_required
def delete_document(doc_id):
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    doc = DocHubDocument.query.get_or_404(doc_id)
    # Owner or admin can delete
    if user.role != 'admin' and (doc.author_id != user.id):
        return error_response('Only owner/admin can delete this document', status_code=403, error_code='ACCESS_DENIED')

    path = doc.stored_path
    shared_inline = bool(getattr(doc, 'inline_asset', False))
    db.session.delete(doc)
    db.session.commit()
    if shared_inline:
        return success_response({'deleted': True}, message='Document removed from list (file kept for document links)')
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        current_app.logger.warning('Could not remove document file: %s', path)

    return success_response({'deleted': True}, message='Document deleted')

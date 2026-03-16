"""
DocHub API routes.
"""
import os
import uuid
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, send_file
from flask_jwt_extended import get_jwt_identity, jwt_required
from werkzeug.utils import secure_filename

from app.middleware import token_required
from app.models import DocHubAccess, DocHubDocument, User, db
from common.error_responses import error_response, success_response

docs_bp = Blueprint('docs_bp', __name__, url_prefix='/api/docs')

ALLOWED_DOC_EXTENSIONS = {'pdf', 'docx', 'xlsx', 'xls', 'pptx', 'md', 'zip'}


def _ext_of(filename):
    return (filename.rsplit('.', 1)[1].lower() if '.' in filename else '')


def _is_allowed_file(filename):
    return _ext_of(filename) in ALLOWED_DOC_EXTENSIONS


def _get_current_user():
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return User.query.get(user_id)


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


@docs_bp.route('', methods=['GET'])
@jwt_required()
@token_required
def list_documents():
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    docs = DocHubDocument.query.order_by(DocHubDocument.updated_at.desc()).all()
    docs_data = [d.to_dict() for d in docs]
    return success_response({'documents': docs_data, 'count': len(docs_data)})


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


@docs_bp.route('/<int:doc_id>/download', methods=['GET'])
@jwt_required()
@token_required
def download_document(doc_id):
    user = _get_current_user()
    if not _has_dochub_access(user):
        return error_response('DocHub access denied', status_code=403, error_code='ACCESS_DENIED')

    doc = DocHubDocument.query.get_or_404(doc_id)
    if not os.path.exists(doc.stored_path):
        return error_response('Document file not found', status_code=404, error_code='NOT_FOUND')
    return send_file(doc.stored_path, as_attachment=True, download_name=doc.filename)


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
    db.session.delete(doc)
    db.session.commit()
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        current_app.logger.warning('Could not remove document file: %s', path)

    return success_response({'deleted': True}, message='Document deleted')

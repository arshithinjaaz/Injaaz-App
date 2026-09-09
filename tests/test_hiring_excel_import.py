"""Hiring Documents Excel import/export — preview of an app export must succeed."""
from io import BytesIO
from pathlib import Path


def _create_candidate(client, headers, name='Import Test Candidate', role='HVAC Technician'):
    response = client.post(
        '/hr/api/hiring/candidates',
        headers=headers,
        json={'full_name': name, 'role': role},
    )
    assert response.status_code == 201, response.get_json()
    return (response.get_json() or {}).get('candidate') or {}


def test_hiring_export_then_import_preview(client, admin_auth_headers):
    created = _create_candidate(client, admin_auth_headers)
    assert created.get('id')

    exported = client.get('/hr/api/hiring/export', headers=admin_auth_headers)
    assert exported.status_code == 200, exported.get_data(as_text=True)
    assert exported.data[:2] == b'PK'

    preview = client.post(
        '/hr/api/hiring/import',
        data={
            'file': (BytesIO(exported.data), 'Hiring_Document_Tracker_Export (1).xlsx'),
            'preview': '1',
        },
        headers=admin_auth_headers,
        content_type='multipart/form-data',
    )
    body = preview.get_json()
    assert preview.status_code == 200, body
    assert body.get('success') is True
    assert (body.get('will_update') or 0) + (body.get('will_create') or 0) >= 1


def test_parse_live_export_workbook():
    path = Path('/Users/arshith/Downloads/Hiring_Document_Tracker_Export (1).xlsx')
    if not path.exists():
        return
    from module_hr.hiring_excel import parse_hiring_workbook

    rows = parse_hiring_workbook(_Upload(path.read_bytes(), path.name))
    assert len(rows) >= 1
    assert any((r.get('fields') or {}).get('full_name') for r in rows)


def test_employee_from_hiring_schema_uses_postgres_timestamp():
    import inspect
    from module_hr.employee_from_hiring import ensure_employee_from_hiring_schema

    src = inspect.getsource(ensure_employee_from_hiring_schema)
    assert 'TIMESTAMP' in src
    assert "dialect == 'postgresql'" in src


class _Upload:
    def __init__(self, data: bytes, name: str):
        self._buf = BytesIO(data)
        self.filename = name

    def read(self, *a, **k):
        return self._buf.read(*a, **k)

    def seek(self, *a, **k):
        return self._buf.seek(*a, **k)

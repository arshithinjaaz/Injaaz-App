"""Manpower Tracker board list must return JSON even with hiring links."""


def test_manpower_vacancies_list_ok_when_empty(client, admin_auth_headers):
    response = client.get('/hr/api/manpower/vacancies', headers=admin_auth_headers)
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json() or {}
    assert body.get('success') is True
    assert isinstance(body.get('vacancies'), list)


def test_manpower_vacancies_list_with_linked_candidate(client, admin_auth_headers, app):
    from app.models import HiringCandidate, ManpowerProject, ManpowerTrade, ManpowerVacancy, db

    with app.app_context():
        trade = ManpowerTrade(name='Electrician', sort_order=1, active=True)
        project = ManpowerProject(name='Board JSON Test Project', sort_order=1, active=True)
        db.session.add_all([trade, project])
        db.session.flush()
        cand = HiringCandidate(full_name='Linked Board Person', role='Electrician')
        db.session.add(cand)
        db.session.flush()
        vac = ManpowerVacancy(
            trade_id=trade.id,
            project_id=project.id,
            requirement_type='new',
            status='open',
            hiring_candidate_id=cand.id,
        )
        db.session.add(vac)
        db.session.commit()

    response = client.get('/hr/api/manpower/vacancies', headers=admin_auth_headers)
    assert response.status_code == 200, response.get_data(as_text=True)
    body = response.get_json() or {}
    rows = body.get('vacancies') or []
    assert any((row.get('candidate_name') or '') == 'Linked Board Person' for row in rows)

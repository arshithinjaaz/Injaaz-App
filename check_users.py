from app.extensions import db
from app.models import User
from Injaaz import create_app

app = create_app()

with app.app_context():
    users = User.query.all()
    print(f'Found {len(users)} users')
    for u in users:
        print(f'User: {u.username}, is_active: {u.is_active}')

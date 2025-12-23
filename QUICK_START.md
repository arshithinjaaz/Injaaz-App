# 🚀 Quick Start - Authentication & Database

## Initialize Database (First Time)
```bash
python scripts/init_db.py
```
**Default Admin:** username=`admin`, password=`Admin@123`

## Start Application
```bash
python Injaaz.py
```
**URL:** http://localhost:5000

## Test Authentication
1. **Register:** http://localhost:5000/register
2. **Login:** http://localhost:5000/login
3. **Dashboard:** http://localhost:5000/dashboard

## API Endpoints
- `POST /api/auth/register` - Create user
- `POST /api/auth/login` - Get JWT tokens
- `POST /api/auth/refresh` - Refresh token
- `POST /api/auth/logout` - Revoke token
- `GET /api/auth/me` - Current user
- `POST /api/auth/change-password` - Update password

## Environment Variables (.env)
```env
SECRET_KEY=<your-secret>
JWT_SECRET_KEY=<your-jwt-secret>
DATABASE_URL=sqlite:///injaaz.db
```

## Cloud Database (Production)
```env
# Render PostgreSQL
DATABASE_URL=postgresql://user:pass@host/db

# Enable production mode
FLASK_ENV=production
DEBUG=false
SESSION_COOKIE_SECURE=true
```

## Protect Routes
```python
from app.middleware import token_required

@app.route('/protected')
@token_required
def protected():
    return "Authenticated!"
```

## Frontend (JavaScript)
```javascript
// Login
const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username, password})
});
const data = await response.json();
localStorage.setItem('access_token', data.access_token);

// Use token
fetch('/api/protected', {
    headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
    }
});
```

## Documentation
- **[AUTHENTICATION_COMPLETE.md](AUTHENTICATION_COMPLETE.md)** - Complete summary
- **[IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)** - Step-by-step guide
- **[AUTH_DATABASE_PLAN.md](AUTH_DATABASE_PLAN.md)** - Architecture details

## Status
✅ Database models created  
✅ Authentication API complete  
✅ Login/Register pages ready  
✅ JWT tokens working  
✅ Security fixes applied  
⏳ Module integration pending  

**Next:** Run `python scripts/init_db.py` to get started!

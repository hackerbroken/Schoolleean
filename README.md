# SchoolLearn - Backend Setup

This is the backend for the SchoolLearn application, built with Python and Flask.

## Prerequisites

- Python 3.8+
- pip (Python package manager)

## Setup Instructions

1. **Create a virtual environment** (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**:
   - Copy `.env.example` to `.env`
   - Update the `SECRET_KEY` in `.env` with a secure secret key

4. **Initialize the database**:
   ```bash
   flask shell
   >>> from app import db
   >>> db.create_all()
   >>> exit()
   ```

5. **Run the development server**:
   ```bash
   flask run --port=5000
   ```

## API Endpoints

### Authentication
- `POST /api/register` - Register a new user
- `POST /api/login` - Login and get JWT token
- `GET /api/logout` - Logout (requires authentication)

### Quiz Progress
- `POST /api/quiz/progress` - Save quiz progress (requires authentication)
- `GET /api/user/progress` - Get user's quiz progress (requires authentication)

## Frontend Integration

Update your frontend API calls to point to the backend URL (e.g., `http://localhost:5000`). Include the JWT token in the `Authorization` header for authenticated routes:

```javascript
const response = await fetch('http://localhost:5000/api/protected-route', {
  headers: {
    'Authorization': `Bearer ${yourJwtToken}`,
    'Content-Type': 'application/json'
  }
});
```

## Deployment

For production deployment, consider using:
- Gunicorn or uWSGI as the WSGI server
- Nginx as a reverse proxy
- PostgreSQL or MySQL instead of SQLite
- Environment variables for sensitive configuration

## License

This project is licensed under the MIT License.

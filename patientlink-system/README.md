# PatientLink Clinic System

A clinic receptionist system for collecting patient data that will later be used by a WhatsApp automation backend.

## Architecture

The application follows a microservice architecture with three main services:

1. **Frontend**: React (Vite) with TailwindCSS
2. **Auth Service**: Django with JWT authentication
3. **Patient API**: FastAPI for patient data management
4. **Database**: PostgreSQL (for production) or SQLite (for development)

## Project Structure

```
patientlink-system/
├── frontend/           # React Vite application
├── api/               # FastAPI service
├── auth_service/      # Django authentication service
└── docker/            # Docker configuration
```

## Prerequisites

- Docker and Docker Compose
- Node.js (for local development without Docker)
- PostgreSQL (optional - for production)

## Quick Start

### Option 1: Using Docker (Production)

1. Clone the repository
2. Navigate to the project directory
3. Update the `.env` file with your production values:
   ```bash
   cp .env.example .env
   # Edit .env with your production settings
   ```
4. Build and start the services:
   ```bash
   cd docker
   docker-compose up --build -d
   ```

All services will be available:
- **Frontend**: http://localhost (via nginx on port 80)
- **Auth Service**: http://localhost:8000
- **Patient API**: http://localhost:8001

### Option 2: Local Development

1. **Setup Django Auth Service:**
   ```bash
   cd patientlink-system/auth_service
   pip install -r requirements.txt
   python manage.py migrate
   python manage.py runserver 8000
   ```

2. **Setup FastAPI Patient Service:**
   ```bash
   cd patientlink-system/api
   pip install -r requirements.txt
   uvicorn main:app --reload --port 8001
   ```

3. **Setup React Frontend:**
   ```bash
   cd patientlink-system/frontend
   npm install
   npm run dev
   ```

## Services Overview

### Auth Service (Django)
- User registration
- User login
- JWT token authentication
- Token verification

**Endpoints:**
- `POST /api/signup` - Create new user account
- `POST /api/login` - Authenticate and get tokens
- `POST /api/verify-token` - Verify JWT token validity

### Patient API (FastAPI)
- Patient data management
- Medicine tracking

**Endpoints:**
- `POST /patients/` - Create new patient
- `GET /patients/` - Get all patients
- `GET /patients/{id}` - Get specific patient
- `DELETE /patients/{id}` - Delete patient

### Frontend (React)
- Login/Signup pages
- Dashboard
- Patient entry form with medicine tracking
- Responsive design for clinic use

## Features

- Receptionist-focused UI with large form elements
- Secure user authentication
- Patient data entry with medicine schedules
- Support for multiple medicines per patient
- Morning/evening/night dosing options
- Duration tracking for medicines

## Usage Flow

1. Receptionist signs up or logs in
2. Navigate to "Add Patient" page
3. Enter patient details (name, WhatsApp number, date of birth)
4. Add one or more medicines with timing and duration
5. Save patient data to the database

## Environment Configuration

### Production Environment Variables

Create a `.env` file in the project root:

```env
# Django Auth Service
DJANGO_SECRET_KEY=your-super-secret-key-change-in-production
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,your-domain.com

# Database
DATABASE_URL=postgresql://postgres:your-password@db:5432/patientlink
POSTGRES_PASSWORD=your-secure-password
```

### Service-Specific Configuration

**auth_service/settings.py** - Development settings
**auth_service/settings_production.py** - Production settings

## Production Deployment

### Using Docker Compose

```bash
# Build and start all services
cd docker
docker-compose up --build -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Manual Production Setup

1. **Build Frontend:**
   ```bash
   cd frontend
   npm ci
   npm run build
   ```

2. **Setup Database:**
   ```bash
   # Install PostgreSQL and create database
   createdb patientlink
   ```

3. **Run Django with Gunicorn:**
   ```bash
   cd auth_service
   pip install -r requirements.txt
   python manage.py migrate
   gunicorn auth_service.auth_service.wsgi:application --bind 0.0.0.0:8000 --workers 4
   ```

4. **Run FastAPI with Uvicorn:**
   ```bash
   cd api
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 8001 --workers 4
   ```

5. **Serve Frontend:**
   - Configure nginx to serve the `dist/` folder
   - Proxy `/api/` to Django (port 8000)
   - Proxy `/patients/` to FastAPI (port 8001)

## Security Notes

- **Change the secret key** in production (use a long random string)
- **Set DEBUG=False** in production
- **Configure ALLOWED_HOSTS** with your domain
- **Use HTTPS** in production (configure SSL/TLS)
- **Secure your database** with strong passwords
- **Review CORS settings** before deploying

## Testing the Complete Flow

1. Open http://localhost (or your production URL)
2. Click "Sign up" and register a new account
3. Log in with your credentials
4. Navigate to "Add Patient" from the dashboard
5. Fill in patient details and add medicines
6. Submit the form to save patient information

The data will be stored in the database and can be retrieved via the API.

## Database Schema

### Users (Django)
- id
- username
- password (hashed)
- clinic_name
- created_at

### Patients (FastAPI)
- id
- name
- whatsapp_number
- dob
- created_at

### Medicines (FastAPI)
- id
- patient_id (foreign key to Patients)
- medicine_name
- morning (boolean)
- evening (boolean)
- night (boolean)
- duration_days (integer)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Submit a pull request

## License

MIT License

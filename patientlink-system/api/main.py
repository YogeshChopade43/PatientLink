"""
PatientLink FastAPI Application
Implements comprehensive security features
"""
import os
import re
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from typing import List, Optional
from pydantic import validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging

import models
import schemas

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="Patient API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    # Security headers in OpenAPI
    swagger_ui_oauth2_redirect_url="/oauth2redirect",
)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ============================================================================
# SECURITY MIDDLEWARE
# ============================================================================

# Gzip compression for performance
app.add_middleware(GZipMiddleware, minimum_size=1000)

# JWT Secret Key - must match Django's SECRET_KEY for token verification
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-your-secret-key-here')
JWT_ALGORITHM = 'HS256'

# CORS Configuration - Restrict to specific origins for security
# For development, allow common localhost ports
CORS_ORIGINS = os.environ.get(
    'CORS_ORIGINS', 
    'http://localhost:5173,http://localhost:5175,http://127.0.0.1:5173,http://127.0.0.1:5175'
).split(',')

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "accept",
        "accept-encoding",
        "authorization",
        "content-type",
        "dnt",
        "origin",
        "user-agent",
        "x-csrftoken",
        "x-requested-with",
    ],
)

# ============================================================================
# DATABASE SETUP
# ============================================================================

# Database URL from environment
SQLALCHEMY_DATABASE_URL = os.environ.get(
    'DATABASE_URL', 
    "sqlite:///./patientlink.db"
)

# Create engine with connection pooling
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {},
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
models.Base.metadata.create_all(bind=engine)

def ensure_patient_owner_column():
    """
    Lightweight schema upgrade:
    add patients.owner_user_id if missing so old DBs keep working.
    """
    try:
        with engine.begin() as conn:
            if "sqlite" in SQLALCHEMY_DATABASE_URL:
                cols = conn.execute(text("PRAGMA table_info(patients)")).fetchall()
                col_names = {row[1] for row in cols}
                if "owner_user_id" not in col_names:
                    conn.execute(text("ALTER TABLE patients ADD COLUMN owner_user_id VARCHAR"))
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_patients_owner_user_id ON patients(owner_user_id)")
                )
            else:
                cols = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'patients'"
                    )
                ).fetchall()
                col_names = {row[0] for row in cols}
                if "owner_user_id" not in col_names:
                    conn.execute(text("ALTER TABLE patients ADD COLUMN owner_user_id VARCHAR"))
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_patients_owner_user_id "
                        "ON patients(owner_user_id)"
                    )
                )
    except Exception as e:
        logger.warning(f"Schema upgrade check failed (owner_user_id): {e}")

ensure_patient_owner_column()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================================
# SECURITY: JWT TOKEN VERIFICATION
# ============================================================================

security = HTTPBearer(auto_error=False)

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verify JWT token from Authorization header using Django's secret key
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    try:
        import jwt
        from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
        
        # Decode WITH signature verification using Django's secret key
        try:
            payload = jwt.decode(
                token, 
                JWT_SECRET_KEY,
                algorithms=[JWT_ALGORITHM]
            )
            return payload
        except ExpiredSignatureError:
            logger.warning("JWT token has expired")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except InvalidTokenError as e:
            logger.warning(f"JWT validation error: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token verification error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

def require_auth():
    """Dependency that requires authentication"""
    return Depends(verify_token)

def get_authenticated_user_id(token_payload: dict) -> str:
    user_id = token_payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user identity",
        )
    return str(user_id)

# ============================================================================
# INPUT VALIDATION & SANITIZATION
# ============================================================================

def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent XSS attacks"""
    if not text:
        return text
    # Remove potentially dangerous characters
    text = re.sub(r'[<>]', '', text)
    return text.strip()

def validate_phone_number(phone: str) -> str:
    """Validate phone number format"""
    # Remove all non-digit characters except +
    cleaned = re.sub(r'[^\d+]', '', phone)
    # Basic validation - should have at least 10 digits
    if len(re.sub(r'\D', '', cleaned)) < 10:
        raise HTTPException(
            status_code=400,
            detail="Invalid phone number format"
        )
    return cleaned

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
@limiter.limit("50/minute")
async def root(request: Request):
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Patient API",
        "version": "1.0.0"
    }

@app.get("/health")
@limiter.limit("100/minute")
async def health_check(request: Request):
    """Detailed health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "service": "PatientLink Patient API"
    }

@app.post("/patients/", response_model=schemas.Patient)
@limiter.limit("30/minute")
async def create_patient(
    request: Request, 
    patient: schemas.PatientCreate, 
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token)
):
    """Create a new patient with medicines"""
    user_id = get_authenticated_user_id(token_payload)
    
    # Sanitize inputs
    sanitized_name = sanitize_input(patient.name)
    sanitized_whatsapp = validate_phone_number(patient.whatsapp_number)
    
    # Check for duplicate (case-insensitive)
    existing = db.query(models.Patient).filter(
        models.Patient.owner_user_id == user_id,
        models.Patient.name.ilike(sanitized_name)
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Patient with this name already exists"
        )
    
    db_patient = models.Patient(
        owner_user_id=user_id,
        name=sanitized_name,
        whatsapp_number=sanitized_whatsapp,
        dob=patient.dob
    )
    db.add(db_patient)
    db.commit()
    db.refresh(db_patient)

    # Add medicines with validation
    for med in patient.medicines:
        # Sanitize medicine name
        med_name = sanitize_input(med.medicine_name)
        if not med_name:
            continue
            
        db_medicine = models.Medicine(
            patient_id=db_patient.id,
            medicine_name=med_name,
            morning=med.morning,
            evening=med.evening,
            night=med.night,
            duration_days=med.duration_days,
            meal_time=med.meal_time or ""
        )
        db.add(db_medicine)

    db.commit()
    db.refresh(db_patient)
    
    # Fetch the patient with medicines
    db_patient.medicines = db.query(models.Medicine).filter(
        models.Medicine.patient_id == db_patient.id
    ).all()
    
    # Send thank you message via WhatsApp (async)
    try:
        import tasks
        tasks.send_thank_you_message.delay(
            patient_name=db_patient.name,
            phone_number=db_patient.whatsapp_number
        )
        logger.info(f"Thank you message queued for patient {db_patient.id}")
    except Exception as e:
        logger.warning(f"Failed to queue thank you message: {e}")
    
    logger.info(f"Patient created: {db_patient.id}")
    return db_patient

@app.get("/patients/", response_model=List[schemas.Patient])
@limiter.limit("60/minute")
async def get_patients(
    request: Request,
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token)
):
    """Get all patients (paginated)"""
    user_id = get_authenticated_user_id(token_payload)
    # Validate pagination
    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0
        
    patients = db.query(models.Patient).filter(
        models.Patient.owner_user_id == user_id
    ).offset(skip).limit(limit).all()
    for patient in patients:
        patient.medicines = db.query(models.Medicine).filter(
            models.Medicine.patient_id == patient.id
        ).all()
    return patients

@app.get("/patients/{patient_id}", response_model=schemas.Patient)
@limiter.limit("60/minute")
async def get_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token)
):
    """Get a specific patient by ID"""
    user_id = get_authenticated_user_id(token_payload)
    patient = db.query(models.Patient).filter(
        models.Patient.id == patient_id,
        models.Patient.owner_user_id == user_id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    patient.medicines = db.query(models.Medicine).filter(
        models.Medicine.patient_id == patient.id
    ).all()
    return patient

@app.delete("/patients/{patient_id}")
@limiter.limit("20/minute")
async def delete_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token)
):
    """Delete a patient and their medicines"""
    user_id = get_authenticated_user_id(token_payload)
    patient = db.query(models.Patient).filter(
        models.Patient.id == patient_id,
        models.Patient.owner_user_id == user_id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Delete associated medicines first
    db.query(models.Medicine).filter(models.Medicine.patient_id == patient_id).delete()
    
    # Then delete the patient
    patient_name = patient.name
    db.delete(patient)
    db.commit()
    
    logger.info(f"Patient deleted: {patient_id} - {patient_name}")
    return {"message": "Patient deleted successfully"}

@app.put("/patients/{patient_id}", response_model=schemas.Patient)
@limiter.limit("30/minute")
async def update_patient(
    request: Request,
    patient_id: str,
    patient_update: schemas.PatientUpdate, 
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token)
):
    """Update patient information"""
    user_id = get_authenticated_user_id(token_payload)
    patient = db.query(models.Patient).filter(
        models.Patient.id == patient_id,
        models.Patient.owner_user_id == user_id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Update patient fields with sanitization
    if patient_update.name is not None:
        patient.name = sanitize_input(patient_update.name)
    if patient_update.whatsapp_number is not None:
        patient.whatsapp_number = validate_phone_number(patient_update.whatsapp_number)
    if patient_update.dob is not None:
        patient.dob = patient_update.dob
    
    # Update medicines if provided
    if patient_update.medicines is not None:
        # Delete existing medicines
        db.query(models.Medicine).filter(models.Medicine.patient_id == patient_id).delete()
        
        # Add new medicines with validation
        for med in patient_update.medicines:
            med_name = sanitize_input(med.medicine_name)
            if not med_name:
                continue
                
            db_medicine = models.Medicine(
                patient_id=patient.id,
                medicine_name=med_name,
                morning=med.morning,
                evening=med.evening,
                night=med.night,
                duration_days=med.duration_days,
                meal_time=med.meal_time or ""
            )
            db.add(db_medicine)
    
    db.commit()
    db.refresh(patient)
    
    # Fetch the patient with medicines
    patient.medicines = db.query(models.Medicine).filter(
        models.Medicine.patient_id == patient.id
    ).all()
    
    logger.info(f"Patient updated: {patient.id}")
    return patient

@app.get("/patients/export/csv")
@limiter.limit("20/minute")
async def export_patients_csv(
    request: Request,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token)
):
    """Export all patients to CSV format"""
    user_id = get_authenticated_user_id(token_payload)
    import csv
    from io import StringIO
    
    patients = db.query(models.Patient).filter(
        models.Patient.owner_user_id == user_id
    ).all()
    
    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        'ID', 'Name', 'WhatsApp Number', 'Date of Birth',
        'Created At', 'Medicine', 'Morning', 'Evening', 'Night', 'Duration (Days)'
    ])
    
    # Data rows
    for patient in patients:
        medicines = db.query(models.Medicine).filter(
            models.Medicine.patient_id == patient.id
        ).all()
        
        if medicines:
            for med in medicines:
                writer.writerow([
                    patient.id,
                    patient.name,
                    patient.whatsapp_number,
                    patient.dob or '',
                    patient.created_at or '',
                    med.medicine_name,
                    'Yes' if med.morning else 'No',
                    'Yes' if med.evening else 'No',
                    'Yes' if med.night else 'No',
                    med.duration_days
                ])
        else:
            writer.writerow([
                patient.id,
                patient.name,
                patient.whatsapp_number,
                patient.dob or '',
                patient.created_at or '',
                '', '', '', '', ''
            ])
    
    csv_content = output.getvalue()
    output.close()
    
    from fastapi.responses import Response
    
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=patients_export.csv"}
    )

@app.post("/whatsapp/send-reminder/{patient_id}")
@limiter.limit("10/minute")
async def send_whatsapp_reminder(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token)
):
    """Send medicine reminder to a specific patient via WhatsApp"""
    import tasks
    user_id = get_authenticated_user_id(token_payload)
    
    patient = db.query(models.Patient).filter(
        models.Patient.id == patient_id,
        models.Patient.owner_user_id == user_id
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    medicines = db.query(models.Medicine).filter(
        models.Medicine.patient_id == patient_id
    ).all()
    
    if not medicines:
        raise HTTPException(status_code=400, detail="No medicines found for this patient")
    
    # Prepare medicines data
    medicines_data = [
        {
            "medicine_name": med.medicine_name,
            "morning": med.morning,
            "evening": med.evening,
            "night": med.night,
            "duration_days": med.duration_days,
            "meal_time": med.meal_time or "",
        }
        for med in medicines
    ]
    
    # Queue the task
    task = tasks.send_patient_medicine_reminder.delay(
        patient_id=patient.id,
        patient_name=patient.name,
        phone_number=patient.whatsapp_number,
        medicines=medicines_data
    )
    
    logger.info(f"Queued WhatsApp reminder for patient {patient_id}")
    return {
        "success": True,
        "message": "Reminder queued successfully",
        "task_id": task.id
    }

@app.post("/whatsapp/send-all-reminders")
@limiter.limit("5/minute")
async def send_all_whatsapp_reminders(
    request: Request,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token)
):
    """Send medicine reminders to all patients with medicines"""
    import tasks
    user_id = get_authenticated_user_id(token_payload)
    
    patients = db.query(models.Patient).filter(
        models.Patient.owner_user_id == user_id
    ).all()
    
    reminders_data = []
    for patient in patients:
        medicines = db.query(models.Medicine).filter(
            models.Medicine.patient_id == patient.id
        ).all()
        
        if medicines:
            reminders_data.append({
                "patient_id": patient.id,
                "patient_name": patient.name,
                "phone_number": patient.whatsapp_number,
                "medicines": [
                    {
                        "medicine_name": med.medicine_name,
                        "morning": med.morning,
                        "evening": med.evening,
                        "night": med.night,
                        "duration_days": med.duration_days,
                        "meal_time": med.meal_time or "",
                    }
                    for med in medicines
                ]
            })
    
    if not reminders_data:
        raise HTTPException(status_code=400, detail="No patients with medicines found")
    
    # Queue bulk reminders
    result = tasks.send_bulk_reminders.delay(reminders_data)
    
    logger.info(f"Queued {len(reminders_data)} bulk reminders")
    return {
        "success": True,
        "message": f"Queued {len(reminders_data)} reminders",
        "task_id": result.id
    }

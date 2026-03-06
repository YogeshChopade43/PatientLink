"""
PatientLink FastAPI Application
Implements comprehensive security features
"""
import os
import re
import json
import csv
import hmac
import hashlib
from io import StringIO
from pathlib import Path
from datetime import datetime, timedelta, date
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from typing import List, Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
try:
    import sentry_sdk
except Exception:
    sentry_sdk = None
try:
    import redis
except Exception:
    redis = None

import models
import schemas

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s'
)
logger = logging.getLogger(__name__)

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")
if SENTRY_DSN and sentry_sdk:
    sentry_sdk.init(dsn=SENTRY_DSN, traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")))

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

def ensure_schema_upgrades():
    """Best-effort schema upgrades for existing databases without Alembic."""
    try:
        with engine.begin() as conn:
            if "sqlite" in SQLALCHEMY_DATABASE_URL:
                cols = conn.execute(text("PRAGMA table_info(patients)")).fetchall()
                col_names = {row[1] for row in cols}
                for col_name, ddl in [
                    ("owner_user_id", "ALTER TABLE patients ADD COLUMN owner_user_id VARCHAR"),
                    ("updated_at", "ALTER TABLE patients ADD COLUMN updated_at DATETIME"),
                    ("deleted_at", "ALTER TABLE patients ADD COLUMN deleted_at DATETIME"),
                    ("deleted_by_user_id", "ALTER TABLE patients ADD COLUMN deleted_by_user_id VARCHAR"),
                ]:
                    if col_name not in col_names:
                        conn.execute(text(ddl))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_patients_owner_user_id ON patients(owner_user_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_patients_deleted_at ON patients(deleted_at)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_patients_name ON patients(name)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_patients_whatsapp_number ON patients(whatsapp_number)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_medicines_medicine_name ON medicines(medicine_name)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_message_logs_status ON message_logs(status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_message_logs_owner_user_id ON message_logs(owner_user_id)"))
            else:
                cols = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = 'patients'"
                    )
                ).fetchall()
                col_names = {row[0] for row in cols}
                for col_name, ddl in [
                    ("owner_user_id", "ALTER TABLE patients ADD COLUMN owner_user_id VARCHAR"),
                    ("updated_at", "ALTER TABLE patients ADD COLUMN updated_at TIMESTAMP"),
                    ("deleted_at", "ALTER TABLE patients ADD COLUMN deleted_at TIMESTAMP"),
                    ("deleted_by_user_id", "ALTER TABLE patients ADD COLUMN deleted_by_user_id VARCHAR"),
                ]:
                    if col_name not in col_names:
                        conn.execute(text(ddl))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_patients_owner_user_id ON patients(owner_user_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_patients_deleted_at ON patients(deleted_at)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_patients_name ON patients(name)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_patients_whatsapp_number ON patients(whatsapp_number)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_medicines_medicine_name ON medicines(medicine_name)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_message_logs_status ON message_logs(status)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_message_logs_owner_user_id ON message_logs(owner_user_id)"))
    except Exception as e:
        logger.warning(f"Schema upgrade check failed: {e}")

ensure_schema_upgrades()

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


def parse_iso_date(value: Optional[str], field_name: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid {field_name}; expected YYYY-MM-DD")


def log_message_event(
    db: Session,
    owner_user_id: str,
    patient_id: Optional[str],
    phone_number: str,
    message_type: str,
    status_value: str,
    provider_message_id: Optional[str] = None,
    error_reason: Optional[str] = None,
    payload: Optional[dict] = None,
):
    log = models.MessageLog(
        owner_user_id=owner_user_id,
        patient_id=patient_id,
        phone_number=phone_number,
        message_type=message_type,
        status=status_value,
        provider_message_id=provider_message_id or "",
        error_reason=error_reason or "",
        payload_json=json.dumps(payload or {}),
    )
    db.add(log)
    db.commit()


def _verify_whatsapp_signature(request_body: bytes, signature_header: str) -> bool:
    app_secret = os.environ.get("META_APP_SECRET", "")
    if not app_secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    provided = signature_header.split("=", 1)[1].strip()
    computed = hmac.new(
        app_secret.encode("utf-8"),
        msg=request_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(provided, computed)


def background_tasks_enabled() -> bool:
    """
    Toggle for Celery/Redis-backed async processing.
    Keep it enabled in production, but allow local environments without Redis.
    """
    return os.environ.get("ENABLE_BACKGROUND_TASKS", "false").lower() == "true"


def whatsapp_enabled() -> bool:
    """Feature toggle for WhatsApp delivery."""
    return os.environ.get("ENABLE_WHATSAPP", "false").lower() == "true"

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


@app.get("/ops/readiness")
@limiter.limit("60/minute")
async def ops_readiness(request: Request):
    """Operational readiness for production dependencies."""
    db_ok = True
    redis_ok = False
    celery_ok = False

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    if redis and redis_url:
        try:
            redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2).ping()
            redis_ok = True
        except Exception:
            redis_ok = False

    try:
        from celery_app import celery_app as _celery_app  # noqa: F401
        import tasks as _tasks  # noqa: F401
        celery_ok = True
    except Exception:
        celery_ok = False

    whatsapp_feature_enabled = whatsapp_enabled()
    whatsapp_api_configured = bool(
        os.environ.get("META_WHATSAPP_TOKEN") and os.environ.get("META_PHONE_NUMBER_ID")
    )
    webhook_security_configured = bool(
        os.environ.get("META_WEBHOOK_VERIFY_TOKEN") and os.environ.get("META_APP_SECRET")
    )
    backup_dir = os.environ.get("BACKUP_DIR", "./backups")
    backup_dir_writable = True
    try:
        p = Path(backup_dir)
        p.mkdir(parents=True, exist_ok=True)
        test_file = p / ".write_test"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink(missing_ok=True)
    except Exception:
        backup_dir_writable = False

    background_enabled = background_tasks_enabled()

    checks = {
        "database": db_ok,
        "redis": (not background_enabled) or redis_ok,
        "celery_imports": (not background_enabled) or celery_ok,
        "backup_dir_writable": backup_dir_writable,
        "whatsapp_api_configured": (not whatsapp_feature_enabled) or whatsapp_api_configured,
        "whatsapp_webhook_security_configured": (not whatsapp_feature_enabled) or webhook_security_configured,
        "whatsapp_enabled": whatsapp_feature_enabled,
        "background_tasks_enabled": background_enabled,
        "sentry_configured": bool(SENTRY_DSN),
    }
    non_blocking_checks = {"sentry_configured", "background_tasks_enabled", "whatsapp_enabled"}
    is_ready = all(v for k, v in checks.items() if k not in non_blocking_checks)
    http_code = 200 if is_ready else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=http_code,
        content={
            "ready": is_ready,
            "service": "Patient API",
            "checks": checks,
        },
    )

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
    
    # Send thank-you WhatsApp only when the feature is enabled.
    if whatsapp_enabled():
        try:
            import tasks
            if background_tasks_enabled():
                tasks.send_thank_you_message.delay(
                    patient_name=db_patient.name,
                    phone_number=db_patient.whatsapp_number
                )
                status_value = "queued"
            else:
                from whatsapp_service import whatsapp_service
                send_result = whatsapp_service.send_message(
                    phone_number=db_patient.whatsapp_number,
                    message=(
                        "Thank you for visiting.\n\n"
                        f"Dear {db_patient.name},\n\n"
                        "Thank you for registering with PatientLink."
                    ),
                )
                status_value = "sent" if send_result.get("success") else "failed"
            log_message_event(
                db=db,
                owner_user_id=user_id,
                patient_id=db_patient.id,
                phone_number=db_patient.whatsapp_number,
                message_type="thank_you",
                status_value=status_value,
                payload={"patient_name": db_patient.name},
            )
        except Exception as e:
            log_message_event(
                db=db,
                owner_user_id=user_id,
                patient_id=db_patient.id,
                phone_number=db_patient.whatsapp_number,
                message_type="thank_you",
                status_value="failed",
                error_reason=str(e),
                payload={"patient_name": db_patient.name},
            )
            logger.warning(f"Failed to process thank you message: {e}")
    
    logger.info(f"Patient created: {db_patient.id}")
    return db_patient

@app.get("/patients/", response_model=schemas.PatientListResponse)
@limiter.limit("60/minute")
async def get_patients(
    request: Request,
    skip: int = 0, 
    limit: int = 100, 
    search: Optional[str] = None,
    medicine: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    active_only: bool = True,
    include_deleted: bool = False,
    reminder_status: Optional[str] = None,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token)
):
    """Get patients with pagination and filters."""
    user_id = get_authenticated_user_id(token_payload)
    if limit > 100:
        limit = 100
    if skip < 0:
        skip = 0
    filter_date_from = parse_iso_date(date_from, "date_from")
    filter_date_to = parse_iso_date(date_to, "date_to")

    query = db.query(models.Patient).filter(models.Patient.owner_user_id == user_id)
    if not include_deleted:
        query = query.filter(models.Patient.deleted_at.is_(None))
    if search:
        search_value = f"%{search.strip()}%"
        query = query.filter(
            (models.Patient.name.ilike(search_value)) |
            (models.Patient.whatsapp_number.ilike(search_value))
        )
    if filter_date_from:
        query = query.filter(models.Patient.created_at >= datetime.combine(filter_date_from, datetime.min.time()))
    if filter_date_to:
        query = query.filter(models.Patient.created_at <= datetime.combine(filter_date_to, datetime.max.time()))
    if active_only:
        query = query.filter(models.Patient.deleted_at.is_(None))
    if reminder_status:
        matching_patient_ids = db.query(models.MessageLog.patient_id).filter(
            models.MessageLog.owner_user_id == user_id,
            models.MessageLog.status == reminder_status,
            models.MessageLog.patient_id.is_not(None),
        ).distinct()
        query = query.filter(models.Patient.id.in_(matching_patient_ids))

    if medicine:
        matching_ids = db.query(models.Medicine.patient_id).filter(
            models.Medicine.medicine_name.ilike(f"%{medicine.strip()}%")
        ).distinct()
        query = query.filter(models.Patient.id.in_(matching_ids))

    total = query.count()
    patients = query.order_by(models.Patient.created_at.desc()).offset(skip).limit(limit).all()
    for patient in patients:
        patient.medicines = db.query(models.Medicine).filter(
            models.Medicine.patient_id == patient.id
        ).all()
    return {"items": patients, "total": total, "skip": skip, "limit": limit}

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
        models.Patient.owner_user_id == user_id,
        models.Patient.deleted_at.is_(None),
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
    """Soft-delete a patient."""
    user_id = get_authenticated_user_id(token_payload)
    patient = db.query(models.Patient).filter(
        models.Patient.id == patient_id,
        models.Patient.owner_user_id == user_id,
        models.Patient.deleted_at.is_(None),
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    patient.deleted_at = datetime.utcnow()
    patient.deleted_by_user_id = user_id
    db.commit()
    
    logger.info(f"Patient soft-deleted: {patient_id} - {patient.name}")
    return {"message": "Patient deleted successfully", "soft_deleted": True}


@app.post("/patients/{patient_id}/restore", response_model=schemas.Patient)
@limiter.limit("20/minute")
async def restore_patient(
    request: Request,
    patient_id: str,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(token_payload)
    patient = db.query(models.Patient).filter(
        models.Patient.id == patient_id,
        models.Patient.owner_user_id == user_id,
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient.deleted_at = None
    patient.deleted_by_user_id = None
    db.commit()
    db.refresh(patient)
    patient.medicines = db.query(models.Medicine).filter(
        models.Medicine.patient_id == patient.id
    ).all()
    return patient

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
        models.Patient.owner_user_id == user_id,
        models.Patient.deleted_at.is_(None),
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
    
    patients = db.query(models.Patient).filter(
        models.Patient.owner_user_id == user_id,
        models.Patient.deleted_at.is_(None),
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
    from whatsapp_service import whatsapp_service
    if not whatsapp_enabled():
        return {"success": True, "message": "WhatsApp delivery is disabled.", "task_id": "disabled"}
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
    
    if background_tasks_enabled():
        try:
            task = tasks.send_patient_medicine_reminder.delay(
                patient_id=patient.id,
                owner_user_id=user_id,
                patient_name=patient.name,
                phone_number=patient.whatsapp_number,
                medicines=medicines_data
            )
            task_id = task.id
        except Exception as exc:
            log_message_event(
                db=db,
                owner_user_id=user_id,
                patient_id=patient.id,
                phone_number=patient.whatsapp_number,
                message_type="reminder_single",
                status_value="failed",
                error_reason=str(exc),
                payload={"medicines": medicines_data},
            )
            raise HTTPException(
                status_code=503,
                detail="Reminder queue is unavailable. Please ensure Redis/Celery are running.",
            )
        response_message = "Reminder queued successfully"
    else:
        direct_result = whatsapp_service.send_medicine_reminder(
            patient_name=patient.name,
            phone_number=patient.whatsapp_number,
            medicines=medicines_data,
        )
        if not direct_result.get("success"):
            log_message_event(
                db=db,
                owner_user_id=user_id,
                patient_id=patient.id,
                phone_number=patient.whatsapp_number,
                message_type="reminder_single",
                status_value="failed",
                error_reason=direct_result.get("error", "WhatsApp send failed"),
                payload={"medicines": medicines_data},
            )
            raise HTTPException(status_code=502, detail=direct_result.get("error", "Failed to send WhatsApp reminder"))
        task_id = f"direct-{patient.id}"
        response_message = "Reminder sent successfully"
    log_message_event(
        db=db,
        owner_user_id=user_id,
        patient_id=patient.id,
        phone_number=patient.whatsapp_number,
        message_type="reminder_single",
        status_value="queued" if background_tasks_enabled() else "sent",
        payload={"medicines": medicines_data, "task_id": task_id},
    )
    
    logger.info(f"Queued WhatsApp reminder for patient {patient_id}")
    return {
        "success": True,
        "message": response_message,
        "task_id": task_id
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
    from whatsapp_service import whatsapp_service
    if not whatsapp_enabled():
        return {"success": True, "message": "WhatsApp delivery is disabled.", "task_id": "disabled"}
    user_id = get_authenticated_user_id(token_payload)
    
    patients = db.query(models.Patient).filter(
        models.Patient.owner_user_id == user_id,
        models.Patient.deleted_at.is_(None),
    ).all()
    
    reminders_data = []
    for patient in patients:
        medicines = db.query(models.Medicine).filter(
            models.Medicine.patient_id == patient.id
        ).all()
        
        if medicines:
            reminders_data.append({
                "patient_id": patient.id,
                "owner_user_id": user_id,
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
    
    if background_tasks_enabled():
        try:
            result = tasks.send_bulk_reminders.delay(reminders_data)
            task_id = result.id
        except Exception as exc:
            for item in reminders_data:
                log_message_event(
                    db=db,
                    owner_user_id=user_id,
                    patient_id=item["patient_id"],
                    phone_number=item["phone_number"],
                    message_type="reminder_bulk",
                    status_value="failed",
                    error_reason=str(exc),
                    payload={"medicines": item["medicines"]},
                )
            raise HTTPException(
                status_code=503,
                detail="Reminder queue is unavailable. Please ensure Redis/Celery are running.",
            )
        response_message = f"Queued {len(reminders_data)} reminders"
    else:
        for item in reminders_data:
            send_result = whatsapp_service.send_medicine_reminder(
                patient_name=item["patient_name"],
                phone_number=item["phone_number"],
                medicines=item["medicines"],
            )
            if not send_result.get("success"):
                log_message_event(
                    db=db,
                    owner_user_id=user_id,
                    patient_id=item["patient_id"],
                    phone_number=item["phone_number"],
                    message_type="reminder_bulk",
                    status_value="failed",
                    error_reason=send_result.get("error", "WhatsApp send failed"),
                    payload={"medicines": item["medicines"]},
                )
                continue
            log_message_event(
                db=db,
                owner_user_id=user_id,
                patient_id=item["patient_id"],
                phone_number=item["phone_number"],
                message_type="reminder_bulk",
                status_value="sent",
                provider_message_id=send_result.get("message_id", ""),
                payload={"medicines": item["medicines"]},
            )
        task_id = "direct-bulk"
        response_message = f"Sent {len(reminders_data)} reminders directly"
    for item in reminders_data:
        log_message_event(
            db=db,
            owner_user_id=user_id,
            patient_id=item["patient_id"],
            phone_number=item["phone_number"],
            message_type="reminder_bulk",
            status_value="queued",
            payload={"medicines": item["medicines"], "task_id": task_id},
        )
    
    logger.info(f"Queued {len(reminders_data)} bulk reminders")
    return {
        "success": True,
        "message": response_message,
        "task_id": task_id
    }


@app.get("/whatsapp/logs", response_model=List[schemas.MessageLog])
@limiter.limit("30/minute")
async def get_whatsapp_logs(
    request: Request,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(token_payload)
    query = db.query(models.MessageLog).filter(models.MessageLog.owner_user_id == user_id)
    if status_filter:
        query = query.filter(models.MessageLog.status == status_filter)
    return query.order_by(models.MessageLog.created_at.desc()).limit(200).all()


@app.get("/whatsapp/retry-queue", response_model=List[schemas.MessageLog])
@limiter.limit("30/minute")
async def get_retry_queue(
    request: Request,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(token_payload)
    return db.query(models.MessageLog).filter(
        models.MessageLog.owner_user_id == user_id,
        models.MessageLog.status == "failed",
    ).order_by(models.MessageLog.updated_at.desc()).limit(200).all()


@app.post("/whatsapp/status/webhook")
@limiter.limit("120/minute")
async def sync_whatsapp_status(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    """
    Sync status updates from provider/webhook payloads.
    Expected fields: provider_message_id, status, error_reason(optional)
    """
    user_id = get_authenticated_user_id(token_payload)
    provider_message_id = payload.get("provider_message_id")
    new_status = payload.get("status")
    error_reason = payload.get("error_reason", "")
    if not provider_message_id or not new_status:
        raise HTTPException(status_code=400, detail="provider_message_id and status are required")

    log_row = db.query(models.MessageLog).filter(
        models.MessageLog.owner_user_id == user_id,
        models.MessageLog.provider_message_id == provider_message_id,
    ).first()
    if not log_row:
        raise HTTPException(status_code=404, detail="Message log not found")

    log_row.status = new_status
    log_row.error_reason = error_reason
    log_row.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True}


@app.get("/whatsapp/webhook")
@limiter.limit("120/minute")
async def verify_whatsapp_webhook(
    request: Request,
    hub_mode: Optional[str] = None,
    hub_verify_token: Optional[str] = None,
    hub_challenge: Optional[str] = None,
):
    """
    Meta webhook verification endpoint.
    Query params usually arrive as hub.mode / hub.verify_token / hub.challenge.
    """
    query_params = dict(request.query_params)
    mode = hub_mode or query_params.get("hub.mode")
    verify_token = hub_verify_token or query_params.get("hub.verify_token")
    challenge = hub_challenge or query_params.get("hub.challenge")
    expected_token = os.environ.get("META_WEBHOOK_VERIFY_TOKEN", "")

    if mode == "subscribe" and expected_token and verify_token == expected_token and challenge:
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(challenge, status_code=200)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@app.post("/whatsapp/webhook")
@limiter.limit("300/minute")
async def receive_whatsapp_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Receives delivery/read/failure events from Meta webhook.
    Verifies X-Hub-Signature-256 using META_APP_SECRET.
    """
    signature = request.headers.get("X-Hub-Signature-256", "")
    raw_body = await request.body()
    if not _verify_whatsapp_signature(raw_body, signature):
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Best-effort parser for Meta status events
    entries = payload.get("entry", [])
    updates = 0
    for entry in entries:
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for status_obj in value.get("statuses", []):
                provider_message_id = status_obj.get("id", "")
                status_value = status_obj.get("status", "")
                error_reason = ""
                errors = status_obj.get("errors", [])
                if errors and isinstance(errors, list):
                    error_reason = errors[0].get("title") or errors[0].get("message") or ""
                if not provider_message_id or not status_value:
                    continue
                log_row = db.query(models.MessageLog).filter(
                    models.MessageLog.provider_message_id == provider_message_id
                ).order_by(models.MessageLog.created_at.desc()).first()
                if log_row:
                    log_row.status = status_value
                    log_row.error_reason = error_reason
                    log_row.updated_at = datetime.utcnow()
                    updates += 1
    db.commit()
    return {"success": True, "updates": updates}


@app.get("/reports/summary", response_model=schemas.ReportSummary)
@limiter.limit("20/minute")
async def reports_summary(
    request: Request,
    period: str = "daily",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(token_payload)
    today = datetime.utcnow().date()
    if period == "weekly":
        start_date = today - timedelta(days=6)
        end_date = today
    else:
        start_date = today
        end_date = today

    parsed_from = parse_iso_date(from_date, "from_date")
    parsed_to = parse_iso_date(to_date, "to_date")
    if parsed_from:
        start_date = parsed_from
    if parsed_to:
        end_date = parsed_to

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    patients = db.query(models.Patient).filter(
        models.Patient.owner_user_id == user_id,
        models.Patient.created_at >= start_dt,
        models.Patient.created_at <= end_dt,
    )
    total_patients = patients.count()
    active_patients = patients.filter(models.Patient.deleted_at.is_(None)).count()

    patient_ids = [
        pid for (pid,) in db.query(models.Patient.id).filter(
            models.Patient.owner_user_id == user_id,
            models.Patient.created_at >= start_dt,
            models.Patient.created_at <= end_dt,
        ).all()
    ]
    total_medicines = 0
    active_medicine_courses = 0
    if patient_ids:
        total_medicines = db.query(models.Medicine).filter(models.Medicine.patient_id.in_(patient_ids)).count()
        now = datetime.utcnow()
        all_meds = db.query(models.Medicine).filter(models.Medicine.patient_id.in_(patient_ids)).all()
        active_medicine_courses = sum(
            1 for med in all_meds
            if med.start_date and med.duration_days and (med.start_date + timedelta(days=med.duration_days)) >= now
        )

    sent_count = db.query(models.MessageLog).filter(
        models.MessageLog.owner_user_id == user_id,
        models.MessageLog.status.in_(["sent", "delivered", "read", "queued"]),
        models.MessageLog.created_at >= start_dt,
        models.MessageLog.created_at <= end_dt,
    ).count()
    failed_count = db.query(models.MessageLog).filter(
        models.MessageLog.owner_user_id == user_id,
        models.MessageLog.status == "failed",
        models.MessageLog.created_at >= start_dt,
        models.MessageLog.created_at <= end_dt,
    ).count()
    total_dose_events = db.query(models.DoseLog).filter(
        models.DoseLog.owner_user_id == user_id,
        models.DoseLog.created_at >= start_dt,
        models.DoseLog.created_at <= end_dt,
    ).count()
    taken_events = db.query(models.DoseLog).filter(
        models.DoseLog.owner_user_id == user_id,
        models.DoseLog.status == "taken",
        models.DoseLog.created_at >= start_dt,
        models.DoseLog.created_at <= end_dt,
    ).count()
    adherence_rate = (taken_events / total_dose_events * 100.0) if total_dose_events > 0 else 0.0

    return {
        "period": period,
        "from_date": str(start_date),
        "to_date": str(end_date),
        "total_patients": total_patients,
        "active_patients": active_patients,
        "total_medicines": total_medicines,
        "active_medicine_courses": active_medicine_courses,
        "message_sent": sent_count,
        "message_failed": failed_count,
        "adherence_rate": round(adherence_rate, 2),
    }


@app.get("/reports/export/csv")
@limiter.limit("10/minute")
async def export_reports_csv(
    request: Request,
    period: str = "daily",
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    summary = await reports_summary(
        request=request,
        period=period,
        db=db,
        token_payload=token_payload,
    )
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Metric", "Value"])
    for k, v in summary.items():
        writer.writerow([k, v])
    content = output.getvalue()
    output.close()
    from fastapi.responses import Response
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=report_{period}.csv"},
    )


@app.get("/backup/export")
@limiter.limit("5/minute")
async def export_backup(
    request: Request,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(token_payload)
    patients = db.query(models.Patient).filter(models.Patient.owner_user_id == user_id).all()
    backup = []
    for patient in patients:
        meds = db.query(models.Medicine).filter(models.Medicine.patient_id == patient.id).all()
        backup.append({
            "patient": {
                "id": patient.id,
                "name": patient.name,
                "whatsapp_number": patient.whatsapp_number,
                "dob": patient.dob,
                "created_at": patient.created_at.isoformat() if patient.created_at else None,
                "deleted_at": patient.deleted_at.isoformat() if patient.deleted_at else None,
            },
            "medicines": [
                {
                    "medicine_name": m.medicine_name,
                    "morning": m.morning,
                    "evening": m.evening,
                    "night": m.night,
                    "duration_days": m.duration_days,
                    "meal_time": m.meal_time,
                }
                for m in meds
            ],
        })
    return {"exported_at": datetime.utcnow().isoformat(), "records": backup}


@app.post("/backup/restore")
@limiter.limit("3/minute")
async def restore_backup(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(token_payload)
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise HTTPException(status_code=400, detail="records must be a list")

    restored = 0
    for item in records:
        patient_obj = item.get("patient", {})
        name = sanitize_input(patient_obj.get("name", ""))
        phone = validate_phone_number(patient_obj.get("whatsapp_number", ""))
        if not name or not phone:
            continue
        db_patient = models.Patient(
            owner_user_id=user_id,
            name=name,
            whatsapp_number=phone,
            dob=patient_obj.get("dob", ""),
            deleted_at=None,
            deleted_by_user_id=None,
        )
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)

        for med in item.get("medicines", []):
            med_name = sanitize_input(med.get("medicine_name", ""))
            if not med_name:
                continue
            db.add(models.Medicine(
                patient_id=db_patient.id,
                medicine_name=med_name,
                morning=bool(med.get("morning")),
                evening=bool(med.get("evening")),
                night=bool(med.get("night")),
                duration_days=int(med.get("duration_days", 7)),
                meal_time=med.get("meal_time", ""),
            ))
        db.commit()
        restored += 1
    return {"restored": restored}


@app.get("/backup/list")
@limiter.limit("10/minute")
async def list_backups(
    request: Request,
    token_payload: dict = Depends(verify_token),
):
    _ = get_authenticated_user_id(token_payload)
    backup_dir = Path(os.environ.get("BACKUP_DIR", "./backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(
        [f.name for f in backup_dir.glob("backup_*.json")],
        reverse=True,
    )
    return {"files": files[:200]}


@app.post("/backup/restore-file")
@limiter.limit("3/minute")
async def restore_backup_from_file(
    request: Request,
    payload: dict,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    _ = get_authenticated_user_id(token_payload)
    filename = payload.get("filename", "")
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    backup_dir = Path(os.environ.get("BACKUP_DIR", "./backups"))
    file_path = backup_dir / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")
    try:
        backup_payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Backup file is invalid")
    return await restore_backup(
        request=request,
        payload=backup_payload,
        db=db,
        token_payload=token_payload,
    )


@app.post("/patients/{patient_id}/dose-events", response_model=schemas.DoseLog)
@limiter.limit("120/minute")
async def create_dose_event(
    request: Request,
    patient_id: str,
    payload: schemas.DoseLogCreate,
    db: Session = Depends(get_db),
    token_payload: dict = Depends(verify_token),
):
    user_id = get_authenticated_user_id(token_payload)
    patient = db.query(models.Patient).filter(
        models.Patient.id == patient_id,
        models.Patient.owner_user_id == user_id,
        models.Patient.deleted_at.is_(None),
    ).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    medicine = db.query(models.Medicine).filter(
        models.Medicine.id == payload.medicine_id,
        models.Medicine.patient_id == patient_id,
    ).first()
    if not medicine:
        raise HTTPException(status_code=404, detail="Medicine not found")
    if payload.slot not in {"morning", "evening", "night"}:
        raise HTTPException(status_code=400, detail="slot must be morning/evening/night")
    if payload.status not in {"taken", "missed"}:
        raise HTTPException(status_code=400, detail="status must be taken/missed")

    dose = models.DoseLog(
        owner_user_id=user_id,
        patient_id=patient_id,
        medicine_id=payload.medicine_id,
        slot=payload.slot,
        status=payload.status,
        taken_at=datetime.utcnow() if payload.status == "taken" else None,
        note=sanitize_input(payload.note or ""),
    )
    db.add(dose)
    db.commit()
    db.refresh(dose)
    return dose

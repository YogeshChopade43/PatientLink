from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class MedicineBase(BaseModel):
    medicine_name: str
    morning: bool = False
    evening: bool = False
    night: bool = False
    duration_days: int
    meal_time: str = ""  # "before_meal", "after_meal", or ""

class MedicineCreate(MedicineBase):
    pass

class Medicine(MedicineBase):
    id: str
    patient_id: str

    class Config:
        from_attributes = True

class PatientBase(BaseModel):
    name: str
    whatsapp_number: str
    dob: str  # Date string in YYYY-MM-DD format

class PatientCreate(PatientBase):
    medicines: List[MedicineCreate] = []

class PatientUpdate(BaseModel):
    name: Optional[str] = None
    whatsapp_number: Optional[str] = None
    dob: Optional[str] = None
    medicines: Optional[List[MedicineCreate]] = None

class Patient(PatientBase):
    id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None
    medicines: List[Medicine] = []

    class Config:
        from_attributes = True


class MessageLog(BaseModel):
    id: str
    owner_user_id: str
    patient_id: Optional[str] = None
    phone_number: str
    message_type: str
    status: str
    direction: str
    provider_message_id: Optional[str] = None
    error_reason: Optional[str] = None
    retry_count: int = 0
    payload_json: str = ""
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PatientListResponse(BaseModel):
    items: List[Patient]
    total: int
    skip: int
    limit: int


class ReportSummary(BaseModel):
    period: str
    from_date: str
    to_date: str
    total_patients: int
    active_patients: int
    total_medicines: int
    active_medicine_courses: int
    message_sent: int
    message_failed: int
    adherence_rate: float


class DoseLogCreate(BaseModel):
    medicine_id: str
    slot: str
    status: str  # taken/missed
    note: str = ""


class DoseLog(BaseModel):
    id: str
    owner_user_id: str
    patient_id: str
    medicine_id: str
    slot: str
    status: str
    taken_at: Optional[datetime] = None
    note: str = ""
    created_at: datetime

    class Config:
        from_attributes = True

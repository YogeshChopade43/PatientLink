from pydantic import BaseModel
from typing import List, Optional
from datetime import date, datetime

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
    medicines: List[Medicine] = []

    class Config:
        from_attributes = True

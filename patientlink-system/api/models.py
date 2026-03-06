from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    owner_user_id = Column(String, index=True)
    name = Column(String, index=True)
    whatsapp_number = Column(String, index=True)
    dob = Column(String)  # Store as string in YYYY-MM-DD format
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to medicines
    medicines = relationship("Medicine", back_populates="patient")


class Medicine(Base):
    __tablename__ = "medicines"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    patient_id = Column(String, ForeignKey("patients.id"))
    medicine_name = Column(String, index=True)
    morning = Column(Boolean, default=False)
    evening = Column(Boolean, default=False)
    night = Column(Boolean, default=False)
    duration_days = Column(Integer)
    start_date = Column(DateTime, default=datetime.utcnow)  # When medicine course started
    meal_time = Column(String, default="")  # "before_meal", "after_meal", or ""

    # Relationship to patient
    patient = relationship("Patient", back_populates="medicines")

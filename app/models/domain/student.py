from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
from datetime import datetime

class StudentBase(BaseModel):
    student_id: str
    full_name: str
    gender: str
    class_name: str
    email: EmailStr
    registered_subjects: List[str] = []

class StudentCreate(StudentBase):
    pass

class StudentInDB(StudentBase):
    id: str = Field(default_factory=str)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Student(StudentBase):
    id: str
    created_at: datetime
    updated_at: datetime

class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    gender: Optional[str] = None
    class_name: Optional[str] = None
    email: Optional[EmailStr] = None
    registered_subjects: Optional[List[str]] = None

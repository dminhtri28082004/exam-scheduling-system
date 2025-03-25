from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SubjectBase(BaseModel):
    code: str
    name: str
    duration: int  # Duration in minutes
    registered_students: List[str] = []
    department: Optional[str] = None
    credits: Optional[int] = None

class SubjectCreate(SubjectBase):
    pass

class SubjectInDB(SubjectBase):
    id: str = Field(default_factory=str)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Subject(SubjectBase):
    id: str
    created_at: datetime
    updated_at: datetime

class SubjectUpdate(BaseModel):
    name: Optional[str] = None
    code: Optional[str] = None
    duration: Optional[int] = None
    registered_students: Optional[List[str]] = None
    credits: Optional[int] = None
    department: Optional[str] = None

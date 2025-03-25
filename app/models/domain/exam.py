from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

class ExamBase(BaseModel):
    subject_id: str
    room_id: str
    start_time: datetime
    end_time: datetime
    supervisor_ids: List[str] = []
    max_students: int
    student_ids: List[str] = []

class ExamCreate(ExamBase):
    pass

class ExamInDB(ExamBase):
    id: str = Field(default_factory=str)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Exam(ExamBase):
    id: str
    created_at: datetime
    updated_at: datetime

class ExamUpdate(BaseModel):
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    supervisor_ids: Optional[List[str]] = None
    max_students: Optional[int] = None
    student_ids: Optional[List[str]] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)

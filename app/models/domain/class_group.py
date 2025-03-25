from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class ClassGroupBase(BaseModel):
    class_id: str  # Mã lớp (ví dụ: CNTT1, HTTT2)
    name: str      # Tên lớp đầy đủ
    department: Optional[str] = None  # Khoa/bộ môn
    year: Optional[int] = None  # Năm bắt đầu khóa học
    
class ClassGroupCreate(ClassGroupBase):
    pass

class ClassGroupInDB(ClassGroupBase):
    id: str = Field(default_factory=str)
    student_count: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ClassGroup(ClassGroupBase):
    id: str
    student_count: int
    created_at: datetime
    updated_at: datetime

class ClassGroupUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None
    year: Optional[int] = None
    student_count: Optional[int] = None

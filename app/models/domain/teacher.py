from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List
from datetime import datetime

class TeacherBase(BaseModel):
    teacher_id: str   # Mã giảng viên (e.g., GV001)
    full_name: str    # Họ và tên giảng viên
    email: Optional[EmailStr] = None  # Email giảng viên
    department: Optional[str] = None  # Khoa/bộ môn
    
class TeacherCreate(TeacherBase):
    pass

class TeacherInDB(TeacherBase):
    id: str = Field(default_factory=str)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Teacher(TeacherBase):
    id: str
    exam_count: Optional[int] = 0  # Số kỳ thi được phân công
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True

class TeacherUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    department: Optional[str] = None

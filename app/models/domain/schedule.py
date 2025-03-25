from pydantic import BaseModel, Field, validator
from typing import Optional, List
from datetime import datetime, time

class ScheduleConfigBase(BaseModel):
    exam_period_name: str  # Add this field for the exam period name
    start_date: datetime
    end_date: datetime
    first_exam_time: time
    last_exam_time: time
    supervisors_per_room: int = Field(default=2, ge=1, le=3)
    
    @validator('end_date')
    def end_date_must_be_after_start_date(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    class Config:
        json_encoders = {
            time: lambda t: t.strftime('%H:%M:%S')
        }
        
class ScheduleConfigCreate(ScheduleConfigBase):
    pass
    
class ScheduleConfigInDB(ScheduleConfigBase):
    id: str = Field(default_factory=str)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str  # ID người dùng tạo lịch
    
class ScheduleConfig(ScheduleConfigBase):
    id: str
    created_at: datetime
    updated_at: datetime
    created_by: str

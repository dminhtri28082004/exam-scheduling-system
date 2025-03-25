from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class RoomInfo(BaseModel):
    room_id: str
    name: str
    building: Optional[str] = None
    capacity: int
    num_students: int

class SubjectInfo(BaseModel):
    id: str
    code: str
    name: str
    duration: Optional[int] = None

class ExamResponse(BaseModel):
    exam_id: str
    subject: SubjectInfo
    start_time: datetime
    end_time: datetime
    duration_minutes: Optional[int] = None
    total_students: int
    rooms: List[RoomInfo]

class ExamDetailsResponse(BaseModel):
    exam_id: str
    subject: SubjectInfo
    start_time: datetime
    end_time: datetime
    duration_minutes: Optional[int] = None
    rooms: List[RoomInfo]
    supervisors: List[Dict[str, Any]]
    total_students: int
    your_room: Optional[Dict[str, Any]] = None

class StudentDashboardResponse(BaseModel):
    student: Dict[str, Any]
    subjects_count: int
    upcoming_subjects_count: int
    next_exam: Optional[Dict[str, Any]] = None
    registered_subjects: List[Dict[str, Any]]

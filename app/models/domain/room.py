from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class RoomBase(BaseModel):
    room_id: str
    capacity: int
    building: Optional[str] = None
    name: Optional[str] = None
    has_computers: Optional[bool] = False

class RoomCreate(RoomBase):
    pass

class RoomInDB(RoomBase):
    id: str = Field(default_factory=str)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class Room(RoomBase):
    id: str
    created_at: datetime
    updated_at: datetime

class RoomUpdate(BaseModel):
    capacity: Optional[int] = None
    building: Optional[str] = None
    name: Optional[str] = None
    has_computers: Optional[bool] = None

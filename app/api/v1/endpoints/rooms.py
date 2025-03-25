from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any
from bson.objectid import ObjectId
from datetime import datetime

from app.db.database import get_database
from app.models.domain.room import Room, RoomCreate, RoomInDB, RoomUpdate
from app.models.domain.user import User
from app.core.auth import get_current_active_user, check_admin_permission

router = APIRouter()

@router.post("/", response_model=Room, status_code=status.HTTP_201_CREATED)
async def create_room(
    room_in: RoomCreate,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Create new room (admin only)"""
    existing = await db.rooms.find_one({"room_id": room_in.room_id})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A room with ID {room_in.room_id} already exists"
        )
    
    room_data = RoomInDB(
        **room_in.dict(),
        id=str(ObjectId())
    )
    
    await db.rooms.insert_one(room_data.dict(by_alias=True))
    return room_data

@router.get("/", response_model=List[Room])
async def read_rooms(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Retrieve rooms"""
    rooms_cursor = db.rooms.find().skip(skip).limit(limit)
    rooms = await rooms_cursor.to_list(length=limit)
    
    # Ánh xạ _id sang id
    for room in rooms:
        room["id"] = room["_id"]
    
    return rooms

@router.get("/{room_id}", response_model=Room)
async def read_room(
    room_id: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Get room by ID"""
    room = await db.rooms.find_one({"_id": room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Ánh xạ _id sang id
    room["id"] = room["_id"]
    return room

@router.put("/{room_id}", response_model=Room)
async def update_room(
    room_id: str,
    room_in: RoomUpdate,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Update a room (admin only)"""
    # First try to find the room using the string ID directly
    room = await db.rooms.find_one({"_id": room_id})
    
    # If not found, try to convert to ObjectId and search again
    if not room:
        try:
            obj_id = ObjectId(room_id)
            room = await db.rooms.find_one({"_id": obj_id})
        except:
            # If conversion fails or room still not found, raise 404
            raise HTTPException(status_code=404, detail="Room not found")
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Get the actual ID from the found room document
    actual_id = room["_id"]
    
    update_data = room_in.dict(exclude_unset=True)
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.rooms.update_one(
            {"_id": actual_id}, {"$set": update_data}
        )
    
    updated_room = await db.rooms.find_one({"_id": actual_id})
    
    # Convert ObjectId to string for the response
    if isinstance(updated_room["_id"], ObjectId):
        updated_room["id"] = str(updated_room["_id"])
    else:
        updated_room["id"] = updated_room["_id"]
    
    return updated_room

@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    room_id: str,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> None:
    """Delete a room (admin only)"""
    # First try to find the room using the string ID directly
    room = await db.rooms.find_one({"_id": room_id})
    
    # If not found, try to convert to ObjectId and search again
    if not room:
        try:
            obj_id = ObjectId(room_id)
            room = await db.rooms.find_one({"_id": obj_id})
        except:
            # If conversion fails or room still not found, raise 404
            raise HTTPException(status_code=404, detail="Room not found")
    
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Get the actual ID from the found room document
    actual_id = room["_id"]
    
    # Check if room is being used in any exams
    exam_count = await db.exams.count_documents({"room_id": actual_id})
    if exam_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete room used in {exam_count} exams. Please remove from exams first."
        )
    
    # Use the actual ID for deletion
    await db.rooms.delete_one({"_id": actual_id})

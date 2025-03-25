from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any, Dict, Optional
from bson.objectid import ObjectId
from datetime import datetime

from app.db.database import get_database
from app.models.domain.teacher import Teacher, TeacherCreate, TeacherInDB, TeacherUpdate
from app.models.domain.user import User
from app.core.auth import get_current_active_user, check_admin_permission
from app.utils.mongo import prepare_mongodb_docs, prepare_mongodb_doc

router = APIRouter()

@router.post("/", response_model=Teacher, status_code=status.HTTP_201_CREATED)
async def create_teacher(
    teacher_in: TeacherCreate,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Create new teacher (admin only)"""
    existing = await db.teachers.find_one({"teacher_id": teacher_in.teacher_id})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A teacher with ID {teacher_in.teacher_id} already exists"
        )
    
    teacher_data = TeacherInDB(
        **teacher_in.dict(),
        id=str(ObjectId()),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    await db.teachers.insert_one(teacher_data.dict(by_alias=True))
    return teacher_data

@router.get("/", response_model=List[Teacher])
async def read_teachers(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Retrieve teachers"""
    teachers_cursor = db.teachers.find().skip(skip).limit(limit)
    teachers = await prepare_mongodb_docs(teachers_cursor)
    
    # Count exams assigned to each teacher
    for teacher in teachers:
        teacher["exam_count"] = await db.exams.count_documents({"supervisor_ids": teacher["_id"]})
    
    return teachers

@router.get("/{teacher_id}", response_model=Teacher)
async def read_teacher(
    teacher_id: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Get teacher by ID"""
    teacher = await db.teachers.find_one({"_id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    teacher = prepare_mongodb_doc(teacher)
    
    # Count exams assigned to this teacher
    teacher["exam_count"] = await db.exams.count_documents({"supervisor_ids": teacher_id})
    
    return teacher

@router.put("/{teacher_id}", response_model=Teacher)
async def update_teacher(
    teacher_id: str,
    teacher_in: TeacherUpdate,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Update a teacher (admin only)"""
    # First try to find the teacher using the string ID directly
    teacher = await db.teachers.find_one({"_id": teacher_id})
    
    # If not found, try to convert to ObjectId and search again
    if not teacher:
        try:
            obj_id = ObjectId(teacher_id)
            teacher = await db.teachers.find_one({"_id": obj_id})
        except:
            # If conversion fails or teacher still not found, raise 404
            raise HTTPException(status_code=404, detail="Teacher not found")
    
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    # Get the actual ID from the found teacher document
    actual_id = teacher["_id"]
    
    update_data = teacher_in.dict(exclude_unset=True)
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.teachers.update_one(
            {"_id": actual_id}, {"$set": update_data}
        )
    
    updated_teacher = await db.teachers.find_one({"_id": actual_id})
    
    # Properly convert ID to string for response
    updated_teacher = prepare_mongodb_doc(updated_teacher)
    
    # Count exams assigned to this teacher
    updated_teacher["exam_count"] = await db.exams.count_documents({"supervisor_ids": teacher_id})
    
    return updated_teacher

@router.delete("/{teacher_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_teacher(
    teacher_id: str,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> None:
    """Delete a teacher (admin only)"""
    teacher = await db.teachers.find_one({"_id": teacher_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")
    
    # Check if teacher is assigned to any exams
    exam_count = await db.exams.count_documents({"supervisor_ids": teacher_id})
    if exam_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete teacher assigned to {exam_count} exams. Please remove from exams first."
        )
    
    await db.teachers.delete_one({"_id": teacher_id})

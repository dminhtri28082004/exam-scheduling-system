from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any
from bson.objectid import ObjectId
from datetime import datetime

from app.db.database import get_database
from app.models.domain.subject import Subject, SubjectCreate, SubjectInDB, SubjectUpdate
from app.models.domain.user import User
from app.core.auth import get_current_active_user, check_teacher_permission, check_admin_permission

router = APIRouter()

@router.post("/", response_model=Subject, status_code=status.HTTP_201_CREATED)
async def create_subject(
    subject_in: SubjectCreate,
    current_user: User = Depends(check_teacher_permission),
    db = Depends(get_database)
) -> Any:
    """Create new subject (teacher or admin only)"""
    existing = await db.subjects.find_one({"code": subject_in.code})
    if existing:
        raise HTTPException(
            status_code=400,
            detail="A subject with this code already exists"
        )
    
    subject_data = SubjectInDB(
        **subject_in.dict(),
        id=str(ObjectId())
    )
    
    await db.subjects.insert_one(subject_data.dict(by_alias=True))
    return subject_data

@router.get("/", response_model=List[Subject])
async def read_subjects(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Retrieve subjects"""
    subjects_cursor = db.subjects.find().skip(skip).limit(limit)
    subjects = await subjects_cursor.to_list(length=limit)
    
    # Ánh xạ _id sang id
    for subject in subjects:
        subject["id"] = subject["_id"]
    
    return subjects

@router.get("/{subject_id}", response_model=Subject)
async def read_subject(
    subject_id: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Get subject by ID"""
    subject = await db.subjects.find_one({"_id": subject_id})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Ánh xạ _id sang id
    subject["id"] = subject["_id"]
    return subject

@router.put("/{subject_id}", response_model=Subject)
async def update_subject(
    subject_id: str,
    subject_in: SubjectUpdate,
    current_user: User = Depends(check_teacher_permission),
    db = Depends(get_database)
) -> Any:
    """Update a subject (teacher or admin only)"""
    # First try to find the subject using the string ID directly
    subject = await db.subjects.find_one({"_id": subject_id})
    
    # If not found, try to convert to ObjectId and search again
    if not subject:
        try:
            obj_id = ObjectId(subject_id)
            subject = await db.subjects.find_one({"_id": obj_id})
        except:
            # If conversion fails or subject still not found, raise 404
            raise HTTPException(status_code=404, detail="Subject not found")
    
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Get the actual ID from the found subject document
    actual_id = subject["_id"]
    
    update_data = subject_in.dict(exclude_unset=True)
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.subjects.update_one(
            {"_id": actual_id}, {"$set": update_data}
        )
    
    updated_subject = await db.subjects.find_one({"_id": actual_id})
    
    # Convert ObjectId to string for the response
    if isinstance(updated_subject["_id"], ObjectId):
        updated_subject["id"] = str(updated_subject["_id"])
    else:
        updated_subject["id"] = updated_subject["_id"]
    
    return updated_subject

@router.delete("/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_subject(
    subject_id: str,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> None:
    """Delete a subject (admin only)"""
    # Try to find the subject by string ID first
    subject = await db.subjects.find_one({"_id": subject_id})
    
    # If not found, try to convert the ID to ObjectId and search again
    if not subject:
        try:
            obj_id = ObjectId(subject_id)
            subject = await db.subjects.find_one({"_id": obj_id})
        except Exception:
            # If conversion fails or still not found, raise 404
            raise HTTPException(status_code=404, detail="Subject not found")
    
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Check if the subject is used in any exams - use the actual ID from found subject
    actual_id = subject["_id"]
    exam_count = await db.exams.count_documents({"subject_id": actual_id})
    
    if exam_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete subject used in {exam_count} exams. Please delete the exams first."
        )
    
    # Delete the subject using the actual ID from the found subject
    delete_result = await db.subjects.delete_one({"_id": actual_id})
    
    if delete_result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subject not found or could not be deleted")

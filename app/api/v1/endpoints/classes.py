from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Any, Dict
from bson.objectid import ObjectId
from datetime import datetime

from app.db.database import get_database
from app.models.domain.class_group import ClassGroup, ClassGroupCreate, ClassGroupInDB, ClassGroupUpdate
from app.models.domain.user import User
from app.core.auth import get_current_active_user, check_admin_permission
from app.utils.mongo import prepare_mongodb_docs, prepare_mongodb_doc

router = APIRouter()

@router.post("/", response_model=ClassGroup, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_in: ClassGroupCreate,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Create new class (admin only)"""
    existing = await db.classes.find_one({"class_id": class_in.class_id})
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"A class with ID {class_in.class_id} already exists"
        )
    
    # Tính số lượng sinh viên trong lớp
    student_count = await db.students.count_documents({"class_name": class_in.class_id})
    
    class_data = ClassGroupInDB(
        **class_in.dict(),
        id=str(ObjectId()),
        student_count=student_count
    )
    
    await db.classes.insert_one(class_data.dict(by_alias=True))
    return class_data

@router.get("/", response_model=List[ClassGroup])
async def read_classes(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Retrieve classes"""
    classes_cursor = db.classes.find().skip(skip).limit(limit)
    classes = await prepare_mongodb_docs(classes_cursor)
    
    return classes

@router.get("/stats", response_model=Dict[str, Any])
async def get_classes_stats(
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Get statistics about classes"""
    total_classes = await db.classes.count_documents({})
    
    # Lấy tổng số sinh viên từ tất cả các lớp
    pipeline = [
        {"$group": {"_id": None, "totalStudents": {"$sum": "$student_count"}}}
    ]
    result = await db.classes.aggregate(pipeline).to_list(length=1)
    total_students = result[0]["totalStudents"] if result else 0
    
    # Lấy số sinh viên thực tế
    actual_students = await db.students.count_documents({})
    
    # Lấy danh sách các khoa
    pipeline = [
        {"$group": {"_id": "$department", "count": {"$sum": 1}}}
    ]
    departments_data = await db.classes.aggregate(pipeline).to_list(length=100)
    departments = [{"name": d["_id"] or "Không xác định", "count": d["count"]} for d in departments_data]
    
    return {
        "total_classes": total_classes,
        "total_students": total_students,
        "actual_students": actual_students,
        "departments": departments
    }

@router.get("/{class_id}", response_model=ClassGroup)
async def read_class(
    class_id: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Get class by ID"""
    class_obj = await db.classes.find_one({"_id": class_id})
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    
    return prepare_mongodb_doc(class_obj)

@router.put("/{class_id}", response_model=ClassGroup)
async def update_class(
    class_id: str,
    class_in: ClassGroupUpdate,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Update a class (admin only)"""
    class_obj = await db.classes.find_one({"_id": class_id})
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    
    update_data = class_in.dict(exclude_unset=True)
    
    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        await db.classes.update_one(
            {"_id": class_id}, {"$set": update_data}
        )
    
    return prepare_mongodb_doc(await db.classes.find_one({"_id": class_id}))

@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_class(
    class_id: str,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> None:
    """Delete a class (admin only)"""
    class_obj = await db.classes.find_one({"_id": class_id})
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    
    # Kiểm tra xem lớp có sinh viên không
    student_count = await db.students.count_documents({"class_name": class_obj["class_id"]})
    if student_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete class with {student_count} students. Please remove students first."
        )
    
    await db.classes.delete_one({"_id": class_id})

@router.get("/{class_id}/students", response_model=List[Dict[str, Any]])
async def read_class_students(
    class_id: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Get students in a class"""
    class_obj = await db.classes.find_one({"_id": class_id})
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")
    
    students_cursor = db.students.find({"class_name": class_obj["class_id"]})
    students = await prepare_mongodb_docs(students_cursor)
    
    # Loại bỏ thông tin không cần thiết
    for student in students:
        if "hashed_password" in student:
            del student["hashed_password"]
    
    return students

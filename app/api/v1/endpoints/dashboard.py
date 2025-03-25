from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Dict, List
from bson.objectid import ObjectId
from datetime import datetime, timedelta

from app.db.database import get_database
from app.models.domain.user import User
from app.core.auth import get_current_active_user, check_admin_permission

async def prepare_mongodb_docs(cursor):
    """
    Convert MongoDB cursor documents to Python dictionaries with string IDs
    """
    result = []
    async for doc in cursor:
        # Convert ObjectId to string
        if isinstance(doc.get("_id"), ObjectId):
            doc["_id"] = str(doc["_id"])
        
        # Handle other ObjectId fields that might be in the document
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                doc[key] = str(value)
        
        result.append(doc)
    
    return result

router = APIRouter()

# Tạo endpoint mới để lấy thông tin tổng quan về hệ thống
@router.get("/stats", response_model=Dict[str, Any])
async def get_system_stats(
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """
    Lấy thống kê tổng quan về hệ thống
    """
    subjects_count = await db.subjects.count_documents({})
    rooms_count = await db.rooms.count_documents({})
    exams_count = await db.exams.count_documents({})
    students_count = await db.students.count_documents({})
    teachers_count = await db.teachers.count_documents({})
    users_count = await db.users.count_documents({})
    
    # Lấy thông tin chi tiết về môn học
    subjects_cursor = db.subjects.find()
    subjects_data = []
    async for subject in subjects_cursor:
        if isinstance(subject.get("_id"), ObjectId):
            subject["_id"] = str(subject["_id"])
        
        # Kiểm tra xem môn học có sinh viên đăng ký không
        registered_students = subject.get("registered_students", [])
        subjects_data.append({
            "id": subject["_id"],
            "code": subject.get("code", ""),
            "name": subject.get("name", ""),
            "registered_students_count": len(registered_students)
        })
    
    # Lấy thông tin chi tiết về phòng thi
    rooms_cursor = db.rooms.find()
    rooms_data = []
    async for room in rooms_cursor:
        if isinstance(room.get("_id"), ObjectId):
            room["_id"] = str(room["_id"])
            
        rooms_data.append({
            "id": room["_id"],
            "room_id": room.get("room_id", ""),
            "name": room.get("name", ""),
            "capacity": room.get("capacity", 0)
        })
    
    # Trả về dữ liệu thống kê
    return {
        "counts": {
            "subjects": subjects_count,
            "rooms": rooms_count,
            "exams": exams_count,
            "students": students_count,
            "teachers": teachers_count,
            "users": users_count
        },
        "subjects": subjects_data,
        "rooms": rooms_data
    }


@router.post("/create-sample-data", response_model=Dict[str, Any])
async def create_sample_data(
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """
    Tạo dữ liệu mẫu để thử nghiệm chức năng lập lịch thi
    """
    # Tạo môn học mẫu
    subject_count = 0
    for i in range(1, 6):
        subject_id = str(ObjectId())
        subject_data = {
            "_id": subject_id,
            "code": f"MON{i:03d}",
            "name": f"Môn học mẫu {i}",
            "duration": 90,
            "department": "Khoa CNTT",
            "credits": 3,
            "registered_students": [f"SV{j:03d}" for j in range(1, 31)],
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        try:
            await db.subjects.insert_one(subject_data)
            subject_count += 1
        except Exception as e:
            pass  # Có thể đã tồn tại
    
    # Tạo phòng thi mẫu
    room_count = 0
    for i in range(1, 6):
        room_id = str(ObjectId())
        room_data = {
            "_id": room_id,
            "room_id": f"P{i:03d}",
            "name": f"Phòng {i:03d}",
            "building": "Tòa A",
            "capacity": 30 + i * 5,
            "has_computers": i % 2 == 0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        try:
            await db.rooms.insert_one(room_data)
            room_count += 1
        except Exception as e:
            pass  # Có thể đã tồn tại
    
    return {
        "message": "Đã tạo dữ liệu mẫu thành công",
        "created": {
            "subjects": subject_count,
            "rooms": room_count
        }
    }

# Tạo endpoint mới để lấy thông tin tổng quan cho sinh viên
@router.get("/student", response_model=Dict[str, Any])
async def get_student_dashboard(
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """
    Lấy thông tin tổng quan cho sinh viên
    """
    # Tìm thông tin sinh viên
    student = await db.students.find_one({"email": current_user.email})
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy hồ sơ sinh viên"
        )
    
    student_id = student.get("student_id")
    
    # Đếm số lượng môn học có kỳ thi (không phải số kỳ thi)
    exams = await db.exams.find({"student_ids": student_id}).to_list(length=100)
    
    # Nhóm theo môn học để đếm chính xác
    subject_ids = set()
    for exam in exams:
        subject_ids.add(exam.get("subject_id"))
    
    total_subjects = len(subject_ids)
    
    # Tìm các kỳ thi sắp tới (trong 7 ngày tới)
    now = datetime.utcnow()
    next_week = now + timedelta(days=7)
    upcoming_exams = await db.exams.find({
        "student_ids": student_id,
        "start_time": {"$gte": now, "$lte": next_week}
    }).to_list(length=100)
    
    # Nhóm các kỳ thi sắp tới theo môn học
    upcoming_subject_ids = set()
    for exam in upcoming_exams:
        upcoming_subject_ids.add(exam.get("subject_id"))
    
    upcoming_subjects_count = len(upcoming_subject_ids)
    
    # Lấy kỳ thi gần nhất
    next_exam_info = None
    if upcoming_exams:
        # Sắp xếp theo thời gian bắt đầu
        upcoming_exams.sort(key=lambda x: x.get("start_time"))
        next_exam_doc = upcoming_exams[0]
        
        # Lấy thông tin môn học và phòng thi
        subject = await db.subjects.find_one({"_id": next_exam_doc.get("subject_id")})
        room = await db.rooms.find_one({"_id": next_exam_doc.get("room_id")})
        
        # Tìm tất cả các phòng thi cho môn học này
        all_rooms_for_subject = []
        for exam in [e for e in upcoming_exams if e.get("subject_id") == next_exam_doc.get("subject_id")]:
            exam_room = await db.rooms.find_one({"_id": exam.get("room_id")})
            if exam_room:
                all_rooms_for_subject.append(exam_room.get("room_id", "Unknown"))
        
        next_exam_info = {
            "exam_id": str(next_exam_doc.get("_id")),
            "subject_name": subject.get("name") if subject else "Unknown Subject",
            "subject_code": subject.get("code") if subject else None,
            "start_time": next_exam_doc.get("start_time"),
            "end_time": next_exam_doc.get("end_time"),
            "rooms": all_rooms_for_subject,
            "your_room": room.get("room_id") if room else "Unknown"
        }
    
    # Lấy danh sách môn học đã đăng ký
    registered_subjects = []
    if "registered_subjects" in student:
        for subject_code in student.get("registered_subjects", []):
            subject = await db.subjects.find_one({"code": subject_code})
            if subject:
                registered_subjects.append({
                    "id": str(subject.get("_id")),
                    "code": subject.get("code"),
                    "name": subject.get("name")
                })
    
    return {
        "student": {
            "id": str(student.get("_id")),
            "student_id": student.get("student_id"),
            "full_name": student.get("full_name"),
            "class_name": student.get("class_name"),
            "email": student.get("email")
        },
        "subjects_count": total_subjects,
        "upcoming_subjects_count": upcoming_subjects_count,
        "next_exam": next_exam_info,
        "registered_subjects": registered_subjects
    }

@router.get("/student/subjects-summary", response_model=List[Dict[str, Any]])
async def get_student_subjects_summary(
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """
    Lấy thông tin tổng quan về môn học và kỳ thi của sinh viên
    """
    # Tìm thông tin sinh viên
    student = await db.students.find_one({"email": current_user.email})
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    student_id = student.get("student_id")
    
    # Lấy tất cả các kỳ thi của sinh viên
    exams_cursor = db.exams.find({"student_ids": student_id})
    exams = await prepare_mongodb_docs(exams_cursor)
    
    # Nhóm kỳ thi theo môn học
    subject_exams = {}
    for exam in exams:
        subject_id = exam.get("subject_id")
        if subject_id not in subject_exams:
            subject_exams[subject_id] = []
        subject_exams[subject_id].append(exam)
    
    # Lấy thông tin chi tiết về môn học
    result = []
    for subject_id, subject_exam_list in subject_exams.items():
        subject = await db.subjects.find_one({"_id": subject_id})
        if subject:
            if isinstance(subject.get("_id"), ObjectId):
                subject["_id"] = str(subject["_id"])
                
            result.append({
                "subject": {
                    "id": subject["_id"],
                    "code": subject.get("code", "Unknown"),
                    "name": subject.get("name", "Unknown"),
                    "duration": subject.get("duration", 0)
                },
                "exams_count": len(subject_exam_list),
                "next_exam": min([exam.get("start_time") for exam in subject_exam_list], default=None)
            })
    
    return result

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Any, Dict, List
from datetime import datetime, timedelta
from bson.objectid import ObjectId
import logging

from app.db.database import get_database
from app.models.domain.user import User
from app.models.domain.schedule import ScheduleConfigCreate, ScheduleConfig
from app.models.domain.subject import Subject
from app.models.domain.room import Room
from app.models.domain.exam import Exam, ExamInDB
from app.core.auth import check_admin_permission, get_current_active_user
from app.services.scheduler import ExamScheduler
from app.utils.mongo import prepare_mongodb_docs, prepare_mongodb_doc

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/create", response_model=Dict[str, Any])
async def create_exam_schedule(
    config: ScheduleConfigCreate,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """
    Tạo lịch thi dựa trên cấu hình được cung cấp cho một kì thi.
    Chỉ admin mới có thể sử dụng endpoint này.
    """
    # Xóa tất cả các kỳ thi hiện có
    delete_result = await db.exams.delete_many({})
    logger.info(f"Xóa {delete_result.deleted_count} kỳ thi hiện có trước khi tạo mới")
    
    # Lưu cấu hình lập lịch thi
    config_data = {
        "_id": str(ObjectId()),
        "exam_period_name": config.exam_period_name,
        "start_date": config.start_date,
        "end_date": config.end_date,
        "first_exam_time": config.first_exam_time.strftime('%H:%M:%S'),
        "last_exam_time": config.last_exam_time.strftime('%H:%M:%S'),
        "supervisors_per_room": config.supervisors_per_room,
        "created_by": current_user.id,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    await db.schedule_configs.insert_one(config_data)
    
    # Lấy tất cả các môn học đăng ký thi
    subjects_cursor = db.subjects.find()
    subjects = []
    async for subject_doc in subjects_cursor:
        # Chuyển đổi ObjectId thành string
        if isinstance(subject_doc.get("_id"), ObjectId):
            subject_doc["_id"] = str(subject_doc["_id"])
        subject_doc["id"] = subject_doc["_id"]
        subjects.append(Subject(**subject_doc))
    
    # Lấy tất cả các phòng thi
    rooms_cursor = db.rooms.find()
    rooms = []
    async for room_doc in rooms_cursor:
        # Chuyển đổi ObjectId thành string
        if isinstance(room_doc.get("_id"), ObjectId):
            room_doc["_id"] = str(room_doc["_id"])
        room_doc["id"] = room_doc["_id"]
        rooms.append(Room(**room_doc))
    
    # Đảm bảo mọi môn học đều có duration
    for subject in subjects:
        if not hasattr(subject, 'duration') or subject.duration <= 0:
            logger.warning(f"Subject {subject.name} has invalid duration, setting to 120 minutes")
            subject.duration = 120
    
    # Khởi tạo scheduler và lập lịch thi
    scheduler_config = ScheduleConfig(
        id=config_data["_id"],
        exam_period_name=config.exam_period_name,  # Add missing field
        start_date=config.start_date,
        end_date=config.end_date,
        first_exam_time=config.first_exam_time,
        last_exam_time=config.last_exam_time,
        supervisors_per_room=config.supervisors_per_room,
        created_by=current_user.id,
        created_at=config_data["created_at"],
        updated_at=config_data["updated_at"]
    )
    
    # Thêm logging để theo dõi tiến trình
    logger.info(f"Creating exam schedule for period: {config.start_date} to {config.end_date}")
    
    scheduler = ExamScheduler(scheduler_config)
    scheduled_exams = await scheduler.schedule_exams(db, subjects, rooms)
    
    if not scheduled_exams:
        logger.warning("No exams were scheduled. Check if you have subjects with students and rooms with capacity.")
    
    # Lưu các kỳ thi đã lập lịch vào database
    created_exams = []
    for exam_data in scheduled_exams:
        # Đảm bảo supervisor_ids chỉ chứa strings, không phải ObjectId
        supervisor_ids = []
        for supervisor_id in exam_data["supervisor_ids"]:
            if isinstance(supervisor_id, ObjectId):
                supervisor_ids.append(str(supervisor_id))
            else:
                supervisor_ids.append(supervisor_id)
        
        # Đảm bảo subject_id và room_id là strings
        subject_id = str(exam_data["subject_id"]) if isinstance(exam_data["subject_id"], ObjectId) else exam_data["subject_id"]
        room_id = str(exam_data["room_id"]) if isinstance(exam_data["room_id"], ObjectId) else exam_data["room_id"]
        
        # Đảm bảo student_ids chỉ chứa strings
        student_ids = []
        for student_id in exam_data.get("student_ids", []):
            if isinstance(student_id, ObjectId):
                student_ids.append(str(student_id))
            else:
                student_ids.append(student_id)
        
        exam = ExamInDB(
            id=str(ObjectId()),
            subject_id=subject_id,
            room_id=room_id,
            start_time=exam_data["start_time"],
            end_time=exam_data["end_time"],
            supervisor_ids=supervisor_ids,
            max_students=exam_data["max_students"],
            student_ids=student_ids
        )
        
        await db.exams.insert_one(exam.dict(by_alias=True))
        created_exams.append(exam)
    
    return {
        "message": "Tạo lịch thi thành công",
        "config_id": config_data["_id"],
        "exams_created": len(created_exams)
    }

@router.post("/preview", response_model=List[Dict[str, Any]])
async def preview_exam_schedule(
    config: ScheduleConfigCreate,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """
    Xem trước lịch thi dựa trên cấu hình được cung cấp cho một kì thi.
    Chỉ admin mới có thể sử dụng endpoint này.
    """
    logger.info(f"Previewing exam schedule for period: {config.start_date} to {config.end_date}")
    
    # Lấy tất cả các môn học đăng ký thi
    subjects_cursor = db.subjects.find()
    subjects = []
    async for subject_doc in subjects_cursor:
        try:
            # Chuyển đổi ObjectId thành string
            if isinstance(subject_doc.get("_id"), ObjectId):
                subject_doc["_id"] = str(subject_doc["_id"])
            subject_doc["id"] = subject_doc["_id"]
            
            # Đảm bảo registered_students tồn tại, nếu không tạo một danh sách trống
            if "registered_students" not in subject_doc:
                subject_doc["registered_students"] = []
                logger.warning(f"Subject {subject_doc.get('name')} has no registered_students field")
            
            # Đảm bảo các trường bắt buộc khác tồn tại
            if "code" not in subject_doc:
                subject_doc["code"] = f"CODE_{len(subjects)+1}"
                logger.warning(f"Subject {subject_doc.get('name')} has no code field")
            
            if "name" not in subject_doc:
                subject_doc["name"] = f"Subject_{len(subjects)+1}"
                logger.warning(f"Subject has no name field")
            
            if "duration" not in subject_doc:
                subject_doc["duration"] = 120  # Default 120 minutes
                logger.warning(f"Subject {subject_doc.get('name')} has no duration field")
            
            # Thêm vào danh sách subjects
            logger.info(f"Found subject: {subject_doc.get('name')} with {len(subject_doc.get('registered_students', []))} students")
            subjects.append(Subject(**subject_doc))
        except Exception as e:
            logger.error(f"Error processing subject: {e}", exc_info=True)
    
    logger.info(f"Found {len(subjects)} subjects")
    
    # Nếu không có môn học, tạo môn học ví dụ
    if not subjects:
        logger.warning("No subjects found, creating example subject")
        example_subject = Subject(
            id=str(ObjectId()),
            code="EXAMPLE101",
            name="Example Subject",
            duration=120,
            registered_students=[f"DEMO_STUDENT_{i}" for i in range(1, 31)]
        )
        subjects.append(example_subject)
    else:
        # Đảm bảo mọi môn học đều có duration
        for subject in subjects:
            if not hasattr(subject, 'duration') or subject.duration <= 0:
                subject.duration = 120
                logger.warning(f"Subject {subject.name} has invalid duration, setting to 120 minutes")
    
    # Lấy tất cả các phòng thi
    rooms_cursor = db.rooms.find()
    rooms = []
    async for room_doc in rooms_cursor:
        try:
            # Chuyển đổi ObjectId thành string
            if isinstance(room_doc.get("_id"), ObjectId):
                room_doc["_id"] = str(room_doc["_id"])
            room_doc["id"] = room_doc["_id"]
            
            # Đảm bảo capacity tồn tại
            if "capacity" not in room_doc or not room_doc["capacity"]:
                room_doc["capacity"] = 30
                logger.warning(f"Room {room_doc.get('room_id')} has no capacity, setting to 30")
            
            # Đảm bảo room_id tồn tại
            if "room_id" not in room_doc:
                room_doc["room_id"] = f"ROOM_{len(rooms)+1}"
                logger.warning(f"Room has no room_id, setting to {room_doc['room_id']}")
            
            # Thêm vào danh sách rooms
            logger.info(f"Found room: {room_doc.get('room_id')} with capacity {room_doc.get('capacity')}")
            rooms.append(Room(**room_doc))
        except Exception as e:
            logger.error(f"Error processing room: {e}", exc_info=True)
    
    logger.info(f"Found {len(rooms)} rooms")
    
    # Nếu không có phòng thi, tạo phòng thi ví dụ
    if not rooms:
        logger.warning("No rooms found, creating example room")
        example_room = Room(
            id=str(ObjectId()),
            room_id="ROOM101",
            capacity=40,
            building="Example Building",
            name="Example Room"
        )
        rooms.append(example_room)
    
    # Khởi tạo scheduler và lập lịch thi
    scheduler_config = ScheduleConfig(
        id=str(ObjectId()),
        exam_period_name=config.exam_period_name,  # Add missing field
        start_date=config.start_date,
        end_date=config.end_date,
        first_exam_time=config.first_exam_time,
        last_exam_time=config.last_exam_time,
        supervisors_per_room=config.supervisors_per_room,
        created_by=current_user.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    try:
        scheduler = ExamScheduler(scheduler_config)
        scheduled_exams = await scheduler.schedule_exams(db, subjects, rooms)
        
        logger.info(f"Scheduler returned {len(scheduled_exams)} exam entries")
        
        if not scheduled_exams:
            # Trường hợp không có lịch thi được tạo
            logger.warning("No exams were scheduled in preview")
            
            # Tạo một lịch thi ví dụ để hiển thị
            if subjects and rooms:
                logger.info("Creating example exam for preview")
                tomorrow = datetime.utcnow() + timedelta(days=1)
                start_time = datetime.combine(tomorrow.date(), config.first_exam_time)
                end_time = start_time + timedelta(minutes=subjects[0].duration)
                
                example_exam = {
                    "subject_id": subjects[0].id,
                    "room_id": rooms[0].id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "supervisor_ids": [f"DEMO_SUPERVISOR_{i}" for i in range(config.supervisors_per_room)],
                    "max_students": rooms[0].capacity,
                    "student_ids": [f"DEMO_STUDENT_{i}" for i in range(min(30, rooms[0].capacity))]
                }
                scheduled_exams = [example_exam]
                logger.info("Added example exam to preview")
    except Exception as e:
        logger.error(f"Error in scheduling process: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error in scheduling process: {str(e)}"
        )
    
    # Thêm thông tin chi tiết để người dùng dễ hiểu
    preview_results = []
    for exam in scheduled_exams:
        try:
            subject_id = exam["subject_id"]
            room_id = exam["room_id"]
            
            # Tìm thông tin môn học và phòng thi
            subject = await db.subjects.find_one({"_id": subject_id})
            room = await db.rooms.find_one({"_id": room_id})
            
            # Nếu không tìm thấy trong DB, tìm trong danh sách đã nạp
            if not subject:
                for s in subjects:
                    if s.id == subject_id:
                        subject = {
                            "_id": s.id,
                            "name": s.name,
                            "code": s.code
                        }
                        break
            
            if not room:
                for r in rooms:
                    if r.id == room_id:
                        room = {
                            "_id": r.id,
                            "name": r.name if hasattr(r, 'name') else "",
                            "room_id": r.room_id,
                            "capacity": r.capacity
                        }
                        break
            
            if subject and room:
                # Chuyển đổi ObjectId thành string
                if isinstance(subject.get("_id"), ObjectId):
                    subject["_id"] = str(subject["_id"])
                if isinstance(room.get("_id"), ObjectId):
                    room["_id"] = str(room["_id"])
                    
                preview_results.append({
                    "subject": {
                        "id": subject["_id"],
                        "name": subject.get("name", "Unknown"),
                        "code": subject.get("code", "Unknown")
                    },
                    "room": {
                        "id": room["_id"],
                        "name": room.get("name", ""),
                        "room_id": room.get("room_id", "Unknown"),
                        "capacity": room.get("capacity", 0)
                    },
                    "start_time": exam["start_time"],
                    "end_time": exam["end_time"],
                    "num_students": len(exam["student_ids"]),
                    "num_supervisors": len(exam["supervisor_ids"])
                })
        except Exception as e:
            logger.error(f"Error creating preview result: {e}", exc_info=True)
    
    logger.info(f"Preview generated {len(preview_results)} exam entries")
    return preview_results

@router.get("/config/{config_id}", response_model=Dict[str, Any])
async def get_schedule_config(
    config_id: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """
    Lấy thông tin cấu hình lịch thi
    """
    config = await db.schedule_configs.find_one({"_id": config_id})
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Schedule configuration not found"
        )
    
    # Chuyển đổi chuỗi thời gian thành định dạng có thể đọc được
    if isinstance(config.get("first_exam_time"), str):
        time_parts = config["first_exam_time"].split(":")
        config["first_exam_time_display"] = f"{time_parts[0]}:{time_parts[1]}"
    
    if isinstance(config.get("last_exam_time"), str):
        time_parts = config["last_exam_time"].split(":")
        config["last_exam_time_display"] = f"{time_parts[0]}:{time_parts[1]}"
    
    return config
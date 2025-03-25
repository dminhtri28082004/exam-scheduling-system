from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Any, Optional, Dict
from bson.objectid import ObjectId
from datetime import datetime, timedelta

from app.db.database import get_database
from app.models.domain.exam import Exam, ExamCreate, ExamInDB, ExamUpdate
from app.models.domain.user import User
from app.core.auth import get_current_active_user, check_teacher_permission
from app.utils.mongo import prepare_mongodb_docs, prepare_mongodb_doc

router = APIRouter()

@router.post("/", response_model=Exam, status_code=status.HTTP_201_CREATED)
async def create_exam(
    exam_in: ExamCreate,
    current_user: User = Depends(check_teacher_permission),
    db = Depends(get_database)
) -> Any:
    """Create new exam (teacher or admin only)"""
    # Validate if subject exists
    subject = await db.subjects.find_one({"_id": exam_in.subject_id})
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    
    # Validate if room exists
    room = await db.rooms.find_one({"_id": exam_in.room_id})
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    # Check if room is available at that time
    overlapping_exam = await db.exams.find_one({
        "room_id": exam_in.room_id,
        "$or": [
            {
                "start_time": {"$lt": exam_in.end_time},
                "end_time": {"$gt": exam_in.start_time}
            }
        ]
    })
    
    if overlapping_exam:
        raise HTTPException(status_code=400, detail="Room already scheduled for another exam during this time")
    
    exam_data = ExamInDB(
        **exam_in.dict(),
        id=str(ObjectId())
    )
    
    await db.exams.insert_one(exam_data.dict(by_alias=True))
    return exam_data

@router.get("/", response_model=List[Exam])
async def read_exams(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """Retrieve exams"""
    query = {}
    if current_user.role == "student":
        # Students can only see exams they're registered for
        query = {"student_ids": current_user.id}
    
    exams_cursor = db.exams.find(query).skip(skip).limit(limit)
    exams = await prepare_mongodb_docs(exams_cursor)
    
    return exams

@router.get("/my-exams", response_model=List[Dict[str, Any]])
async def read_student_exams(
    subject_code: Optional[str] = Query(None, description="Filter by subject code"),
    start_date: Optional[datetime] = Query(None, description="Filter by start date"),
    end_date: Optional[datetime] = Query(None, description="Filter by end date"),
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """
    Retrieve exams for the current student user.
    Students can filter exams by subject code, start date, and end date.
    """
    # Kiểm tra xem người dùng có phải là sinh viên không
    if current_user.role != "student":
        # Nếu không phải sinh viên, kiểm tra trong collection students
        student = await db.students.find_one({"email": current_user.email})
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        student_id = student.get("student_id")
    else:
        # Nếu là sinh viên, tìm student_id tương ứng
        student = await db.students.find_one({"email": current_user.email})
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        student_id = student.get("student_id")
    
    # Xây dựng query dựa trên các filter
    query = {"student_ids": student_id}
    
    if start_date and end_date:
        query["start_time"] = {
            "$gte": start_date,
            "$lte": end_date
        }
    elif start_date:
        query["start_time"] = {"$gte": start_date}
    elif end_date:
        query["start_time"] = {"$lte": end_date}
    
    # Tìm tất cả các kỳ thi của sinh viên
    exams_cursor = db.exams.find(query).sort("start_time", 1)
    exams = await prepare_mongodb_docs(exams_cursor)
    
    # Nếu có filter theo môn học, lọc trước khi nhóm
    if subject_code:
        subject = await db.subjects.find_one({"code": subject_code})
        if not subject:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subject with code {subject_code} not found"
            )
        
        # Lọc các kỳ thi có subject_id tương ứng
        subject_id = subject.get("_id")
        exams = [exam for exam in exams if exam.get("subject_id") == subject_id]
    
    # Nhóm các kỳ thi theo môn học
    subject_exams = {}
    for exam in exams:
        subject_id = exam.get("subject_id")
        if subject_id not in subject_exams:
            subject_exams[subject_id] = {
                "subject_id": subject_id,
                "exams": [],
                "start_time": exam.get("start_time"),  # Lấy thời gian sớm nhất
                "end_time": exam.get("end_time"),      # Sẽ cập nhật nếu có phòng thi kết thúc muộn hơn
                "total_students": 0
            }
        
        # Thêm kỳ thi vào danh sách và cập nhật thông tin tổng hợp
        subject_exams[subject_id]["exams"].append(exam)
        subject_exams[subject_id]["total_students"] += len(exam.get("student_ids", []))
        
        # Cập nhật thời gian kết thúc nếu kỳ thi này kết thúc muộn hơn
        if exam.get("end_time") > subject_exams[subject_id]["end_time"]:
            subject_exams[subject_id]["end_time"] = exam.get("end_time")
    
    # Tạo kết quả với định dạng môn học và các phòng thi
    result = []
    for subject_id, subject_data in subject_exams.items():
        # Lấy thông tin môn học
        subject = await db.subjects.find_one({"_id": subject_id})
        if not subject:
            continue  # Bỏ qua nếu không tìm thấy môn học
        
        subject = prepare_mongodb_doc(subject)
        
        # Lấy danh sách phòng thi
        rooms_info = []
        for exam in subject_data["exams"]:
            room = await db.rooms.find_one({"_id": exam.get("room_id")})
            if room:
                room = prepare_mongodb_doc(room)
                rooms_info.append({
                    "room_id": room.get("room_id"),
                    "name": room.get("name", "Unknown Room"),
                    "building": room.get("building"),
                    "capacity": room.get("capacity"),
                    "num_students": len(exam.get("student_ids", [])),
                    "student_ids": exam.get("student_ids", [])
                })
        
        # Thêm vào kết quả
        result.append({
            "exam_id": subject_data["exams"][0].get("id"),  # Dùng ID của kỳ thi đầu tiên làm ID đại diện
            "subject": {
                "id": subject.get("id"),
                "code": subject.get("code"),
                "name": subject.get("name", "Unknown Subject"),
                "duration": subject.get("duration", 120)
            },
            "start_time": subject_data["start_time"],
            "end_time": subject_data["end_time"],
            "duration_minutes": (subject_data["end_time"] - subject_data["start_time"]).total_seconds() // 60 if subject_data["end_time"] and subject_data["start_time"] else None,
            "total_students": subject_data["total_students"],
            "rooms": rooms_info
        })
    
    return result

@router.get("/upcoming", response_model=List[Dict[str, Any]])
async def read_upcoming_exams(
    days: int = Query(7, description="Number of upcoming days to check"),
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """
    Retrieve upcoming exams for the current user within the specified number of days.
    """
    # Tính toán khoảng thời gian
    now = datetime.utcnow()
    end_date = now + timedelta(days=days)
    
    # Redirect đến hàm read_student_exams với các tham số phù hợp
    return await read_student_exams(
        start_date=now,
        end_date=end_date,
        current_user=current_user,
        db=db
    )

@router.get("/{exam_id}/details", response_model=Dict[str, Any])
async def read_exam_details(
    exam_id: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """
    Get detailed information about a specific exam.
    """
    # Kiểm tra xem kỳ thi có tồn tại không
    exam = await db.exams.find_one({"_id": exam_id})
    if not exam:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found"
        )
    
    # Ánh xạ _id sang id
    exam = prepare_mongodb_doc(exam)
    
    # Nếu người dùng là sinh viên, kiểm tra xem họ có được đăng ký tham gia kỳ thi này không
    if current_user.role == "student":
        student = await db.students.find_one({"email": current_user.email})
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found"
            )
        
        student_id = student.get("student_id")
        if student_id not in exam.get("student_ids", []):
            # Tìm các kỳ thi khác của cùng môn học
            other_exams = await db.exams.find({
                "subject_id": exam.get("subject_id"),
                "student_ids": student_id
            }).to_list(length=10)
            
            if not other_exams:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not registered for this exam"
                )
    
    # Lấy thông tin chi tiết
    subject = await db.subjects.find_one({"_id": exam.get("subject_id")})
    subject = prepare_mongodb_doc(subject) if subject else None
    
    # Tìm tất cả các phòng thi cho môn học này
    all_exams = await db.exams.find({"subject_id": exam.get("subject_id")}).to_list(length=50)
    all_exams = [prepare_mongodb_doc(e) for e in all_exams]
    
    # Lấy thông tin các phòng thi
    rooms_info = []
    for e in all_exams:
        room = await db.rooms.find_one({"_id": e.get("room_id")})
        if room:
            room = prepare_mongodb_doc(room)
            rooms_info.append({
                "room_id": room.get("room_id"),
                "name": room.get("name", "Unknown Room"),
                "building": room.get("building"),
                "capacity": room.get("capacity"),
                "num_students": len(e.get("student_ids", [])),
                "exam_id": e.get("id")
            })
    
    # Lấy thông tin giám thị từ tất cả các phòng
    supervisors = []
    for e in all_exams:
        for supervisor_id in e.get("supervisor_ids", []):
            if isinstance(supervisor_id, str) and not supervisor_id.startswith("DEMO_"):
                supervisor = await db.teachers.find_one({"_id": supervisor_id})
                if supervisor:
                    supervisors.append({
                        "id": supervisor.get("_id"),
                        "name": supervisor.get("full_name"),
                        "email": supervisor.get("email")
                    })
    
    # Loại bỏ giám thị trùng lặp
    unique_supervisors = []
    supervisor_ids = set()
    for supervisor in supervisors:
        if supervisor["id"] not in supervisor_ids:
            supervisor_ids.add(supervisor["id"])
            unique_supervisors.append(supervisor)
    
    # Tạo kết quả chi tiết
    result = {
        "exam_id": exam.get("id"),
        "subject": {
            "id": subject.get("id") if subject else None,
            "code": subject.get("code") if subject else None,
            "name": subject.get("name") if subject else "Unknown Subject"
        },
        "start_time": exam.get("start_time"),
        "end_time": exam.get("end_time"),
        "duration_minutes": (exam.get("end_time") - exam.get("start_time")).total_seconds() // 60 if exam.get("end_time") and exam.get("start_time") else None,
        "rooms": rooms_info,
        "supervisors": unique_supervisors,
        "total_students": sum(len(e.get("student_ids", [])) for e in all_exams),
        "your_room": next((r for r in rooms_info if exam.get("room_id") == r.get("room_id")), None)
    }
    
    return result

@router.get("/{exam_id}", response_model=Dict[str, Any])
async def get_exam(
    exam_id: str,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """
    Lấy thông tin chi tiết của một kỳ thi
    """
    # Try multiple ways to find the exam
    exam = None
    
    # Try 1: Direct string ID lookup
    exam = await db.exams.find_one({"_id": exam_id})
    
    # Try 2: Look for 'id' field instead
    if not exam:
        exam = await db.exams.find_one({"id": exam_id})
    
    # Try 3: Convert to ObjectId if possible and try again
    if not exam and len(exam_id) == 24:
        try:
            obj_id = ObjectId(exam_id)
            exam = await db.exams.find_one({"_id": obj_id})
        except Exception as e:
            print(f"Error converting to ObjectId: {str(e)}")
    
    if not exam:
        # Enhanced error details for debugging
        print(f"Exam with ID {exam_id} not found. Tried direct lookup and ObjectId conversion.")
        
        # Add debug information
        sample_exam = await db.exams.find_one()
        if sample_exam:
            print(f"Sample exam ID format in DB: {type(sample_exam.get('_id')).__name__}")
            
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam with ID {exam_id} not found"
        )
    
    # Get the actual ID from the found exam document
    actual_id = exam["_id"]
    
    # Chuyển đổi ObjectId sang string
    exam = prepare_mongodb_doc(exam)
    
    # Lấy thông tin chi tiết
    subject = None
    subject_id = exam.get("subject_id")
    if subject_id:
        # Try direct lookup first
        subject = await db.subjects.find_one({"_id": subject_id})
        
        # If not found and subject_id is a string, try ObjectId conversion
        if not subject and isinstance(subject_id, str) and len(subject_id) == 24:
            try:
                obj_id = ObjectId(subject_id)
                subject = await db.subjects.find_one({"_id": obj_id})
            except:
                print(f"Failed to convert subject_id {subject_id} to ObjectId")
        
        # If still not found, try looking up by id field
        if not subject:
            subject = await db.subjects.find_one({"id": subject_id})
    
    room = None
    room_id = exam.get("room_id")
    if room_id:
        # Try direct lookup first
        room = await db.rooms.find_one({"_id": room_id})
        
        # If not found and room_id is a string, try ObjectId conversion
        if not room and isinstance(room_id, str) and len(room_id) == 24:
            try:
                obj_id = ObjectId(room_id)
                room = await db.rooms.find_one({"_id": obj_id})
            except:
                print(f"Failed to convert room_id {room_id} to ObjectId")
        
        # If still not found, try looking up by id field
        if not room:
            room = await db.rooms.find_one({"id": room_id})
    
    if not subject or not room:
        print(f"Related subject or room not found. Subject ID: {subject_id}, Room ID: {room_id}")
        if subject_id and not subject:
            print(f"Subject lookup failed. Type: {type(subject_id).__name__}")
        if room_id and not room:
            print(f"Room lookup failed. Type: {type(room_id).__name__}")
            
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Related subject or room not found"
        )
    
    # Chuyển đổi ObjectId sang string
    subject = prepare_mongodb_doc(subject)
    room = prepare_mongodb_doc(room)
    
    # Lấy thông tin giám thị
    supervisors = []
    for supervisor_id in exam.get("supervisor_ids", []):
        # Handle ObjectId if present
        if isinstance(supervisor_id, ObjectId):
            supervisor_id = str(supervisor_id)
            
        # Xử lý trường hợp giám thị là demo
        if isinstance(supervisor_id, str) and supervisor_id.startswith("DEMO_SUPERVISOR"):
            supervisors.append({
                "id": supervisor_id,
                "name": f"Giám thị {supervisor_id.split('_')[-1]}"
            })
        else:
            # Convert to ObjectId for lookup if it's a string representation
            lookup_id = supervisor_id
            if isinstance(supervisor_id, str) and len(supervisor_id) == 24:
                try:
                    lookup_id = ObjectId(supervisor_id)
                except:
                    pass  # Keep as string if conversion fails
                    
            # Tìm thông tin giám thị trong database
            teacher = await db.teachers.find_one({"_id": lookup_id})
            if teacher:
                teacher = prepare_mongodb_doc(teacher)
                supervisors.append({
                    "id": teacher["_id"],
                    "name": teacher.get("full_name", "Chưa xác định")
                })
            else:
                # Fallback if supervisor not found
                supervisors.append({
                    "id": str(supervisor_id),
                    "name": f"Giám thị (ID: {supervisor_id})"
                })
    
    # Lấy thông tin sinh viên
    students = []
    for student_id in exam.get("student_ids", []):
        # Xử lý trường hợp sinh viên là demo
        if isinstance(student_id, str) and student_id.startswith("DEMO_STUDENT"):
            students.append({
                "id": student_id,
                "student_id": student_id,
                "name": f"Sinh viên {student_id.split('_')[-1]}"
            })
        else:
            # Tìm thông tin sinh viên trong database
            student = await db.students.find_one({"student_id": student_id})
            if student:
                student = prepare_mongodb_doc(student)
                students.append({
                    "id": student["_id"],
                    "student_id": student["student_id"],
                    "name": student.get("full_name", "Chưa xác định")
                })
    
    # Tìm các phòng thi song song (cùng môn, cùng thời gian)
    parallel_exams = []
    if "parallel_exam_group" in exam and exam["parallel_exam_group"]:
        # Tìm tất cả các kỳ thi cùng nhóm song song
        parallel_group = exam["parallel_exam_group"]
        parallel_exams_cursor = db.exams.find({
            "parallel_exam_group": parallel_group,
            "_id": {"$ne": actual_id}  # Không lấy exam hiện tại
        })
        
        # Lấy thông tin chi tiết về các phòng thi song song
        async for parallel_exam in parallel_exams_cursor:
            p_exam = prepare_mongodb_doc(parallel_exam)
            
            # Lấy thông tin phòng
            p_room = await db.rooms.find_one({"_id": p_exam["room_id"]})
            if p_room:
                p_room = prepare_mongodb_doc(p_room)
                parallel_exams.append({
                    "id": p_exam["id"],
                    "room_id": p_room.get("room_id", "Unknown"),
                    "room_name": p_room.get("name", p_room.get("room_id", "Unknown")),
                    "student_count": len(p_exam.get("student_ids", [])),
                    "capacity": p_room.get("capacity", 0)
                })
    
    # Trả về thông tin chi tiết
    return {
        "id": exam["_id"],
        "subject": {
            "id": subject["_id"],
            "code": subject.get("code", "Unknown"),
            "name": subject.get("name", "Unknown")
        },
        "room": {
            "id": room["_id"],
            "room_id": room.get("room_id", "Unknown"),
            "name": room.get("name", room.get("room_id", "Unknown")),
            "capacity": room.get("capacity", 0)
        },
        "start_time": exam["start_time"],
        "end_time": exam["end_time"],
        "supervisors": supervisors,
        "students": students,
        "max_students": exam.get("max_students", 0),
        "created_at": exam.get("created_at", None),
        "updated_at": exam.get("updated_at", None),
        "parallel_rooms": parallel_exams  # Thêm thông tin về các phòng thi song song
    }

@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(
    exam_id: str,
    current_user: User = Depends(check_teacher_permission),
    db = Depends(get_database)
) -> None:
    """Delete an exam (teacher or admin only)"""
    # First try to find the exam using the string ID directly
    exam = await db.exams.find_one({"_id": exam_id})
    
    # If not found, try to convert to ObjectId and search again
    if not exam:
        try:
            obj_id = ObjectId(exam_id)
            exam = await db.exams.find_one({"_id": obj_id})
        except:
            # If conversion fails or exam still not found, raise 404
            raise HTTPException(status_code=404, detail="Exam not found")
    
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # Get the actual ID from the found exam document
    actual_id = exam["_id"]
    
    # Now delete the exam
    result = await db.exams.delete_one({"_id": actual_id})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Exam not found or could not be deleted")
    
    # Return no content on successful deletion
    return None

from fastapi import APIRouter, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordRequestForm
from typing import Optional, Any  # Add Any to the imports
import os
from pathlib import Path
from bson.objectid import ObjectId
from datetime import datetime

from app.db.database import get_database
from app.core.security import verify_password, create_access_token
from app.models.domain.user import User
from app.core.auth import get_current_active_user, check_admin_permission
from app.utils.mongo import prepare_mongodb_docs, prepare_mongodb_doc  # Add missing import

# Tạo router
web_router = APIRouter(include_in_schema=False)

# Tạo thư mục templates nếu chưa tồn tại
templates_dir = Path("app/templates")
templates_dir.mkdir(exist_ok=True)

# Cấu hình templates
templates = Jinja2Templates(directory="app/templates")

# Route trang chủ
@web_router.get("/ui", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Route đăng nhập
@web_router.get("/ui/login", response_class=HTMLResponse)
async def login_page(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(
        "shared/login.html", {"request": request, "error": error}
    )

@web_router.post("/ui/login")
async def login_process(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db = Depends(get_database)
):
    user = await db.users.find_one({"email": username})
    if not user or not verify_password(password, user["hashed_password"]):
        return templates.TemplateResponse(
            "shared/login.html", 
            {"request": request, "error": "Email hoặc mật khẩu không chính xác"}
        )
    
    # Tạo token và lưu vào cookie
    access_token = create_access_token(user["_id"], user["role"])
    response = RedirectResponse(url="/ui/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=1800  # 30 phút
    )
    return response

# Route dashboard
@web_router.get("/ui/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    return templates.TemplateResponse(
        "shared/dashboard.html", 
        {"request": request, "user": current_user}
    )

# Route cho phần sinh viên xem lịch thi
@web_router.get("/ui/exams", response_class=HTMLResponse)
async def exams_page(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
):
    # Tìm kiếm student với email của user hiện tại
    student = await db.students.find_one({"email": current_user.email})
    
    if not student:
        return templates.TemplateResponse(
            "shared/error.html", 
            {"request": request, "message": "Không tìm thấy thông tin sinh viên"}
        )
    
    student_id = student.get("student_id")
    exam_details = []
    registered_subjects = []
    
    # Trực tiếp kiểm tra xem có các môn đã đăng ký không
    if "registered_subjects" in student and student["registered_subjects"]:
        # Lấy thông tin về các môn học đã đăng ký
        for subject_code in student.get("registered_subjects", []):
            subject = await db.subjects.find_one({"code": subject_code})
            if subject:
                registered_subjects.append({
                    "code": subject_code,
                    "name": subject.get("name", "Unknown"),
                    "id": str(subject.get("_id"))  # Lưu ID để tìm kiếm kỳ thi
                })
    
        # Tìm kỳ thi dựa trên môn học đã đăng ký
        subject_ids_str = [subject["id"] for subject in registered_subjects]
        subject_ids_obj = [ObjectId(subject["id"]) for subject in registered_subjects]
        
        if subject_ids_str:
            # Lấy lịch thi từ các môn đã đăng ký - tìm cả dạng string và ObjectId
            exams_cursor = db.exams.find({
                "$or": [
                    {"subject_id": {"$in": subject_ids_str}},  # Tìm theo string ID
                    {"subject_id": {"$in": subject_ids_obj}}   # Tìm theo ObjectId
                ]
            }).sort("start_time", 1)
            
            exams = await exams_cursor.to_list(length=100)
            
            # Đảm bảo sinh viên được thêm vào danh sách tham gia kỳ thi
            for exam in exams:
                if "student_ids" not in exam:
                    exam["student_ids"] = []
                    
                if student_id not in exam["student_ids"]:
                    await db.exams.update_one(
                        {"_id": exam["_id"]},
                        {"$push": {"student_ids": student_id}}
                    )
                
                # Lấy thông tin chi tiết
                subject_id = exam.get("subject_id")
                room_id = exam.get("room_id")
                
                # Thử tìm subject bằng cả string và ObjectId
                subject = None
                if isinstance(subject_id, str):
                    # Nếu là string, thử tìm bằng _id là ObjectId hoặc string
                    subject = await db.subjects.find_one({"_id": subject_id})
                    if not subject:
                        try:
                            subject = await db.subjects.find_one({"_id": ObjectId(subject_id)})
                        except:
                            pass
                else:
                    # Nếu không phải string (có thể là ObjectId), tìm trực tiếp
                    subject = await db.subjects.find_one({"_id": subject_id})
                
                # Tương tự với room
                room = None
                if isinstance(room_id, str):
                    room = await db.rooms.find_one({"_id": room_id})
                    if not room:
                        try:
                            room = await db.rooms.find_one({"_id": ObjectId(room_id)})
                        except:
                            pass
                else:
                    room = await db.rooms.find_one({"_id": room_id})
                
                if subject and room:
                    # Lấy thông tin giảng viên coi thi
                    supervisors = []
                    for supervisor_id in exam.get("supervisor_ids", []):
                        # Handle ObjectId if it's an ObjectId
                        if isinstance(supervisor_id, ObjectId):
                            supervisor_id = str(supervisor_id)
                            
                        if isinstance(supervisor_id, str) and supervisor_id.startswith("DEMO_SUPERVISOR"):
                            # Trường hợp giám thị demo
                            supervisors.append({"full_name": f"Giảng viên {supervisor_id.split('_')[-1]}"})
                        else:
                            # First try direct lookup
                            teacher = await db.teachers.find_one({"_id": supervisor_id})
                            if not teacher:
                                # Try to find by converting string to ObjectId
                                try:
                                    teacher = await db.teachers.find_one({"_id": ObjectId(supervisor_id)})
                                except:
                                    pass
                            
                            if teacher:
                                supervisors.append({"full_name": teacher.get("full_name", "Chưa xác định")})
                            else:
                                # Fallback for unknown supervisors
                                supervisors.append({"full_name": f"Giám thị (ID: {supervisor_id})"})
                    
                    # Tính số báo danh cho sinh viên
                    exam_number = None
                    student_ids = exam.get("student_ids", [])
                    if student_id in student_ids:
                        exam_number = student_ids.index(student_id) + 1
                    
                    exam_details.append({
                        "subject_name": subject.get("name", "Unknown"),
                        "subject_code": subject.get("code", "Unknown"),
                        "room": room.get("room_id", "Unknown"),
                        "start_time": exam.get("start_time"),
                        "end_time": exam.get("end_time"),
                        "duration": (exam.get("end_time") - exam.get("start_time")).total_seconds() // 60,
                        "supervisors": supervisors,
                        "exam_number": exam_number
                    })
    
    # Xác định môn nào đã đăng ký nhưng chưa có lịch thi
    subjects_with_exams = {exam["subject_code"] for exam in exam_details}
    subjects_without_exams = [
        subject for subject in registered_subjects 
        if subject["code"] not in subjects_with_exams
    ]
    
    return templates.TemplateResponse(
        "student/exams.html", 
        {
            "request": request, 
            "user": current_user, 
            "student": student,
            "exams": exam_details,
            "registered_subjects": subjects_without_exams
        }
    )

# Route cho xem thông tin cá nhân
@web_router.get("/ui/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
):
    # Nếu là sinh viên, lấy thêm thông tin sinh viên
    student = None
    if current_user.role == "student":
        student = await db.students.find_one({"email": current_user.email})
    
    # Nếu là giáo viên, lấy thêm thông tin giáo viên
    teacher = None
    if current_user.role == "teacher":
        teacher = await db.teachers.find_one({"email": current_user.email})
    
    return templates.TemplateResponse(
        "shared/profile.html", 
        {
            "request": request, 
            "user": current_user,
            "student": student,
            "teacher": teacher
        }
    )

# Route cho xem lịch thi dạng lịch
@web_router.get("/ui/exams/calendar", response_class=HTMLResponse)
async def exams_calendar_page(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
):
    # Tìm kiếm sinh viên
    student = await db.students.find_one({"email": current_user.email})
    
    if not student:
        return templates.TemplateResponse(
            "shared/error.html", 
            {"request": request, "message": "Không tìm thấy thông tin sinh viên"}
        )
    
    student_id = student.get("student_id")
    registered_subjects = []
    
    # Trực tiếp kiểm tra xem có các môn đã đăng ký không
    if "registered_subjects" in student and student["registered_subjects"]:
        # Lấy thông tin về các môn học đã đăng ký
        for subject_code in student.get("registered_subjects", []):
            subject = await db.subjects.find_one({"code": subject_code})
            if subject:
                registered_subjects.append({
                    "code": subject_code,
                    "id": str(subject.get("_id"))  # Lưu ID để tìm kiếm kỳ thi
                })
    
    exam_details = []
    
    # Tìm kỳ thi dựa trên môn học đã đăng ký
    if registered_subjects:
        subject_ids_str = [subject["id"] for subject in registered_subjects]
        subject_ids_obj = [ObjectId(subject["id"]) for subject in registered_subjects]
        
        # Tìm cả dạng string và ObjectId
        exams_cursor = db.exams.find({
            "$or": [
                {"subject_id": {"$in": subject_ids_str}},
                {"subject_id": {"$in": subject_ids_obj}}
            ]
        }).sort("start_time", 1)
        
        exams = await exams_cursor.to_list(length=100)
        
        # Đảm bảo sinh viên được thêm vào danh sách tham gia kỳ thi
        for exam in exams:
            if "student_ids" not in exam:
                exam["student_ids"] = []
                
            if student_id not in exam["student_ids"]:
                await db.exams.update_one(
                    {"_id": exam["_id"]},
                    {"$push": {"student_ids": student_id}}
                )
                
            # Lấy thông tin chi tiết
            subject_id = exam.get("subject_id")
            room_id = exam.get("room_id")
            
            # Try to find subject with both string and ObjectId
            subject = None
            if isinstance(subject_id, str):
                subject = await db.subjects.find_one({"_id": subject_id})
                if not subject:
                    try:
                        subject = await db.subjects.find_one({"_id": ObjectId(subject_id)})
                    except:
                        pass
            else:
                subject = await db.subjects.find_one({"_id": subject_id})
            
            # Similar for room
            room = None
            if isinstance(room_id, str):
                room = await db.rooms.find_one({"_id": room_id})
                if not room:
                    try:
                        room = await db.rooms.find_one({"_id": ObjectId(room_id)})
                    except:
                        pass
            else:
                room = await db.rooms.find_one({"_id": room_id})
                
            if subject and room:
                # Lấy thông tin giảng viên coi thi và số báo danh
                supervisors = []
                for supervisor_id in exam.get("supervisor_ids", []):
                    # Handle ObjectId if it's an ObjectId
                    if isinstance(supervisor_id, ObjectId):
                        supervisor_id = str(supervisor_id)
                        
                    if isinstance(supervisor_id, str) and supervisor_id.startswith("DEMO_SUPERVISOR"):
                        supervisors.append({"full_name": f"Giảng viên {supervisor_id.split('_')[-1]}"})
                    else:
                        # First try direct lookup
                        teacher = await db.teachers.find_one({"_id": supervisor_id})
                        if not teacher:
                            # Try to find by converting string to ObjectId
                            try:
                                teacher = await db.teachers.find_one({"_id": ObjectId(supervisor_id)})
                            except:
                                pass
                        
                        if teacher:
                            supervisors.append({"full_name": teacher.get("full_name", "Chưa xác định")})
                        else:
                            # Fallback for unknown supervisors
                            supervisors.append({"full_name": f"Giám thị (ID: {supervisor_id})"})
                
                # Tính số báo danh cho sinh viên
                exam_number = None
                student_ids = exam.get("student_ids", [])
                if student_id in student_ids:
                    exam_number = student_ids.index(student_id) + 1
                    
                # Danh sách tên giám thị để hiển thị trong lịch
                supervisor_names = ", ".join([s.get("full_name", "") for s in supervisors])
                
                exam_details.append({
                    "id": str(exam.get("_id")),
                    "subject_name": subject.get("name", "Unknown"),
                    "subject_code": subject.get("code", "Unknown"),
                    "room": room.get("room_id", "Unknown"),
                    "start_time": exam.get("start_time"),
                    "end_time": exam.get("end_time"),
                    "duration": (exam.get("end_time") - exam.get("start_time")).total_seconds() // 60,
                    "color": "#" + ''.join([hex(hash(subject.get("code", "")) % 256)[2:].zfill(2) for _ in range(3)])[:6],
                    "supervisors": supervisors,
                    "supervisor_names": supervisor_names,
                    "exam_number": exam_number
                })
    
    return templates.TemplateResponse(
        "student/calendar.html", 
        {
            "request": request, 
            "user": current_user, 
            "student": student,
            "exams": exam_details
        }
    )

# Route quản lý lịch thi cho admin
@web_router.get("/ui/admin/scheduler", response_class=HTMLResponse)
async def admin_scheduler_page(
    request: Request,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
):
    # Lấy thông tin tổng quan
    subjects_count = await db.subjects.count_documents({})
    rooms_count = await db.rooms.count_documents({})
    
    # Lấy thông tin kì thi hiện tại nếu có
    current_period = await db.schedule_configs.find_one({}, sort=[("created_at", -1)])
    
    return templates.TemplateResponse(
        "admin/scheduler.html", 
        {
            "request": request, 
            "user": current_user,
            "subjects_count": subjects_count,
            "rooms_count": rooms_count,
            "current_period": current_period
        }
    )

# Route quản lý môn học cho admin
@web_router.get("/ui/admin/subjects", response_class=HTMLResponse)
async def admin_subjects_page(
    request: Request,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
):
    # Lấy danh sách môn học
    subjects_cursor = db.subjects.find().sort("code", 1)
    subjects = await subjects_cursor.to_list(length=100)
    
    # Chuyển đổi ObjectId sang string
    for subject in subjects:
        if isinstance(subject.get("_id"), ObjectId):
            subject["_id"] = str(subject["_id"])
    
    return templates.TemplateResponse(
        "admin/subjects.html", 
        {
            "request": request, 
            "user": current_user,
            "subjects": subjects
        }
    )

# Route quản lý lớp học cho admin
@web_router.get("/ui/admin/classes", response_class=HTMLResponse)
async def admin_classes_page(
    request: Request,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
):
    # Lấy danh sách lớp học
    classes_cursor = db.classes.find().sort("class_id", 1)
    classes = await classes_cursor.to_list(length=100)
    
    # Chuyển đổi ObjectId sang string
    for class_obj in classes:
        if isinstance(class_obj.get("_id"), ObjectId):
            class_obj["_id"] = str(class_obj["_id"])
    
    # Lấy tổng số lớp và sinh viên
    classes_count = await db.classes.count_documents({})
    students_count = await db.students.count_documents({})
    
    return templates.TemplateResponse(
        "admin/classes.html", 
        {
            "request": request, 
            "user": current_user,
            "classes": classes,
            "classes_count": classes_count,
            "students_count": students_count
        }
    )

# Route quản lý phòng thi cho admin
@web_router.get("/ui/admin/rooms", response_class=HTMLResponse)
async def admin_rooms_page(
    request: Request,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
):
    # Lấy danh sách phòng thi
    rooms_cursor = db.rooms.find().sort("room_id", 1)
    rooms = await rooms_cursor.to_list(length=100)
    
    # Chuyển đổi ObjectId sang string
    for room in rooms:
        if isinstance(room.get("_id"), ObjectId):
            room["_id"] = str(room["_id"])
    
    # Lấy tổng số phòng
    rooms_count = await db.rooms.count_documents({})
    
    # Tính tổng sức chứa
    total_capacity = sum(room.get("capacity", 0) for room in rooms)
    
    return templates.TemplateResponse(
        "admin/rooms.html", 
        {
            "request": request, 
            "user": current_user,
            "rooms": rooms,
            "rooms_count": rooms_count,
            "total_capacity": total_capacity
        }
    )

# Route quản lý người dùng cho admin
@web_router.get("/ui/admin/users", response_class=HTMLResponse)
async def admin_users_page(
    request: Request,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
):
    # Lấy danh sách người dùng
    users_cursor = db.users.find().sort("email", 1)
    users = await users_cursor.to_list(length=100)
    
    # Chuyển đổi ObjectId sang string
    for user in users:
        if isinstance(user.get("_id"), ObjectId):
            user["_id"] = str(user["_id"])
    
    # Tổng số người dùng theo role
    admin_count = sum(1 for user in users if user.get("role") == "admin")
    teacher_count = sum(1 for user in users if user.get("role") == "teacher")
    student_count = sum(1 for user in users if user.get("role") == "student")
    
    return templates.TemplateResponse(
        "admin/users.html", 
        {
            "request": request, 
            "user": current_user,
            "users": users,
            "admin_count": admin_count,
            "teacher_count": teacher_count,
            "student_count": student_count
        }
    )

# Route quản lý lịch thi đã tạo cho admin
@web_router.get("/ui/admin/exams", response_class=HTMLResponse)
async def admin_exams_page(
    request: Request,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Retrieve and display all exams for admin"""
    # Get all scheduled exams
    exams_cursor = db.exams.find().sort("start_time", 1)
    exams = await prepare_mongodb_docs(exams_cursor)
    
    # Get detailed information about each exam
    exam_details = []
    for exam in exams:
        try:
            # Get subject and room info
            subject_id = exam.get("subject_id")
            room_id = exam.get("room_id")
            
            # Handle both string IDs and ObjectId strings
            subject = await db.subjects.find_one({"_id": subject_id})
            if not subject and isinstance(subject_id, str):
                try:
                    # Try with ObjectId
                    obj_id = ObjectId(subject_id)
                    subject = await db.subjects.find_one({"_id": obj_id})
                except:
                    pass
            
            # Similarly for room
            room = await db.rooms.find_one({"_id": room_id})
            if not room and isinstance(room_id, str):
                try:
                    # Try with ObjectId
                    obj_id = ObjectId(room_id)
                    room = await db.rooms.find_one({"_id": obj_id})
                except:
                    pass
            
            if not subject or not room:
                # Skip exams with missing subject or room
                continue
            
            # Process subject and room data
            subject = prepare_mongodb_doc(subject)
            room = prepare_mongodb_doc(room)
            
            # Get supervisors info
            supervisors = []
            for supervisor_id in exam.get("supervisor_ids", []):
                # Handle demo supervisors
                if isinstance(supervisor_id, str) and supervisor_id.startswith("DEMO_SUPERVISOR"):
                    supervisors.append({"full_name": f"Giám thị {supervisor_id.split('_')[-1]}"})
                    continue
                
                # Try to find teacher
                teacher = await db.teachers.find_one({"_id": supervisor_id})
                if not teacher and isinstance(supervisor_id, str):
                    try:
                        obj_id = ObjectId(supervisor_id)
                        teacher = await db.teachers.find_one({"_id": obj_id})
                    except:
                        pass
                
                if teacher:
                    teacher = prepare_mongodb_doc(teacher)
                    supervisors.append({"full_name": teacher.get("full_name", "Chưa xác định")})
                else:
                    # Fallback
                    supervisors.append({"full_name": f"Giám thị (ID: {supervisor_id})"})
            
            # Add to exam details
            exam_details.append({
                "id": exam.get("id"),
                "subject_name": subject.get("name", "Unknown"),
                "subject_code": subject.get("code", "Unknown"),
                "room_id": room.get("room_id", "Unknown"),
                "capacity": room.get("capacity", 0),
                "start_time": exam.get("start_time"),
                "end_time": exam.get("end_time"),
                "duration": (exam.get("end_time") - exam.get("start_time")).total_seconds() // 60,
                "supervisors": supervisors,
                "student_count": len(exam.get("student_ids", [])),
                "max_students": exam.get("max_students", 0)
            })
        except Exception as e:
            # Log error and continue
            print(f"Error processing exam {exam.get('id')}: {str(e)}")
    
    # Get stats
    total_exams = len(exam_details)
    total_student_slots = sum(exam.get("student_count", 0) for exam in exam_details)
    upcoming_exams = sum(1 for exam in exam_details if exam.get("start_time") > datetime.utcnow())
    
    # Get subjects and rooms for filtering
    subjects_cursor = db.subjects.find()
    subjects = await prepare_mongodb_docs(subjects_cursor)
    
    rooms_cursor = db.rooms.find()
    rooms = await prepare_mongodb_docs(rooms_cursor)
    
    return templates.TemplateResponse(
        "admin/exams.html", 
        {
            "request": request, 
            "user": current_user,
            "exams": exam_details,
            "total_exams": total_exams,
            "total_student_slots": total_student_slots,
            "upcoming_exams": upcoming_exams,
            "subjects": subjects,
            "rooms": rooms,
            "now": datetime.utcnow()
        }
    )

# Route quản lý giám thị cho admin
@web_router.get("/ui/admin/supervisors", response_class=HTMLResponse)
async def admin_supervisors_page(
    request: Request,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
):
    # Lấy danh sách giám thị
    teachers_cursor = db.teachers.find().sort("teacher_id", 1)
    teachers = await teachers_cursor.to_list(length=100)
    
    # Chuyển đổi ObjectId sang string
    for teacher in teachers:
        if isinstance(teacher.get("_id"), ObjectId):
            teacher["_id"] = str(teacher["_id"])
        
        # Đếm số lần giám thị được phân công
        teacher["exam_count"] = await db.exams.count_documents({"supervisor_ids": teacher["_id"]})
    
    return templates.TemplateResponse(
        "admin/supervisors.html", 
        {
            "request": request, 
            "user": current_user,
            "teachers": teachers
        }
    )

# Route quản lý nhập dữ liệu cho admin
@web_router.get("/ui/admin/import", response_class=HTMLResponse)
async def admin_import_page(
    request: Request,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
):
    return templates.TemplateResponse(
        "admin/import.html", 
        {"request": request, "user": current_user}
    )

# Route for database browser (admin only)
@web_router.get("/ui/admin/database", response_class=HTMLResponse)
async def admin_database_page(
    request: Request,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
):
    """Database browser interface for admins"""
    return templates.TemplateResponse(
        "admin/database.html", 
        {"request": request, "user": current_user}
    )

# Route đăng xuất
@web_router.get("/ui/logout")
async def logout():
    response = RedirectResponse(url="/ui/login")
    response.delete_cookie("access_token")
    return response

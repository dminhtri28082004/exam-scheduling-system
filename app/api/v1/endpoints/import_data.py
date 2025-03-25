from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from typing import Any, Dict, List
import pandas as pd
from io import BytesIO
from bson.objectid import ObjectId
import logging
from datetime import datetime

from app.db.database import get_database
from app.models.domain.user import User
from app.models.domain.student import StudentInDB
from app.models.domain.teacher import TeacherInDB
from app.models.domain.subject import SubjectInDB
from app.models.domain.room import RoomInDB
from app.core.auth import check_admin_permission

router = APIRouter()

@router.post("/excel", status_code=status.HTTP_200_OK)
async def import_excel_data(
    file: UploadFile = File(...),
    clear_existing: bool = Form(False, description="Clear all existing data before import"),
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    Import data from Excel file with sheets: students, subjects, teachers, rooms, and classes.
    Only admin users can use this endpoint.
    """
    if not file.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Please upload an Excel file."
        )
    
    try:
        # Read Excel file
        contents = await file.read()
        excel_data = BytesIO(contents)
        
        # Get all sheet names
        xls = pd.ExcelFile(excel_data)
        sheet_names = xls.sheet_names
        
        # Clear existing data if requested
        if clear_existing:
            logging.warning("Clearing all existing data before import")
            if 'sinh viên' in sheet_names:
                await db.students.delete_many({})
            if 'môn thi' in sheet_names:
                await db.subjects.delete_many({})
            if 'giảng viên' in sheet_names:
                await db.teachers.delete_many({})
            if 'phòng thi' in sheet_names:
                await db.rooms.delete_many({})
            if 'lớp học' in sheet_names:
                await db.classes.delete_many({})
        
        # Import data from each available sheet
        students_count = 0
        subjects_count = 0
        teachers_count = 0
        rooms_count = 0
        classes_count = 0
        
        if 'sinh viên' in sheet_names:
            students_df = pd.read_excel(excel_data, sheet_name='sinh viên')
            students_count = await import_students(students_df, db)
        
        if 'môn thi' in sheet_names:
            subjects_df = pd.read_excel(excel_data, sheet_name='môn thi')
            subjects_count = await import_subjects(subjects_df, db)
        
        if 'giảng viên' in sheet_names:
            teachers_df = pd.read_excel(excel_data, sheet_name='giảng viên')
            teachers_count = await import_teachers(teachers_df, db)
        
        if 'phòng thi' in sheet_names:
            rooms_df = pd.read_excel(excel_data, sheet_name='phòng thi')
            rooms_count = await import_rooms(rooms_df, db)
            
        if 'lớp học' in sheet_names:
            classes_df = pd.read_excel(excel_data, sheet_name='lớp học')
            classes_count = await import_classes(classes_df, db)
        
        return {
            "message": "Data imported successfully",
            "imported_data": {
                "students": students_count,
                "subjects": subjects_count,
                "teachers": teachers_count,
                "rooms": rooms_count,
                "classes": classes_count
            }
        }
    
    except Exception as e:
        logging.error(f"Error importing data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error importing data: {str(e)}"
        )

@router.get("/template", response_class=StreamingResponse)
async def create_excel_template(
    current_user: User = Depends(check_admin_permission),
) -> Any:
    """
    Create and download an Excel template for data import.
    The template includes sheets for students, subjects, teachers, rooms, and classes.
    """
    try:
        # Create a BytesIO object to store the Excel file
        output = BytesIO()
        
        # Create Excel writer
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            workbook = writer.book
            
            # Create a format for headers
            header_format = workbook.add_format({
                'bold': True,
                'font_color': 'white',
                'bg_color': '#4F81BD',
                'border': 1
            })
            
            # Create Students template
            students_df = pd.DataFrame({
                'mã sinh viên': ['SV001', 'SV002'],
                'tên sinh viên': ['Nguyễn Văn A', 'Trần Thị B'],
                'giới tính': ['Nam', 'Nữ'],
                'lớp': ['L01', 'L02'],
                'gmail': ['sinhvien.a@example.com', 'sinhvien.b@example.com'],
                'danh sách môn đăng kí': ['MON001,MON002', 'MON001,MON003']
            })
            students_df.to_excel(writer, sheet_name='sinh viên', index=False)
            
            # Format students sheet
            students_sheet = writer.sheets['sinh viên']
            for col_num, value in enumerate(students_df.columns.values):
                students_sheet.write(0, col_num, value, header_format)
                students_sheet.set_column(col_num, col_num, 18)
            
            # Create Subjects template
            subjects_df = pd.DataFrame({
                'mã môn': ['MON001', 'MON002', 'MON003'],
                'tên môn': ['Lập trình Python', 'Cơ sở dữ liệu', 'Mạng máy tính'],
                'thời lượng thi (phút)': [90, 120, 90],
                'danh sách sinh viên đăng kí môn': ['SV001,SV002', 'SV001', 'SV002']
            })
            subjects_df.to_excel(writer, sheet_name='môn thi', index=False)
            
            # Format subjects sheet
            subjects_sheet = writer.sheets['môn thi']
            for col_num, value in enumerate(subjects_df.columns.values):
                subjects_sheet.write(0, col_num, value, header_format)
                subjects_sheet.set_column(col_num, col_num, 20)
            
            # Create Teachers template
            teachers_df = pd.DataFrame({
                'mã giảng viên': ['GV001', 'GV002'],
                'tên giảng viên': ['Nguyễn Văn X', 'Trần Thị Y'],
                'gmail': ['giangvien.x@example.com', 'giangvien.y@example.com']
            })
            teachers_df.to_excel(writer, sheet_name='giảng viên', index=False)
            
            # Format teachers sheet
            teachers_sheet = writer.sheets['giảng viên']
            for col_num, value in enumerate(teachers_df.columns.values):
                teachers_sheet.write(0, col_num, value, header_format)
                teachers_sheet.set_column(col_num, col_num, 18)
            
            # Create Rooms template
            rooms_df = pd.DataFrame({
                'mã phòng thi': ['P001', 'P002', 'P003'],
                'sức chứa': [30, 40, 50],
                'tòa nhà': ['Tòa A', 'Tòa B', 'Tòa B'],
                'tên phòng': ['Phòng 101', 'Phòng 202', 'Phòng 303']
            })
            rooms_df.to_excel(writer, sheet_name='phòng thi', index=False)
            
            # Format rooms sheet
            rooms_sheet = writer.sheets['phòng thi']
            for col_num, value in enumerate(rooms_df.columns.values):
                rooms_sheet.write(0, col_num, value, header_format)
                rooms_sheet.set_column(col_num, col_num, 15)
            
            # Create Classes template
            classes_df = pd.DataFrame({
                'mã lớp': ['L01', 'L02'],
                'tên lớp': ['Lớp CNTT-01', 'Lớp CNTT-02'],
                'khoa bộ môn': ['CNTT', 'CNTT'],
                'khóa': [2020, 2020]
            })
            classes_df.to_excel(writer, sheet_name='lớp học', index=False)
            
            # Format classes sheet
            classes_sheet = writer.sheets['lớp học']
            for col_num, value in enumerate(classes_df.columns.values):
                classes_sheet.write(0, col_num, value, header_format)
                classes_sheet.set_column(col_num, col_num, 15)
            
            # Add instructions sheet
            instructions = [
                ["Hướng dẫn nhập dữ liệu:"],
                [""],
                ["1. Sinh viên: Mã sinh viên là bắt buộc và không được trùng lặp. Danh sách môn đăng ký có thể để trống hoặc là danh sách mã môn ngăn cách bởi dấu phẩy."],
                ["2. Môn thi: Mã môn là bắt buộc và không được trùng lặp. Thời lượng thi phải là số phút."],
                ["3. Giảng viên: Mã giảng viên là bắt buộc và không được trùng lặp."],
                ["4. Phòng thi: Mã phòng thi là bắt buộc và không được trùng lặp. Sức chứa phải là số nguyên dương."],
                ["5. Lớp học: Mã lớp là bắt buộc và không được trùng lặp."],
                [""],
                ["Lưu ý: Không thay đổi tên các sheet và cột dữ liệu."]
            ]
            instructions_df = pd.DataFrame(instructions)
            instructions_df.to_excel(writer, sheet_name='hướng dẫn', index=False, header=False)
            
            # Format instructions sheet
            instructions_sheet = writer.sheets['hướng dẫn']
            instructions_sheet.set_column(0, 0, 100)
            
        # Reset file pointer to beginning
        output.seek(0)
        
        # Return the Excel file as a downloadable response
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=import_template.xlsx"}
        )
    
    except Exception as e:
        logging.error(f"Error creating template: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating template: {str(e)}"
        )

async def import_students(df: pd.DataFrame, db) -> int:
    """Import students data to the database"""
    count = 0
    for _, row in df.iterrows():
        try:
            # Extract and handle registered subjects (may be separated by commas or as a list)
            registered_subjects = []
            if not pd.isna(row.get('danh sách môn đăng kí', '')):
                if isinstance(row['danh sách môn đăng kí'], str):
                    registered_subjects = [s.strip() for s in row['danh sách môn đăng kí'].split(',')]
                elif isinstance(row['danh sách môn đăng kí'], list):
                    registered_subjects = row['danh sách môn đăng kí']
            
            # Check if student already exists
            existing = await db.students.find_one({"student_id": row['mã sinh viên']})
            if existing:
                # Update existing student
                await db.students.update_one(
                    {"student_id": row['mã sinh viên']},
                    {"$set": {
                        "full_name": row['tên sinh viên'],
                        "gender": row['giới tính'],
                        "class_name": row['lớp'],
                        "email": row['gmail'],
                        "registered_subjects": registered_subjects,
                        "updated_at": datetime.utcnow()
                    }}
                )
            else:
                # Create new student
                student_data = StudentInDB(
                    id=str(ObjectId()),
                    student_id=row['mã sinh viên'],
                    full_name=row['tên sinh viên'],
                    gender=row['giới tính'],
                    class_name=row['lớp'],
                    email=row['gmail'],
                    registered_subjects=registered_subjects
                )
                
                await db.students.insert_one(student_data.dict(by_alias=True))
            
            count += 1
        except Exception as e:
            logging.error(f"Error importing student {row.get('mã sinh viên', 'unknown')}: {str(e)}")
            continue
    
    return count

async def import_subjects(df: pd.DataFrame, db) -> int:
    """Import subjects data to the database"""
    count = 0
    for _, row in df.iterrows():
        try:
            # Extract and handle registered students (may be separated by commas or as a list)
            registered_students = []
            if not pd.isna(row.get('danh sách sinh viên đăng kí môn', '')):
                if isinstance(row['danh sách sinh viên đăng kí môn'], str):
                    registered_students = [s.strip() for s in row['danh sách sinh viên đăng kí môn'].split(',')]
                elif isinstance(row['danh sách sinh viên đăng kí môn'], list):
                    registered_students = row['danh sách sinh viên đăng kí môn']
            
            # Check if subject already exists
            existing = await db.subjects.find_one({"code": row['mã môn']})
            if existing:
                # Update existing subject
                await db.subjects.update_one(
                    {"code": row['mã môn']},
                    {"$set": {
                        "name": row['tên môn'],
                        "duration": row['thời lượng thi (phút)'],
                        "registered_students": registered_students,
                        "updated_at": datetime.utcnow()
                    }}
                )
            else:
                # Create new subject
                subject_data = SubjectInDB(
                    id=str(ObjectId()),
                    code=row['mã môn'],
                    name=row['tên môn'],
                    duration=row['thời lượng thi (phút)'],
                    registered_students=registered_students
                )
                
                await db.subjects.insert_one(subject_data.dict(by_alias=True))
            
            count += 1
        except Exception as e:
            logging.error(f"Error importing subject {row.get('mã môn', 'unknown')}: {str(e)}")
            continue
    
    return count

async def import_teachers(df: pd.DataFrame, db) -> int:
    """Import teachers data to the database"""
    count = 0
    for _, row in df.iterrows():
        try:
            # Check if teacher already exists
            existing = await db.teachers.find_one({"teacher_id": row['mã giảng viên']})
            if existing:
                # Update existing teacher
                await db.teachers.update_one(
                    {"teacher_id": row['mã giảng viên']},
                    {"$set": {
                        "full_name": row['tên giảng viên'],
                        "email": row['gmail'],
                        "updated_at": datetime.utcnow()
                    }}
                )
            else:
                # Create new teacher
                teacher_data = TeacherInDB(
                    id=str(ObjectId()),
                    teacher_id=row['mã giảng viên'],
                    full_name=row['tên giảng viên'],
                    email=row['gmail']
                )
                
                await db.teachers.insert_one(teacher_data.dict(by_alias=True))
            
            count += 1
        except Exception as e:
            logging.error(f"Error importing teacher {row.get('mã giảng viên', 'unknown')}: {str(e)}")
            continue
    
    return count

async def import_rooms(df: pd.DataFrame, db) -> int:
    """Import rooms data to the database"""
    count = 0
    for _, row in df.iterrows():
        try:
            # Check if room already exists
            existing = await db.rooms.find_one({"room_id": row['mã phòng thi']})
            
            # Prepare data dict with optional fields
            room_data = {
                "room_id": row['mã phòng thi'],
                "capacity": row['sức chứa']
            }
            
            # Add optional fields if they exist in the DataFrame
            if 'tòa nhà' in row and not pd.isna(row['tòa nhà']):
                room_data["building"] = row['tòa nhà']
            
            if 'tên phòng' in row and not pd.isna(row['tên phòng']):
                room_data["name"] = row['tên phòng']
            
            if existing:
                # Update existing room
                room_data["updated_at"] = datetime.utcnow()
                await db.rooms.update_one(
                    {"room_id": row['mã phòng thi']},
                    {"$set": room_data}
                )
            else:
                # Create new room
                room_data["id"] = str(ObjectId())
                room_data["created_at"] = datetime.utcnow()
                room_data["updated_at"] = datetime.utcnow()
                
                await db.rooms.insert_one(room_data)
            
            count += 1
        except Exception as e:
            logging.error(f"Error importing room {row.get('mã phòng thi', 'unknown')}: {str(e)}")
            continue
    
    return count

async def import_classes(df: pd.DataFrame, db) -> int:
    """Import classes data to the database"""
    count = 0
    for _, row in df.iterrows():
        try:
            # Check if class already exists
            existing = await db.classes.find_one({"class_id": row['mã lớp']})
            
            # Count students in this class
            student_count = await db.students.count_documents({"class_name": row['mã lớp']})
            
            if existing:
                # Update existing class
                await db.classes.update_one(
                    {"class_id": row['mã lớp']},
                    {"$set": {
                        "name": row['tên lớp'],
                        "department": row.get('khoa bộ môn'),
                        "year": int(row['khóa']) if pd.notna(row.get('khóa')) else None,
                        "student_count": student_count,
                        "updated_at": datetime.utcnow()
                    }}
                )
            else:
                # Create new class
                class_data = {
                    "_id": str(ObjectId()),
                    "class_id": row['mã lớp'],
                    "name": row['tên lớp'],
                    "department": row.get('khoa bộ môn'),
                    "year": int(row['khóa']) if pd.notna(row.get('khóa')) else None,
                    "student_count": student_count,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
                
                await db.classes.insert_one(class_data)
            
            count += 1
        except Exception as e:
            logging.error(f"Error importing class {row.get('mã lớp', 'unknown')}: {str(e)}")
            continue
    
    return count

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
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
            if existing:
                # Update existing room
                await db.rooms.update_one(
                    {"room_id": row['mã phòng thi']},
                    {"$set": {
                        "capacity": row['sức chứa'],
                        "updated_at": datetime.utcnow()
                    }}
                )
            else:
                # Create new room
                room_data = RoomInDB(
                    id=str(ObjectId()),
                    room_id=row['mã phòng thi'],
                    capacity=row['sức chứa']
                )
                
                await db.rooms.insert_one(room_data.dict(by_alias=True))
            
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

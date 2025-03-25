import asyncio
import argparse
from bson.objectid import ObjectId
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from getpass import getpass
import re
import os
from dotenv import load_dotenv

from app.core.security import get_password_hash
from app.models.user import UserRole

# Load environment variables
load_dotenv()

# Email validation regex
email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

async def create_student_user(student_id, email, full_name, password, mongodb_url, db_name):
    """
    Tạo tài khoản student và liên kết với thông tin sinh viên trong database
    """
    # Kết nối đến MongoDB
    client = AsyncIOMotorClient(mongodb_url)
    db = client[db_name]
    
    # Kiểm tra email hợp lệ
    if not email_regex.match(email):
        print("Error: Invalid email format")
        return False
    
    # Kiểm tra nếu user đã tồn tại
    existing_user = await db.users.find_one({"email": email})
    if existing_user:
        print(f"Tài khoản với email {email} đã tồn tại.")
        return False
    
    # Kiểm tra nếu student_id đã tồn tại
    existing_student = await db.students.find_one({"student_id": student_id})
    
    # Tạo tài khoản người dùng mới
    user_data = {
        "_id": str(ObjectId()),
        "email": email,
        "full_name": full_name,
        "hashed_password": get_password_hash(password),
        "role": "student",  # Đặt role là student
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Thêm vào collection users
    user_result = await db.users.insert_one(user_data)
    
    if not user_result.inserted_id:
        print("Không thể tạo tài khoản user.")
        return False
    
    # Nếu sinh viên đã tồn tại, cập nhật email
    if existing_student:
        await db.students.update_one(
            {"student_id": student_id},
            {"$set": {
                "email": email,
                "updated_at": datetime.utcnow()
            }}
        )
        print(f"Đã liên kết tài khoản với sinh viên {student_id} đã tồn tại.")
    else:
        # Nếu không tồn tại, tạo mới thông tin sinh viên
        student_data = {
            "_id": str(ObjectId()),
            "student_id": student_id,
            "full_name": full_name,
            "email": email,
            "gender": "Không xác định",  # Giá trị mặc định
            "class_name": "Chưa cập nhật",  # Giá trị mặc định
            "registered_subjects": [],  # Không có môn đăng ký mặc định
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        student_result = await db.students.insert_one(student_data)
        if not student_result.inserted_id:
            print("Đã tạo tài khoản, nhưng không thể tạo hồ sơ sinh viên.")
            return False
        
        print(f"Đã tạo mới hồ sơ sinh viên {student_id}.")
    
    print(f"Tạo tài khoản sinh viên {email} thành công!")
    return True

async def main():
    parser = argparse.ArgumentParser(description="Tạo tài khoản sinh viên cho hệ thống lịch thi")
    parser.add_argument("--student-id", help="Mã số sinh viên")
    parser.add_argument("--email", help="Địa chỉ email sinh viên")
    parser.add_argument("--name", help="Họ và tên sinh viên")
    parser.add_argument("--mongodb-url", default=os.getenv("MONGODB_URL", "mongodb://localhost:27017"),
                        help="MongoDB connection URL")
    parser.add_argument("--db-name", default=os.getenv("MONGODB_DB", "exam_scheduler"),
                        help="MongoDB database name")
    
    args = parser.parse_args()
    
    # Nhập mã sinh viên
    student_id = args.student_id
    if not student_id:
        student_id = input("Nhập mã số sinh viên: ")
    
    # Nhập email
    email = args.email
    if not email:
        email = input("Nhập địa chỉ email sinh viên: ")
    
    # Nhập họ tên
    full_name = args.name
    if not full_name:
        full_name = input("Nhập họ và tên sinh viên: ")
    
    # Nhập và xác nhận mật khẩu
    password = getpass("Nhập mật khẩu: ")
    confirm_password = getpass("Xác nhận mật khẩu: ")
    
    if password != confirm_password:
        print("Lỗi: Mật khẩu xác nhận không khớp")
        return
    
    if len(password) < 8:
        print("Lỗi: Mật khẩu phải có ít nhất 8 ký tự")
        return
    
    await create_student_user(student_id, email, full_name, password, args.mongodb_url, args.db_name)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

async def check_users():
    # Kết nối đến MongoDB
    client = AsyncIOMotorClient(os.getenv("MONGODB_URL", "mongodb://localhost:27017"))
    db = client[os.getenv("MONGODB_DB", "exam_scheduler")]
    
    # Hiển thị danh sách người dùng
    users = await db.users.find().to_list(length=100)
    print(f"Tìm thấy {len(users)} người dùng:")
    
    for user in users:
        print(f"ID: {user['_id']}")
        print(f"Email: {user['email']}")
        print(f"Role: {user['role']}")
        print(f"Is Active: {user.get('is_active', False)}")
        print("-" * 30)

if __name__ == "__main__":
    asyncio.run(check_users())

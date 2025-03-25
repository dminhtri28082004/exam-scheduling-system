from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings  # Update import path to use the new location
import logging

# Khởi tạo biến toàn cục
client = None
db = None

async def get_database():
    """
    Trả về đối tượng database. Nếu chưa kết nối, thử kết nối trước.
    """
    if db is None:
        await connect_to_mongo()
    return db

async def connect_to_mongo():
    """Connect to MongoDB database."""
    global client, db
    try:
        logging.info(f"Connecting to MongoDB at {settings.MONGODB_URL}")
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.MONGODB_DB]
        
        # Kiểm tra kết nối
        await client.admin.command('ping')
        logging.info("Successfully connected to MongoDB")
    except Exception as e:
        logging.error(f"Could not connect to MongoDB: {e}")
        raise e
    
async def close_mongo_connection():
    """Close MongoDB connection."""
    global client
    if client:
        logging.info("Closing MongoDB connection")
        client.close()

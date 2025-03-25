from pydantic_settings import BaseSettings
from typing import Optional
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings(BaseSettings):
    # API information
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Hệ thống lập lịch thi"
    PROJECT_DESCRIPTION: str = "Hệ thống lập lịch thi tự động cho trường đại học"
    VERSION: str = "1.0.0"
    
    # MongoDB settings
    MONGODB_URL: str = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
    MONGODB_DB: str = os.getenv("MONGODB_DB", "exam_scheduler")
    
    # JWT Authentication
    SECRET_KEY: str = os.getenv("SECRET_KEY", "yoursecretkey")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Additional settings
    STATIC_DIR: str = "app/static"
    TEMPLATES_DIR: str = "app/templates"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        from_attributes = True  # This is the new name for orm_mode in Pydantic v2

# Create global settings object
settings = Settings()

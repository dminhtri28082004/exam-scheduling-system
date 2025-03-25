from fastapi import FastAPI
import logging
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
from pathlib import Path

from app.api.v1.router import api_router
from app.web.router import web_router
from app.core.config import settings
from app.db.database import connect_to_mongo, close_mongo_connection

# Thiết lập logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Tạo thư mục templates và static nếu chưa tồn tại
templates_dir = Path("app/templates")
static_dir = Path("app/static")
templates_dir.mkdir(exist_ok=True)
static_dir.mkdir(exist_ok=True)

# Ensure static directories exist
static_dir = Path("app/static")
css_dir = static_dir / "css"
js_dir = static_dir / "js"
static_dir.mkdir(exist_ok=True)
css_dir.mkdir(exist_ok=True)
js_dir.mkdir(exist_ok=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION
)

# Mount static files with correct directory
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Thêm sự kiện startup và shutdown
@app.on_event("startup")
async def startup_db_client():
    logging.info("Starting up database connection")
    await connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_db_client():
    logging.info("Shutting down database connection")
    await close_mongo_connection()

# Include API router
app.include_router(api_router, prefix="/api/v1")

# Include Web router (HTML frontend)
app.include_router(web_router)

@app.get("/")
async def root():
    return {"message": "Welcome to Exam Scheduler API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

from fastapi import APIRouter
from app.api.v1.endpoints import users, auth, exams, subjects, rooms, import_data, scheduler, dashboard, classes, teachers

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(exams.router, prefix="/exams", tags=["exams"])
api_router.include_router(subjects.router, prefix="/subjects", tags=["subjects"])
api_router.include_router(rooms.router, prefix="/rooms", tags=["rooms"])
api_router.include_router(classes.router, prefix="/classes", tags=["classes"])
api_router.include_router(import_data.router, prefix="/import", tags=["data-import"])
api_router.include_router(scheduler.router, prefix="/scheduler", tags=["exam-scheduler"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(teachers.router, prefix="/teachers", tags=["teachers"])

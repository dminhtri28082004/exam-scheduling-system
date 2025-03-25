from fastapi import Depends, HTTPException, status, Cookie, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from typing import Optional
import logging
from bson.objectid import ObjectId

from app.db.database import get_database
from app.models.domain.user import TokenPayload, User, UserRole
from app.core.config import settings

# Sử dụng OAuth2 để xác thực
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

# Hàm để lấy token từ cookie hoặc header
async def get_token(
    request: Request,
    access_token: Optional[str] = Cookie(None)
) -> str:
    # Nếu có cookie, sử dụng cookie
    if (access_token and access_token.startswith("Bearer ")):
        return access_token.replace("Bearer ", "")
    
    # Nếu không, thử lấy từ Authorization header
    auth_header = request.headers.get("Authorization")
    if (auth_header and auth_header.startswith("Bearer ")):
        return auth_header.replace("Bearer ", "")
    
    # Nếu không có cả hai, báo lỗi
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )

# Hàm để lấy thông tin người dùng từ token
async def get_current_user(
    token: str = Depends(get_token),
    db = Depends(get_database)
) -> User:
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
        user_id = token_data.sub
        logging.info(f"Extracted user ID from token: {user_id}")
    except (JWTError, ValidationError) as e:
        logging.error(f"Token validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể xác thực thông tin đăng nhập",
        )
    
    # Try multiple ways to find the user
    user = None
    
    # Try 1: Direct lookup with string ID
    user = await db.users.find_one({"_id": user_id})
    
    # Try 2: Look for 'id' field instead of '_id'
    if not user:
        user = await db.users.find_one({"id": user_id})
    
    # Try 3: Convert to ObjectId if possible and try again
    if not user and len(user_id) == 24:
        try:
            obj_id = ObjectId(user_id)
            user = await db.users.find_one({"_id": obj_id})
        except Exception as e:
            logging.error(f"Failed to convert ID to ObjectId: {str(e)}")
    
    if not user:
        # Log actual database content for debugging
        try:
            total_users = await db.users.count_documents({})
            logging.error(f"User not found. ID: {user_id}, Total users in DB: {total_users}")
            
            # If there are users, log a sample for debugging
            if total_users > 0:
                sample_user = await db.users.find_one({})
                logging.error(f"Sample user structure: {sample_user}")
        except Exception as e:
            logging.error(f"Error while checking database: {str(e)}")
            
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    # Ensure id field exists for Pydantic model
    if "id" not in user:
        user["id"] = str(user["_id"])
    
    return User(**user)

# Hàm để lấy thông tin người dùng hiện tại
async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Người dùng không hoạt động")
    return current_user

# Hàm để kiểm tra quyền admin
def check_admin_permission(current_user: User = Depends(get_current_active_user)):
    if current_user.role != UserRole.ADMIN:
        logging.warning(f"Người dùng {current_user.email} có vai trò {current_user.role} đã cố gắng truy cập điểm cuối chỉ dành cho quản trị viên")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không đủ quyền. Yêu cầu vai trò quản trị viên."
        )
    return current_user

# Hàm để kiểm tra quyền giáo viên
def check_teacher_permission(current_user: User = Depends(get_current_active_user)):
    if current_user.role not in [UserRole.ADMIN, UserRole.TEACHER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không đủ quyền"
        )
    return current_user

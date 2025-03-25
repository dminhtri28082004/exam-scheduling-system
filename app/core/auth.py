from fastapi import Depends, HTTPException, status, Cookie, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from typing import Optional
import logging
from bson.objectid import ObjectId  # Add this import

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
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể xác thực thông tin đăng nhập",
        )
    
    # Try to find user by _id as string first
    user = await db.users.find_one({"_id": token_data.sub})
    
    # If not found, try to find using ObjectId
    if not user:
        try:
            # Try to convert string to ObjectId and search again
            obj_id = ObjectId(token_data.sub)
            user = await db.users.find_one({"_id": obj_id})
        except:
            # If conversion fails or user still not found
            pass
    
    if not user:
        # If still not found, log details for debugging
        logging.error(f"User not found with ID: {token_data.sub}")
        # Check if any users exist at all
        total_users = await db.users.count_documents({})
        logging.info(f"Total users in database: {total_users}")
        
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
    
    # Ánh xạ _id sang id để phù hợp với Pydantic model
    user["id"] = str(user["_id"]) if isinstance(user["_id"], ObjectId) else user["_id"]
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

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Any, Dict

from app.core.security import verify_password, create_access_token
from app.db.database import get_database
from app.models.domain.user import Token, User
from app.core.auth import get_current_active_user
from app.models.domain.user import UserRole

router = APIRouter()

@router.post("/login", response_model=Token)
async def login_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_database)
) -> Any:
    """Đăng nhập bằng mã thông báo tương thích OAuth2, nhận mã thông báo truy cập cho các yêu cầu trong tương lai"""
    user = await db.users.find_one({"email": form_data.username})
    if not user: # Không tìm thấy người dùng
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )
    
    if not verify_password(form_data.password, user["hashed_password"]): # Mật khẩu không đúng
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng"
        )
    
    # Tạo mã thông báo truy cập
    return {
        "access_token": create_access_token(user["_id"], user["role"]),
        "token_type": "bearer",
    }

@router.get("/check-admin", response_model=Dict[str, Any])
async def check_admin_access(current_user: User = Depends(get_current_active_user)):
    """Check if current user has admin access"""
    is_admin = current_user.role == UserRole.ADMIN
    return {
        "is_admin": is_admin,
        "user_id": current_user.id,
        "email": current_user.email,
        "role": current_user.role
    }

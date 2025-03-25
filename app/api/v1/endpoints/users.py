from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Any, Dict
from bson.objectid import ObjectId
from datetime import datetime

from app.db.database import get_database
from app.models.domain.user import User, UserCreate, UserInDB
from app.core.security import get_password_hash, verify_password
from app.core.auth import get_current_active_user, check_admin_permission

router = APIRouter()

@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Create new user (admin only)"""
    user = await db.users.find_one({"email": user_in.email})
    if user:
        raise HTTPException(
            status_code=400,
            detail="A user with this email already exists",
        )
    
    # Generate a new ObjectId as string
    user_id = str(ObjectId())
    
    # Create user data with consistent ID field
    user_data = UserInDB(
        **user_in.dict(exclude={"password"}),
        id=user_id,
        hashed_password=get_password_hash(user_in.password)
    )
    
    # Ensure _id is set to the same value as id for consistency
    user_dict = user_data.dict(by_alias=True)
    user_dict["_id"] = user_id
    
    await db.users.insert_one(user_dict)
    return user_data

@router.get("/", response_model=List[User])
async def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Retrieve users (admin only)"""
    users_cursor = db.users.find().skip(skip).limit(limit)
    users = await users_cursor.to_list(length=limit)
    
    # Ánh xạ _id sang id cho mỗi người dùng
    for user in users:
        user["id"] = user["_id"]
    
    return users

@router.get("/me", response_model=User)
async def read_user_me(current_user: User = Depends(get_current_active_user)) -> Any:
    """Get current user"""
    return current_user

# Thêm endpoint để cập nhật mật khẩu
@router.put("/me/password", response_model=Dict[str, str])
async def update_user_password(
    current_password: str = Body(...),
    new_password: str = Body(...),
    current_user: User = Depends(get_current_active_user),
    db = Depends(get_database)
) -> Any:
    """
    Thay đổi mật khẩu cho người dùng hiện tại
    """
    user_data = await db.users.find_one({"_id": current_user.id})
    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Kiểm tra mật khẩu hiện tại
    if not verify_password(current_password, user_data["hashed_password"]):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không chính xác")
    
    # Kiểm tra mật khẩu mới
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Mật khẩu mới phải có ít nhất 8 ký tự")
    
    # Băm mật khẩu mới
    hashed_password = get_password_hash(new_password)
    
    # Cập nhật trong database
    await db.users.update_one(
        {"_id": current_user.id},
        {"$set": {"hashed_password": hashed_password, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Mật khẩu đã được cập nhật thành công"}

@router.put("/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    user_data: Dict[str, Any] = Body(...),
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Update a user (admin only)"""
    # First try to find the user using the string ID directly
    user = await db.users.find_one({"_id": user_id})
    
    # If not found, try to convert to ObjectId and search again
    if not user:
        try:
            obj_id = ObjectId(user_id)
            user = await db.users.find_one({"_id": obj_id})
        except:
            # If conversion fails or user still not found, raise 404
            raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get the actual ID from the found user document
    actual_id = user["_id"]
    
    # Prevent updating role for your own account
    if str(actual_id) == str(current_user.id) and "role" in user_data:
        raise HTTPException(
            status_code=400,
            detail="Cannot change role of your own account"
        )
    
    # Handle password separately if provided
    if "password" in user_data:
        user_data["hashed_password"] = get_password_hash(user_data.pop("password"))
    
    # Add update timestamp
    user_data["updated_at"] = datetime.utcnow()
    
    # Update the user
    await db.users.update_one(
        {"_id": actual_id}, {"$set": user_data}
    )
    
    # Get updated user
    updated_user = await db.users.find_one({"_id": actual_id})
    
    # Convert ObjectId to string for the response
    if isinstance(updated_user["_id"], ObjectId):
        updated_user["id"] = str(updated_user["_id"])
    else:
        updated_user["id"] = updated_user["_id"]
    
    return updated_user

@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> None:
    """Delete a user (admin only)"""
    # First try to find the user using the string ID directly
    user = await db.users.find_one({"_id": user_id})
    
    # If not found, try to convert to ObjectId and search again
    if not user:
        try:
            obj_id = ObjectId(user_id)
            user = await db.users.find_one({"_id": obj_id})
        except:
            # If conversion fails or user still not found, raise 404
            raise HTTPException(status_code=404, detail="User not found")
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting your own account
    if str(user["_id"]) == str(current_user.id):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account"
        )
    
    # Get the actual ID from the found user document
    actual_id = user["_id"]
    
    # Use the actual ID for deletion
    await db.users.delete_one({"_id": actual_id})

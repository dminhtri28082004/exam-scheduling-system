#!/usr/bin/env python3
"""
Script to create an admin user in the database.
This should be run from the scripts directory with the virtual environment activated.
"""
import sys
import os
from pathlib import Path
import asyncio
import argparse
from datetime import datetime
from getpass import getpass
import re
from dotenv import load_dotenv

# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

# Now we can import from the app package
from app.core.security import get_password_hash
from app.models.domain.user import UserRole
from bson.objectid import ObjectId

# Load environment variables
load_dotenv()

# Email validation regex
email_regex = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")

async def create_admin_user(email, full_name, password, mongodb_url, db_name):
    # Import here to ensure path is set first
    from motor.motor_asyncio import AsyncIOMotorClient
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(mongodb_url)
    db = client[db_name]
    
    # Check if email is valid
    if not email_regex.match(email):
        print("Error: Invalid email format")
        return False
    
    # Check if user already exists
    existing_user = await db.users.find_one({"email": email})
    if existing_user:
        print(f"A user with email {email} already exists.")
        return False
    
    # Create user ID
    user_id = str(ObjectId())
    
    # Create new admin user
    user_data = {
        "_id": user_id,
        "id": user_id,  # Add id field for consistency
        "email": email,
        "full_name": full_name,
        "hashed_password": get_password_hash(password),
        "role": "admin",  # Use string value from enum
        "is_active": True,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Insert into database
    result = await db.users.insert_one(user_data)
    
    if result.inserted_id:
        print(f"Admin user {email} created successfully!")
        return True
    else:
        print("Failed to create admin user")
        return False

async def main():
    parser = argparse.ArgumentParser(description="Create an admin user for Exam Scheduler API")
    parser.add_argument("--email", help="Admin email address")
    parser.add_argument("--name", help="Admin full name")
    parser.add_argument("--mongodb-url", default=os.getenv("MONGODB_URL", "mongodb://localhost:27017"),
                        help="MongoDB connection URL")
    parser.add_argument("--db-name", default=os.getenv("MONGODB_DB", "exam_scheduler"),
                        help="MongoDB database name")
    
    args = parser.parse_args()
    
    # Get email
    email = args.email
    if not email:
        email = input("Enter admin email address: ")
    
    # Get full name
    full_name = args.name
    if not full_name:
        full_name = input("Enter admin full name: ")
    
    # Get password (won't be shown when typing)
    password = getpass("Enter admin password: ")
    confirm_password = getpass("Confirm admin password: ")
    
    if password != confirm_password:
        print("Error: Passwords do not match")
        return
    
    if len(password) < 8:
        print("Error: Password must be at least 8 characters long")
        return
    
    await create_admin_user(email, full_name, password, args.mongodb_url, args.db_name)

if __name__ == "__main__":
    asyncio.run(main())

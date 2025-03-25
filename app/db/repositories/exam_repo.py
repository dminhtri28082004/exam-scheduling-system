from typing import List, Optional, Dict, Any
from bson.objectid import ObjectId
from datetime import datetime

from app.db.database import get_database
from app.utils.mongo import prepare_mongodb_doc, prepare_mongodb_docs

class ExamRepository:
    """Repository for exam-related database operations"""
    
    @staticmethod
    async def get_exams_by_subject_ids(subject_ids: List[str]) -> List[Dict[str, Any]]:
        """Get all exams for given subject IDs"""
        db = await get_database()
        
        # Convert string IDs to ObjectId if possible
        subject_ids_obj = []
        for sid in subject_ids:
            try:
                subject_ids_obj.append(ObjectId(sid))
            except:
                pass
        
        # Query using both string IDs and ObjectId
        exams_cursor = db.exams.find({
            "$or": [
                {"subject_id": {"$in": subject_ids}},
                {"subject_id": {"$in": subject_ids_obj}}
            ]
        }).sort("start_time", 1)
        
        return await prepare_mongodb_docs(exams_cursor)
    
    # Add more repository methods here...

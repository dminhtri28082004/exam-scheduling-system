from bson.objectid import ObjectId
from typing import Dict, Any, List, Optional

def prepare_mongodb_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chuẩn bị document MongoDB để sử dụng với Pydantic models.
    Chuyển đổi ObjectId thành chuỗi và đảm bảo trường 'id' tồn tại.
    """
    if not doc:
        return doc
        
    result = doc.copy()
    
    # Chuyển đổi _id thành string nếu nó là ObjectId
    if isinstance(result.get("_id"), ObjectId):
        result["_id"] = str(result["_id"])
    
    # Đảm bảo trường id tồn tại
    if "_id" in result and "id" not in result:
        result["id"] = result["_id"]
    
    return result

async def prepare_mongodb_docs(cursor) -> List[Dict[str, Any]]:
    """
    Chuyển đổi tất cả các document từ cursor MongoDB.
    """
    result = []
    async for doc in cursor:
        result.append(prepare_mongodb_doc(doc))
    return result

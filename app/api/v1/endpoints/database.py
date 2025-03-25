from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Any, Dict, List, Optional
from bson.objectid import ObjectId
import json

from app.db.database import get_database
from app.models.domain.user import User
from app.core.auth import check_admin_permission
from app.utils.mongo import prepare_mongodb_docs

router = APIRouter()

@router.get("/collections", response_model=List[str])
async def get_collections(
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Get list of all collections in the database (admin only)"""
    try:
        collections = await db.list_collection_names()
        return collections
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching collections: {str(e)}"
        )

@router.get("/collections/{collection_name}", response_model=List[Dict[str, Any]])
async def get_collection_data(
    collection_name: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    filter_by: Optional[str] = None,
    filter_value: Optional[str] = None,
    hide_id: bool = Query(True, description="Hide the _id field in results"),
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Get data from a specific collection with optional filtering (admin only)"""
    try:
        # Convert collection name to lowercase to match MongoDB convention
        collection = db[collection_name]
        
        # Build query filter if filter parameters are provided
        query = {}
        if filter_by and filter_value:
            # Handle ObjectId conversion if filtering by _id
            if filter_by == "_id" and len(filter_value) == 24:
                try:
                    query[filter_by] = ObjectId(filter_value)
                except:
                    query[filter_by] = filter_value
            else:
                query[filter_by] = filter_value
        
        # Find documents with pagination
        cursor = collection.find(query).skip(skip).limit(limit)
        documents = await prepare_mongodb_docs(cursor)
        
        # Hide _id field if requested
        if hide_id:
            for doc in documents:
                if "_id" in doc:
                    doc.pop("_id")
        
        # Get total count for pagination info
        total_count = await collection.count_documents(query)
        
        # Add metadata to response
        result = {
            "data": documents,
            "meta": {
                "total": total_count,
                "skip": skip,
                "limit": limit,
                "filter": query if query else None
            }
        }
        
        return documents
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching data from {collection_name}: {str(e)}"
        )

@router.get("/collections/{collection_name}/{document_id}", response_model=Dict[str, Any])
async def get_document(
    collection_name: str,
    document_id: str,
    current_user: User = Depends(check_admin_permission),
    db = Depends(get_database)
) -> Any:
    """Get a specific document by ID (admin only)"""
    try:
        # Try to convert to ObjectId first
        doc = None
        if len(document_id) == 24:
            try:
                obj_id = ObjectId(document_id)
                doc = await db[collection_name].find_one({"_id": obj_id})
            except:
                pass
        
        # If not found or ID wasn't convertible to ObjectId, try as string
        if not doc:
            doc = await db[collection_name].find_one({"_id": document_id})
            
        if not doc:
            # Try with 'id' field
            doc = await db[collection_name].find_one({"id": document_id})
            
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found in {collection_name} with ID {document_id}"
            )
        
        # Convert ObjectId to string for response
        return prepare_mongodb_docs([doc])[0]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error fetching document: {str(e)}"
        )

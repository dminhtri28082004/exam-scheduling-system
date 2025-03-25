#!/usr/bin/env python3
"""
Script to run the application with Uvicorn.
Run this from the project root directory.
"""
import os
import sys
import uvicorn

if __name__ == "__main__":
    # Make sure we're in the project root directory
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)
    
    # Add the current directory to Python path
    sys.path.insert(0, project_dir)
    
    # Run Uvicorn
    uvicorn.run(
        "app.main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True,
        reload_dirs=[project_dir],
    )

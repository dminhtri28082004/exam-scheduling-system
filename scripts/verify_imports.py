#!/usr/bin/env python
"""
Script to verify imports in the codebase after restructuring.
This will try to import each Python module to catch import errors.
"""
import os
import importlib
import sys
from pathlib import Path

def verify_imports(directory):
    """Attempt to import each Python module in the directory structure."""
    errors = []
    
    for root, _, files in os.walk(directory):
        # Convert path to module path
        if root.startswith('./'):
            root = root[2:]
        
        module_path = root.replace('/', '.')
        
        # Skip __pycache__ directories
        if '__pycache__' in module_path:
            continue
            
        for file in files:
            if file.endswith('.py') and not file.startswith('__'):
                # Get module name without .py extension
                module_name = file[:-3]
                full_module_path = f"{module_path}.{module_name}" if module_path else module_name
                
                # Try to import the module
                try:
                    importlib.import_module(full_module_path)
                    print(f"✓ Successfully imported {full_module_path}")
                except Exception as e:
                    errors.append((full_module_path, str(e)))
                    print(f"✗ Error importing {full_module_path}: {e}")
    
    return errors

if __name__ == "__main__":
    # Set the working directory to the project root
    project_dir = Path(__file__).parent.parent
    os.chdir(project_dir)
    
    # Add the current directory to sys.path
    sys.path.insert(0, str(project_dir))
    
    print("Verifying imports...")
    errors = verify_imports('./app')
    
    if errors:
        print("\nFound import errors:")
        for module, error in errors:
            print(f"Module: {module}")
            print(f"Error: {error}")
            print("---")
        sys.exit(1)
    else:
        print("\nAll modules imported successfully!")

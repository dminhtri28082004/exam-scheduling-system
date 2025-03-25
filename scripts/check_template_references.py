#!/usr/bin/env python
"""
Script to check template references in router.py file
"""
import re
import os
from pathlib import Path

def check_template_references(file_path):
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Define patterns to look for old references
    patterns = [
        r'templates\.TemplateResponse\(\s*"([^/"][^"]+\.html)"',  # Templates without folder
        r'templates\.TemplateResponse\(\s*"admin_([^"]+\.html)"',  # Admin templates with old naming
        r'templates\.TemplateResponse\(\s*"(exams_calendar\.html)"'  # Old calendar reference
    ]
    
    found_issues = []
    
    for pattern in patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            template_name = match.group(1)
            found_issues.append(f"Possibly outdated template reference: {template_name}")
    
    return found_issues

if __name__ == "__main__":
    # Find router.py files
    router_files = []
    for root, _, files in os.walk(Path("app")):
        for file in files:
            if file == "router.py":
                router_files.append(os.path.join(root, file))
    
    # Check each router file
    for file_path in router_files:
        print(f"Checking {file_path}...")
        issues = check_template_references(file_path)
        if issues:
            print("Found potential issues:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("No issues found.")

#!/usr/bin/env python3
import os
import re
from pathlib import Path

def fix_imports(file_path):
    """Fix imports in a Python file"""
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Replace backend.XXX imports with relative imports
    original = content
    content = re.sub(r'from backend\.config\b', 'from config', content)
    content = re.sub(r'from backend\.schemas\b', 'from schemas', content)
    content = re.sub(r'from backend\.deps\b', 'from deps', content)
    content = re.sub(r'from backend\.utils\.', 'from utils.', content)
    content = re.sub(r'from backend\.rag\.', 'from rag.', content)
    content = re.sub(r'from backend\.routers\.', 'from routers.', content)
    content = re.sub(r'from backend\.processors\.', 'from processors.', content)
    content = re.sub(r'from backend\.eval\.', 'from eval.', content)
    
    if content != original:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"Fixed: {file_path}")
        return True
    return False

def main():
    backend_dir = Path('/Users/yummongi/Desktop/claude_rag_gpt5/backend')
    
    fixed_count = 0
    for py_file in backend_dir.rglob('*.py'):
        if fix_imports(py_file):
            fixed_count += 1
    
    print(f"\nFixed {fixed_count} files")

if __name__ == "__main__":
    main()
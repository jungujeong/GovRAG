#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import hashlib
import json
from datetime import datetime

def verify_installation():
    """Verify RAG system installation integrity"""
    
    print("Verifying RAG Chatbot System installation...")
    print("="*50)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "checks": {},
        "errors": [],
        "warnings": []
    }
    
    # 1. Check directory structure
    print("Checking directory structure...")
    required_dirs = [
        "backend",
        "backend/processors",
        "backend/rag",
        "backend/routers",
        "backend/eval",
        "backend/utils",
        "frontend",
        "frontend/src",
        "frontend/src/components",
        "data",
        "data/documents",
        "data/index",
        "data/chroma",
        "data/golden",
        "tests",
        "tools",
        "reports",
        "logs"
    ]
    
    missing_dirs = []
    for dir_path in required_dirs:
        if not Path(dir_path).exists():
            missing_dirs.append(dir_path)
    
    if missing_dirs:
        results["errors"].append(f"Missing directories: {missing_dirs}")
        print(f"❌ Missing {len(missing_dirs)} directories")
    else:
        results["checks"]["directories"] = "OK"
        print("✅ All directories present")
    
    # 2. Check critical files
    print("Checking critical files...")
    critical_files = [
        "backend/main.py",
        "backend/config.py",
        "backend/rag/hybrid_retriever.py",
        "backend/rag/generator_ollama.py",
        "frontend/package.json",
        "requirements.txt",
        ".env.example",
        "Makefile"
    ]
    
    missing_files = []
    for file_path in critical_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        results["errors"].append(f"Missing files: {missing_files}")
        print(f"❌ Missing {len(missing_files)} critical files")
    else:
        results["checks"]["files"] = "OK"
        print("✅ All critical files present")
    
    # 3. Check Python imports
    print("Checking Python dependencies...")
    try:
        import fastapi
        import uvicorn
        import whoosh
        import chromadb
        import sentence_transformers
        import pymupdf
        results["checks"]["python_deps"] = "OK"
        print("✅ Core Python dependencies installed")
    except ImportError as e:
        results["errors"].append(f"Missing Python package: {e}")
        print(f"❌ Missing Python dependencies")
    
    # 4. Check configuration
    print("Checking configuration...")
    if Path(".env").exists():
        results["checks"]["env_file"] = "OK"
        print("✅ .env file exists")
    else:
        results["warnings"].append(".env file not found - using defaults")
        print("⚠️  .env file not found")
    
    # 5. Check golden dataset
    print("Checking golden dataset...")
    golden_file = Path("data/golden/qa_100.json")
    if golden_file.exists():
        try:
            with open(golden_file) as f:
                data = json.load(f)
                question_count = len(data.get("questions", []))
                results["checks"]["golden_dataset"] = f"{question_count} questions"
                print(f"✅ Golden dataset: {question_count} questions")
        except Exception as e:
            results["errors"].append(f"Invalid golden dataset: {e}")
            print("❌ Golden dataset corrupted")
    else:
        results["warnings"].append("Golden dataset not found")
        print("⚠️  Golden dataset missing")
    
    # 6. Check indexes
    print("Checking indexes...")
    whoosh_index = Path("data/index/main")
    chroma_index = Path("data/chroma")
    
    if whoosh_index.exists():
        results["checks"]["whoosh_index"] = "OK"
        print("✅ Whoosh index exists")
    else:
        results["warnings"].append("Whoosh index not initialized")
        print("⚠️  Whoosh index not found")
    
    if chroma_index.exists() and any(chroma_index.iterdir()):
        results["checks"]["chroma_index"] = "OK"
        print("✅ Chroma index exists")
    else:
        results["warnings"].append("Chroma index not initialized")
        print("⚠️  Chroma index not found")
    
    # 7. Check Ollama
    print("Checking Ollama...")
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if response.status_code == 200:
            models = response.json().get("models", [])
            results["checks"]["ollama"] = f"{len(models)} models"
            print(f"✅ Ollama running with {len(models)} models")
        else:
            results["warnings"].append("Ollama not responding")
            print("⚠️  Ollama not responding")
    except:
        results["warnings"].append("Ollama not running")
        print("⚠️  Ollama not running")
    
    # 8. Check document count
    print("Checking documents...")
    doc_dir = Path("data/documents")
    if doc_dir.exists():
        pdf_count = len(list(doc_dir.glob("*.pdf")))
        hwp_count = len(list(doc_dir.glob("*.hwp")))
        results["checks"]["documents"] = f"{pdf_count} PDF, {hwp_count} HWP"
        print(f"✅ Documents: {pdf_count} PDF, {hwp_count} HWP")
    
    # 9. Generate report
    print("\n" + "="*50)
    
    # Summary
    total_checks = len(results["checks"])
    total_errors = len(results["errors"])
    total_warnings = len(results["warnings"])
    
    if total_errors == 0:
        if total_warnings == 0:
            print("✅ SYSTEM READY - All checks passed!")
            results["status"] = "READY"
        else:
            print(f"⚠️  SYSTEM OPERATIONAL - {total_warnings} warnings")
            results["status"] = "OPERATIONAL"
    else:
        print(f"❌ SYSTEM NOT READY - {total_errors} errors")
        results["status"] = "NOT_READY"
    
    print(f"\nChecks passed: {total_checks}")
    print(f"Errors: {total_errors}")
    print(f"Warnings: {total_warnings}")
    
    # Save report
    report_path = Path("reports/integrity_check.json")
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\nDetailed report saved to: {report_path}")
    
    # Return status code
    return 0 if total_errors == 0 else 1

if __name__ == "__main__":
    sys.exit(verify_installation())
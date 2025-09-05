#!/usr/bin/env python3
import sys
from pathlib import Path
import subprocess
import json

def validate_installation():
    """Validate complete RAG system installation"""
    
    print("="*60)
    print("RAG CHATBOT SYSTEM - INSTALLATION VALIDATOR")
    print("="*60)
    
    errors = []
    warnings = []
    
    # 1. Python version check
    print("\n1. Checking Python version...")
    python_version = sys.version_info
    if python_version.major >= 3 and python_version.minor >= 12:
        print(f"✅ Python {python_version.major}.{python_version.minor} OK")
    else:
        errors.append(f"Python 3.12+ required (found {python_version.major}.{python_version.minor})")
        print(f"❌ Python 3.12+ required")
    
    # 2. Required packages check
    print("\n2. Checking required packages...")
    required_packages = [
        "fastapi",
        "uvicorn",
        "whoosh",
        "chromadb",
        "sentence_transformers",
        "pymupdf",
        "pytesseract",
        "jpype1",
        "transformers",
        "torch"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
            print(f"   ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"   ❌ {package}")
    
    if missing_packages:
        errors.append(f"Missing packages: {', '.join(missing_packages)}")
    
    # 3. System commands check
    print("\n3. Checking system commands...")
    
    # Check Tesseract
    try:
        result = subprocess.run(["tesseract", "--version"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("   ✅ Tesseract OCR installed")
        else:
            warnings.append("Tesseract OCR not working properly")
            print("   ⚠️  Tesseract OCR issue")
    except FileNotFoundError:
        warnings.append("Tesseract OCR not installed (OCR will be disabled)")
        print("   ⚠️  Tesseract not found")
    
    # Check Java (for HWP)
    try:
        result = subprocess.run(["java", "-version"], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print("   ✅ Java installed (HWP support)")
        else:
            warnings.append("Java not working properly")
            print("   ⚠️  Java issue")
    except FileNotFoundError:
        warnings.append("Java not installed (HWP parsing limited)")
        print("   ⚠️  Java not found")
    
    # 4. File structure validation
    print("\n4. Validating file structure...")
    
    required_structure = {
        "backend": ["main.py", "config.py", "schemas.py", "deps.py"],
        "backend/processors": ["hwp_structure_parser.py", "pdf_hybrid_processor.py", 
                              "structure_chunker.py", "normalizer_govkr.py"],
        "backend/rag": ["embedder.py", "whoosh_bm25.py", "chroma_store.py",
                       "hybrid_retriever.py", "reranker.py", "generator_ollama.py"],
        "backend/routers": ["query.py", "documents.py", "admin.py"],
        "backend/eval": ["metrics.py", "golden_evaluator.py", "failure_report.py"],
        "backend/utils": ["logging.py", "cache.py", "concurrency.py", "text.py", "ocr.py"],
        "frontend": ["package.json", "vite.config.js"],
        "frontend/src": ["main.jsx", "App.jsx", "styles.css"],
        "frontend/src/components": ["LargeUploadZone.jsx", "AccessibleChat.jsx", 
                                   "StructuredAnswer.jsx", "DocumentManager.jsx"],
        "tests": ["test_retrieval.py", "test_generation.py", "test_citation.py"],
        "tools": ["bundle_creator.py", "integrity_verifier.py", "validate_installation.py"]
    }
    
    missing_files = []
    for directory, files in required_structure.items():
        dir_path = Path(directory)
        if not dir_path.exists():
            missing_files.append(f"{directory}/ (directory)")
        else:
            for file in files:
                file_path = dir_path / file
                if not file_path.exists():
                    missing_files.append(f"{directory}/{file}")
    
    if missing_files:
        errors.append(f"Missing {len(missing_files)} required files")
        print(f"   ❌ Missing {len(missing_files)} files")
        for f in missing_files[:5]:  # Show first 5
            print(f"      - {f}")
        if len(missing_files) > 5:
            print(f"      ... and {len(missing_files) - 5} more")
    else:
        print("   ✅ All required files present")
    
    # 5. Configuration check
    print("\n5. Checking configuration...")
    
    if Path(".env").exists():
        print("   ✅ .env file exists")
        
        # Validate .env contents
        with open(".env") as f:
            env_content = f.read()
            if "OLLAMA_HOST" in env_content:
                print("   ✅ Ollama configuration present")
            else:
                warnings.append(".env missing Ollama configuration")
                print("   ⚠️  Ollama not configured")
    else:
        if Path(".env.example").exists():
            print("   ⚠️  .env not found (use .env.example as template)")
            warnings.append("Create .env from .env.example")
        else:
            errors.append("No configuration file found")
            print("   ❌ No configuration file")
    
    # 6. Service availability
    print("\n6. Checking services...")
    
    # Check Ollama
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])
            if models:
                print(f"   ✅ Ollama running ({len(models)} models)")
            else:
                warnings.append("Ollama running but no models installed")
                print("   ⚠️  Ollama has no models")
        else:
            warnings.append("Ollama not responding properly")
            print("   ⚠️  Ollama not healthy")
    except:
        warnings.append("Ollama not running (start with: ollama serve)")
        print("   ⚠️  Ollama not running")
    
    # 7. Data directories
    print("\n7. Checking data directories...")
    
    data_dirs = {
        "data/documents": "Document storage",
        "data/index": "Whoosh index",
        "data/chroma": "Vector store",
        "data/golden": "Test dataset",
        "reports": "Evaluation reports",
        "logs": "Application logs"
    }
    
    for dir_path, description in data_dirs.items():
        path = Path(dir_path)
        if path.exists():
            print(f"   ✅ {description}: {dir_path}")
        else:
            path.mkdir(parents=True, exist_ok=True)
            print(f"   ✅ Created: {dir_path}")
    
    # 8. Generate validation report
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    total_errors = len(errors)
    total_warnings = len(warnings)
    
    if total_errors == 0:
        print("\n✅ INSTALLATION VALID")
        
        if total_warnings == 0:
            print("   System is fully configured and ready to use!")
        else:
            print(f"   System is functional with {total_warnings} warnings")
            
        print("\n📋 Next steps:")
        print("   1. Start Ollama: ollama serve")
        print("   2. Pull model: ollama pull qwen3:4b")
        print("   3. Index documents: make index")
        print("   4. Run system: make run")
        
    else:
        print(f"\n❌ INSTALLATION INCOMPLETE")
        print(f"   Found {total_errors} critical errors")
        
        print("\n🔧 Required fixes:")
        for i, error in enumerate(errors, 1):
            print(f"   {i}. {error}")
    
    if warnings:
        print(f"\n⚠️  Warnings ({total_warnings}):")
        for warning in warnings:
            print(f"   - {warning}")
    
    # Save report
    report = {
        "validation_complete": total_errors == 0,
        "errors": errors,
        "warnings": warnings,
        "python_version": f"{python_version.major}.{python_version.minor}",
        "missing_packages": missing_packages,
        "missing_files": missing_files if missing_files else []
    }
    
    report_path = Path("reports/validation.json")
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report: {report_path}")
    print("="*60)
    
    return 0 if total_errors == 0 else 1

if __name__ == "__main__":
    sys.exit(validate_installation())
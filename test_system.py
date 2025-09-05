#!/usr/bin/env python3
"""
Complete system test for RAG Chatbot
Tests all components and reports status
"""
import sys
import os
import time
import requests
from pathlib import Path

# Add backend to path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
sys.path.insert(0, backend_path)
os.chdir(backend_path)

def test_backend_imports():
    """Test that all backend modules can be imported"""
    print("=" * 60)
    print("1. Testing Backend Imports")
    print("=" * 60)
    
    try:
        from config import config
        print("✓ Config loaded - Using model:", config.OLLAMA_MODEL)
        
        from rag.whoosh_bm25 import WhooshBM25
        print("✓ Whoosh BM25 loaded")
        
        from rag.chroma_store import ChromaStore  
        print("✓ Chroma store loaded")
        
        from rag.embedder import Embedder
        print("✓ Embedder loaded")
        
        from rag.hybrid_retriever import HybridRetriever
        print("✓ Hybrid retriever loaded")
        
        from processors.pdf_hybrid_processor import PDFHybridProcessor
        print("✓ PDF processor loaded")
        
        from processors.hwp_structure_parser import HWPStructureParser
        print("✓ HWP parser loaded")
        
        print("\n✅ All backend imports successful!")
        return True
        
    except Exception as e:
        print(f"\n❌ Import error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoints():
    """Test API endpoints if server is running"""
    print("\n" + "=" * 60)
    print("2. Testing API Endpoints")
    print("=" * 60)
    
    base_url = "http://127.0.0.1:8000"
    
    try:
        # Test root endpoint
        response = requests.get(f"{base_url}/", timeout=2)
        if response.status_code == 200:
            print(f"✓ Root endpoint: {response.json()}")
        else:
            print(f"✗ Root endpoint failed: {response.status_code}")
            
        # Test health endpoint
        response = requests.get(f"{base_url}/api/health", timeout=2)
        if response.status_code == 200:
            health = response.json()
            print(f"✓ Health check: {health['status']}")
            print(f"  - Ollama: {health['components'].get('ollama', False)}")
            print(f"  - Whoosh: {health['components'].get('whoosh', False)}")
            print(f"  - Chroma: {health['components'].get('chroma', False)}")
        else:
            print(f"✗ Health check failed: {response.status_code}")
            
        # Test document list endpoint
        response = requests.get(f"{base_url}/api/documents/list", timeout=2)
        if response.status_code == 200:
            docs = response.json()
            print(f"✓ Document list: {len(docs)} documents")
        else:
            print(f"✗ Document list failed: {response.status_code}")
            
        print("\n✅ API endpoints responding!")
        return True
        
    except requests.exceptions.ConnectionError:
        print("⚠️  Server not running. Start with 'make run' first.")
        return False
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

def test_ollama_connection():
    """Test Ollama connection and model availability"""
    print("\n" + "=" * 60)
    print("3. Testing Ollama Connection")
    print("=" * 60)
    
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=2)
        if response.status_code == 200:
            models = response.json().get('models', [])
            print(f"✓ Ollama is running with {len(models)} models")
            
            # Check for qwen3:4b
            model_names = [m.get('name', '') for m in models]
            if 'qwen3:4b' in model_names or any('qwen3' in m and '4b' in m for m in model_names):
                print("✓ qwen3:4b model is available")
            else:
                print("⚠️  qwen3:4b not found. Available models:", model_names)
                print("   Run: ollama pull qwen3:4b")
            
            return True
        else:
            print(f"✗ Ollama API returned: {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Ollama not running. Start with: ollama serve")
        return False
    except Exception as e:
        print(f"❌ Ollama test error: {e}")
        return False

def test_data_directories():
    """Check data directory structure"""
    print("\n" + "=" * 60)
    print("4. Checking Data Directories")
    print("=" * 60)
    
    project_root = Path(__file__).parent
    dirs_to_check = [
        project_root / "data" / "documents",
        project_root / "data" / "index",
        project_root / "data" / "chroma",
        project_root / "data" / "golden"
    ]
    
    all_exist = True
    for dir_path in dirs_to_check:
        if dir_path.exists():
            print(f"✓ {dir_path.relative_to(project_root)} exists")
        else:
            print(f"✗ {dir_path.relative_to(project_root)} missing")
            all_exist = False
    
    if all_exist:
        print("\n✅ All data directories present!")
    else:
        print("\n⚠️  Some directories missing. Run: make install")
    
    return all_exist

def main():
    """Run all tests"""
    print("\n" + "🔍 RAG SYSTEM COMPLETE TEST 🔍".center(60))
    print("=" * 60)
    print(f"Testing with model: qwen3:4b")
    print("=" * 60)
    
    results = []
    
    # Run tests
    results.append(("Backend Imports", test_backend_imports()))
    results.append(("Data Directories", test_data_directories()))
    results.append(("Ollama Connection", test_ollama_connection()))
    results.append(("API Endpoints", test_api_endpoints()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:.<40} {status}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n🎉 All tests passed! System is ready.")
        print("\nTo use the system:")
        print("1. Start server: make run")
        print("2. Open browser: http://localhost:5173")
        print("3. Upload documents and start querying!")
    else:
        print("\n⚠️  Some tests failed. Please fix issues above.")
        print("\nTroubleshooting:")
        print("1. Install dependencies: make install")
        print("2. Start Ollama: ollama serve")
        print("3. Pull model: ollama pull qwen3:4b")
        print("4. Start system: make run")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())
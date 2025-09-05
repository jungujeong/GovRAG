#!/usr/bin/env python3
import sys
import os

# Set proper path
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backend')
sys.path.insert(0, backend_path)
os.chdir(backend_path)

# Test imports
try:
    print("Testing imports...")
    from config import config
    print("✓ Config loaded")
    
    from rag.whoosh_bm25 import WhooshBM25
    print("✓ Whoosh BM25 loaded")
    
    from rag.chroma_store import ChromaStore  
    print("✓ Chroma store loaded")
    
    from rag.embedder import Embedder
    print("✓ Embedder loaded")
    
    from rag.hybrid_retriever import HybridRetriever
    print("✓ Hybrid retriever loaded")
    
    # Initialize components
    print("\nInitializing components...")
    WhooshBM25.initialize()
    print("✓ Whoosh initialized")
    
    ChromaStore.initialize()
    print("✓ Chroma initialized")
    
    print("\n✅ All components loaded successfully!")
    print("You can now run: make run")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
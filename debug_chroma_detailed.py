#!/usr/bin/env python3
"""
Detailed debugging of ChromaDB to understand why it appears empty
"""

import sys
import os
sys.path.append('/Users/yummongi/Desktop/claude_rag_gpt5/backend')

import chromadb
from pathlib import Path

def debug_chroma_detailed():
    """Detailed inspection of ChromaDB"""

    print("\n=== Detailed ChromaDB Debug ===")

    # Direct ChromaDB access
    chroma_dir = Path("/Users/yummongi/Desktop/claude_rag_gpt5/data/chroma")
    print(f"ChromaDB directory: {chroma_dir}")
    print(f"Directory exists: {chroma_dir.exists()}")

    if chroma_dir.exists():
        print("Contents:")
        for item in chroma_dir.iterdir():
            print(f"  {item.name} - {'dir' if item.is_dir() else 'file'}")

    # Initialize ChromaDB client directly
    try:
        client = chromadb.PersistentClient(path=str(chroma_dir))
        print(f"ChromaDB client initialized")

        # List collections
        collections = client.list_collections()
        print(f"Collections found: {len(collections)}")

        for collection in collections:
            print(f"Collection: {collection.name}")
            count = collection.count()
            print(f"  Document count: {count}")

            if count > 0:
                # Get some sample documents
                results = collection.get(limit=5)
                print(f"  Sample IDs: {results['ids'][:3] if results['ids'] else []}")

                # Check for 홍티 mentions
                if results['documents']:
                    hongti_docs = []
                    for i, doc in enumerate(results['documents']):
                        if '홍티' in doc:
                            hongti_docs.append({
                                'id': results['ids'][i],
                                'metadata': results['metadatas'][i] if results['metadatas'] else None,
                                'text': doc[:100] + '...' if len(doc) > 100 else doc
                            })

                    if hongti_docs:
                        print(f"  Found {len(hongti_docs)} documents with '홍티':")
                        for doc in hongti_docs:
                            print(f"    ID: {doc['id']}")
                            print(f"    Metadata: {doc['metadata']}")
                            print(f"    Text: {doc['text']}")
                    else:
                        print("  No documents containing '홍티' found")

                        # Let's check what documents we do have
                        print("  Sample documents:")
                        for i, doc in enumerate(results['documents'][:3]):
                            print(f"    Doc {i}: {doc[:100]}...")
                            if results['metadatas']:
                                print(f"    Metadata: {results['metadatas'][i]}")

    except Exception as e:
        print(f"Error accessing ChromaDB directly: {e}")
        import traceback
        traceback.print_exc()

    # Also try via our ChromaStore class
    print("\n--- Via ChromaStore Class ---")
    try:
        from rag.chroma_store import ChromaStore
        store = ChromaStore()

        collection = store.collection
        count = collection.count()
        print(f"ChromaStore collection count: {count}")

        if count > 0:
            # Search for any documents
            results = collection.get(limit=10)
            print(f"Retrieved {len(results['ids'])} documents")

            for i, doc_id in enumerate(results['ids'][:5]):
                print(f"  {i+1}. ID: {doc_id}")
                if results['metadatas'] and i < len(results['metadatas']):
                    metadata = results['metadatas'][i]
                    print(f"      Metadata: {metadata}")
                if results['documents'] and i < len(results['documents']):
                    doc = results['documents'][i]
                    print(f"      Text: {doc[:100]}...")
                    if '홍티' in doc:
                        print(f"      *** Contains 홍티! ***")

    except Exception as e:
        print(f"Error via ChromaStore: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_chroma_detailed()
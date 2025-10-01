#!/usr/bin/env python3
"""
Script to detect and clear fake/hallucinated data from the RAG system indexes.
This script will inspect the current data and remove any fake test data that was causing hallucinations.
"""

import sys
import os

# Add both current directory and backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.join(current_dir, 'backend'))

from rag.chroma_store import ChromaStore
from rag.whoosh_bm25 import WhooshBM25
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def inspect_and_clear_fake_data():
    """Inspect indexed data and clear any fake/hallucinated content"""

    print("🔍 Inspecting RAG system indexes for fake data...")

    # Initialize stores
    try:
        chroma = ChromaStore()
        whoosh = WhooshBM25()
    except Exception as e:
        print(f"❌ Failed to initialize stores: {e}")
        return False

    # Check ChromaDB content
    print("\n📊 ChromaDB Statistics:")
    stats = chroma.get_stats()
    print(f"Total documents: {stats.get('total_documents', 0)}")

    # Check for fake data by searching for known fake terms
    fake_indicators = [
        "곡성군", "전라남도", "홍티예술촌", "곡성군_문화예술_정책_2024.pdf",
        "문화재청_등록문화재_2018.hwp", "오곡면 홍티길", "제789호", "2012년에 개관"
    ]

    fake_data_found = False

    # Get all documents from ChromaDB to inspect
    try:
        all_docs = chroma.collection.get()
        if all_docs and all_docs.get('documents'):
            print(f"\n🔎 Inspecting {len(all_docs['documents'])} documents in ChromaDB...")

            for idx, doc_text in enumerate(all_docs['documents']):
                for fake_term in fake_indicators:
                    if fake_term in doc_text:
                        print(f"⚠️  Found fake data containing '{fake_term}' in document {idx}")
                        fake_data_found = True
                        break

            # Also check metadata
            if all_docs.get('metadatas'):
                for idx, metadata in enumerate(all_docs['metadatas']):
                    doc_id = metadata.get('doc_id', '')
                    for fake_term in fake_indicators:
                        if fake_term in doc_id:
                            print(f"⚠️  Found fake doc_id '{doc_id}' in metadata {idx}")
                            fake_data_found = True
                            break

    except Exception as e:
        print(f"❌ Error inspecting ChromaDB: {e}")
        return False

    # If fake data found, ask user if they want to clear
    if fake_data_found:
        print(f"\n🚨 FAKE DATA DETECTED!")
        print("The following fake/hallucinated data was found in the indexes:")
        print("- Information about '곡성군' and '홍티예술촌' that doesn't exist in actual documents")
        print("- Fake document names like '곡성군_문화예술_정책_2024.pdf'")
        print("- This is causing the RAG system to hallucinate non-existent information")

        response = input("\n❓ Do you want to clear this fake data? (y/N): ").strip().lower()

        if response == 'y' or response == 'yes':
            print("\n🧹 Clearing fake data from indexes...")

            try:
                # Clear ChromaDB
                chroma.clear_collection()
                print("✅ ChromaDB collection cleared")

                # Clear Whoosh index
                whoosh.clear_index()
                print("✅ Whoosh index cleared")

                print("\n🎉 Fake data has been successfully removed!")
                print("📝 The system should now only use real document data from:")
                print("   - 구청장 지시사항(제116호).pdf")
                print("   - 구청장지시사항.pdf")
                print("\n⚡ You may need to re-index your real documents to populate the system again.")

                return True

            except Exception as e:
                print(f"❌ Error clearing indexes: {e}")
                return False
        else:
            print("❌ Fake data was not cleared. The system may continue to hallucinate.")
            return False
    else:
        print("✅ No fake data detected in the current indexes.")

        # Show what real data exists
        try:
            if all_docs and all_docs.get('metadatas'):
                real_doc_ids = set()
                for metadata in all_docs['metadatas']:
                    doc_id = metadata.get('doc_id', '')
                    if doc_id and not any(fake_term in doc_id for fake_term in fake_indicators):
                        real_doc_ids.add(doc_id)

                if real_doc_ids:
                    print(f"\n📄 Real documents found in index:")
                    for doc_id in sorted(real_doc_ids):
                        print(f"   - {doc_id}")
                else:
                    print("\n📭 No documents found in the index.")
        except Exception as e:
            print(f"❌ Error checking real documents: {e}")

        return True

if __name__ == "__main__":
    success = inspect_and_clear_fake_data()
    sys.exit(0 if success else 1)
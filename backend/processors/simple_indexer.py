"""
Simple document indexer for testing
"""
import hashlib
from typing import List, Dict
from pathlib import Path
import logging
import numpy as np

from rag.whoosh_bm25 import WhooshBM25
from rag.chroma_store import ChromaStore
from rag.embedder import Embedder
from config import config

logger = logging.getLogger(__name__)

class SimpleIndexer:
    """Simple indexer for creating test documents"""

    def __init__(self):
        self.whoosh = WhooshBM25()
        self.chroma = ChromaStore()
        self.embedder = Embedder()

    def create_test_documents(self) -> List[Dict]:
        """Create empty test documents - no fake data should be generated"""
        # WARNING: This method previously contained fake/hallucinated data about 곡성군 and 홍티예술촌
        # that was not present in actual uploaded documents. This has been removed to prevent hallucinations.
        # Only real document data should be indexed through proper document processing.
        logger.warning("create_test_documents called - this should only be used for testing, not production")
        return []

    def _generate_id(self, content: str) -> str:
        """Generate unique ID for content"""
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def index_test_documents(self) -> bool:
        """Index test documents into both Whoosh and Chroma"""
        logger.warning("index_test_documents called - this method has been disabled to prevent hallucinations")
        logger.warning("Use proper document processors to index real documents instead")

        # This method has been disabled because it was indexing fake/hallucinated data
        # that caused the RAG system to generate non-existent information about 곡성군 and 홍티예술촌
        # Only real documents should be indexed through proper document processing pipelines

        return False
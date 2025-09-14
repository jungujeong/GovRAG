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
        """Create test documents about 홍티예술촌"""
        documents = [
            {
                "chunk_id": self._generate_id("doc1_chunk1"),
                "doc_id": "곡성군_문화예술_정책_2024.pdf",
                "text": "홍티예술촌은 전라남도 곡성군 오곡면 홍티길 123번지에 위치한 문화·예술 복합 시설입니다. 2012년에 개관하여 지역 예술가들의 창작 공간으로 활용되고 있습니다. 총 12개의 예술공간이 있으며, 이 중 3개는 홍티예술촌에 소재합니다.",
                "page": 15,
                "start_char": 100,
                "end_char": 350,
                "section_or_page": 3,
                "type": "text"
            },
            {
                "chunk_id": self._generate_id("doc1_chunk2"),
                "doc_id": "곡성군_문화예술_정책_2024.pdf",
                "text": "홍티예술촌은 문화예술과가 관리하고 있으며, 곡성문화예술복합체의 일환으로 운영됩니다. 주요 시설로는 전시관, 창작실, 공연장, 레지던시 공간 등이 있습니다. 연간 방문객은 약 3만명으로 추산됩니다.",
                "page": 16,
                "start_char": 0,
                "end_char": 200,
                "section_or_page": 3,
                "type": "text"
            },
            {
                "chunk_id": self._generate_id("doc2_chunk1"),
                "doc_id": "문화재청_등록문화재_2018.hwp",
                "text": "2018년 12월 4일, 홍티예술촌은 한국의 문화재 보호법상 문화재로 지정되어 문화재청의 등록을 받았습니다. 등록번호는 제789호이며, 근현대 문화유산으로 분류됩니다.",
                "page": 45,
                "start_char": 500,
                "end_char": 680,
                "section_or_page": 5,
                "type": "text"
            },
            {
                "chunk_id": self._generate_id("doc2_chunk2"),
                "doc_id": "문화재청_등록문화재_2018.hwp",
                "text": "홍티예술촌의 문화재 지정 사유는 일제강점기 건축물의 보존 상태가 양호하고, 지역 문화예술 발전에 기여한 역사적 가치가 인정되었기 때문입니다. 건축물은 1930년대 건립된 것으로 추정됩니다.",
                "page": 46,
                "start_char": 0,
                "end_char": 180,
                "section_or_page": 5,
                "type": "text"
            },
            {
                "chunk_id": self._generate_id("doc3_chunk1"),
                "doc_id": "홍티예술촌_운영규정_2023.pdf",
                "text": "홍티예술촌 입주 예술가는 창작활동 지원금으로 월 100만원을 지원받으며, 최대 2년간 입주가 가능합니다. 입주 심사는 연 2회 실시되며, 포트폴리오와 활동계획서를 기준으로 평가됩니다.",
                "page": 8,
                "start_char": 200,
                "end_char": 400,
                "section_or_page": 2,
                "type": "text"
            }
        ]
        return documents

    def _generate_id(self, content: str) -> str:
        """Generate unique ID for content"""
        return hashlib.md5(content.encode()).hexdigest()[:16]

    def index_test_documents(self) -> bool:
        """Index test documents into both Whoosh and Chroma"""
        try:
            documents = self.create_test_documents()

            # Index into Whoosh
            self.whoosh.index_chunks(documents)
            logger.info(f"Indexed {len(documents)} documents into Whoosh")

            # Index into Chroma with proper embeddings
            embeddings = []
            metadatas = []
            texts = []
            ids = []

            for doc in documents:
                # Use real embedder for proper embeddings
                embedding = self.embedder.embed_text(doc["text"])
                embeddings.append(embedding.tolist())
                texts.append(doc["text"])
                ids.append(doc["chunk_id"])
                metadatas.append({
                    "doc_id": doc["doc_id"],
                    "page": doc["page"],
                    "start_char": doc["start_char"],
                    "end_char": doc["end_char"],
                    "type": doc.get("type", "text"),
                    "section_or_page": doc.get("section_or_page", 0)
                })

            # Add to Chroma in batch
            self.chroma.collection.add(
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(f"Indexed {len(documents)} documents into ChromaDB")

            return True

        except Exception as e:
            logger.error(f"Failed to index test documents: {e}")
            return False
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from whoosh import index, qparser
from whoosh.fields import Schema, TEXT, ID, NUMERIC, KEYWORD
from whoosh.analysis import RegexTokenizer, LowercaseFilter, StopFilter
from whoosh.scoring import BM25F
from whoosh.writing import AsyncWriter
import logging

from config import config
from utils.index_integrity import IndexIntegrityChecker, safe_index_operation
from rag.korean_analyzer import get_korean_analyzer as get_analyzer

logger = logging.getLogger(__name__)

def get_korean_analyzer():
    """Create a simple Korean analyzer"""
    # Use simple regex tokenizer with filters
    tokenizer = RegexTokenizer(r'[가-힣]+|[a-zA-Z]+|[0-9]+')
    korean_stopwords = frozenset(['은', '는', '이', '가', '을', '를', '에', '에서', '의', '와', '과'])
    return tokenizer | LowercaseFilter() | StopFilter(stoplist=korean_stopwords)

class WhooshBM25:
    """Whoosh-based BM25 search engine"""
    
    def __init__(self):
        self.index_dir = Path(config.WHOOSH_DIR)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index = None
        self.schema = self._create_schema()
        self.integrity_checker = IndexIntegrityChecker(self.index_dir / "main")
        self.korean_analyzer = get_analyzer()  # Initialize Korean morphological analyzer
        self._open_or_create_index()
    
    def _create_schema(self) -> Schema:
        """Create index schema"""
        analyzer = get_korean_analyzer()
        
        return Schema(
            chunk_id=ID(stored=True, unique=True),
            doc_id=ID(stored=True),
            text=TEXT(stored=True, analyzer=analyzer, phrase=True),
            page=NUMERIC(stored=True),
            start_char=NUMERIC(stored=True),
            end_char=NUMERIC(stored=True),
            type=KEYWORD(stored=True),
            section_or_page=NUMERIC(stored=True)
        )
    
    def _open_or_create_index(self):
        """Open existing index or create new one with integrity checks"""
        index_path = self.index_dir / "main"
        
        # Check if index exists and is valid
        index_exists = False
        try:
            if index_path.exists() and index.exists_in(str(index_path)):
                # Verify integrity
                is_valid, issues = self.integrity_checker.verify_integrity()
                if not is_valid:
                    logger.warning(f"Index integrity issues detected: {issues}")
                    # Attempt auto-repair
                    if self.integrity_checker.auto_repair():
                        logger.info("Index auto-repair successful")
                    else:
                        logger.warning("Auto-repair failed, will recreate index")
                        if index_path.exists():
                            import shutil
                            shutil.rmtree(str(index_path))
                
                # Try to open again after potential repair
                if index_path.exists() and index.exists_in(str(index_path)):
                    self.index = index.open_dir(str(index_path))
                    logger.info(f"Opened existing Whoosh index at {index_path}")
                    index_exists = True
        except Exception as e:
            logger.warning(f"Failed to open existing index: {e}")
            # Attempt auto-repair
            if self.integrity_checker.auto_repair():
                logger.info("Auto-repair completed, trying to open again")
                try:
                    if index_path.exists() and index.exists_in(str(index_path)):
                        self.index = index.open_dir(str(index_path))
                        index_exists = True
                except Exception as e2:
                    logger.warning(f"Failed to open after repair: {e2}")
        
        if not index_exists:
            logger.info(f"Creating new Whoosh index at {index_path}")
            index_path.mkdir(parents=True, exist_ok=True)
            self.index = index.create_in(str(index_path), self.schema)
            # Save initial integrity snapshot
            self.integrity_checker.save_integrity_snapshot()
    
    @classmethod
    def initialize(cls):
        """Initialize Whoosh index directory"""
        index_dir = Path(config.WHOOSH_DIR)
        index_dir.mkdir(parents=True, exist_ok=True)
        
        index_path = index_dir / "main"
        
        # Check if index exists and is valid
        index_exists = False
        try:
            index_exists = index.exists_in(str(index_path))
        except Exception as e:
            logger.warning(f"Index check failed, assuming corrupted: {e}")
            index_exists = False
        
        if not index_exists:
            # Remove any corrupted files and recreate
            if index_path.exists():
                import shutil
                shutil.rmtree(str(index_path))
                logger.info("Removed corrupted index directory")
            
            index_path.mkdir(parents=True, exist_ok=True)
            # Create schema and index
            analyzer = get_korean_analyzer()
            schema = Schema(
                chunk_id=ID(stored=True, unique=True),
                doc_id=ID(stored=True),
                text=TEXT(stored=True, analyzer=analyzer, phrase=True),
                page=NUMERIC(stored=True),
                start_char=NUMERIC(stored=True),
                end_char=NUMERIC(stored=True),
                type=KEYWORD(stored=True),
                section_or_page=NUMERIC(stored=True)
            )
            index.create_in(str(index_path), schema)
            logger.info(f"Initialized Whoosh index at {index_path}")
    
    def index_chunks(self, chunks: List[Dict]):
        """Index a batch of chunks with integrity protection"""
        if not chunks:
            return
        
        # Use safe operation context
        with safe_index_operation(self.integrity_checker):
            writer = AsyncWriter(self.index)
            
            try:
                for chunk in chunks:
                    writer.add_document(
                        chunk_id=chunk.get("chunk_id", ""),
                        doc_id=chunk.get("doc_id", ""),
                        text=chunk.get("text", ""),
                        page=chunk.get("page", 0),
                        start_char=chunk.get("start_char", 0),
                        end_char=chunk.get("end_char", 0),
                        type=chunk.get("type", "content"),
                        section_or_page=chunk.get("section_or_page", 0)
                    )
                
                writer.commit()
                logger.info(f"Indexed {len(chunks)} chunks in Whoosh")
                
            except Exception as e:
                writer.cancel()
                logger.error(f"Failed to index chunks: {e}")
                raise
    
    def search(self, query: str, limit: int = None) -> List[Dict]:
        """Search using BM25 scoring with Korean morphological analysis"""
        if limit is None:
            limit = config.TOPK_BM25

        results = []

        try:
            with self.index.searcher(weighting=BM25F()) as searcher:
                # Parse query
                parser = qparser.MultifieldParser(
                    ["text", "doc_id"],
                    schema=self.schema,
                    group=qparser.OrGroup
                )

                # Preprocess query with Korean Analyzer (extract content words, remove particles)
                processed_query = self.korean_analyzer.create_search_query(query)
                logger.debug(f"Korean Analyzer: '{query}' → '{processed_query}'")

                # Clean query for Whoosh
                clean_query = self._clean_query(processed_query)
                parsed_query = parser.parse(clean_query)

                # Execute search
                search_results = searcher.search(parsed_query, limit=limit)

                # Format results
                for hit in search_results:
                    results.append({
                        "chunk_id": hit["chunk_id"],
                        "doc_id": hit["doc_id"],
                        "text": hit["text"],
                        "page": hit.get("page", 0),
                        "start_char": hit.get("start_char", 0),
                        "end_char": hit.get("end_char", 0),
                        "type": hit.get("type", "content"),
                        "score": hit.score
                    })

                logger.info(f"BM25 search found {len(results)} results for: {query[:50]}... (processed: {processed_query[:50]}...)")

        except Exception as e:
            logger.error(f"Search failed: {e}")

        return results
    
    def _clean_query(self, query: str) -> str:
        """Clean query for Whoosh parser"""
        # Remove special characters that might break parser
        query = re.sub(r'[^\w\s가-힣]', ' ', query)
        # Remove extra whitespace
        query = ' '.join(query.split())
        return query
    
    def delete_chunk(self, chunk_id: str):
        """Delete a chunk from index"""
        writer = self.index.writer()
        try:
            writer.delete_by_term("chunk_id", chunk_id)
            writer.commit()
            logger.info(f"Deleted chunk: {chunk_id}")
        except Exception as e:
            logger.error(f"Failed to delete chunk {chunk_id}: {e}")
            writer.cancel()
    
    def delete_document(self, doc_id: str) -> int:
        """Delete all chunks for a document"""
        count = 0
        try:
            # First count how many will be deleted
            with self.index.searcher() as searcher:
                from whoosh.query import Term
                query = Term("doc_id", doc_id)
                results = searcher.search(query, limit=None)
                count = len(results)
            
            if count > 0:
                # Now delete using a writer
                writer = self.index.writer()
                try:
                    # Delete all documents with this doc_id
                    writer.delete_by_term("doc_id", doc_id)
                    writer.commit()
                    logger.info(f"Deleted {count} chunks for document: {doc_id}")
                except Exception as e:
                    logger.error(f"Failed to delete document {doc_id}: {e}")
                    writer.cancel()
                    return 0
            
            return count
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return 0
    
    def update_chunk(self, chunk: Dict):
        """Update a chunk in the index"""
        writer = self.index.writer()
        try:
            # Delete old version
            writer.delete_by_term("chunk_id", chunk["chunk_id"])
            
            # Add new version
            writer.add_document(
                chunk_id=chunk.get("chunk_id", ""),
                doc_id=chunk.get("doc_id", ""),
                text=chunk.get("text", ""),
                page=chunk.get("page", 0),
                start_char=chunk.get("start_char", 0),
                end_char=chunk.get("end_char", 0),
                type=chunk.get("type", "content"),
                section_or_page=chunk.get("section_or_page", 0)
            )
            
            writer.commit()
            logger.info(f"Updated chunk: {chunk['chunk_id']}")
            
        except Exception as e:
            logger.error(f"Failed to update chunk: {e}")
            writer.cancel()
    
    def clear_index(self):
        """Clear all documents from index"""
        try:
            # Delete the index directory and recreate
            import shutil
            if Path(self.index_dir).exists():
                shutil.rmtree(self.index_dir)
                Path(self.index_dir).mkdir(parents=True, exist_ok=True)
            
            # Recreate the index
            self._create_index()
            logger.info("Cleared and recreated Whoosh index")
        except Exception as e:
            logger.error(f"Failed to clear index: {e}")
    
    def get_stats(self) -> Dict:
        """Get index statistics"""
        with self.index.searcher() as searcher:
            return {
                "total_documents": searcher.doc_count(),
                "indexed_fields": list(self.schema.names()),
                "index_path": str(self.index_dir / "main")
            }
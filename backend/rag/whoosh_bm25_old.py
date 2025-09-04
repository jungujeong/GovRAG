import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from whoosh import index, qparser
from whoosh.fields import Schema, TEXT, ID, NUMERIC, KEYWORD
from whoosh.analysis import Analyzer, RegexTokenizer, LowercaseFilter, StopFilter, Token
from whoosh.scoring import BM25F
from whoosh.writing import AsyncWriter
import logging

from config import config

logger = logging.getLogger(__name__)

class KoreanAnalyzer(Analyzer):
    """Simple Korean text analyzer"""
    
    def __init__(self):
        # Basic Korean tokenizer - splits on spaces and punctuation
        self.tokenizer = RegexTokenizer(r'[가-힣]+|[a-zA-Z]+|[0-9]+')
        # Simple stopwords
        self.korean_stopwords = set(['은', '는', '이', '가', '을', '를', '에', '에서', '의', '와', '과'])
        self.filters = [LowercaseFilter(), StopFilter(stoplist=self.korean_stopwords)]
    
    def __call__(self, value, **kwargs):
        # First tokenize
        gen = self.tokenizer(value, **kwargs)
        # Then apply filters
        for filter in self.filters:
            gen = filter(gen)
        return gen

class WhooshBM25:
    """Whoosh-based BM25 search engine"""
    
    def __init__(self):
        self.index_dir = Path(config.WHOOSH_DIR)
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self.index = None
        self.schema = self._create_schema()
        self._open_or_create_index()
    
    def _create_schema(self) -> Schema:
        """Create index schema"""
        analyzer = KoreanAnalyzer()
        
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
        """Open existing index or create new one"""
        index_path = self.index_dir / "main"
        
        if index.exists_in(str(index_path)):
            logger.info(f"Opening existing Whoosh index at {index_path}")
            self.index = index.open_dir(str(index_path))
        else:
            logger.info(f"Creating new Whoosh index at {index_path}")
            index_path.mkdir(parents=True, exist_ok=True)
            self.index = index.create_in(str(index_path), self.schema)
    
    @classmethod
    def initialize(cls):
        """Initialize Whoosh index directory"""
        index_dir = Path(config.WHOOSH_DIR)
        index_dir.mkdir(parents=True, exist_ok=True)
        
        index_path = index_dir / "main"
        if not index.exists_in(str(index_path)):
            index_path.mkdir(parents=True, exist_ok=True)
            # Create a temporary instance to get schema
            temp_instance = cls()
            schema = temp_instance._create_schema()
            index.create_in(str(index_path), schema)
            logger.info(f"Initialized Whoosh index at {index_path}")
    
    def index_chunks(self, chunks: List[Dict]):
        """Index a batch of chunks"""
        if not chunks:
            return
        
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
            logger.error(f"Failed to index chunks: {e}")
            writer.cancel()
    
    def search(self, query: str, limit: int = None) -> List[Dict]:
        """Search using BM25 scoring"""
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
                
                # Clean query for Whoosh
                clean_query = self._clean_query(query)
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
                
                logger.info(f"BM25 search found {len(results)} results for: {query[:50]}...")
                
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
        writer = self.index.writer()
        try:
            writer.commit(mergetype=writer.CLEAR)
            logger.info("Cleared Whoosh index")
        except Exception as e:
            logger.error(f"Failed to clear index: {e}")
            writer.cancel()
    
    def get_stats(self) -> Dict:
        """Get index statistics"""
        with self.index.searcher() as searcher:
            return {
                "total_documents": searcher.doc_count(),
                "indexed_fields": list(self.schema.names()),
                "index_path": str(self.index_dir / "main")
            }
import os
from pathlib import Path
from typing import List, Dict, Optional
import chromadb
from chromadb.config import Settings
import numpy as np
import logging

from config import config

logger = logging.getLogger(__name__)

class ChromaStore:
    """ChromaDB vector store with DuckDB backend"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize ChromaDB client"""
        try:
            # Create ChromaDB client with DuckDB persistence
            self.client = chromadb.PersistentClient(
                path=str(config.CHROMA_DIR),
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Get or create collection
            try:
                self.collection = self.client.get_collection("documents")
                logger.info(f"Loaded existing ChromaDB collection: documents")
            except:
                self.collection = self.client.create_collection(
                    name="documents",
                    metadata={"hnsw:space": "cosine"}
                )
                logger.info(f"Created new ChromaDB collection: documents")
                
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            raise
    
    @classmethod
    def initialize(cls):
        """Initialize ChromaDB storage"""
        chroma_dir = Path(config.CHROMA_DIR)
        chroma_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized ChromaDB at {chroma_dir}")
    
    def index_chunks(self, chunks: List[Dict], embeddings: List[List[float]]):
        """Index chunks with embeddings"""
        if not chunks or not embeddings:
            return
        
        if len(chunks) != len(embeddings):
            logger.error(f"Mismatch: {len(chunks)} chunks vs {len(embeddings)} embeddings")
            return
        
        try:
            # Prepare data for ChromaDB
            ids = []
            documents = []
            metadatas = []
            
            for chunk in chunks:
                ids.append(chunk["chunk_id"])
                documents.append(chunk["text"])
                
                # Prepare metadata
                metadata = {
                    "doc_id": chunk.get("doc_id", ""),
                    "page": chunk.get("page", 0),
                    "start_char": chunk.get("start_char", 0),
                    "end_char": chunk.get("end_char", 0),
                    "type": chunk.get("type", "content"),
                    "section_or_page": chunk.get("section_or_page", 0)
                }
                
                # ChromaDB requires all metadata values to be strings, ints, floats, or bools
                metadata = {k: v for k, v in metadata.items() if v is not None}
                metadatas.append(metadata)
            
            # Add to collection
            self.collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas
            )
            
            logger.info(f"Indexed {len(chunks)} chunks in ChromaDB")
            
        except Exception as e:
            logger.error(f"Failed to index in ChromaDB: {e}")
    
    def add_documents(self, texts: List[str], embeddings: List[List[float]], 
                      metadatas: List[Dict], ids: List[str]):
        """Add documents to ChromaDB (alternative interface)"""
        try:
            self.collection.add(
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas
            )
            logger.info(f"Added {len(texts)} documents to ChromaDB")
        except Exception as e:
            logger.error(f"Failed to add documents to ChromaDB: {e}")
    
    def search(self, query_embedding: List[float], limit: int = None) -> List[Dict]:
        """Search using vector similarity"""
        if limit is None:
            limit = config.TOPK_VECTOR
        
        results = []
        
        try:
            # Query collection
            query_results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            if query_results and query_results["ids"]:
                ids = query_results["ids"][0]
                documents = query_results["documents"][0]
                metadatas = query_results["metadatas"][0]
                distances = query_results["distances"][0]
                
                for i in range(len(ids)):
                    # Convert distance to similarity score (1 - cosine distance)
                    score = 1.0 - distances[i]
                    
                    result = {
                        "chunk_id": ids[i],
                        "text": documents[i],
                        "score": score,
                        **metadatas[i]  # Include all metadata
                    }
                    results.append(result)
            
            logger.info(f"Vector search found {len(results)} results")
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
        
        return results
    
    def get_chunk(self, chunk_id: str) -> Optional[Dict]:
        """Get a specific chunk by ID"""
        try:
            result = self.collection.get(
                ids=[chunk_id],
                include=["documents", "metadatas"]
            )
            
            if result and result["ids"]:
                return {
                    "chunk_id": result["ids"][0],
                    "text": result["documents"][0],
                    **result["metadatas"][0]
                }
            
        except Exception as e:
            logger.error(f"Failed to get chunk {chunk_id}: {e}")
        
        return None
    
    def delete_chunk(self, chunk_id: str):
        """Delete a chunk from the store"""
        try:
            self.collection.delete(ids=[chunk_id])
            logger.info(f"Deleted chunk: {chunk_id}")
        except Exception as e:
            logger.error(f"Failed to delete chunk {chunk_id}: {e}")
    
    def delete_document(self, doc_id: str) -> int:
        """Delete all chunks for a document"""
        try:
            # Query for all chunks with this doc_id
            results = self.collection.get(
                where={"doc_id": doc_id}
            )
            
            if results and results['ids']:
                chunk_ids = results['ids']
                self.collection.delete(ids=chunk_ids)
                logger.info(f"Deleted {len(chunk_ids)} chunks for document: {doc_id}")
                return len(chunk_ids)
            else:
                logger.info(f"No chunks found for document: {doc_id}")
                return 0
        except Exception as e:
            logger.error(f"Failed to delete document {doc_id}: {e}")
            return 0
    
    def update_chunk(self, chunk: Dict, embedding: List[float]):
        """Update a chunk in the store"""
        try:
            # Delete old version
            self.collection.delete(ids=[chunk["chunk_id"]])
            
            # Add new version
            metadata = {
                "doc_id": chunk.get("doc_id", ""),
                "page": chunk.get("page", 0),
                "start_char": chunk.get("start_char", 0),
                "end_char": chunk.get("end_char", 0),
                "type": chunk.get("type", "content"),
                "section_or_page": chunk.get("section_or_page", 0)
            }
            
            self.collection.add(
                ids=[chunk["chunk_id"]],
                documents=[chunk["text"]],
                embeddings=[embedding],
                metadatas=[metadata]
            )
            
            logger.info(f"Updated chunk: {chunk['chunk_id']}")
            
        except Exception as e:
            logger.error(f"Failed to update chunk: {e}")
    
    def clear_collection(self):
        """Clear all documents from collection"""
        try:
            # Delete and recreate collection
            self.client.delete_collection("documents")
            self.collection = self.client.create_collection(
                name="documents",
                metadata={"hnsw:space": "cosine"}
            )
            logger.info("Cleared ChromaDB collection")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
    
    def get_stats(self) -> Dict:
        """Get collection statistics"""
        try:
            count = self.collection.count()
            return {
                "total_documents": count,
                "collection_name": "documents",
                "storage_path": str(config.CHROMA_DIR)
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {
                "total_documents": 0,
                "error": str(e)
            }
import os
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
from pathlib import Path

from config import config

logger = logging.getLogger(__name__)

class Embedder:
    """Multi-model embedder with fallback support"""
    
    def __init__(self):
        self.model = None
        self.model_name = None
        self.batch_size = config.EMBED_BATCH
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize embedding model with fallback"""
        model_candidates = [
            config.PRIMARY_EMBED,
            config.SECONDARY_EMBED, 
            config.FALLBACK_EMBED
        ]
        
        for model_name in model_candidates:
            try:
                # Check for local cached model first
                local_path = f"models/embeddings/{model_name.replace('/', '_')}"
                if Path(local_path).exists():
                    logger.info(f"Loading cached model: {local_path}")
                    self.model = SentenceTransformer(local_path)
                    self.model_name = model_name
                    break
                else:
                    # Try to load from HuggingFace
                    logger.info(f"Loading model: {model_name}")
                    self.model = SentenceTransformer(model_name)
                    self.model_name = model_name
                    break
            except Exception as e:
                logger.warning(f"Failed to load {model_name}: {e}")
                continue
        
        if self.model is None:
            # Ultimate fallback - use a very basic model
            logger.error("All embedding models failed, using basic fallback")
            self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
            self.model_name = "fallback-miniLM"
        
        logger.info(f"Using embedding model: {self.model_name}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text"""
        if not text:
            return np.zeros(self.model.get_sentence_embedding_dimension())
        
        try:
            embedding = self.model.encode(
                text,
                normalize_embeddings=True,
                show_progress_bar=False
            )
            return embedding
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return np.zeros(self.model.get_sentence_embedding_dimension())
    
    def embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        """Embed a batch of texts"""
        if not texts:
            return []
        
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=self.batch_size,
                normalize_embeddings=True,
                show_progress_bar=len(texts) > 100
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Batch embedding failed: {e}")
            # Fallback to individual embedding
            return [self.embed_text(text).tolist() for text in texts]
    
    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.model.get_sentence_embedding_dimension()
    
    def encode_query(self, query: str) -> np.ndarray:
        """Encode query with special handling if needed"""
        # Some models have different encoding for queries vs documents
        if self.model_name and "bge" in self.model_name.lower():
            # BGE models benefit from query prefix
            query = f"query: {query}"
        
        return self.embed_text(query)
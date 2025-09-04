from typing import List, Dict, Tuple, Optional
import numpy as np
from pathlib import Path
import logging
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from config import config

logger = logging.getLogger(__name__)

class Reranker:
    """Multilingual reranker with ONNX support"""
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.use_onnx = config.RERANK_USE_ONNX
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize reranker model"""
        try:
            # Check for local model first
            local_path = Path("models/reranker/jina-reranker")
            
            if local_path.exists():
                logger.info(f"Loading local reranker from {local_path}")
                self.tokenizer = AutoTokenizer.from_pretrained(str(local_path))
                
                if self.use_onnx and (local_path / "model.onnx").exists():
                    # Load ONNX model
                    self._load_onnx_model(str(local_path))
                else:
                    # Load PyTorch model
                    self.model = AutoModelForSequenceClassification.from_pretrained(
                        str(local_path),
                        torch_dtype=torch.float32  # Force FP32 to avoid BFloat16 issues
                    ).to(self.device)
                    self.model.eval()
            else:
                # Load from HuggingFace
                logger.info(f"Loading reranker: {config.RERANKER_ID}")
                self.tokenizer = AutoTokenizer.from_pretrained(config.RERANKER_ID, trust_remote_code=True)
                self.model = AutoModelForSequenceClassification.from_pretrained(
                    config.RERANKER_ID,
                    trust_remote_code=True,
                    torch_dtype=torch.float32  # Force FP32 to avoid BFloat16 issues
                ).to(self.device)
                self.model.eval()
            
            logger.info(f"Reranker loaded successfully (device: {self.device})")
            
        except Exception as e:
            logger.error(f"Failed to load reranker: {e}")
            logger.warning("Reranking will be disabled")
            self.model = None
            self.tokenizer = None
    
    def _load_onnx_model(self, model_path: str):
        """Load ONNX model for faster inference"""
        try:
            import onnxruntime as ort
            
            onnx_path = Path(model_path) / "model.onnx"
            
            # Create ONNX session
            providers = ['CUDAExecutionProvider', 'CPUExecutionProvider']
            self.ort_session = ort.InferenceSession(str(onnx_path), providers=providers)
            
            logger.info("Loaded ONNX reranker model")
            self.use_onnx = True
            
        except ImportError:
            logger.warning("ONNX Runtime not available, falling back to PyTorch")
            self.use_onnx = False
            # Fall back to PyTorch
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_path
            ).to(self.device)
            self.model.eval()
        except Exception as e:
            logger.error(f"Failed to load ONNX model: {e}")
            self.use_onnx = False
    
    def rerank(self, query: str, passages: List[Dict], top_k: int = None) -> List[Dict]:
        """Rerank passages based on relevance to query"""
        if top_k is None:
            top_k = config.TOPK_RERANK
        
        if not self.model and not (self.use_onnx and hasattr(self, 'ort_session')):
            logger.warning("Reranker not available, returning original order")
            return passages[:top_k]
        
        if not passages:
            return []
        
        try:
            # Score each passage
            scores = self._score_passages(query, passages)
            
            # Add rerank scores to passages
            for passage, score in zip(passages, scores):
                passage["rerank_score"] = score
            
            # Sort by rerank score
            reranked = sorted(passages, key=lambda x: x["rerank_score"], reverse=True)
            
            # Apply weight and update hybrid score
            for p in reranked[:top_k]:
                if "hybrid_score" in p:
                    p["hybrid_score"] = (
                        p.get("rrf_score", 0) * (1 - config.W_RERANK) +
                        p["rerank_score"] * config.W_RERANK
                    )
                else:
                    p["hybrid_score"] = p["rerank_score"]
            
            logger.info(f"Reranked {len(passages)} passages, returning top {top_k}")
            return reranked[:top_k]
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            return passages[:top_k]
    
    def _score_passages(self, query: str, passages: List[Dict]) -> List[float]:
        """Score passages using the reranker model"""
        texts = [p.get("text", "") for p in passages]
        
        if self.use_onnx and hasattr(self, 'ort_session'):
            return self._score_with_onnx(query, texts)
        else:
            return self._score_with_pytorch(query, texts)
    
    def _score_with_pytorch(self, query: str, passages: List[str]) -> List[float]:
        """Score using PyTorch model"""
        scores = []
        
        # Process in batches for efficiency
        batch_size = 8
        
        for i in range(0, len(passages), batch_size):
            batch_passages = passages[i:i+batch_size]
            
            # Tokenize
            inputs = self.tokenizer(
                [query] * len(batch_passages),
                batch_passages,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt"
            ).to(self.device)
            
            # Get scores
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                
                # Convert to probabilities
                if logits.shape[-1] == 1:
                    # Regression score
                    batch_scores = torch.sigmoid(logits).squeeze(-1).cpu().numpy()
                else:
                    # Classification - use positive class probability
                    batch_scores = torch.softmax(logits, dim=-1)[:, 1].cpu().numpy()
            
            scores.extend(batch_scores.tolist())
        
        return scores
    
    def _score_with_onnx(self, query: str, passages: List[str]) -> List[float]:
        """Score using ONNX model"""
        scores = []
        
        # Process in batches
        batch_size = 8
        
        for i in range(0, len(passages), batch_size):
            batch_passages = passages[i:i+batch_size]
            
            # Tokenize
            inputs = self.tokenizer(
                [query] * len(batch_passages),
                batch_passages,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="np"
            )
            
            # Prepare ONNX inputs
            ort_inputs = {
                "input_ids": inputs["input_ids"],
                "attention_mask": inputs["attention_mask"]
            }
            
            if "token_type_ids" in inputs:
                ort_inputs["token_type_ids"] = inputs["token_type_ids"]
            
            # Run inference
            outputs = self.ort_session.run(None, ort_inputs)
            logits = outputs[0]
            
            # Convert to scores
            if logits.shape[-1] == 1:
                # Regression
                batch_scores = 1 / (1 + np.exp(-logits)).squeeze(-1)
            else:
                # Classification
                exp_logits = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
                batch_scores = exp_logits[:, 1] / np.sum(exp_logits, axis=-1)
            
            scores.extend(batch_scores.tolist())
        
        return scores
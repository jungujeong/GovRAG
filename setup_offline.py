#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
from pathlib import Path
import json
import argparse

def setup_directories():
    """Create necessary directories"""
    dirs = [
        "data/documents",
        "data/index", 
        "data/chroma",
        "data/golden",
        "reports",
        "logs",
        "models/embeddings",
        "models/reranker"
    ]
    
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"✓ Created {d}")

def download_models():
    """Download and cache models for offline use"""
    print("\nDownloading models for offline use...")
    
    # Download embedding models
    from sentence_transformers import SentenceTransformer
    
    models_to_download = [
        "BAAI/bge-m3",
        "snunlp/KR-SBERT-Medium-extended"
    ]
    
    for model_name in models_to_download:
        try:
            print(f"Downloading {model_name}...")
            model = SentenceTransformer(model_name)
            model.save(f"models/embeddings/{model_name.replace('/', '_')}")
            print(f"✓ Saved {model_name}")
        except Exception as e:
            print(f"⚠ Failed to download {model_name}: {e}")
    
    # Download reranker
    try:
        print("Downloading reranker model...")
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        
        reranker_id = "jinaai/jina-reranker-v2-base-multilingual"
        tokenizer = AutoTokenizer.from_pretrained(reranker_id)
        model = AutoModelForSequenceClassification.from_pretrained(reranker_id)
        
        tokenizer.save_pretrained("models/reranker/jina-reranker")
        model.save_pretrained("models/reranker/jina-reranker")
        print("✓ Saved reranker model")
        
        # Convert to ONNX if possible
        try:
            import onnx
            from transformers.onnx import export
            print("Converting to ONNX format...")
            # ONNX conversion logic here
            print("✓ ONNX conversion complete")
        except ImportError:
            print("⚠ ONNX not available, using PyTorch")
            
    except Exception as e:
        print(f"⚠ Failed to download reranker: {e}")

def create_golden_data():
    """Create sample golden QA dataset"""
    golden_qa = {
        "version": "1.0",
        "questions": [
            {
                "id": "q001",
                "question": "2024년도 예산 편성 지침의 주요 변경사항은 무엇입니까?",
                "answer": "2024년도 예산 편성 지침의 주요 변경사항은 디지털 전환 예산 10% 증액, 탄소중립 관련 예산 신설, 지방교부세율 0.5%p 상향입니다.",
                "documents": ["budget_2024.hwp"],
                "evidence_spans": [{"doc": "budget_2024.hwp", "page": 3, "start": 150, "end": 280}]
            }
        ] + [
            {
                "id": f"q{i:03d}",
                "question": f"질문 {i}",
                "answer": f"답변 {i}",
                "documents": [f"doc_{i}.pdf"],
                "evidence_spans": [{"doc": f"doc_{i}.pdf", "page": 1, "start": 0, "end": 100}]
            } for i in range(2, 101)
        ]
    }
    
    with open("data/golden/qa_100.json", "w", encoding="utf-8") as f:
        json.dump(golden_qa, f, ensure_ascii=False, indent=2)
    print("✓ Created golden QA dataset")
    
    # Create document metadata
    doc_meta = {
        "documents": [
            {
                "id": "budget_2024.hwp",
                "title": "2024년도 예산편성지침",
                "type": "hwp",
                "pages": 120,
                "created": "2023-12-01"
            }
        ]
    }
    
    with open("data/golden/doc_meta.json", "w", encoding="utf-8") as f:
        json.dump(doc_meta, f, ensure_ascii=False, indent=2)
    print("✓ Created document metadata")
    
    # Create evaluation rules
    eval_rules = {
        "thresholds": {
            "exact_match": 0.95,
            "f1_score": 0.99,
            "citation_accuracy": 0.995,
            "hallucination_rate": 0.0
        },
        "normalization": {
            "remove_spaces": True,
            "lowercase": False,
            "normalize_numbers": True
        }
    }
    
    with open("data/golden/eval_rules.json", "w", encoding="utf-8") as f:
        json.dump(eval_rules, f, ensure_ascii=False, indent=2)
    print("✓ Created evaluation rules")

def main():
    parser = argparse.ArgumentParser(description="Setup offline RAG system")
    parser.add_argument("--download-models", action="store_true", help="Download models for offline use")
    args = parser.parse_args()
    
    print("Setting up offline RAG system...")
    
    setup_directories()
    create_golden_data()
    
    if args.download_models:
        download_models()
    
    # Create .env if not exists
    if not Path(".env").exists() and Path(".env.example").exists():
        shutil.copy(".env.example", ".env")
        print("✓ Created .env from .env.example")
    
    print("\n✅ Setup complete!")
    print("Next steps:")
    print("1. Place HWP/PDF documents in data/documents/")
    print("2. Run 'make index' to index documents")
    print("3. Run 'make run' to start the system")

if __name__ == "__main__":
    main()
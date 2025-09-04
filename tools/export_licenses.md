# Open Source Licenses

This document lists all open source dependencies and their licenses used in the RAG Chatbot System.

## Python Dependencies

### Core Framework
- **FastAPI** - MIT License
- **Uvicorn** - BSD 3-Clause License
- **Pydantic** - MIT License

### Search & Retrieval
- **Whoosh** - BSD 2-Clause License
- **ChromaDB** - Apache License 2.0
- **Sentence-Transformers** - Apache License 2.0

### Document Processing
- **PyMuPDF (fitz)** - AGPL-3.0 License
- **pytesseract** - Apache License 2.0
- **JPype1** - Apache License 2.0

### Machine Learning
- **Transformers** - Apache License 2.0
- **PyTorch** - BSD 3-Clause License
- **ONNX Runtime** - MIT License

### Utilities
- **NumPy** - BSD 3-Clause License
- **Pandas** - BSD 3-Clause License
- **scikit-learn** - BSD 3-Clause License
- **RapidFuzz** - MIT License
- **httpx** - BSD 3-Clause License
- **python-dotenv** - BSD 3-Clause License

## Frontend Dependencies

### Core Framework
- **React** - MIT License
- **React DOM** - MIT License
- **Vite** - MIT License

### UI Components
- **Tailwind CSS** - MIT License
- **React Dropzone** - MIT License
- **React Markdown** - MIT License

### State Management
- **Zustand** - MIT License

### HTTP Client
- **Axios** - MIT License

## Model Licenses

### Embedding Models
- **BAAI/bge-m3** - MIT License
- **KoE5** - Apache License 2.0
- **KR-SBERT** - Apache License 2.0

### Reranker Models
- **Jina Reranker** - Apache License 2.0

### Language Models (via Ollama)
- **Qwen** - Apache License 2.0
- Model licenses vary - check specific model documentation

## System Dependencies

### OCR
- **Tesseract OCR** - Apache License 2.0

### Java (for HWP)
- **OpenJDK** - GPL v2 with Classpath Exception
- **hwplib** - Apache License 2.0

## License Summary

Most components use permissive licenses (MIT, Apache 2.0, BSD):
- ✅ Commercial use allowed
- ✅ Modification allowed
- ✅ Distribution allowed
- ✅ Private use allowed

**Important Notes:**
1. PyMuPDF uses AGPL-3.0 which requires source disclosure if distributed
2. Some models may have additional usage restrictions
3. Always review individual licenses before commercial deployment

## Compliance Checklist

For production deployment:
- [ ] Review all dependency licenses
- [ ] Include license notices in distribution
- [ ] Comply with AGPL requirements for PyMuPDF
- [ ] Verify model licenses for intended use
- [ ] Document any modifications to open source code

---

*Last updated: 2024*
*This list may not be exhaustive. Run `pip-licenses` for complete Python dependency licenses.*
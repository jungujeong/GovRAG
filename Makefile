.PHONY: install bundle index qa run clean setup validate

install:
	@echo "Installing dependencies..."
	python3 -m pip install --upgrade pip
	python3 -m pip install -r requirements.txt
	python3 setup_offline.py --download-models
	@echo "Setting up Tesseract OCR..."
	@if ! command -v tesseract > /dev/null; then \
		echo "Tesseract not found. Please install manually:"; \
		echo "  macOS: brew install tesseract tesseract-lang"; \
		echo "  Linux: sudo apt-get install tesseract-ocr tesseract-ocr-kor"; \
		echo "  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki"; \
	fi
	cd frontend && npm install
	@echo "Installation complete!"

bundle:
	@echo "Creating offline bundle..."
	python3 tools/bundle_creator.py
	@echo "Bundle created at dist/offline_bundle.tar.gz"

index:
	@echo "Indexing documents..."
	python3 -c "from backend.processors.indexer import index_all_documents; index_all_documents()"
	@echo "Indexing complete!"

qa:
	@echo "Running golden QA evaluation..."
	python3 -m backend.eval.golden_evaluator
	@echo "Evaluation complete! Check reports/accuracy_dashboard.html"

run:
	@echo "Starting RAG system..."
	@trap 'kill %1 %2' SIGINT; \
	(cd backend && PYTHONPATH=. uvicorn main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

clean:
	@echo "Cleaning up generated files..."
	rm -rf data/index/* data/chroma/* __pycache__ .pytest_cache
	find . -name "*.pyc" -delete
	@echo "Cleanup complete!"

setup:
	@echo "Setting up project structure..."
	mkdir -p data/documents data/index data/chroma data/golden
	mkdir -p reports logs
	cp .env.example .env
	@echo "Project structure ready!"

validate:
	@echo "Validating installation..."
	python3 tools/validate_installation.py
	@echo "Validation complete!"
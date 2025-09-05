.PHONY: install bundle index qa run clean help

# Default target
help:
	@echo "RAG Chatbot System - Make Commands"
	@echo "=================================="
	@echo "make install  - Install dependencies"
	@echo "make bundle   - Create offline bundle"
	@echo "make index    - Index documents"
	@echo "make qa       - Run quality tests"
	@echo "make run      - Start the system"
	@echo "make clean    - Clean generated files"

# Install dependencies
install:
	@echo "Installing Python dependencies..."
	pip install -r requirements.txt
	@echo "Creating data directories..."
	mkdir -p data/documents data/index data/chroma data/golden reports
	@echo "Copying .env.example to .env if not exists..."
	[ -f .env ] || cp .env.example .env
	@echo "Installing frontend dependencies..."
	cd frontend && npm install
	@echo "✅ Installation complete!"

# Create offline bundle
bundle:
	@echo "Creating offline bundle..."
	python tools/bundle_creator.py
	@echo "✅ Bundle created!"

# Index documents
index:
	@echo "Indexing documents..."
	cd backend && python processors/indexer.py
	@echo "✅ Indexing complete!"

# Run QA tests
qa:
	@echo "Running QA evaluation..."
	cd backend && python eval/golden_evaluator.py
	@echo "✅ QA evaluation complete!"

# Run the system
run:
	@echo "Starting RAG system..."
	@trap 'kill %1 %2' SIGINT; \
	(cd backend && PYTHONPATH=. uvicorn main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf data/index/* data/chroma/* reports/* __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	@echo "✅ Clean complete!"

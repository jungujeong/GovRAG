.PHONY: install bundle index qa run run-dev stop clean setup validate index-backup index-restore index-verify index-repair index-list index-clean

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
	cd backend && PYTHONPATH=. python3 -c "import asyncio; from processors.indexer import index_all_documents; asyncio.run(index_all_documents())"
	@echo "Indexing complete!"

qa:
	@echo "Running golden QA evaluation..."
	python3 -m backend.eval.golden_evaluator
	@echo "Evaluation complete! Check reports/accuracy_dashboard.html"

run:
	@echo "Starting RAG system..."
	@# Ensure dev ports are free before starting
	@if command -v lsof >/dev/null 2>&1; then \
		if lsof -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then \
			echo "Error: Port 8000 is in use. Run 'make stop' or free the port."; \
			exit 1; \
		fi; \
		if lsof -tiTCP:5173 -sTCP:LISTEN >/dev/null 2>&1; then \
			echo "Error: Port 5173 is in use. Run 'make stop' or free the port."; \
			exit 1; \
		fi; \
	fi
	@echo "Starting backend..."
	@(cd backend && PYTHONPATH=. uvicorn main:app --port 8000) & \
	BACKEND_PID=$$!; \
	sleep 2; \
	echo "Starting frontend..."; \
	(cd frontend && npm run dev) & \
	FRONTEND_PID=$$!; \
	trap 'kill $$BACKEND_PID $$FRONTEND_PID 2>/dev/null' SIGINT SIGTERM; \
	echo "✓ Both servers started. Press Ctrl+C to stop."; \
	echo "  Frontend: http://localhost:5173"; \
	echo "  Backend:  http://localhost:8000"; \
	wait

run-dev:
	@echo "Starting RAG system in dev mode (auto-reload)..."
	@trap 'kill %1 %2' SIGINT; \
	(cd backend && PYTHONPATH=. uvicorn main:app --reload --port 8000) & \
	(cd frontend && npm run dev) & \
	wait

stop:
	@echo "Stopping RAG system..."
	@bash ./stop.sh || true
	@echo "Stopped."

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

# Index management commands
index-backup:
	@echo "Creating index backup..."
	cd backend && python3 utils/index_manager.py backup
	@echo "Backup complete!"

index-restore:
	@echo "Restoring index from backup..."
	cd backend && python3 utils/index_manager.py restore
	@echo "Restore complete!"

index-verify:
	@echo "Verifying index integrity..."
	cd backend && python3 utils/index_manager.py verify
	@echo "Verification complete!"

index-repair:
	@echo "Repairing corrupted indexes..."
	cd backend && python3 utils/index_manager.py repair
	@echo "Repair complete!"

index-list:
	@echo "Listing available backups..."
	cd backend && python3 utils/index_manager.py list

index-clean:
	@echo "Cleaning old backups..."
	cd backend && python3 utils/index_manager.py clean
	@echo "Cleanup complete!"

# Repository Guidelines

## Project Structure & Module Organization
- `backend/` FastAPI app (`main.py`), API `routers/`, RAG logic in `rag/`, indexing in `processors/`, shared `services/` and `utils/`.
- `frontend/` Vite + React UI (`src/components`, `src/hooks`, `src/services`).
- `data/` runtime artifacts: `documents/`, `index/`, `chroma/` (never commit).
- `tests/` Python tests for retrieval/generation; `tools/` utilities; `scripts/` Windows helpers; `reports/`, `logs/` outputs.

## Build, Test, and Development Commands
- `make setup` Create folders and copy `.env.example` to `.env`.
- `make install` Install Python deps and frontend packages; download models.
- `make index` Index documents in `data/documents/`.
- `make run` Run backend (Uvicorn) and frontend (Vite) together.
- `make qa` Run golden QA evaluation; results in `reports/`.
- Backend only: `cd backend && PYTHONPATH=. uvicorn main:app --reload --port 8000`.
- Frontend only: `cd frontend && npm run dev`.

## Coding Style & Naming Conventions
- Python: PEP 8, 4‑space indent, type hints, module names `snake_case.py`, classes `PascalCase`, functions `snake_case`. Keep functions small; add docstrings when non‑trivial.
- JavaScript/React: functional components, hooks, components `PascalCase` (e.g., `DocumentDetail.jsx`), variables/functions `camelCase`. Co-locate small helpers in `src/utils`.

## Testing Guidelines
- Framework: `pytest`. Run with `pytest tests -q` (install `pytest` if missing).
- Name tests `tests/test_*.py`; prefer fast, deterministic unit tests around `backend/rag` and `processors`.
- When adding features, include tests and, when applicable, golden cases for `make qa`. No strict coverage threshold; aim for meaningful coverage on new code.

## Commit & Pull Request Guidelines
- Use Conventional Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:` (e.g., `feat(rag): add RRF fusion weights`).
- PRs: clear description, linked issues, steps to validate. Include screenshots/GIFs for UI changes and sample requests for API changes. Update README or comments when behavior changes.

## Security & Configuration Tips
- Configure via `.env` (see `.env.example`); common keys: `APP_PORT`, `OLLAMA_HOST`, `WHOOSH_DIR`, `CHROMA_DIR`.
- Never commit data, indexes, logs, or secrets (`.gitignore` already protects `data/*`, `logs/`, `reports/*.json/html`).
- Use Node `lts/*` (`.nvmrc`) and Python 3.11+ where possible.

## Agent-Specific Instructions
- Prefer `make` targets; avoid ad‑hoc scripts when a target exists.
- Touch only files relevant to the task; keep patches focused and consistent with existing patterns in `backend/rag`, `routers`, and `frontend/src`.
- Do not write to `data/` in patches; rely on runtime indexing.

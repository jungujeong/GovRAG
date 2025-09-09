@echo off
REM Windows indexing script

echo Indexing documents...
cd backend
set PYTHONPATH=.
python -c "import asyncio; from processors.indexer import index_all_documents; asyncio.run(index_all_documents())"
cd ..
echo Indexing complete!
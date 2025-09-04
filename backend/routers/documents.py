from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks
from typing import List, Dict, Optional
from pathlib import Path
import shutil
import logging

from config import config
from processors.indexer import DocumentIndexer

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize indexer
indexer = DocumentIndexer()

@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict:
    """Upload and index a document"""
    
    # Validate file type
    if not file.filename.lower().endswith(('.pdf', '.hwp')):
        raise HTTPException(
            status_code=400,
            detail="Only PDF and HWP files are supported"
        )
    
    # Save file
    file_path = Path(config.DOC_DIR) / file.filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.info(f"Saved file: {file_path}")
        
        # Index in background - make sure path is absolute
        absolute_path = file_path.resolve()
        logger.info(f"Indexing document: {absolute_path}")
        background_tasks.add_task(indexer.index_document, absolute_path)
        
        return {
            "status": "uploaded",
            "filename": file.filename,
            "path": str(file_path),
            "message": "Document uploaded and queued for indexing"
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        file.file.close()

@router.post("/upload-batch")
async def upload_batch(
    files: List[UploadFile] = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> Dict:
    """Upload multiple documents"""
    
    uploaded = []
    failed = []
    
    for file in files:
        try:
            # Validate file type
            if not file.filename.lower().endswith(('.pdf', '.hwp')):
                failed.append({
                    "filename": file.filename,
                    "error": "Unsupported file type"
                })
                continue
            
            # Save file
            file_path = Path(config.DOC_DIR) / file.filename
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            uploaded.append(file.filename)
            
            # Queue for indexing - use absolute path
            absolute_path = file_path.resolve()
            logger.info(f"Queuing for indexing: {absolute_path}")
            background_tasks.add_task(indexer.index_document, absolute_path)
            
        except Exception as e:
            logger.error(f"Failed to upload {file.filename}: {e}")
            failed.append({
                "filename": file.filename,
                "error": str(e)
            })
        finally:
            file.file.close()
    
    return {
        "uploaded": uploaded,
        "failed": failed,
        "total": len(files),
        "message": f"Uploaded {len(uploaded)} files, {len(failed)} failed"
    }

@router.get("/list")
async def list_documents() -> List[Dict]:
    """List all indexed documents"""
    
    doc_dir = Path(config.DOC_DIR)
    
    if not doc_dir.exists():
        return []
    
    documents = []
    
    for file_path in doc_dir.glob("**/*"):
        if file_path.suffix.lower() in ['.pdf', '.hwp']:
            documents.append({
                "filename": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size,
                "modified": file_path.stat().st_mtime,
                "type": file_path.suffix[1:].upper()
            })
    
    return documents

@router.delete("/{filename}")
async def delete_document(filename: str) -> Dict:
    """Delete a document and its index"""
    
    from rag.whoosh_bm25 import WhooshBM25
    from rag.chroma_store import ChromaStore
    import unicodedata
    
    file_path = Path(config.DOC_DIR) / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    
    try:
        # Get document ID (filename without extension)
        doc_id = file_path.stem
        # Normalize for matching (handle Unicode normalization)
        doc_id_normalized = unicodedata.normalize("NFC", doc_id)
        
        # Delete from Whoosh index
        whoosh = WhooshBM25()
        whoosh_count = whoosh.delete_document(doc_id_normalized)
        
        # Delete from ChromaDB
        chroma = ChromaStore()
        chroma_count = chroma.delete_document(doc_id_normalized)
        
        # Delete physical file
        file_path.unlink()
        
        logger.info(f"Deleted document: {filename} (Whoosh: {whoosh_count} chunks, Chroma: {chroma_count} chunks)")
        
        return {
            "status": "deleted",
            "filename": filename,
            "chunks_deleted": {
                "whoosh": whoosh_count,
                "chroma": chroma_count
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to delete {filename}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/reset/all")
async def reset_all_documents() -> Dict:
    """Delete all documents and clear all indexes"""
    
    from rag.whoosh_bm25 import WhooshBM25
    from rag.chroma_store import ChromaStore
    import shutil
    
    try:
        # Count documents before deletion
        doc_dir = Path(config.DOC_DIR)
        doc_count = len(list(doc_dir.glob("*.pdf"))) + len(list(doc_dir.glob("*.hwp")))
        
        # Clear Whoosh index
        whoosh = WhooshBM25()
        whoosh.clear_index()
        
        # Clear ChromaDB collection
        chroma = ChromaStore()
        chroma.clear_collection()
        
        # Delete all files in document directory
        for file_path in doc_dir.glob("*"):
            if file_path.is_file():
                file_path.unlink()
        
        # Also clear the extracted_directives directories if they exist
        extracted_dirs = [
            Path("data/extracted_directives"),
            Path("data/extracted_directives_v2")
        ]
        for dir_path in extracted_dirs:
            if dir_path.exists():
                shutil.rmtree(dir_path)
                dir_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Reset complete: Deleted {doc_count} documents and cleared all indexes")
        
        return {
            "status": "reset_complete",
            "documents_deleted": doc_count,
            "indexes_cleared": True
        }
        
    except Exception as e:
        logger.error(f"Failed to reset all: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reindex")
async def reindex_all(background_tasks: BackgroundTasks) -> Dict:
    """Reindex all documents"""
    
    doc_dir = Path(config.DOC_DIR)
    
    if not doc_dir.exists():
        raise HTTPException(status_code=404, detail="Document directory not found")
    
    # Clear existing indexes
    from rag.whoosh_bm25 import WhooshBM25
    from rag.chroma_store import ChromaStore
    
    whoosh = WhooshBM25()
    chroma = ChromaStore()
    
    whoosh.clear_index()
    chroma.clear_collection()
    
    # Queue reindexing
    background_tasks.add_task(indexer.index_directory, doc_dir)
    
    return {
        "status": "reindexing",
        "message": "All documents queued for reindexing"
    }

@router.get("/stats")
async def get_document_stats() -> Dict:
    """Get document and index statistics"""
    
    from rag.whoosh_bm25 import WhooshBM25
    from rag.chroma_store import ChromaStore
    
    whoosh = WhooshBM25()
    chroma = ChromaStore()
    
    # Count documents
    doc_dir = Path(config.DOC_DIR)
    doc_count = 0
    total_size = 0
    
    if doc_dir.exists():
        for file_path in doc_dir.glob("**/*"):
            if file_path.suffix.lower() in ['.pdf', '.hwp']:
                doc_count += 1
                total_size += file_path.stat().st_size
    
    return {
        "documents": {
            "count": doc_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        },
        "whoosh": whoosh.get_stats(),
        "chroma": chroma.get_stats()
    }

@router.get("/detail/{filename}")
async def get_document_detail(filename: str) -> Dict:
    """Get detailed information about a document including processed text"""
    
    from rag.whoosh_bm25 import WhooshBM25
    from rag.chroma_store import ChromaStore
    import unicodedata
    
    # Check if file exists
    file_path = Path(config.DOC_DIR) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get basic file info
    doc_info = {
        "filename": file_path.name,
        "path": str(file_path),
        "size": file_path.stat().st_size,
        "size_mb": round(file_path.stat().st_size / (1024 * 1024), 2),
        "modified": file_path.stat().st_mtime,
        "type": file_path.suffix[1:].upper(),
        "chunks": [],
        "processed_text": []
    }
    
    # Get chunks from Whoosh index
    whoosh = WhooshBM25()
    doc_id = file_path.stem  # Document ID is filename without extension
    # Normalize the doc_id for comparison (handle Unicode normalization)
    doc_id_normalized = unicodedata.normalize("NFC", doc_id)
    
    try:
        # Search for all chunks of this document
        with whoosh.index.searcher() as searcher:
            # Get all documents and filter by doc_id manually
            # This is a workaround for the Term query not working
            results = []
            for docnum in range(searcher.doc_count_all()):
                stored = searcher.stored_fields(docnum)
                stored_doc_id = stored.get("doc_id", "")
                # Normalize the stored doc_id for comparison
                stored_doc_id_normalized = unicodedata.normalize("NFC", stored_doc_id)
                if stored_doc_id_normalized == doc_id_normalized:
                    results.append(stored)
            
            chunks_by_page = {}
            for result in results:
                page = result.get("page", 0)
                if page not in chunks_by_page:
                    chunks_by_page[page] = []
                
                chunk_info = {
                    "chunk_id": result.get("chunk_id", ""),
                    "page": page,
                    "text": result.get("text", ""),
                    "start_char": result.get("start_char", 0),
                    "end_char": result.get("end_char", 0)
                }
                chunks_by_page[page].append(chunk_info)
            
            # Sort chunks by page and position
            for page in sorted(chunks_by_page.keys()):
                chunks_by_page[page].sort(key=lambda x: x.get("start_char", 0))
                doc_info["chunks"].extend(chunks_by_page[page])
                
                # Combine chunks text for each page
                page_text = "\n".join([chunk["text"] for chunk in chunks_by_page[page]])
                if page_text:
                    doc_info["processed_text"].append({
                        "page": page,
                        "text": page_text
                    })
    
    except Exception as e:
        logger.error(f"Error retrieving document chunks: {e}")
        doc_info["error"] = f"Could not retrieve indexed content: {str(e)}"
    
    # Add statistics
    doc_info["stats"] = {
        "total_chunks": len(doc_info["chunks"]),
        "total_pages": len(doc_info["processed_text"]),
        "avg_chunk_size": round(sum(len(c["text"]) for c in doc_info["chunks"]) / max(len(doc_info["chunks"]), 1), 2)
    }
    
    return doc_info
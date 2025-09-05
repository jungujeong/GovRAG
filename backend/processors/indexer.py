import os
from pathlib import Path
from typing import List, Dict
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed

# Handle imports based on how the module is run
import sys
if __name__ == "__main__":
    # Running as main script
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from backend.config import config
    from backend.processors.hwp_structure_parser import HWPStructureParser
    from backend.processors.pdf_hybrid_processor import PDFHybridProcessor
    from backend.processors.structure_chunker import StructureChunker
    from backend.processors.normalizer_govkr import NormalizerGovKR
    from backend.rag.whoosh_bm25 import WhooshBM25
    from backend.rag.chroma_store import ChromaStore
    from backend.rag.embedder import Embedder
else:
    # Imported as module
    from config import config
    from processors.hwp_structure_parser import HWPStructureParser
    from processors.pdf_hybrid_processor import PDFHybridProcessor
    from processors.structure_chunker import StructureChunker
    from processors.normalizer_govkr import NormalizerGovKR
    from rag.whoosh_bm25 import WhooshBM25
    from rag.chroma_store import ChromaStore
    from rag.embedder import Embedder

logger = logging.getLogger(__name__)

class DocumentIndexer:
    """Main document indexer orchestrator"""
    
    def __init__(self):
        self.hwp_parser = HWPStructureParser()
        self.pdf_processor = PDFHybridProcessor()
        self.chunker = StructureChunker(
            chunk_tokens=config.CHUNK_TOKENS,
            chunk_overlap=config.CHUNK_OVERLAP,
            table_as_separate=config.TABLE_AS_SEPARATE,
            footnote_backlink=config.FOOTNOTE_BACKLINK
        )
        self.normalizer = NormalizerGovKR()
        
        # Lazy initialization to avoid blocking on startup
        self._whoosh = None
        self._chroma = None
        self._embedder = None
        
    @property
    def whoosh(self):
        """Lazy-loaded Whoosh BM25 instance"""
        if self._whoosh is None:
            logger.info("Initializing Whoosh BM25...")
            self._whoosh = WhooshBM25()
        return self._whoosh
        
    @property
    def chroma(self):
        """Lazy-loaded ChromaDB instance"""
        if self._chroma is None:
            logger.info("Initializing ChromaDB...")
            self._chroma = ChromaStore()
        return self._chroma
        
    @property
    def embedder(self):
        """Lazy-loaded Embedder instance"""
        if self._embedder is None:
            logger.info("Initializing Embedder...")
            self._embedder = Embedder()
        return self._embedder
    
    def index_document_sync(self, file_path: Path) -> Dict:
        """Synchronous wrapper for index_document for background tasks"""
        import asyncio
        import threading
        
        # Handle event loop properly
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, run in thread pool
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._run_in_new_loop, file_path)
                return future.result()
        except RuntimeError:
            # No running loop, we can create one
            return asyncio.run(self.index_document(file_path))
    
    def _run_in_new_loop(self, file_path: Path) -> Dict:
        """Run indexing in a new event loop"""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.index_document(file_path))
        finally:
            loop.close()
    
    async def index_document(self, file_path: Path) -> Dict:
        """Index a single document"""
        logger.info(f"Indexing document: {file_path}")
        
        try:
            # Validate file exists
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return {"status": "error", "file": str(file_path), "error": "File not found"}
            
            # Parse document
            logger.info(f"Parsing document: {file_path.name}")
            if file_path.suffix.lower() == ".hwp":
                doc = self.hwp_parser.parse_hwp(str(file_path))
            elif file_path.suffix.lower() == ".pdf":
                doc = self.pdf_processor.parse_pdf(str(file_path))
            else:
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return {"status": "skipped", "file": str(file_path), "error": "Unsupported file type"}
            
            # Validate document parsing
            if not doc or not doc.get('pages'):
                logger.warning(f"No content extracted from {file_path.name}")
                return {"status": "no_content", "file": str(file_path), "error": "No content extracted"}
            
            # Log parsed content
            pages_count = len(doc.get('pages', []))
            tables_count = len(doc.get('tables', []))
            logger.info(f"Document parsed: {pages_count} pages, {tables_count} tables")
            
            # Chunk document
            logger.info(f"Chunking document: {file_path.name}")
            chunks = self.chunker.chunk_document(doc)
            logger.info(f"Created {len(chunks)} chunks from {file_path.name}")
            
            if not chunks:
                logger.warning(f"No chunks created for {file_path.name}")
                return {"status": "no_chunks", "file": str(file_path), "chunks": 0, "pages": pages_count}
            
            # Log first few chunks for debugging
            for i, chunk in enumerate(chunks[:3]):
                logger.info(f"Chunk {i}: {chunk.get('text', '')[:100]}...")
            
            # First, delete any existing chunks for this document to avoid duplicates
            doc_id = doc.get("doc_id", Path(file_path).stem)
            import unicodedata
            doc_id_normalized = unicodedata.normalize("NFC", doc_id)
            
            # Delete existing chunks from both indexes
            logger.info(f"Deleting existing chunks for {doc_id_normalized}")
            old_whoosh = self.whoosh.delete_document(doc_id_normalized)
            old_chroma = self.chroma.delete_document(doc_id_normalized)
            if old_whoosh > 0 or old_chroma > 0:
                logger.info(f"Removed {old_whoosh} chunks from Whoosh, {old_chroma} from ChromaDB")
            
            # Normalize chunks and remove duplicates
            normalized_chunks = []
            seen_texts = set()
            
            for chunk in chunks:
                normalized_chunk = self.normalizer.normalize_chunk(chunk)
                
                # Create a fingerprint for deduplication
                text_fingerprint = normalized_chunk["text"][:200].strip()
                if text_fingerprint not in seen_texts:
                    seen_texts.add(text_fingerprint)
                    normalized_chunks.append(normalized_chunk)
                else:
                    logger.debug(f"Skipping duplicate chunk: {normalized_chunk['chunk_id']}")
            
            logger.info(f"After deduplication: {len(chunks)} -> {len(normalized_chunks)} chunks")
            
            # Index in Whoosh
            try:
                logger.info(f"Indexing {len(normalized_chunks)} chunks in Whoosh...")
                self.whoosh.index_chunks(normalized_chunks)
                logger.info(f"✓ Added {len(normalized_chunks)} chunks to Whoosh")
            except Exception as e:
                logger.error(f"Failed to index in Whoosh: {e}")
                return {"status": "whoosh_error", "file": str(file_path), "error": str(e)}
            
            # Generate embeddings and index in Chroma
            try:
                logger.info(f"Generating embeddings for {len(normalized_chunks)} chunks...")
                texts = [chunk["text"] for chunk in normalized_chunks]
                embeddings = self.embedder.embed_batch(texts)
                logger.info(f"✓ Generated {len(embeddings)} embeddings")
            except Exception as e:
                logger.error(f"Failed to generate embeddings: {e}")
                return {"status": "embedding_error", "file": str(file_path), "error": str(e)}
            
            # Add to ChromaDB with proper metadata
            try:
                logger.info(f"Adding documents to ChromaDB...")
                self.chroma.add_documents(
                    texts=texts,
                    embeddings=embeddings,
                    metadatas=[{
                        "doc_id": chunk["doc_id"],
                        "page": chunk.get("page", 0),
                        "chunk_id": chunk["chunk_id"],
                        "start_char": chunk.get("start_char", 0),
                        "end_char": chunk.get("end_char", 0)
                    } for chunk in normalized_chunks],
                    ids=[chunk["chunk_id"] for chunk in normalized_chunks]
                )
                logger.info(f"✓ Added {len(normalized_chunks)} chunks to ChromaDB")
            except Exception as e:
                logger.error(f"Failed to add to ChromaDB: {e}")
                return {"status": "chroma_error", "file": str(file_path), "error": str(e)}
            
            return {
                "status": "success",
                "file": str(file_path),
                "chunks": len(chunks),
                "pages": len(doc.get('pages', [])),
                "tables": len(doc.get('tables', []))
            }
            
        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "status": "error",
                "file": str(file_path),
                "error": str(e)
            }
    
    async def index_directory(self, directory: Path, extensions: List[str] = [".hwp", ".pdf"]) -> List[Dict]:
        """Index all documents in a directory"""
        results = []
        
        # Find all documents
        documents = []
        for ext in extensions:
            documents.extend(directory.glob(f"**/*{ext}"))
        
        logger.info(f"Found {len(documents)} documents to index")
        
        # Index documents sequentially (to avoid overwhelming the system)
        for doc in documents:
            result = await self.index_document(doc)
            results.append(result)
            
            if result["status"] == "success":
                logger.info(f"✓ Indexed: {result['file']} ({result['chunks']} chunks, {result.get('pages', 0)} pages)")
            else:
                logger.warning(f"✗ Failed: {result['file']}: {result.get('error', 'Unknown error')}")
        
        # Log summary
        successful = sum(1 for r in results if r["status"] == "success")
        failed = sum(1 for r in results if r["status"] == "error")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        no_chunks = sum(1 for r in results if r["status"] == "no_chunks")
        
        logger.info(f"Indexing complete: {successful} successful, {failed} failed, {skipped} skipped, {no_chunks} no chunks")
        
        return results

async def index_all_documents():
    """Main function to index all documents"""
    indexer = DocumentIndexer()
    
    # Index documents
    doc_dir = Path(config.DOC_DIR)
    if not doc_dir.exists():
        logger.error(f"Document directory not found: {doc_dir}")
        return
    
    results = await indexer.index_directory(doc_dir)
    
    # Save indexing report
    import json
    report_path = Path("reports/indexing_report.json")
    report_path.parent.mkdir(exist_ok=True)
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    logger.info(f"Indexing report saved to {report_path}")
    
    # Get index statistics
    whoosh_stats = indexer.whoosh.get_stats()
    logger.info(f"Whoosh index: {whoosh_stats.get('doc_count', 0)} documents")
    
    return results

if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run async function
    asyncio.run(index_all_documents())
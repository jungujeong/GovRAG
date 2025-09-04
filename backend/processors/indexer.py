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
        self.whoosh = WhooshBM25()
        self.chroma = ChromaStore()
        self.embedder = Embedder()
    
    async def index_document(self, file_path: Path) -> Dict:
        """Index a single document"""
        logger.info(f"Indexing document: {file_path}")
        
        try:
            # Parse document
            if file_path.suffix.lower() == ".hwp":
                doc = self.hwp_parser.parse_hwp(str(file_path))
            elif file_path.suffix.lower() == ".pdf":
                doc = self.pdf_processor.parse_pdf(str(file_path))
            else:
                logger.warning(f"Unsupported file type: {file_path.suffix}")
                return {"status": "skipped", "file": str(file_path)}
            
            # Log parsed content
            logger.info(f"Document has {len(doc.get('pages', []))} pages, {len(doc.get('tables', []))} tables")
            
            # Chunk document
            chunks = self.chunker.chunk_document(doc)
            logger.info(f"Created {len(chunks)} chunks from {file_path.name}")
            
            if not chunks:
                logger.warning(f"No chunks created for {file_path}")
                return {"status": "no_chunks", "file": str(file_path)}
            
            # Log first few chunks for debugging
            for i, chunk in enumerate(chunks[:3]):
                logger.info(f"Chunk {i}: {chunk.get('text', '')[:100]}...")
            
            # Normalize chunks
            normalized_chunks = []
            for chunk in chunks:
                normalized_chunk = self.normalizer.normalize_chunk(chunk)
                normalized_chunks.append(normalized_chunk)
            
            # Index in Whoosh
            self.whoosh.index_chunks(normalized_chunks)
            logger.info(f"Added {len(normalized_chunks)} chunks to Whoosh")
            
            # Generate embeddings and index in Chroma
            texts = [chunk["text"] for chunk in normalized_chunks]
            embeddings = self.embedder.embed_batch(texts)
            
            # Add to ChromaDB with proper metadata
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
            logger.info(f"Added {len(normalized_chunks)} chunks to ChromaDB")
            
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
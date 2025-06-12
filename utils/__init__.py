# 기존 컴포넌트 (하위 호환성 유지)
from .document_processor import DocumentProcessor
from .vector_store import VectorStore
from .rag_chain import RAGChain

# 새로운 개선된 컴포넌트
from .enhanced_document_processor import EnhancedDocumentProcessor
from .enhanced_vector_store import EnhancedVectorStore, KoreanEmbeddings
from .enhanced_rag_chain import EnhancedRAGChain

# 기본적으로 개선된 컴포넌트를 사용하도록 별칭 설정
DocumentProcessorV2 = EnhancedDocumentProcessor
VectorStoreV2 = EnhancedVectorStore
RAGChainV2 = EnhancedRAGChain

__all__ = [
    # 기존 컴포넌트
    'DocumentProcessor',
    'VectorStore', 
    'RAGChain',
    
    # 새로운 컴포넌트
    'EnhancedDocumentProcessor',
    'EnhancedVectorStore',
    'EnhancedRAGChain',
    'KoreanEmbeddings',
    
    # 별칭
    'DocumentProcessorV2',
    'VectorStoreV2',
    'RAGChainV2'
] 
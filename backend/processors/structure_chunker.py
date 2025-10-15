import re
from typing import List, Dict, Optional, Tuple
import tiktoken
import logging
import unicodedata

logger = logging.getLogger(__name__)

class StructureChunker:
    """Document structure-aware chunker with table/footnote handling"""

    def __init__(self,
                 chunk_tokens: int = 2048,
                 chunk_overlap: int = 256,
                 table_as_separate: bool = True,
                 footnote_backlink: bool = True):
        self.chunk_tokens = chunk_tokens
        self.chunk_overlap = chunk_overlap
        self.table_as_separate = table_as_separate
        self.footnote_backlink = footnote_backlink

        # Use tiktoken for token counting
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except:
            self.tokenizer = None
            logger.warning("tiktoken not available, using character-based chunking")
    
    def chunk_document(self, doc: Dict) -> List[Dict]:
        """Chunk a parsed document"""
        chunks = []
        
        # Process HWP document
        if "sections" in doc:
            chunks.extend(self._chunk_hwp_document(doc))
        # Process PDF document
        elif "pages" in doc:
            chunks.extend(self._chunk_pdf_document(doc))
        else:
            logger.warning(f"Unknown document format: {doc.get('doc_id', 'unknown')}")
        
        # Add backlinks for tables and footnotes
        if self.footnote_backlink:
            chunks = self._add_backlinks(chunks)
        
        return chunks
    
    def _chunk_hwp_document(self, doc: Dict) -> List[Dict]:
        """Chunk HWP document"""
        chunks = []
        chunk_id = 0
        
        for section in doc.get("sections", []):
            # Group paragraphs by structure
            para_groups = self._group_paragraphs_by_structure(section["paragraphs"])
            
            for group in para_groups:
                # Create chunks from paragraph group
                group_chunks = self._create_chunks_from_paragraphs(
                    group, 
                    doc["doc_id"], 
                    section["section_id"],
                    chunk_id
                )
                chunks.extend(group_chunks)
                chunk_id += len(group_chunks)
            
            # Process tables
            if self.table_as_separate:
                for table in section.get("tables", []):
                    table_chunk = self._create_table_chunk(
                        table, 
                        doc["doc_id"], 
                        section["section_id"],
                        chunk_id
                    )
                    chunks.append(table_chunk)
                    chunk_id += 1
            
            # Process footnotes
            for footnote in section.get("footnotes", []):
                footnote_chunk = self._create_footnote_chunk(
                    footnote,
                    doc["doc_id"],
                    section["section_id"],
                    chunk_id
                )
                chunks.append(footnote_chunk)
                chunk_id += 1
        
        return chunks
    
    def _chunk_pdf_document(self, doc: Dict) -> List[Dict]:
        """Chunk PDF document"""
        chunks = []
        chunk_id = 0
        
        # Check if document has directive processing results
        if any(page.get("directive_records") for page in doc.get("pages", [])):
            # Use directive-based chunking
            chunks.extend(self._chunk_directive_document(doc, chunk_id))
        else:
            # Traditional block-based chunking
            for page in doc.get("pages", []):
                # Create chunks from page blocks
                page_chunks = self._create_chunks_from_blocks(
                    page["blocks"],
                    doc["doc_id"],
                    page["page_num"],
                    chunk_id
                )
                chunks.extend(page_chunks)
                chunk_id += len(page_chunks)
        
        # Process tables
        if self.table_as_separate:
            for table in doc.get("tables", []):
                table_chunk = self._create_table_chunk(
                    table,
                    doc["doc_id"],
                    table.get("page_num", 0),
                    chunk_id
                )
                chunks.append(table_chunk)
                chunk_id += 1
        
        return chunks
    
    def _group_paragraphs_by_structure(self, paragraphs: List[Dict]) -> List[List[Dict]]:
        """Group paragraphs by document structure (조/항/호)"""
        groups = []
        current_group = []
        current_article = None
        
        for para in paragraphs:
            structure_type = para.get("structure_type")
            
            if structure_type == "article":
                # New article starts a new group
                if current_group:
                    groups.append(current_group)
                current_group = [para]
                current_article = para["text"]
            elif structure_type in ["paragraph", "item", "subitem"]:
                # Sub-items belong to current article
                current_group.append(para)
            else:
                # Regular paragraph
                if not current_group or len(current_group) > 5:
                    # Start new group if too large or empty
                    if current_group:
                        groups.append(current_group)
                    current_group = [para]
                else:
                    current_group.append(para)
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _create_chunks_from_paragraphs(self, paragraphs: List[Dict], 
                                       doc_id: str, section_id: int, 
                                       start_chunk_id: int) -> List[Dict]:
        """Create chunks from a group of paragraphs"""
        chunks = []
        current_chunk_text = []
        current_chunk_tokens = 0
        chunk_id = start_chunk_id
        
        for para in paragraphs:
            para_text = para["text"]
            para_tokens = self._count_tokens(para_text)
            
            # Check if adding this paragraph exceeds chunk size
            if current_chunk_tokens + para_tokens > self.chunk_tokens and current_chunk_text:
                # Create chunk
                chunk = self._create_chunk(
                    "\n".join(current_chunk_text),
                    doc_id,
                    section_id,
                    chunk_id,
                    paragraphs[0].get("page", 1),
                    paragraphs[0].get("start_char", 0),
                    para.get("end_char", 0)
                )
                chunks.append(chunk)
                chunk_id += 1
                
                # Start new chunk with overlap
                if self.chunk_overlap > 0 and len(current_chunk_text) > 0:
                    # Keep last paragraph for overlap
                    current_chunk_text = [current_chunk_text[-1], para_text]
                    current_chunk_tokens = self._count_tokens("\n".join(current_chunk_text))
                else:
                    current_chunk_text = [para_text]
                    current_chunk_tokens = para_tokens
            else:
                current_chunk_text.append(para_text)
                current_chunk_tokens += para_tokens
        
        # Create final chunk
        if current_chunk_text:
            chunk = self._create_chunk(
                "\n".join(current_chunk_text),
                doc_id,
                section_id,
                chunk_id,
                paragraphs[0].get("page", 1),
                paragraphs[0].get("start_char", 0),
                paragraphs[-1].get("end_char", 0)
            )
            chunks.append(chunk)
        
        return chunks
    
    def _create_chunks_from_blocks(self, blocks: List[Dict],
                                   doc_id: str, page_num: int,
                                   start_chunk_id: int) -> List[Dict]:
        """Create chunks from PDF blocks"""
        chunks = []
        current_chunk_text = []
        current_chunk_tokens = 0
        chunk_id = start_chunk_id
        
        for block in blocks:
            block_text = block["text"]
            block_tokens = self._count_tokens(block_text)
            
            if current_chunk_tokens + block_tokens > self.chunk_tokens and current_chunk_text:
                # Create chunk
                chunk = self._create_chunk(
                    "\n".join(current_chunk_text),
                    doc_id,
                    page_num,
                    chunk_id,
                    page_num,
                    blocks[0].get("start_char", 0),
                    block.get("end_char", 0)
                )
                chunks.append(chunk)
                chunk_id += 1
                
                # Start new chunk
                current_chunk_text = [block_text]
                current_chunk_tokens = block_tokens
            else:
                current_chunk_text.append(block_text)
                current_chunk_tokens += block_tokens
        
        # Create final chunk
        if current_chunk_text:
            chunk = self._create_chunk(
                "\n".join(current_chunk_text),
                doc_id,
                page_num,
                chunk_id,
                page_num,
                blocks[0].get("start_char", 0) if blocks else 0,
                blocks[-1].get("end_char", 0) if blocks else 0
            )
            chunks.append(chunk)
        
        return chunks
    
    def _chunk_directive_document(self, doc: Dict, start_chunk_id: int) -> List[Dict]:
        """Chunk document using directive processing results"""
        chunks = []
        chunk_id = start_chunk_id
        
        # Get directive records from the first page that has them
        directive_records = None
        for page in doc.get("pages", []):
            if page.get("directive_records"):
                directive_records = page["directive_records"]
                break
        
        if not directive_records:
            return []
        
        # Create one chunk per directive record
        for i, record in enumerate(directive_records):
            # Create chunk from directive record
            directive_text = self._format_directive_for_chunk(record)
            
            chunk = {
                "chunk_id": f"{doc['doc_id']}-directive-{chunk_id}",
                "doc_id": doc["doc_id"],
                "section_or_page": record.get("page", 1),
                "page": record.get("page", 1),
                "text": directive_text,
                "start_char": 0,
                "end_char": len(directive_text),
                "type": "directive",
                "directive_category": record.get("category", "지시"),
                "directive_title": record.get("title", ""),
                "directive_departments": record.get("departments", []),
                "directive_deadline": record.get("deadline", ""),
                "directive_index": record.get("index", i + 1),
                "tokens": self._count_tokens(directive_text)
            }
            
            chunks.append(chunk)
            chunk_id += 1
        
        return chunks
    
    def _format_directive_for_chunk(self, record: Dict) -> str:
        """Format directive record as searchable text"""
        parts = []

        # Add title
        if record.get("title"):
            parts.append(f"제목: {record['title']}")

        # Add category
        if record.get("category"):
            parts.append(f"분류: {record['category']}")

        # Add main directive text
        if record.get("directive"):
            parts.append(f"내용: {record['directive']}")

        # Add body if different from directive
        if record.get("body") and record["body"] != record.get("directive", ""):
            parts.append(f"상세: {record['body']}")

        # Add departments
        if record.get("departments"):
            parts.append(f"담당부서: {', '.join(record['departments'])}")

        # Add deadline
        if record.get("deadline"):
            parts.append(f"처리기한: {record['deadline']}")

        # Add source info
        parts.append(f"출처: {record.get('source_file', '')} (페이지 {record.get('page', 1)})")

        formatted_text = "\n".join(parts)

        # Clean text before returning (ROOT CAUSE FIX)
        return self._clean_text_for_indexing(formatted_text)
    
    def _create_chunk(self, text: str, doc_id: str, section_or_page: int,
                     chunk_id: int, page: int, start_char: int, end_char: int) -> Dict:
        """Create a chunk dictionary

        CRITICAL: Clean text at indexing time to prevent problematic characters
        from entering the evidence database. This is the ROOT CAUSE fix.
        """
        # Clean text before storing in index (ROOT CAUSE FIX)
        cleaned_text = self._clean_text_for_indexing(text)

        return {
            "chunk_id": f"{doc_id}-chunk-{chunk_id}",
            "doc_id": doc_id,
            "section_or_page": section_or_page,
            "page": page,
            "text": cleaned_text,  # Store cleaned text
            "start_char": start_char,
            "end_char": end_char,
            "type": "content",
            "tokens": self._count_tokens(cleaned_text)
        }

    def _clean_text_for_indexing(self, text: str) -> str:
        """Clean text at indexing time (ROOT CAUSE FIX)

        This prevents problematic characters from entering the evidence database.
        Better than post-processing LLM output.

        Removes:
        - Private Use Area Unicode (U+E000-U+F8FF) like 󰏅
        - Control characters (Cc, Cf, Cn) except whitespace
        - Normalizes whitespace
        """
        if not text:
            return ""

        # Step 1: Remove Private Use Area Unicode (U+E000-U+F8FF)
        # These are proprietary symbols from PDF/HWP that have no universal meaning
        cleaned = re.sub(r'[\uE000-\uF8FF]', '', text)

        # Step 2: Remove problematic Unicode categories
        # Cc = Control characters, Cf = Format characters, Cn = Unassigned
        # Keep whitespace (\n, \t, space) for structure
        cleaned = ''.join(
            char for char in cleaned
            if unicodedata.category(char) not in ('Cc', 'Cf', 'Cn')
            or char in ('\n', '\t', ' ')
        )

        # Step 3: Normalize whitespace (statistical approach)
        # Collapse multiple spaces/tabs but preserve line breaks
        lines = cleaned.split('\n')
        normalized_lines = [re.sub(r'[ \t]+', ' ', line.strip()) for line in lines]

        # Remove excessive blank lines (max 2 consecutive)
        result_lines = []
        blank_count = 0
        for line in normalized_lines:
            if not line:
                blank_count += 1
                if blank_count <= 2:
                    result_lines.append(line)
            else:
                blank_count = 0
                result_lines.append(line)

        return '\n'.join(result_lines).strip()
    
    def _create_table_chunk(self, table: Dict, doc_id: str,
                           section_or_page: int, chunk_id: int) -> Dict:
        """Create a chunk for a table"""
        # Convert table to text
        table_text = self._table_to_text(table)

        # Clean text before storing (ROOT CAUSE FIX)
        cleaned_text = self._clean_text_for_indexing(table_text)

        return {
            "chunk_id": f"{doc_id}-table-{chunk_id}",
            "doc_id": doc_id,
            "section_or_page": section_or_page,
            "page": table.get("page_num", section_or_page),
            "text": cleaned_text,
            "start_char": 0,
            "end_char": len(cleaned_text),
            "type": "table",
            "table_id": table.get("table_id", ""),
            "tokens": self._count_tokens(cleaned_text)
        }
    
    def _create_footnote_chunk(self, footnote: Dict, doc_id: str,
                              section_id: int, chunk_id: int) -> Dict:
        """Create a chunk for a footnote"""
        footnote_text = f"[각주 {footnote.get('number', '')}] {footnote.get('text', '')}"

        # Clean text before storing (ROOT CAUSE FIX)
        cleaned_text = self._clean_text_for_indexing(footnote_text)

        return {
            "chunk_id": f"{doc_id}-footnote-{chunk_id}",
            "doc_id": doc_id,
            "section_or_page": section_id,
            "page": 0,  # Footnotes don't have specific page
            "text": cleaned_text,
            "start_char": 0,
            "end_char": len(cleaned_text),
            "type": "footnote",
            "footnote_id": footnote.get("footnote_id", ""),
            "tokens": self._count_tokens(cleaned_text)
        }
    
    def _table_to_text(self, table: Dict) -> str:
        """Convert table to text representation"""
        rows = table.get("rows", [])
        if not rows:
            return "[빈 표]"
        
        text_parts = []
        
        # Add caption if available
        if table.get("caption"):
            text_parts.append(f"[표: {table['caption']}]")
        
        # Convert rows to text
        for i, row in enumerate(rows):
            row_text = " | ".join(str(cell) for cell in row)
            text_parts.append(row_text)
        
        return "\n".join(text_parts)
    
    def _add_backlinks(self, chunks: List[Dict]) -> List[Dict]:
        """Add backlinks between content chunks and tables/footnotes"""
        # Create lookup maps
        table_map = {c["table_id"]: c["chunk_id"] 
                    for c in chunks if c["type"] == "table" and "table_id" in c}
        footnote_map = {c["footnote_id"]: c["chunk_id"]
                       for c in chunks if c["type"] == "footnote" and "footnote_id" in c}
        
        # Add backlinks to content chunks
        for chunk in chunks:
            if chunk["type"] == "content":
                text = chunk["text"]
                
                # Add table references
                for table_id, chunk_id in table_map.items():
                    if table_id:
                        text = text.replace(f"[표]", f"[→{chunk_id}]", 1)
                
                # Add footnote references
                for footnote_id, chunk_id in footnote_map.items():
                    if footnote_id:
                        text = re.sub(r'\[\d+\]', f"[→{chunk_id}]", text, count=1)
                
                chunk["text"] = text
        
        return chunks
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text"""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        else:
            # Fallback to character-based estimation
            # Rough estimate: 1 token ≈ 3 characters for Korean
            return len(text) // 3
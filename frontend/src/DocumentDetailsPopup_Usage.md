# Enhanced Document Details Popup - Usage Guide

## Overview
The enhanced document details popup provides a comprehensive tabbed interface for viewing document details with advanced features like search, copy, export, and collapsible sections.

## Features Implemented

### 1. **Tabbed Interface**
- **Overview Tab**: Shows document metadata and statistics
  - Document information (ID, size, format, indexing status)
  - Processing statistics (character count, token count, processing time)
  - Chunk information (total chunks, pages, size distribution)

- **Pages Tab**: Page-by-page view of extracted text
  - Navigation controls (Previous/Next)
  - Page counter
  - Copy functionality per page
  - Search highlighting

- **Chunks Tab**: All document chunks with full text
  - Collapsible chunk sections
  - Preview mode (150 chars) and expanded mode (full text)
  - Individual copy buttons per chunk
  - Search functionality with result count

- **Raw Text Tab**: Full processed text view
  - Complete document text
  - Copy all functionality
  - Clean presentation with serif font

- **Directives Tab**: Document directives (if available)
  - Categorized directives
  - Individual copy functionality
  - Green-tinted headers for distinction

### 2. **Search Functionality**
- Real-time search within chunks and pages
- Case-insensitive matching
- Highlighted search results with yellow background
- Search result counter
- Clear search button

### 3. **Copy to Clipboard**
- Individual copy buttons for:
  - Each page
  - Each chunk
  - Full raw text
  - Each directive
- Visual feedback ("복사됨!" = "Copied!") for 2 seconds
- Styled copy buttons with hover effects

### 4. **Export Options**
- **JSON Export**: Complete document data including all metadata, chunks, pages, and directives
- **TXT Export**: Formatted text export based on current tab
  - Chunks tab: All chunks with separators
  - Pages tab: All pages with separators
  - Other tabs: Raw processed text

### 5. **Performance Optimizations**
- Lazy rendering of tab content
- Collapsible chunks to reduce DOM size
- Smooth animations with CSS transitions
- Optimized scrollbars for content areas
- Responsive design for mobile devices

### 6. **Accessibility Features**
- Keyboard navigation support
- ARIA labels (can be added as needed)
- High contrast design
- Clear focus indicators
- Disabled state for unavailable tabs

### 7. **Design Features**
- Medium.com-inspired aesthetic
- Georgia serif font for content
- System fonts for UI elements
- Subtle animations and transitions
- Responsive grid layouts
- Custom scrollbar styling

## Usage Example

```javascript
// The popup is triggered when viewing document details
const handleViewDocDetails = async (docId) => {
  try {
    const response = await axios.get(`http://localhost:8000/api/documents/${docId}/details`)
    setDocDetails(response.data)
    setShowDocDetails(true)
  } catch (error) {
    console.error('Failed to load document details:', error)
  }
}

// Document details structure expected:
{
  doc_id: "doc_123",
  filename: "example.pdf",
  size: 1024000,
  has_index: true,
  chunks_count: 25,
  chunks: [
    { text: "chunk content...", metadata: {...} }
  ],
  pages_data: [
    { text: "page content...", page_num: 1 }
  ],
  processed_text: "full document text...",
  statistics: {
    total_chars: 50000,
    total_tokens: 12000,
    avg_chunk_size: 2000,
    processing_time: 3.5
  },
  directives: [
    { type: "instruction", content: "directive text..." }
  ]
}
```

## Responsive Breakpoints
- Desktop: Full layout with side-by-side elements
- Tablet (768px): Adjusted spacing and font sizes
- Mobile: Stacked layout with full-width search

## Browser Compatibility
- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support (including iOS)
- Requires modern JavaScript features (ES6+)

## Performance Considerations
- Large documents (>100 chunks) render efficiently with collapsible sections
- Search is optimized for documents up to 1000 chunks
- Export functions handle documents up to 10MB efficiently
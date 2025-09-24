import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

function AnswerWithCitations({ content, sources = [], onCitationClick }) {
  console.log('AnswerWithCitations received:', { content, sources })

  // Ensure onCitationClick is a function
  const handleCitationClick = (source) => {
    if (typeof onCitationClick === 'function') {
      onCitationClick(source)
    } else {
      console.warn('onCitationClick is not a function')
    }
  }

  // Parse the content to make citation numbers clickable
  const renderContent = () => {
    if (!content) return null

    // Custom renderer for markdown
    const components = {
      p: ({ children }) => {
        // Convert string children to processable format
        const processChildren = (child) => {
          if (typeof child === 'string') {
            // Split by citation pattern and create clickable elements
            const parts = child.split(/(\[\d+\])/)
            return parts.map((part, idx) => {
              const citationMatch = part.match(/\[(\d+)\]/)
              if (citationMatch) {
                const citationNum = parseInt(citationMatch[1])
                const source = sources.find(s =>
                  s.display_index === citationNum ||
                  s.original_index === citationNum
                )

                if (source) {
                  return (
                    <button
                      key={idx}
                      className="citation-link"
                      onClick={() => handleCitationClick(source)}
                      style={{
                        color: '#1a73e8',
                        textDecoration: 'underline',
                        cursor: 'pointer',
                        background: 'none',
                        border: 'none',
                        padding: '0 2px',
                        fontWeight: 'bold',
                        fontSize: 'inherit'
                      }}
                      title={`출처: ${source.doc_id || source.document}`}
                    >
                      [{citationNum}]
                    </button>
                  )
                }
              }
              return part
            })
          }
          return child
        }

        // Process all children
        const processedChildren = React.Children.map(children, processChildren)
        return <p>{processedChildren}</p>
      }
    }

    return (
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    )
  }

  return (
    <div className="answer-with-citations">
      <div className="answer-content">
        {renderContent()}
      </div>

      {sources && sources.length > 0 && (
        <div className="sources-section" style={{
          marginTop: '20px',
          padding: '15px',
          backgroundColor: '#f8f9fa',
          borderRadius: '8px',
          borderLeft: '4px solid #1a73e8'
        }}>
          <h4 style={{
            margin: '0 0 10px 0',
            fontSize: '16px',
            fontWeight: 'bold',
            color: '#333'
          }}>
            📚 출처 (클릭하여 상세 정보 보기)
          </h4>
          <div className="sources-list">
            {sources.map((source, idx) => {
              const displayNum = source.display_index || source.original_index || (idx + 1)
              return (
                <button
                  key={`source-${idx}`}
                  className="source-item"
                  onClick={() => handleCitationClick(source)}
                  style={{
                    display: 'block',
                    width: '100%',
                    textAlign: 'left',
                    padding: '8px 12px',
                    marginBottom: '8px',
                    backgroundColor: 'white',
                    border: '1px solid #e0e0e0',
                    borderRadius: '4px',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    fontSize: '14px'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = '#f0f7ff'
                    e.currentTarget.style.borderColor = '#1a73e8'
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'white'
                    e.currentTarget.style.borderColor = '#e0e0e0'
                  }}
                >
                  <span style={{ fontWeight: 'bold', color: '#1a73e8' }}>
                    [{displayNum}]
                  </span>
                  {' '}
                  <span style={{ color: '#333' }}>
                    {source.doc_id || source.document || '문서'}
                  </span>
                  {source.page && (
                    <span style={{ color: '#666', marginLeft: '8px' }}>
                      - {source.page}페이지
                    </span>
                  )}
                  {source.text_snippet && (
                    <div style={{
                      marginTop: '4px',
                      fontSize: '12px',
                      color: '#666',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      "{source.text_snippet.substring(0, 100)}..."
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

export default AnswerWithCitations
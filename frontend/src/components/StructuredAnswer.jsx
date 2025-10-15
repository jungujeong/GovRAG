import React, { useState } from 'react'
import CitationPopup from './CitationPopup'

function StructuredAnswer({ answer }) {
  const [selectedCitation, setSelectedCitation] = useState(null)
  const [copySuccess, setCopySuccess] = useState(false)
  const [highlightedCitation, setHighlightedCitation] = useState(null)
  const [citationPreview, setCitationPreview] = useState(null)

  const metadata = (answer && answer.metadata) || {}
  const docScope = metadata.doc_scope || {}
  const resolvedDocs = docScope.resolved_doc_ids || docScope.doc_scope_ids || []
  const requestedDocs = docScope.requested_doc_ids || []
  const averageScore = typeof docScope.average_score === 'number' ? docScope.average_score : null
  const topicChanged = !!docScope.topic_change_detected
  const topicReason = docScope.topic_change_reason

  const formattedAnswer = metadata.formatted_text || answer?.formatted_text || answer?.answer || ''
  const rawAnswer = metadata.raw_answer ?? answer?.answer ?? ''
  const keyFacts = Array.isArray(answer?.key_facts) ? answer.key_facts : (Array.isArray(metadata.key_facts) ? metadata.key_facts : [])
  const detailsText = answer?.details ?? metadata.details ?? ''
  const sources = Array.isArray(answer?.sources) ? answer.sources : []
  
  // Enhanced markdown renderer - FIXED: Preserve text structure
  const renderMarkdown = (text) => {
    if (!text) return text

    // Process the text for various markdown patterns
    const processText = (str) => {
      // IMPORTANT: Split ONLY by double line breaks (paragraphs), NOT single line breaks
      // This preserves the structure of the formatted text from backend
      const paragraphs = str.split(/\n\n+/)

      return paragraphs.map((paragraph, pIndex) => {
        if (!paragraph.trim()) return null

        // Check if this paragraph contains list items (with line breaks inside)
        const lines = paragraph.split('\n').filter(line => line.trim())

        // Check if ALL lines are list items
        const allBulletItems = lines.every(line => /^[-*•]\s+/.test(line))
        const allNumberedItems = lines.every(line => /^\d+\.\s+/.test(line))

        if (allBulletItems || allNumberedItems) {
          return (
            <ul key={pIndex} className="list-disc list-inside space-y-1 my-2">
              {lines.map((line, iIndex) => {
                const cleanItem = line.replace(/^[-*•]\s+/, '').replace(/^\d+\.\s+/, '')
                return (
                  <li key={iIndex} className="text-gray-800">
                    {formatInlineElements(cleanItem)}
                  </li>
                )
              })}
            </ul>
          )
        }

        // For non-list paragraphs, preserve line breaks within the paragraph
        return (
          <div key={pIndex} className="mb-3">
            {lines.map((line, lineIndex) => (
              <React.Fragment key={lineIndex}>
                {formatInlineElements(line)}
                {lineIndex < lines.length - 1 && <br />}
              </React.Fragment>
            ))}
          </div>
        )
      })
    }
    
    // Format inline elements (bold, italic, code)
    const formatInlineElements = (text) => {
      if (!text) return null
      
      // Combined pattern for all inline elements
      const pattern = /(\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`|\[(\d+)\])/g
      const parts = []
      let lastIndex = 0
      let match
      
      while ((match = pattern.exec(text)) !== null) {
        // Add text before the match
        if (match.index > lastIndex) {
          parts.push(text.substring(lastIndex, match.index))
        }
        
        // Handle the matched pattern
        if (match[2]) {
          // Bold + Italic (***text***)
          parts.push(
            <strong key={match.index} className="font-bold italic">
              {match[2]}
            </strong>
          )
        } else if (match[3]) {
          // Bold (**text**)
          parts.push(
            <strong key={match.index} className="font-bold">
              {match[3]}
            </strong>
          )
        } else if (match[4]) {
          // Italic (*text*)
          parts.push(
            <em key={match.index} className="italic">
              {match[4]}
            </em>
          )
        } else if (match[5]) {
          // Code (`text`)
          parts.push(
            <code key={match.index} className="px-1 py-0.5 bg-gray-100 rounded text-sm font-mono">
              {match[5]}
            </code>
          )
        } else if (match[6]) {
          // Citation [1] - make it clickable
          const citationNum = parseInt(match[6])
          const isHighlighted = highlightedCitation === citationNum
          parts.push(
            <button
              key={match.index}
              onClick={() => handleCitationClick(citationNum)}
              className={`inline-flex items-center px-1.5 py-0.5 rounded-md transition-all ${
                isHighlighted 
                  ? 'bg-yellow-200 text-blue-800 ring-2 ring-yellow-400' 
                  : 'text-blue-600 hover:bg-blue-50 hover:text-blue-700'
              } font-medium cursor-pointer`}
              title={`출처 ${citationNum} 보기`}
            >
              [{match[6]}]
              {isHighlighted && (
                <svg className="w-3 h-3 ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
              )}
            </button>
          )
        }
        
        lastIndex = match.index + match[0].length
      }
      
      // Add remaining text
      if (lastIndex < text.length) {
        parts.push(text.substring(lastIndex))
      }
      
      return parts.length > 0 ? parts : text
    }
    
    return processText(text)
  }
  
  // Handle citation click
  const handleCitationClick = (citationNum) => {
    const availableSources = sources || []
    // Find source by display_index (the renumbered sequential index) or index
    const source = availableSources.find(s =>
      s.display_index === citationNum ||
      s.index === citationNum ||
      (s.display_index === undefined && s.index === undefined && availableSources.indexOf(s) === citationNum - 1)
    )

    if (source) {
      // Toggle highlight and preview
      if (highlightedCitation === citationNum) {
        setHighlightedCitation(null)
        setCitationPreview(null)
      } else {
        setHighlightedCitation(citationNum)
        setCitationPreview(source)
      }
    } else {
      console.warn(`Citation [${citationNum}] not found in sources:`, availableSources)
    }
  }
  
  // Copy text to clipboard
  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopySuccess(true)
      setTimeout(() => setCopySuccess(false), 2000)
    } catch (err) {
      console.error('Failed to copy:', err)
    }
  }
  
  if (!answer) return null
  
  const isError = answer.error
  
  return (
    <div className={`card ${isError ? 'border-red-300' : ''}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <h2 className="text-2xl font-bold text-gray-900">
          {isError ? '❌ 오류' : '✅ 답변'}
        </h2>
        
        {answer.confidence && (
          <div className="text-right">
            <p className="text-sm text-gray-500">신뢰도</p>
            <p className="text-xl font-bold text-blue-600">
              {(answer.confidence * 100).toFixed(0)}%
            </p>
          </div>
        )}
      </div>

      {(resolvedDocs.length > 0 || requestedDocs.length > 0) && (
        <div className="flex flex-wrap items-center gap-2 mb-4 text-sm text-gray-600">
          <span className="font-medium">참조 문서</span>
          {resolvedDocs.length > 0 ? (
            resolvedDocs.map((docId) => (
              <span
                key={`resolved-pill-${docId}`}
                className="inline-flex items-center px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200"
              >
                {docId}
              </span>
            ))
          ) : (
            <span className="text-gray-400">없음</span>
          )}
          {topicChanged && (
            <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
              🔄 주제 확장{topicReason ? ` (${topicReason})` : ''}
            </span>
          )}
        </div>
      )}

      {/* Core Answer */}
      <div className="answer-section">
        <div className="mb-6 p-5 bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl border-l-4 border-blue-500 shadow-sm">
          <div className="answer-header">
            <h3 className="answer-title">
              📌 핵심 답변
            </h3>
            <button
              onClick={() => copyToClipboard(rawAnswer)}
              className={`copy-button ${copySuccess ? 'copy-button-success' : ''}`}
              title="답변 복사"
            >
              {copySuccess ? (
                <>
                  <svg className="w-4 h-4 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  복사됨
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  복사
                </>
              )}
            </button>
          </div>
          <div className="answer-content text-lg">
            {renderMarkdown(formattedAnswer) || '답변을 생성할 수 없습니다.'}
          </div>
        </div>
      </div>
      
      {/* Key Facts */}
      {keyFacts.length > 0 && (
        <div className="answer-section">
          <h3 className="answer-title mb-4">📊 주요 사실</h3>
          <div className="space-y-3">
            {keyFacts.map((fact, index) => (
              <div 
                key={index}
                className="fact-item"
              >
                <span className="fact-marker text-xl">✓</span>
                <div className="answer-content flex-1">{renderMarkdown(fact)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
      
      {/* Detailed Explanation */}
      {detailsText && (
        <div className="answer-section">
          <h3 className="answer-title mb-4">📝 상세 설명</h3>
          <div className="answer-content p-4 bg-gray-50 rounded-lg">
            {renderMarkdown(detailsText)}
          </div>
        </div>
      )}
      
      {/* Sources - Already filtered by backend */}
      {sources.length > 0 && (
        <div className="border-t pt-4">
          <h3 className="text-xl font-semibold mb-3">📚 출처</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {sources.map((source, index) => {
              // Use display_index for the renumbered citation
              const displayIndex = source.display_index || source.index || (index + 1)
              return (
                <button
                  key={`source-${displayIndex}-${index}`}
                  onClick={() => handleCitationClick(displayIndex)}
                  className="text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors group"
                >
                  <div className="flex items-start">
                    <span className="text-blue-600 mr-2">[{displayIndex}]</span>
                    <div className="flex-1">
                      <p className="font-medium">{source.doc_id}</p>
                      <p className="text-sm text-gray-600">
                        {source.page}페이지
                        {source.start_char && source.end_char && source.start_char !== -1 && 
                          ` (${source.start_char}-${source.end_char})`
                        }
                        {source.keyword_relevance && (
                          <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                            관련도: {(source.keyword_relevance * 100).toFixed(0)}%
                          </span>
                        )}
                      </p>
                      {source.text_snippet && (
                        <p className="text-sm text-gray-500 mt-1 line-clamp-2">
                          {source.text_snippet}
                        </p>
                      )}
                    </div>
                    <span className="text-gray-400 group-hover:text-gray-600 ml-2">
                      →
                    </span>
                  </div>
                </button>
              )
            })}
          </div>
        </div>
      )}
      
      {/* Metadata */}
      {metadata && (
        <div className="mt-6 pt-4 border-t text-sm text-gray-500 space-y-3">
          <div>
            <p>증거 문서: {metadata.evidence_count ?? sources.length}개</p>
            {metadata.hallucination_detected && (
              <p className="text-red-600 font-semibold">⚠️ 할루시네이션 감지됨</p>
            )}
          </div>

          {metadata.grounding && metadata.grounding.length > 0 && (
            <div className="text-gray-600">
              <p>정렬된 문장 수: {metadata.grounding.length}개</p>
            </div>
          )}

          {requestedDocs.length > 0 && (
            <div className="text-gray-600">
              <span className="text-gray-500 mr-2">요청 문서</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {requestedDocs.map((docId) => (
                  <span key={`metadata-requested-${docId}`} className="inline-flex items-center px-2 py-0.5 rounded bg-blue-50 text-blue-700 border border-blue-200 text-xs">
                    {docId}
                  </span>
                ))}
              </div>
            </div>
          )}

          {averageScore !== null && (
            <div className="text-xs text-gray-500">
              평균 스코어: {(averageScore * 100).toFixed(1)}%
            </div>
          )}
        </div>
      )}
      
      {/* Citation Preview Box */}
      {citationPreview && (
        <div className="fixed bottom-4 right-4 max-w-md w-96 bg-white rounded-lg shadow-xl border-2 border-blue-500 p-4 z-50 animate-slide-up">
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center">
              <span className="text-blue-600 font-bold mr-2">
                [{citationPreview.display_index || citationPreview.index || highlightedCitation}]
              </span>
              <h4 className="font-semibold text-gray-900">
                {citationPreview.doc_id}
              </h4>
            </div>
            <button
              onClick={() => {
                setHighlightedCitation(null)
                setCitationPreview(null)
              }}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <div className="text-sm text-gray-600 mb-2">
            {citationPreview.page}페이지
            {citationPreview.start_char && citationPreview.end_char && citationPreview.start_char !== -1 && 
              ` (${citationPreview.start_char}-${citationPreview.end_char})`
            }
          </div>
          
          {citationPreview.text_snippet && (
            <div className="bg-yellow-50 border-l-4 border-yellow-400 p-3 rounded">
              <p className="text-sm text-gray-800 leading-relaxed">
                {citationPreview.text_snippet}
              </p>
            </div>
          )}
          
          <button
            onClick={() => setSelectedCitation(citationPreview)}
            className="mt-3 w-full py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
          >
            전체 내용 보기
          </button>
        </div>
      )}
      
      {/* Citation Popup */}
      {selectedCitation && (
        <CitationPopup
          citation={selectedCitation}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </div>
  )
}

export default StructuredAnswer

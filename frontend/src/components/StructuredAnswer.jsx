import React, { useState } from 'react'
import CitationPopup from './CitationPopup'

function StructuredAnswer({ answer }) {
  const [selectedCitation, setSelectedCitation] = useState(null)
  const [copySuccess, setCopySuccess] = useState(false)
  
  // Enhanced markdown renderer with line breaks
  const renderMarkdown = (text) => {
    if (!text) return text
    
    // First, split by line breaks to preserve them
    const lines = text.split('\n')
    
    return lines.map((line, lineIndex) => {
      // Convert **bold** to <strong> tags within each line
      const parts = line.split(/\*\*(.*?)\*\*/g)
      const formattedLine = parts.map((part, partIndex) => {
        if (partIndex % 2 === 1) {
          return <strong key={`${lineIndex}-${partIndex}`} className="font-bold">{part}</strong>
        }
        return part
      })
      
      // Return each line with proper line breaks
      return (
        <React.Fragment key={lineIndex}>
          {formattedLine}
          {lineIndex < lines.length - 1 && <br />}
        </React.Fragment>
      )
    })
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
      
      {/* Core Answer */}
      <div className="mb-6 p-4 bg-blue-50 rounded-lg border-l-4 border-blue-500 relative">
        <div className="flex items-start justify-between mb-2">
          <h3 className="text-xl font-semibold">📌 핵심 답변</h3>
          <button
            onClick={() => copyToClipboard(answer.answer || '')}
            className="px-3 py-1 text-sm bg-white hover:bg-gray-100 border border-gray-300 rounded-md transition-colors flex items-center gap-2"
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
        <div className="text-lg text-gray-800 leading-relaxed">
          {renderMarkdown(answer.answer) || '답변을 생성할 수 없습니다.'}
        </div>
      </div>
      
      {/* Key Facts */}
      {answer.key_facts && answer.key_facts.length > 0 && (
        <div className="mb-6">
          <h3 className="text-xl font-semibold mb-3">📊 주요 사실</h3>
          <ul className="space-y-2">
            {answer.key_facts.map((fact, index) => (
              <li 
                key={index}
                className="flex items-start p-3 bg-gray-50 rounded-lg"
              >
                <span className="text-green-600 mr-3 text-xl">✓</span>
                <div className="text-lg">{renderMarkdown(fact)}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Detailed Explanation */}
      {answer.details && (
        <div className="mb-6">
          <h3 className="text-xl font-semibold mb-3">📝 상세 설명</h3>
          <div className="text-lg text-gray-700 leading-relaxed">
            {renderMarkdown(answer.details)}
          </div>
        </div>
      )}
      
      {/* Sources */}
      {answer.sources && answer.sources.length > 0 && (
        <div className="border-t pt-4">
          <h3 className="text-xl font-semibold mb-3">📚 출처</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {answer.sources.map((source, index) => (
              <button
                key={index}
                onClick={() => setSelectedCitation(source)}
                className="text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors group"
              >
                <div className="flex items-start">
                  <span className="text-blue-600 mr-2">[{index + 1}]</span>
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
            ))}
          </div>
        </div>
      )}
      
      {/* Metadata */}
      {answer.metadata && (
        <div className="mt-6 pt-4 border-t text-sm text-gray-500">
          <p>증거 문서: {answer.metadata.evidence_count}개</p>
          {answer.metadata.hallucination_detected && (
            <p className="text-red-600 font-semibold">
              ⚠️ 할루시네이션 감지됨
            </p>
          )}
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
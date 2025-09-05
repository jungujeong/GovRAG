import React, { useState } from 'react'
import CitationPopup from './CitationPopup'

function StructuredAnswer({ answer }) {
  const [selectedCitation, setSelectedCitation] = useState(null)
  
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
      <div className="mb-6 p-4 bg-blue-50 rounded-lg border-l-4 border-blue-500">
        <h3 className="text-xl font-semibold mb-2">📌 핵심 답변</h3>
        <p className="text-lg text-gray-800 leading-relaxed">
          {answer.answer || '답변을 생성할 수 없습니다.'}
        </p>
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
                <span className="text-lg">{fact}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      
      {/* Detailed Explanation */}
      {answer.details && (
        <div className="mb-6">
          <h3 className="text-xl font-semibold mb-3">📝 상세 설명</h3>
          <p className="text-lg text-gray-700 leading-relaxed whitespace-pre-wrap">
            {answer.details}
          </p>
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
                      {source.start_char && source.end_char && 
                        ` (${source.start_char}-${source.end_char})`
                      }
                    </p>
                    {source.text_snippet && (
                      <p className="text-sm text-gray-500 mt-1 truncate">
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
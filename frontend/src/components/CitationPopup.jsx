import React from 'react'

function CitationPopup({ citation, onClose }) {
  if (!citation) return null
  
  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-lg p-6 max-w-2xl max-h-[80vh] overflow-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start mb-4">
          <h2 className="text-2xl font-bold">출처 상세 정보</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
            aria-label="닫기"
          >
            ✕
          </button>
        </div>
        
        <div className="space-y-4">
          <div>
            <h3 className="font-semibold text-lg mb-2">문서 정보</h3>
            <dl className="grid grid-cols-2 gap-2 text-lg">
              <dt className="text-gray-600">문서 ID:</dt>
              <dd className="font-medium">{citation.doc_id}</dd>
              
              <dt className="text-gray-600">페이지:</dt>
              <dd className="font-medium">{citation.page}</dd>
              
              {citation.chunk_id && (
                <>
                  <dt className="text-gray-600">청크 ID:</dt>
                  <dd className="font-mono text-sm">{citation.chunk_id}</dd>
                </>
              )}
            </dl>
          </div>
          
          {(citation.start_char !== undefined || citation.end_char !== undefined) && (
            <div>
              <h3 className="font-semibold text-lg mb-2">위치 정보</h3>
              <p className="text-lg">
                문자 위치: {citation.start_char || 0} - {citation.end_char || 0}
              </p>
            </div>
          )}
          
          {citation.text_snippet && (
            <div>
              <h3 className="font-semibold text-lg mb-2">인용 텍스트</h3>
              <div className="p-4 bg-gray-50 rounded-lg border-l-4 border-blue-500">
                <p className="text-lg leading-relaxed">
                  {citation.text_snippet}
                </p>
              </div>
            </div>
          )}
        </div>
        
        <div className="mt-6 flex justify-end">
          <button
            onClick={onClose}
            className="btn-primary"
          >
            확인
          </button>
        </div>
      </div>
    </div>
  )
}

export default CitationPopup
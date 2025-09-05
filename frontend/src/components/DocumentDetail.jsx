import React, { useState, useEffect } from 'react'
import axios from 'axios'

function DocumentDetail({ document, onClose }) {
  const [detail, setDetail] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('info')
  const [selectedPage, setSelectedPage] = useState(0)

  useEffect(() => {
    fetchDocumentDetail()
  }, [document])

  const fetchDocumentDetail = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await axios.get(`/api/documents/detail/${document.filename}`)
      setDetail(response.data)
      if (response.data.processed_text && response.data.processed_text.length > 0) {
        setSelectedPage(response.data.processed_text[0].page)
      }
    } catch (err) {
      console.error('Failed to fetch document detail:', err)
      setError('문서 상세 정보를 불러올 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  }

  const formatDate = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleString('ko-KR')
  }

  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-lg w-full max-w-6xl max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="border-b p-6 flex justify-between items-center">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">문서 상세 정보</h2>
            <p className="text-lg text-gray-600 mt-1">{document.filename}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
          >
            ✕
          </button>
        </div>

        {loading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-lg text-gray-600">정보를 불러오는 중...</p>
            </div>
          </div>
        ) : error ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <p className="text-xl text-red-600">{error}</p>
            </div>
          </div>
        ) : detail ? (
          <>
            {/* Tabs */}
            <div className="border-b">
              <div className="flex space-x-8 px-6">
                <button
                  onClick={() => setActiveTab('info')}
                  className={`py-3 px-1 border-b-2 font-medium text-lg transition-colors ${
                    activeTab === 'info'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  기본 정보
                </button>
                <button
                  onClick={() => setActiveTab('text')}
                  className={`py-3 px-1 border-b-2 font-medium text-lg transition-colors ${
                    activeTab === 'text'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  처리된 텍스트 ({detail.stats?.total_pages || 0}페이지)
                </button>
                <button
                  onClick={() => setActiveTab('chunks')}
                  className={`py-3 px-1 border-b-2 font-medium text-lg transition-colors ${
                    activeTab === 'chunks'
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  청크 정보 ({detail.stats?.total_chunks || 0}개)
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-auto p-6">
              {activeTab === 'info' && (
                <div className="space-y-6">
                  <div className="grid grid-cols-2 gap-6">
                    <div>
                      <h3 className="text-lg font-semibold mb-3">파일 정보</h3>
                      <dl className="space-y-2">
                        <div>
                          <dt className="text-gray-600">파일 유형</dt>
                          <dd className="text-lg font-medium">{detail.type}</dd>
                        </div>
                        <div>
                          <dt className="text-gray-600">파일 크기</dt>
                          <dd className="text-lg font-medium">{formatFileSize(detail.size)}</dd>
                        </div>
                        <div>
                          <dt className="text-gray-600">수정일</dt>
                          <dd className="text-lg">{formatDate(detail.modified)}</dd>
                        </div>
                      </dl>
                    </div>

                    <div>
                      <h3 className="text-lg font-semibold mb-3">인덱스 통계</h3>
                      <dl className="space-y-2">
                        <div>
                          <dt className="text-gray-600">총 청크 수</dt>
                          <dd className="text-lg font-medium">{detail.stats?.total_chunks || 0}개</dd>
                        </div>
                        <div>
                          <dt className="text-gray-600">총 페이지 수</dt>
                          <dd className="text-lg font-medium">{detail.stats?.total_pages || 0}페이지</dd>
                        </div>
                        <div>
                          <dt className="text-gray-600">평균 청크 크기</dt>
                          <dd className="text-lg font-medium">{detail.stats?.avg_chunk_size || 0}자</dd>
                        </div>
                      </dl>
                    </div>
                  </div>

                  <div>
                    <h3 className="text-lg font-semibold mb-3">파일 경로</h3>
                    <code className="block bg-gray-100 p-3 rounded font-mono text-sm">
                      {detail.path}
                    </code>
                  </div>
                </div>
              )}

              {activeTab === 'text' && (
                <div className="space-y-4">
                  {detail.processed_text && detail.processed_text.length > 0 ? (
                    <>
                      {/* Page selector */}
                      <div className="flex space-x-2 mb-4 pb-4 border-b">
                        {detail.processed_text.map((pageData) => (
                          <button
                            key={pageData.page}
                            onClick={() => setSelectedPage(pageData.page)}
                            className={`px-4 py-2 rounded transition-colors ${
                              selectedPage === pageData.page
                                ? 'bg-blue-600 text-white'
                                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                            }`}
                          >
                            페이지 {pageData.page}
                          </button>
                        ))}
                      </div>

                      {/* Page content */}
                      <div className="bg-gray-50 rounded-lg p-6">
                        <h3 className="text-lg font-semibold mb-3">
                          페이지 {selectedPage} 내용
                        </h3>
                        <div className="whitespace-pre-wrap text-lg leading-relaxed">
                          {detail.processed_text.find(p => p.page === selectedPage)?.text || ''}
                        </div>
                      </div>
                    </>
                  ) : (
                    <div className="text-center py-12 text-gray-500">
                      <p className="text-xl">처리된 텍스트가 없습니다.</p>
                      <p className="text-lg mt-2">문서가 아직 인덱싱되지 않았을 수 있습니다.</p>
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'chunks' && (
                <div className="space-y-4">
                  {detail.chunks && detail.chunks.length > 0 ? (
                    detail.chunks.map((chunk, index) => (
                      <div key={chunk.chunk_id} className="bg-gray-50 rounded-lg p-4">
                        <div className="flex justify-between items-start mb-2">
                          <h4 className="text-lg font-semibold">
                            청크 #{index + 1}
                          </h4>
                          <span className="text-sm text-gray-600">
                            페이지 {chunk.page} | {chunk.start_char}-{chunk.end_char}
                          </span>
                        </div>
                        <div className="text-sm font-mono text-gray-600 mb-2">
                          ID: {chunk.chunk_id}
                        </div>
                        <div className="bg-white p-3 rounded border">
                          <p className="whitespace-pre-wrap text-sm">
                            {chunk.text}
                          </p>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-12 text-gray-500">
                      <p className="text-xl">청크 정보가 없습니다.</p>
                      <p className="text-lg mt-2">문서가 아직 인덱싱되지 않았을 수 있습니다.</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </>
        ) : null}
      </div>
    </div>
  )
}

export default DocumentDetail
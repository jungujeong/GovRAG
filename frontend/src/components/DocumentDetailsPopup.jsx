import React, { useState } from 'react'
import '../styles/DocumentDetailsPopup.css'

function DocumentDetailsPopup({ docDetails, onClose }) {
  const [activeTab, setActiveTab] = useState('overview')
  
  if (!docDetails) return null
  
  return (
    <div className="doc-popup-overlay" onClick={onClose}>
      <div className="doc-popup-container" onClick={(e) => e.stopPropagation()}>
        <div className="doc-popup-header">
          <h2 className="doc-popup-title">
            📄 {docDetails.filename}
          </h2>
          <button className="doc-popup-close" onClick={onClose}>
            ×
          </button>
        </div>
        
        <div className="doc-popup-tabs">
          <button 
            className={`doc-popup-tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            개요
          </button>
          <button
            className={`doc-popup-tab ${activeTab === 'chunks' ? 'active' : ''}`}
            onClick={() => setActiveTab('chunks')}
          >
            청크 ({docDetails.chunks?.length || docDetails.stats?.total_chunks || 0})
          </button>
          <button 
            className={`doc-popup-tab ${activeTab === 'text' ? 'active' : ''}`}
            onClick={() => setActiveTab('text')}
          >
            추출 텍스트
          </button>
          {(docDetails.directive_processing?.directive_records?.length > 0 ||
            docDetails.directives?.length > 0) && (
            <button
              className={`doc-popup-tab ${activeTab === 'directives' ? 'active' : ''}`}
              onClick={() => setActiveTab('directives')}
            >
              지시사항 ({docDetails.directive_processing?.directive_records?.length || docDetails.directives?.length || 0})
            </button>
          )}
        </div>
        
        <div className="doc-popup-content">
          {activeTab === 'overview' && (
            <div className="doc-overview">
              <div className="doc-stats-grid">
                <div className="doc-stat-card">
                  <span className="doc-stat-label">파일 크기</span>
                  <span className="doc-stat-value">
                    {(docDetails.size / 1024).toFixed(1)} KB
                  </span>
                </div>
                <div className="doc-stat-card">
                  <span className="doc-stat-label">총 청크</span>
                  <span className="doc-stat-value">
                    {docDetails.chunks_count || 0}개
                  </span>
                </div>
                <div className="doc-stat-card">
                  <span className="doc-stat-label">페이지 수</span>
                  <span className="doc-stat-value">
                    {docDetails.statistics?.total_pages || 0}
                  </span>
                </div>
                <div className="doc-stat-card">
                  <span className="doc-stat-label">총 문자 수</span>
                  <span className="doc-stat-value">
                    {(docDetails.statistics?.total_characters || 0).toLocaleString()}
                  </span>
                </div>
                <div className="doc-stat-card">
                  <span className="doc-stat-label">평균 청크 크기</span>
                  <span className="doc-stat-value">
                    {docDetails.statistics?.avg_chunk_size || 0}자
                  </span>
                </div>
                <div className="doc-stat-card">
                  <span className="doc-stat-label">인덱싱 상태</span>
                  <span className={`doc-stat-value ${(docDetails.has_index || docDetails.stats?.whoosh_chunks > 0 || docDetails.stats?.chroma_chunks > 0) ? 'success' : 'pending'}`}>
                    {(docDetails.has_index || docDetails.stats?.whoosh_chunks > 0 || docDetails.stats?.chroma_chunks > 0) ? '✅ 완료' : '⏳ 대기중'}
                  </span>
                </div>
              </div>
            </div>
          )}
          
          {activeTab === 'chunks' && (
            <div className="doc-chunks">
              {docDetails.chunks && docDetails.chunks.length > 0 ? (
                <div className="doc-chunks-list">
                  {docDetails.chunks.map((chunk, idx) => (
                    <div key={idx} className="doc-chunk-item">
                      <div className="doc-chunk-header">
                        <span className="doc-chunk-id">청크 #{idx + 1}</span>
                        <span className="doc-chunk-meta">
                          페이지 {chunk.page || 0} | {chunk.text?.length || 0}자
                        </span>
                      </div>
                      <div className="doc-chunk-text">
                        {chunk.text?.substring(0, 200)}
                        {chunk.text?.length > 200 && '...'}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="doc-empty-state">
                  청크 데이터가 없습니다.
                </div>
              )}
            </div>
          )}
          
          {activeTab === 'text' && (
            <div className="doc-text">
              {docDetails.directive_processing?.processed_text ? (
                <div className="doc-text-content">
                  <pre>{docDetails.directive_processing.processed_text}</pre>
                </div>
              ) : docDetails.processed_text && docDetails.processed_text.length > 0 ? (
                <div className="doc-text-content">
                  {docDetails.processed_text.map((page, idx) => (
                    <div key={idx} className="doc-page-text">
                      <h4>페이지 {page.page}</h4>
                      <pre>{page.text}</pre>
                    </div>
                  ))}
                </div>
              ) : docDetails.pages_data ? (
                <div className="doc-pages">
                  {Object.entries(docDetails.pages_data).map(([page, chunks]) => (
                    <div key={page} className="doc-page-section">
                      <h3 className="doc-page-title">페이지 {page}</h3>
                      <div className="doc-page-content">
                        {chunks.map((chunk, idx) => (
                          <p key={idx}>{chunk.text}</p>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="doc-empty-state">
                  추출된 텍스트가 없습니다.
                </div>
              )}
            </div>
          )}
          
          {activeTab === 'directives' && (
            <div className="doc-directives">
              {(docDetails.directive_processing?.directive_records || docDetails.directives || []).map((directive, idx) => (
                <div key={idx} className="doc-directive-item">
                  <div className="doc-directive-header">
                    <span className="doc-directive-category">
                      {directive.category || '지시'}
                    </span>
                    {directive.departments && directive.departments.length > 0 && (
                      <span className="doc-directive-dept">
                        {directive.departments.join(', ')}
                      </span>
                    )}
                  </div>
                  <div className="doc-directive-content">
                    {directive.content || directive.text}
                  </div>
                  {directive.deadline && (
                    <div className="doc-directive-deadline">
                      기한: {directive.deadline}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default DocumentDetailsPopup
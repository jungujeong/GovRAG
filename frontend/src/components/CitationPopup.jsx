import React from 'react'
import '../styles/MediumDesign.css'

function CitationPopup({ citation, onClose }) {
  if (!citation) return null

  return (
    <div
      className="medium-modal-overlay"
      onClick={onClose}
    >
      <div
        className="medium-modal-container"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="medium-modal-header">
          <h2 className="medium-modal-title">
            📚 출처 상세 정보
          </h2>
          <button
            onClick={onClose}
            className="medium-modal-close"
            aria-label="닫기"
          >
            ✕
          </button>
        </div>

        <div className="medium-modal-content">
          <div className="medium-citation-info">
            <div className="medium-info-section">
              <h3 className="medium-info-title">문서 정보</h3>
              <div className="medium-info-grid">
                <div className="medium-info-item">
                  <span className="medium-info-label">문서명:</span>
                  <span className="medium-info-value">{citation.doc_id || citation.document}</span>
                </div>
                <div className="medium-info-item">
                  <span className="medium-info-label">페이지:</span>
                  <span className="medium-info-value">{citation.page || '-'}페이지</span>
                </div>
                {citation.chunk_id && (
                  <div className="medium-info-item">
                    <span className="medium-info-label">청크 ID:</span>
                    <span className="medium-info-value">{citation.chunk_id}</span>
                  </div>
                )}
              </div>
            </div>

            {(citation.start_char !== undefined || citation.end_char !== undefined) && (
              <div className="medium-info-section">
                <h3 className="medium-info-title">위치 정보</h3>
                <div className="medium-info-item">
                  <span className="medium-info-label">문자 위치:</span>
                  <span className="medium-info-value">
                    {citation.start_char || citation.start || 0} - {citation.end_char || citation.end || 0}
                  </span>
                </div>
              </div>
            )}

            {citation.text_snippet && (
              <div className="medium-info-section">
                <h3 className="medium-info-title">인용 텍스트</h3>
                <div className="medium-citation-text">
                  <p>{citation.text_snippet}</p>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="medium-modal-footer">
          <button
            onClick={onClose}
            className="medium-button medium-button-primary"
          >
            확인
          </button>
        </div>
      </div>
    </div>
  )
}

export default CitationPopup
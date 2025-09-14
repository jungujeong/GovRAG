import React, { useEffect, useRef } from 'react'
import './ConfirmDialog.css'

const ConfirmDialog = ({
  title,
  message,
  onConfirm,
  onCancel,
  confirmText = '확인',
  cancelText = '취소',
  type = 'default' // default, danger, warning
}) => {
  const dialogRef = useRef(null)
  const confirmButtonRef = useRef(null)
  
  // 포커스 관리
  useEffect(() => {
    // 다이얼로그 표시 시 확인 버튼에 포커스
    confirmButtonRef.current?.focus()
    
    // ESC 키로 취소
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onCancel()
      }
    }
    
    document.addEventListener('keydown', handleEscape)
    return () => document.removeEventListener('keydown', handleEscape)
  }, [onCancel])
  
  // 외부 클릭으로 닫기
  const handleOverlayClick = (e) => {
    if (e.target === e.currentTarget) {
      onCancel()
    }
  }
  
  return (
    <div className="confirm-overlay" onClick={handleOverlayClick}>
      <div className={`confirm-dialog ${type}`} ref={dialogRef}>
        {/* 아이콘 */}
        <div className="dialog-icon">
          {type === 'danger' && (
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="3"/>
              <path d="M24 14v12m0 4v4" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
            </svg>
          )}
          {type === 'warning' && (
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <path d="M24 8l20 32H4L24 8z" stroke="currentColor" strokeWidth="3" strokeLinejoin="round"/>
              <path d="M24 20v8m0 4v2" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
            </svg>
          )}
          {type === 'default' && (
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
              <circle cx="24" cy="24" r="20" stroke="currentColor" strokeWidth="3"/>
              <path d="M24 20v12m0-16v2" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/>
            </svg>
          )}
        </div>
        
        {/* 내용 */}
        <div className="dialog-content">
          <h3 className="dialog-title">{title}</h3>
          <p className="dialog-message">{message}</p>
        </div>
        
        {/* 버튼 */}
        <div className="dialog-actions">
          <button
            className="btn btn-cancel"
            onClick={onCancel}
          >
            {cancelText}
          </button>
          <button
            ref={confirmButtonRef}
            className={`btn btn-confirm btn-${type}`}
            onClick={onConfirm}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ConfirmDialog
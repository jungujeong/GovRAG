import React, { useState, useEffect } from 'react'
import './MessageInput.css'

const MessageInput = ({
  value,
  onChange,
  onSend,
  onStop,
  isGenerating,
  disabled,
  inputRef,
  onKeyPress,
  maxLength = 5000
}) => {
  const [charCount, setCharCount] = useState(0)
  const [showCharCount, setShowCharCount] = useState(false)
  
  useEffect(() => {
    setCharCount(value.length)
    setShowCharCount(value.length > maxLength * 0.8) // 80% 넘으면 표시
  }, [value, maxLength])
  
  const handleSubmit = (e) => {
    e.preventDefault()
    if (!isGenerating && value.trim()) {
      onSend()
    }
  }
  
  const handleKeyDown = (e) => {
    // Enter로 전송, Shift+Enter로 줄바꿈
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
    
    // Escape로 생성 중단
    if (e.key === 'Escape' && isGenerating) {
      e.preventDefault()
      onStop()
    }
    
    // 추가 키보드 이벤트 전달
    if (onKeyPress) {
      onKeyPress(e)
    }
  }
  
  const getPlaceholder = () => {
    if (disabled) return '대화를 불러오는 중...'
    if (isGenerating) return 'Esc 키로 중단할 수 있습니다...'
    return '메시지를 입력하세요... (Shift+Enter로 줄바꿈)'
  }
  
  return (
    <div className="message-input-container">
      <form onSubmit={handleSubmit} className="message-form">
        <div className="input-wrapper">
          <textarea
            ref={inputRef}
            value={value}
            onChange={(e) => {
              if (e.target.value.length <= maxLength) {
                onChange(e.target.value)
              }
            }}
            onKeyDown={handleKeyDown}
            placeholder={getPlaceholder()}
            disabled={disabled || isGenerating}
            className={`message-input ${charCount > maxLength * 0.9 ? 'near-limit' : ''}`}
            rows={3}
            maxLength={maxLength}
          />
          
          {/* 문자 수 표시 */}
          {showCharCount && (
            <div className={`char-count ${charCount >= maxLength ? 'at-limit' : ''}`}>
              {charCount} / {maxLength}
            </div>
          )}
          
          {/* 도움말 */}
          <div className="input-hints">
            {isGenerating ? (
              <span className="hint-generating">답변 생성 중... Esc로 중단</span>
            ) : (
              <>
                <span>Enter: 전송</span>
                <span>Shift+Enter: 줄바꿈</span>
              </>
            )}
          </div>
        </div>
        
        {/* 버튼 영역 */}
        <div className="input-actions">
          {isGenerating ? (
            <button
              type="button"
              onClick={onStop}
              className="btn btn-stop"
              title="생성 중단 (Esc)"
            >
              <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <rect x="4" y="4" width="12" height="12" fill="currentColor"/>
              </svg>
              <span>중지</span>
            </button>
          ) : (
            <>
              <button
                type="submit"
                disabled={disabled || !value.trim()}
                className="btn btn-send"
                title="메시지 전송 (Enter)"
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M2 10l16-8v16L2 10z" fill="currentColor"/>
                </svg>
                <span>전송</span>
              </button>
              
              {value && (
                <button
                  type="button"
                  onClick={() => onChange('')}
                  className="btn btn-clear"
                  title="입력 지우기"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                    <path d="M4 4l8 8m0-8L4 12" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                  </svg>
                </button>
              )}
            </>
          )}
        </div>
      </form>
      
      {/* 상태 표시 */}
      {isGenerating && (
        <div className="generation-status">
          <div className="status-bar">
            <div className="status-progress"></div>
          </div>
        </div>
      )}
    </div>
  )
}

export default MessageInput
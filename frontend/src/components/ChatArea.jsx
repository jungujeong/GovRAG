import React from 'react'
import MessageRenderer from './MessageRenderer'
import './ChatArea.css'

const ChatArea = ({
  messages = [],
  streamingMessage = '',
  isGenerating = false,
  messagesEndRef
}) => {
  
  // 빈 상태 렌더링
  if (messages.length === 0 && !streamingMessage) {
    return (
      <div className="chat-area">
        <div className="empty-chat">
          <div className="welcome-message">
            <h2>안녕하세요! 무엇을 도와드릴까요?</h2>
            <p>문서를 업로드하고 질문해 보세요.</p>
            <div className="tips">
              <h3>💡 사용 팁</h3>
              <ul>
                <li>문서를 먼저 업로드하면 더 정확한 답변을 받을 수 있습니다</li>
                <li>구체적인 질문일수록 좋은 답변을 받을 수 있습니다</li>
                <li>대화 제목을 더블클릭하면 수정할 수 있습니다</li>
                <li>Ctrl+N으로 새 대화를 시작할 수 있습니다</li>
              </ul>
            </div>
          </div>
        </div>
        <div ref={messagesEndRef} />
      </div>
    )
  }
  
  return (
    <div className="chat-area">
      <div className="messages-container">
        {/* 기존 메시지들 */}
        {messages.map((message, index) => (
          <MessageRenderer
            key={`${message.timestamp}-${index}`}
            message={message}
            isLatest={index === messages.length - 1 && !streamingMessage}
          />
        ))}
        
        {/* 스트리밍 중인 메시지 */}
        {streamingMessage && (
          <div className="message assistant streaming">
            <div className="message-avatar">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2"/>
                <path d="M12 8v4l3 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="message-content">
              <div className="message-bubble">
                <div className="message-text">
                  {streamingMessage}
                  <span className="cursor-blink">▌</span>
                </div>
              </div>
              <div className="message-status">
                답변 생성 중... (Enter 키로 중단)
              </div>
            </div>
          </div>
        )}
        
        {/* 생성 중 표시 (스트리밍 시작 전) */}
        {isGenerating && !streamingMessage && (
          <div className="message assistant generating">
            <div className="message-avatar">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" className="spinning">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" strokeDasharray="4 2"/>
              </svg>
            </div>
            <div className="message-content">
              <div className="message-bubble">
                <div className="thinking-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <div className="message-status">
                  문서 검색 중...
                </div>
              </div>
            </div>
          </div>
        )}
        
        {/* 스크롤 앵커 */}
        <div ref={messagesEndRef} />
      </div>
    </div>
  )
}

export default ChatArea
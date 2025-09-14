import React, { useState, useEffect, useRef } from 'react'
import './SessionSidebar.css'

const SessionSidebar = ({
  sessions = [],
  currentSessionId,
  onNewSession,
  onSelectSession,
  onDeleteSession,
  isGenerating
}) => {
  const [searchQuery, setSearchQuery] = useState('')
  const [filteredSessions, setFilteredSessions] = useState(sessions)
  const [showArchived, setShowArchived] = useState(false)
  const searchInputRef = useRef(null)
  
  // 세션 필터링
  useEffect(() => {
    let filtered = sessions
    
    // 아카이브 필터
    if (!showArchived) {
      filtered = filtered.filter(s => !s.archived)
    }
    
    // 검색 필터
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      filtered = filtered.filter(s => 
        s.title?.toLowerCase().includes(query) ||
        s.messages?.some(m => m.content?.toLowerCase().includes(query))
      )
    }
    
    // 최신순 정렬
    filtered.sort((a, b) => 
      new Date(b.updated_at || b.created_at) - new Date(a.updated_at || a.created_at)
    )
    
    setFilteredSessions(filtered)
  }, [sessions, searchQuery, showArchived])
  
  // 세션 항목 렌더링
  const renderSessionItem = (session) => {
    const isActive = session.session_id === currentSessionId
    const messageCount = session.message_count || session.messages?.length || 0
    const lastUpdate = session.updated_at || session.created_at
    const formattedDate = formatDate(lastUpdate)
    
    return (
      <div
        key={session.session_id}
        className={`session-item ${isActive ? 'active' : ''} ${session.archived ? 'archived' : ''}`}
        onClick={() => onSelectSession(session.session_id)}
        title={session.title}
      >
        <div className="session-content">
          <div className="session-title">
            {session.title || '새 대화'}
          </div>
          <div className="session-meta">
            <span className="session-date">{formattedDate}</span>
            {messageCount > 0 && (
              <span className="session-count">{messageCount}개 메시지</span>
            )}
          </div>
        </div>
        
        <button
          className="session-delete"
          onClick={(e) => {
            e.stopPropagation()
            onDeleteSession(session.session_id)
          }}
          title="대화 삭제"
          disabled={isGenerating && isActive}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M2 4h12M5 4V2.5C5 2.22386 5.22386 2 5.5 2h5c.27614 0 .5.22386.5.5V4m1.5 0v9.5c0 .27614-.22386.5-.5.5h-7c-.27614 0-.5-.22386-.5-.5V4h8z" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>
    )
  }
  
  // 날짜 포맷
  const formatDate = (dateString) => {
    if (!dateString) return ''
    
    const date = new Date(dateString)
    const now = new Date()
    const diff = now - date
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    
    if (days === 0) {
      const hours = Math.floor(diff / (1000 * 60 * 60))
      if (hours === 0) {
        const minutes = Math.floor(diff / (1000 * 60))
        if (minutes === 0) return '방금 전'
        return `${minutes}분 전`
      }
      return `${hours}시간 전`
    } else if (days === 1) {
      return '어제'
    } else if (days < 7) {
      return `${days}일 전`
    } else if (days < 30) {
      const weeks = Math.floor(days / 7)
      return `${weeks}주 전`
    } else if (days < 365) {
      const months = Math.floor(days / 30)
      return `${months}개월 전`
    } else {
      return date.toLocaleDateString('ko-KR')
    }
  }
  
  return (
    <div className="sidebar">
      {/* 새 대화 버튼 */}
      <button 
        className="new-session-btn"
        onClick={onNewSession}
        disabled={isGenerating}
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M10 4v12m6-6H4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
        </svg>
        <span>새 대화 시작</span>
      </button>
      
      {/* 검색 영역 */}
      <div className="search-box">
        <svg className="search-icon" width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="6.5" cy="6.5" r="5.5" stroke="currentColor"/>
          <path d="M11 11l3.5 3.5" stroke="currentColor" strokeLinecap="round"/>
        </svg>
        <input
          ref={searchInputRef}
          type="text"
          placeholder="대화 검색..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="search-input"
        />
        {searchQuery && (
          <button
            className="search-clear"
            onClick={() => {
              setSearchQuery('')
              searchInputRef.current?.focus()
            }}
          >
            ✕
          </button>
        )}
      </div>
      
      {/* 필터 옵션 */}
      <div className="filter-options">
        <label className="filter-checkbox">
          <input
            type="checkbox"
            checked={showArchived}
            onChange={(e) => setShowArchived(e.target.checked)}
          />
          <span>보관된 대화 표시</span>
        </label>
      </div>
      
      {/* 세션 목록 */}
      <div className="session-list">
        {filteredSessions.length === 0 ? (
          <div className="empty-state">
            {searchQuery ? (
              <>
                <p>검색 결과가 없습니다</p>
                <button 
                  className="link-btn"
                  onClick={() => setSearchQuery('')}
                >
                  검색 초기화
                </button>
              </>
            ) : (
              <>
                <p>대화가 없습니다</p>
                <p className="empty-hint">위의 "새 대화 시작" 버튼을 눌러 시작하세요</p>
              </>
            )}
          </div>
        ) : (
          <>
            {filteredSessions.map(renderSessionItem)}
            
            {/* 더 보기 표시 */}
            {sessions.length > filteredSessions.length && (
              <div className="more-indicator">
                {sessions.length - filteredSessions.length}개 더 있음
              </div>
            )}
          </>
        )}
      </div>
      
      {/* 하단 정보 */}
      <div className="sidebar-footer">
        <div className="storage-info">
          <span className="storage-label">총 대화:</span>
          <span className="storage-value">{sessions.length}개</span>
        </div>
        {isGenerating && (
          <div className="generating-indicator">
            <span className="spinner"></span>
            <span>답변 생성 중...</span>
          </div>
        )}
      </div>
    </div>
  )
}

export default SessionSidebar
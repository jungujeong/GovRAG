import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useSessionStorage, useLocalStorage } from '../hooks/useStorage'

const SessionManager = ({ children }) => {
  // 세션 관리 상태
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useSessionStorage('current_session_id', null)
  const [sessionList, setSessionList] = useLocalStorage('session_list', [])
  const [draftState, setDraftState] = useLocalStorage('draft_state', {})
  
  // UI 상태
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [editingSessionId, setEditingSessionId] = useState(null)
  const [editingTitle, setEditingTitle] = useState('')
  
  // 자동 저장 타이머
  const autoSaveTimer = useRef(null)
  const tokenCounter = useRef(0)
  
  // 키보드 단축키
  useEffect(() => {
    const handleKeyPress = (e) => {
      // Cmd/Ctrl + N: 새 대화
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault()
        createNewSession()
      }
      // /: 검색
      if (e.key === '/' && !e.target.matches('input, textarea')) {
        e.preventDefault()
        document.getElementById('session-search')?.focus()
      }
    }
    
    window.addEventListener('keydown', handleKeyPress)
    return () => window.removeEventListener('keydown', handleKeyPress)
  }, [])
  
  // 세션 목록 로드
  useEffect(() => {
    loadSessions()
  }, [])
  
  // 자동 저장 (2초마다 또는 200토큰마다)
  useEffect(() => {
    if (currentSessionId && draftState[currentSessionId]) {
      clearTimeout(autoSaveTimer.current)
      autoSaveTimer.current = setTimeout(() => {
        saveDraft()
      }, 2000)
    }
    
    return () => clearTimeout(autoSaveTimer.current)
  }, [draftState, currentSessionId])
  
  // 세션 목록 로드
  const loadSessions = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/sessions/list?limit=50')
      const data = await response.json()
      setSessions(data.sessions)
      setSessionList(data.sessions)
    } catch (error) {
      console.error('Failed to load sessions:', error)
    }
  }
  
  // 새 세션 생성 (중복 방지)
  const [isCreatingSession, setIsCreatingSession] = useState(false)
  
  const createNewSession = async (initialQuery = null) => {
    // 이미 생성 중이면 무시
    if (isCreatingSession) {
      console.log('Already creating a session')
      return currentSessionId
    }
    
    setIsCreatingSession(true)
    
    try {
      const response = await fetch('http://localhost:8000/api/sessions/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initial_query: initialQuery })
      })
      const data = await response.json()
      
      setCurrentSessionId(data.session_id)
      await loadSessions()
      
      return data.session_id
    } catch (error) {
      console.error('Failed to create session:', error)
      return null
    } finally {
      setIsCreatingSession(false)
    }
  }
  
  // 세션 전환
  const switchSession = async (sessionId) => {
    // 현재 세션 초안 저장
    if (currentSessionId) {
      await saveDraft()
    }
    
    setCurrentSessionId(sessionId)
    
    // 새 세션 데이터 로드
    try {
      const response = await fetch(`/api/sessions/${sessionId}`)
      const data = await response.json()
      
      // 복구 가능한 상태 확인
      const resumeResponse = await fetch(`/api/sessions/resume/${sessionId}`, {
        method: 'POST'
      })
      
      if (resumeResponse.ok) {
        const resumeData = await resumeResponse.json()
        if (resumeData.draft_state) {
          setDraftState(prev => ({
            ...prev,
            [sessionId]: resumeData.draft_state
          }))
        }
      }
      
      return data
    } catch (error) {
      console.error('Failed to switch session:', error)
    }
  }
  
  // 세션 삭제
  const deleteSession = async (sessionId) => {
    if (confirm('이 대화를 삭제하시겠습니까?')) {
      try {
        await fetch(`/api/sessions/${sessionId}`, {
          method: 'DELETE'
        })
        
        // 현재 세션이면 새 세션으로
        if (currentSessionId === sessionId) {
          await createNewSession()
        }
        
        await loadSessions()
      } catch (error) {
        console.error('Failed to delete session:', error)
      }
    }
  }
  
  // 세션 제목 변경
  const updateSessionTitle = async (sessionId, title) => {
    if (!title.trim()) return
    
    try {
      await fetch(`/api/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title_user: title })
      })
      
      setEditingSessionId(null)
      setEditingTitle('')
      await loadSessions()
    } catch (error) {
      console.error('Failed to update title:', error)
    }
  }
  
  // 제목 편집 시작
  const startEditingTitle = (sessionId, currentTitle) => {
    setEditingSessionId(sessionId)
    setEditingTitle(currentTitle)
  }
  
  // 제목 편집 취소
  const cancelEditingTitle = () => {
    setEditingSessionId(null)
    setEditingTitle('')
  }
  
  // 세션 아카이브
  const archiveSession = async (sessionId) => {
    try {
      await fetch(`/api/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ archived: true })
      })
      
      await loadSessions()
    } catch (error) {
      console.error('Failed to archive session:', error)
    }
  }
  
  // 초안 저장
  const saveDraft = useCallback(async () => {
    if (!currentSessionId || !draftState[currentSessionId]) return
    
    try {
      await fetch('http://localhost:8000/api/sessions/draft/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: currentSessionId,
          draft_data: draftState[currentSessionId]
        })
      })
    } catch (error) {
      console.error('Failed to save draft:', error)
    }
  }, [currentSessionId, draftState])
  
  // 검색
  const searchSessions = async (query) => {
    if (!query) {
      await loadSessions()
      return
    }
    
    try {
      const response = await fetch(`/api/sessions/search?q=${encodeURIComponent(query)}&limit=20`)
      const data = await response.json()
      setSessions(data.results)
    } catch (error) {
      console.error('Failed to search sessions:', error)
    }
  }
  
  // 세션 복구
  const resumeSession = async () => {
    if (!currentSessionId) return
    
    try {
      const response = await fetch(`/api/sessions/resume/${currentSessionId}`, {
        method: 'POST'
      })
      
      if (response.ok) {
        const data = await response.json()
        return data
      }
    } catch (error) {
      console.error('Failed to resume session:', error)
    }
  }
  
  return (
    <div className="flex h-screen bg-gray-50">
      {/* 좌측 사이드바 - 세션 목록 */}
      <div className={`${sidebarOpen ? 'w-80' : 'w-0'} transition-all duration-300 bg-white border-r border-gray-200 flex flex-col overflow-hidden`}>
        {/* 헤더 */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-lg font-semibold">대화 목록</h2>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-1 hover:bg-gray-100 rounded"
              title="사이드바 토글"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
          </div>
          
          {/* 새 대화 버튼 */}
          <button
            onClick={() => createNewSession()}
            disabled={isCreatingSession}
            className="w-full py-2 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            새 대화 (Ctrl+N)
          </button>
          
          {/* 검색 */}
          <div className="mt-3 relative">
            <input
              id="session-search"
              type="text"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value)
                searchSessions(e.target.value)
              }}
              placeholder="대화 검색... (/)"
              className="w-full px-3 py-2 pl-9 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <svg className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </div>
        </div>
        
        {/* 세션 목록 */}
        <div className="flex-1 overflow-y-auto">
          {sessions.length === 0 ? (
            <div className="p-4 text-center text-gray-500">
              <svg className="w-12 h-12 mx-auto mb-3 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
              </svg>
              <p className="font-medium mb-1">대화가 없습니다</p>
              <p className="text-sm">새 대화를 시작해보세요</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {sessions.map((session) => (
                <div
                  key={session.session_id}
                  className={`group relative hover:bg-gray-50 transition-colors ${
                    currentSessionId === session.session_id ? 'bg-blue-50 border-l-4 border-blue-600' : ''
                  }`}
                >
                  <div
                    onClick={() => switchSession(session.session_id)}
                    className="w-full text-left p-4 cursor-pointer"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        {editingSessionId === session.session_id ? (
                          <div className="flex items-center gap-2 pr-24 relative z-10" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="text"
                              value={editingTitle}
                              onChange={(e) => setEditingTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') {
                                  updateSessionTitle(session.session_id, editingTitle)
                                } else if (e.key === 'Escape') {
                                  cancelEditingTitle()
                                }
                              }}
                              className="flex-1 px-2 py-1 border border-blue-500 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
                              autoFocus
                              onClick={(e) => e.stopPropagation()}
                            />
                            <div className="flex items-center gap-1 bg-white rounded px-1">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  updateSessionTitle(session.session_id, editingTitle)
                                }}
                                className="p-1 text-green-600 hover:text-green-700 hover:bg-green-50 rounded"
                                title="저장"
                              >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  cancelEditingTitle()
                                }}
                                className="p-1 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded"
                                title="취소"
                              >
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                          </div>
                        ) : (
                          <p className="font-medium text-gray-900 truncate">
                            {session.title}
                          </p>
                        )}
                        <p className="text-sm text-gray-500 mt-1">
                          {new Date(session.updated_at).toLocaleDateString('ko-KR')}
                          {' · '}
                          {session.message_count}개 메시지
                        </p>
                        {session.match_preview && (
                          <p className="text-sm text-gray-600 mt-1 line-clamp-2">
                            {session.match_preview}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {/* 액션 버튼들 - 수정 중이 아닐 때만 표시 */}
                  {editingSessionId !== session.session_id && (
                  <div className="absolute top-4 right-4 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity z-0">
                    {session.archived && (
                      <span className="px-2 py-1 text-xs bg-gray-200 text-gray-700 rounded mr-2">
                        보관됨
                      </span>
                    )}
                    {/* 제목 수정 버튼 */}
                    {editingSessionId !== session.session_id && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          startEditingTitle(session.session_id, session.title)
                        }}
                        className="p-1.5 hover:bg-gray-200 rounded transition-colors"
                        title="제목 수정"
                      >
                        <svg className="w-4 h-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                        </svg>
                      </button>
                    )}
                    {/* 삭제 버튼 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        if (confirm(`"${session.title}" 대화를 삭제하시겠습니까?`)) {
                          deleteSession(session.session_id)
                        }
                      }}
                      className="p-1.5 hover:bg-red-100 rounded transition-colors group/delete"
                      title="삭제"
                    >
                      <svg className="w-4 h-4 text-gray-600 group-hover/delete:text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
        
        {/* 하단 상태 표시 */}
        <div className="p-4 border-t border-gray-200 text-xs text-gray-500">
          <div className="flex items-center justify-between">
            <span>{sessions.length}개 대화</span>
            {draftState[currentSessionId] && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                자동 저장 중
              </span>
            )}
          </div>
        </div>
      </div>
      
      {/* 우측 메인 영역 */}
      <div className="flex-1 flex flex-col">
        {/* 토글 버튼 (사이드바 닫혔을 때) */}
        {!sidebarOpen && (
          <button
            onClick={() => setSidebarOpen(true)}
            className="absolute left-2 top-2 p-2 bg-white shadow-md rounded-lg hover:bg-gray-50"
            title="사이드바 열기"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        )}
        
        {/* 자식 컴포넌트에 세션 정보 전달 */}
        {React.cloneElement(children, {
          currentSessionId,
          createNewSession,
          switchSession,
          updateDraft: (draft) => {
            setDraftState(prev => ({
              ...prev,
              [currentSessionId]: draft
            }))
            tokenCounter.current += 1
            
            // 200토큰마다 강제 저장
            if (tokenCounter.current >= 200) {
              saveDraft()
              tokenCounter.current = 0
            }
          },
          resumeSession,
          sessionList
        })}
      </div>
    </div>
  )
}

export default SessionManager
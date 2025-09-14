import React, { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'
import './styles/MultiSession.css'
import SessionSidebar from './components/SessionSidebar'
import ChatArea from './components/ChatArea'
import MessageInput from './components/MessageInput'
import ConfirmDialog from './components/ConfirmDialog'
import ErrorBoundary from './components/ErrorBoundary'
import LoadingOverlay from './components/LoadingOverlay'
import { useSessionManager } from './hooks/useSessionManager'
import { useStreamingResponse } from './hooks/useStreamingResponse'
import { useAutoSave } from './hooks/useAutoSave'
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts'

// API 기본 설정
axios.defaults.baseURL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
axios.defaults.timeout = 30000

// 에러 인터셉터
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.data?.user_message) {
      // 사용자 친화적 메시지가 있으면 표시
      const userMessage = error.response.data.user_message
      console.error('API Error:', userMessage)
      return Promise.reject(new Error(userMessage))
    }
    
    // 네트워크 오류
    if (!error.response) {
      return Promise.reject(new Error('인터넷 연결을 확인해 주세요.'))
    }
    
    // 서버 오류
    if (error.response.status >= 500) {
      return Promise.reject(new Error('일시적인 오류입니다. 잠시 후 다시 시도해 주세요.'))
    }
    
    return Promise.reject(error)
  }
)

function App() {
  // 세션 관리
  const {
    sessions,
    currentSession,
    currentSessionId,
    loading: sessionsLoading,
    error: sessionsError,
    createSession,
    selectSession,
    updateSession,
    deleteSession,
    refreshSessions
  } = useSessionManager()
  
  // 메시지 관리
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [streamingMessage, setStreamingMessage] = useState('')
  
  // 스트리밍 응답
  const {
    startStreaming,
    stopStreaming,
    isStreaming,
    streamedContent,
    streamError
  } = useStreamingResponse()
  
  // 자동 저장
  const { 
    saveNow,
    lastSaved,
    isSaving 
  } = useAutoSave(currentSessionId, messages, inputMessage)
  
  // UI 상태
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [deleteTargetId, setDeleteTargetId] = useState(null)
  const [showSwitchConfirm, setShowSwitchConfirm] = useState(false)
  const [switchTargetId, setSwitchTargetId] = useState(null)
  const [editingTitle, setEditingTitle] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)
  
  // Refs
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const abortControllerRef = useRef(null)
  
  // 키보드 단축키
  useKeyboardShortcuts({
    'Ctrl+N': () => handleNewSession(),
    'Ctrl+D': () => currentSessionId && handleDeleteRequest(currentSessionId),
    'Escape': () => {
      if (isGenerating) handleStopGeneration()
      if (editingTitle) setEditingTitle(false)
    }
  })
  
  // 세션 변경 시 메시지 로드
  useEffect(() => {
    if (currentSession) {
      setMessages(currentSession.messages || [])
      scrollToBottom()
    } else {
      setMessages([])
    }
  }, [currentSession])
  
  // 에러/정보 메시지 자동 숨김
  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000)
      return () => clearTimeout(timer)
    }
  }, [error])
  
  useEffect(() => {
    if (info) {
      const timer = setTimeout(() => setInfo(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [info])
  
  // 스크롤 제어
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])
  
  // 새 세션 생성
  const handleNewSession = async () => {
    try {
      if (isGenerating) {
        setError('답변 생성 중입니다. 잠시만 기다려주세요.')
        return
      }
      
      const session = await createSession()
      setInfo('새 대화가 시작되었습니다.')
      inputRef.current?.focus()
    } catch (err) {
      setError(err.message || '새 대화를 시작할 수 없습니다.')
    }
  }
  
  // 세션 전환
  const handleSessionSelect = async (sessionId) => {
    if (sessionId === currentSessionId) return
    
    if (isGenerating) {
      setSwitchTargetId(sessionId)
      setShowSwitchConfirm(true)
      return
    }
    
    try {
      await selectSession(sessionId)
      setInputMessage('')
      setInfo('대화를 불러왔습니다.')
    } catch (err) {
      setError(err.message || '대화를 불러올 수 없습니다.')
    }
  }
  
  // 세션 전환 확인
  const confirmSessionSwitch = async () => {
    if (isGenerating) {
      await handleStopGeneration()
    }
    
    setShowSwitchConfirm(false)
    await handleSessionSelect(switchTargetId)
    setSwitchTargetId(null)
  }
  
  // 제목 수정
  const handleTitleEdit = () => {
    if (!currentSession) return
    setNewTitle(currentSession.title || '')
    setEditingTitle(true)
  }
  
  const handleTitleSave = async () => {
    if (!newTitle.trim()) {
      setError('제목을 입력해주세요.')
      return
    }
    
    if (newTitle.length > 50) {
      setError('제목은 50자 이하로 입력해주세요.')
      return
    }
    
    try {
      await updateSession(currentSessionId, { title_user: newTitle })
      setEditingTitle(false)
      setInfo('제목이 변경되었습니다.')
    } catch (err) {
      setError(err.message || '제목을 변경할 수 없습니다.')
    }
  }
  
  // 메시지 전송
  const handleSendMessage = async () => {
    const message = inputMessage.trim()
    
    if (!message) {
      setError('메시지를 입력해 주세요.')
      inputRef.current?.focus()
      return
    }
    
    if (message.length > 5000) {
      setError('메시지가 너무 깁니다. 짧게 나누어 보내주세요.')
      return
    }
    
    if (isGenerating) {
      setError('이전 메시지 처리 중입니다. 잠시만 기다려주세요.')
      return
    }
    
    // 세션이 없으면 생성
    let sessionId = currentSessionId
    if (!sessionId) {
      try {
        const session = await createSession(message)
        sessionId = session.session_id
      } catch (err) {
        setError('대화를 시작할 수 없습니다.')
        return
      }
    }
    
    // 사용자 메시지 추가
    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    }
    
    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsGenerating(true)
    setStreamingMessage('')
    
    try {
      // 서버에 메시지 전송 및 스트리밍 응답 받기
      abortControllerRef.current = new AbortController()
      
      const response = await fetch('/api/sessions/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          content: message,
          stream: true
        }),
        signal: abortControllerRef.current.signal
      })
      
      if (!response.ok) {
        throw new Error('메시지 전송에 실패했습니다.')
      }
      
      // SSE 스트리밍 처리
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let assistantMessage = ''
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              
              if (data.type === 'token') {
                assistantMessage += data.content
                setStreamingMessage(assistantMessage)
              } else if (data.type === 'complete') {
                const finalMessage = {
                  role: 'assistant',
                  content: data.response.answer,
                  citations: data.response.sources,
                  timestamp: new Date().toISOString()
                }
                setMessages(prev => [...prev, finalMessage])
                setStreamingMessage('')
              } else if (data.type === 'error') {
                throw new Error(data.message)
              }
            } catch (e) {
              console.error('SSE parse error:', e)
            }
          }
        }
      }
      
    } catch (err) {
      if (err.name === 'AbortError') {
        setInfo('답변 생성이 중단되었습니다.')
      } else {
        setError(err.message || '답변을 생성할 수 없습니다.')
      }
    } finally {
      setIsGenerating(false)
      setStreamingMessage('')
      scrollToBottom()
      await saveNow()
    }
  }
  
  // 생성 중단
  const handleStopGeneration = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    setIsGenerating(false)
    setStreamingMessage('')
    setInfo('답변 생성을 중단했습니다.')
  }
  
  // 세션 삭제 요청
  const handleDeleteRequest = (sessionId) => {
    if (isGenerating) {
      setError('답변 생성 중에는 삭제할 수 없습니다.')
      return
    }
    
    setDeleteTargetId(sessionId)
    setShowDeleteConfirm(true)
  }
  
  // 세션 삭제 확인
  const confirmDelete = async () => {
    try {
      await deleteSession(deleteTargetId)
      setShowDeleteConfirm(false)
      setDeleteTargetId(null)
      setInfo('대화가 삭제되었습니다.')
      
      // 현재 세션이 삭제되면 새 세션 생성
      if (deleteTargetId === currentSessionId) {
        await handleNewSession()
      }
    } catch (err) {
      setError(err.message || '대화를 삭제할 수 없습니다.')
    }
  }
  
  // Enter 키 처리
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }
  
  // 페이지 나가기 방지
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isGenerating || inputMessage.trim()) {
        e.preventDefault()
        e.returnValue = '작성 중인 내용이 있습니다. 페이지를 떠나시겠습니까?'
      }
    }
    
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isGenerating, inputMessage])
  
  return (
    <ErrorBoundary>
      <div className="app-container">
        {/* 로딩 오버레이 */}
        {sessionsLoading && <LoadingOverlay message="대화 목록을 불러오는 중..." />}
        
        {/* 에러/정보 메시지 */}
        {error && (
          <div className="toast toast-error">
            <span>{error}</span>
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}
        
        {info && (
          <div className="toast toast-info">
            <span>{info}</span>
          </div>
        )}
        
        {/* 사이드바 */}
        <SessionSidebar
          sessions={sessions}
          currentSessionId={currentSessionId}
          onNewSession={handleNewSession}
          onSelectSession={handleSessionSelect}
          onDeleteSession={handleDeleteRequest}
          isGenerating={isGenerating}
        />
        
        {/* 메인 채팅 영역 */}
        <div className="main-content">
          {/* 헤더 */}
          <div className="chat-header">
            {editingTitle ? (
              <div className="title-edit">
                <input
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleTitleSave()}
                  onBlur={handleTitleSave}
                  autoFocus
                  maxLength={50}
                  className="title-input"
                />
              </div>
            ) : (
              <h2 
                className="chat-title"
                onDoubleClick={handleTitleEdit}
                title="더블클릭하여 수정"
              >
                {currentSession?.title || '새 대화'}
              </h2>
            )}
            
            {/* 상태 표시 */}
            <div className="header-status">
              {isSaving && <span className="status-saving">저장 중...</span>}
              {lastSaved && (
                <span className="status-saved">
                  마지막 저장: {new Date(lastSaved).toLocaleTimeString()}
                </span>
              )}
            </div>
          </div>
          
          {/* 채팅 영역 */}
          <ChatArea
            messages={messages}
            streamingMessage={streamingMessage}
            isGenerating={isGenerating}
            messagesEndRef={messagesEndRef}
          />
          
          {/* 입력 영역 */}
          <MessageInput
            value={inputMessage}
            onChange={setInputMessage}
            onSend={handleSendMessage}
            onStop={handleStopGeneration}
            isGenerating={isGenerating}
            disabled={sessionsLoading}
            inputRef={inputRef}
            onKeyPress={handleKeyPress}
          />
        </div>
        
        {/* 확인 다이얼로그 */}
        {showDeleteConfirm && (
          <ConfirmDialog
            title="대화 삭제"
            message="정말 이 대화를 삭제하시겠습니까? 삭제된 대화는 복구할 수 없습니다."
            onConfirm={confirmDelete}
            onCancel={() => {
              setShowDeleteConfirm(false)
              setDeleteTargetId(null)
            }}
            confirmText="삭제"
            cancelText="취소"
            type="danger"
          />
        )}
        
        {showSwitchConfirm && (
          <ConfirmDialog
            title="대화 전환"
            message="답변 생성을 중단하고 다른 대화로 이동하시겠습니까?"
            onConfirm={confirmSessionSwitch}
            onCancel={() => {
              setShowSwitchConfirm(false)
              setSwitchTargetId(null)
            }}
            confirmText="이동"
            cancelText="취소"
            type="warning"
          />
        )}
      </div>
    </ErrorBoundary>
  )
}

export default App
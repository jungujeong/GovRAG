import React, { useState, useEffect, useRef, useCallback } from 'react'
import SessionSidebar from './components/SessionSidebar'
import ChatArea from './components/ChatArea'
import MessageInput from './components/MessageInput'
import StatusIndicator from './components/StatusIndicator'
import LoadingOverlay from './components/LoadingOverlay'
import ConfirmDialog from './components/ConfirmDialog'
import ErrorBoundary from './components/ErrorBoundary'
import { useSessionStore } from './stores/sessionStore'
import { useChatStore } from './stores/chatStore'
import { useDocumentStore } from './stores/documentStore'
import { chatAPI } from './services/chatAPI'
import { documentAPI } from './services/documentAPI'
import './styles/Chat.css'

function AppChat() {
  // Store hooks
  const {
    sessions,
    currentSessionId,
    loadSessions,
    createSession,
    selectSession,
    updateSession,
    deleteSession
  } = useSessionStore()
  
  const {
    messages,
    isLoading,
    streamingContent,
    loadMessages,
    addMessage,
    clearMessages,
    setLoading,
    setStreamingContent
  } = useChatStore()
  
  const {
    documents,
    loadDocuments,
    uploadDocuments
  } = useDocumentStore()
  
  // Local state
  const [systemStatus, setSystemStatus] = useState({
    status: 'checking',
    components: {}
  })
  const [showConfirm, setShowConfirm] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [error, setError] = useState(null)
  const [inputMessage, setInputMessage] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [abortController, setAbortController] = useState(null)
  
  // Refs
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const fileInputRef = useRef(null)
  
  // WebSocket connection
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  
  // Initialize
  useEffect(() => {
    initializeApp()
    return () => {
      cleanup()
    }
  }, [])
  
  // Scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom()
  }, [messages, streamingContent])
  
  // Connect WebSocket when session changes
  useEffect(() => {
    if (currentSessionId) {
      connectWebSocket(currentSessionId)
    }
    return () => {
      disconnectWebSocket()
    }
  }, [currentSessionId])
  
  const initializeApp = async () => {
    try {
      // Check system health
      const health = await chatAPI.checkHealth()
      setSystemStatus(health)
      
      // Load initial data
      await Promise.all([
        loadSessions(),
        loadDocuments()
      ])
      
      // Create initial session if none exists
      const sessionList = useSessionStore.getState().sessions
      if (sessionList.length === 0) {
        await handleNewSession()
      }
    } catch (error) {
      console.error('Failed to initialize app:', error)
      setError('시스템 초기화에 실패했습니다. 페이지를 새로고침해 주세요.')
    }
  }
  
  const cleanup = () => {
    disconnectWebSocket()
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (abortController) {
      abortController.abort()
    }
  }
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
  
  // WebSocket management
  const connectWebSocket = (sessionId) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return
    }
    
    const wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/chat/sessions/${sessionId}/ws`
    
    try {
      const ws = new WebSocket(wsUrl)
      
      ws.onopen = () => {
        console.log('WebSocket connected')
        setSystemStatus(prev => ({
          ...prev,
          websocket: true
        }))
      }
      
      ws.onmessage = (event) => {
        handleWebSocketMessage(JSON.parse(event.data))
      }
      
      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        setSystemStatus(prev => ({
          ...prev,
          websocket: false
        }))
      }
      
      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setSystemStatus(prev => ({
          ...prev,
          websocket: false
        }))
        
        // Reconnect after delay
        reconnectTimeoutRef.current = setTimeout(() => {
          if (currentSessionId) {
            connectWebSocket(currentSessionId)
          }
        }, 3000)
      }
      
      wsRef.current = ws
    } catch (error) {
      console.error('Failed to connect WebSocket:', error)
    }
  }
  
  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }
  
  const handleWebSocketMessage = (data) => {
    switch (data.type) {
      case 'status':
        setLoading(true)
        setStreamingContent(data.message)
        break
        
      case 'response':
        if (data.complete) {
          // Add complete message
          addMessage({
            role: 'assistant',
            content: streamingContent + (data.content || ''),
            sources: data.sources
          })
          setStreamingContent('')
          setIsGenerating(false)
          setLoading(false)
        } else {
          // Append streaming content
          setStreamingContent(prev => prev + data.content)
        }
        break
        
      case 'error':
        setError(data.message)
        setIsGenerating(false)
        setLoading(false)
        break
        
      case 'stopped':
        setIsGenerating(false)
        setLoading(false)
        break
    }
  }
  
  // Session handlers
  const handleNewSession = async () => {
    try {
      const session = await createSession('새 대화')
      selectSession(session.id)
      setInputMessage('')
      inputRef.current?.focus()
    } catch (error) {
      console.error('Failed to create session:', error)
      setError('새 대화를 시작할 수 없습니다.')
    }
  }
  
  const handleSelectSession = async (sessionId) => {
    if (isGenerating) {
      setConfirmAction({
        title: '대화 전환',
        message: '답변 생성을 중단하고 다른 대화로 이동하시겠습니까?',
        onConfirm: async () => {
          handleStopGeneration()
          await selectAndLoadSession(sessionId)
        }
      })
      setShowConfirm(true)
    } else {
      await selectAndLoadSession(sessionId)
    }
  }
  
  const selectAndLoadSession = async (sessionId) => {
    try {
      selectSession(sessionId)
      const sessionData = await chatAPI.getSession(sessionId)
      loadMessages(sessionData.messages)
      setInputMessage('')
    } catch (error) {
      console.error('Failed to load session:', error)
      setError('대화를 불러올 수 없습니다.')
    }
  }
  
  const handleRenameSession = async (sessionId, newTitle) => {
    if (!newTitle.trim()) return
    
    try {
      await updateSession(sessionId, { title: newTitle })
    } catch (error) {
      console.error('Failed to rename session:', error)
      setError('대화 이름을 변경할 수 없습니다.')
    }
  }
  
  const handleDeleteSession = (sessionId) => {
    setConfirmAction({
      title: '대화 삭제',
      message: '이 대화를 삭제하시겠습니까? 모든 메시지가 삭제됩니다.',
      onConfirm: async () => {
        try {
          await deleteSession(sessionId)
          
          // Select another session if current was deleted
          if (sessionId === currentSessionId) {
            const remainingSessions = useSessionStore.getState().sessions
            if (remainingSessions.length > 0) {
              await selectAndLoadSession(remainingSessions[0].id)
            } else {
              await handleNewSession()
            }
          }
        } catch (error) {
          console.error('Failed to delete session:', error)
          setError('대화를 삭제할 수 없습니다.')
        }
      }
    })
    setShowConfirm(true)
  }
  
  // Message handlers
  const handleSendMessage = async (message) => {
    if (!message.trim()) {
      setError('메시지를 입력해 주세요.')
      return
    }
    
    if (message.length > 2000) {
      setError('메시지가 너무 깁니다. 짧게 나누어 보내주세요.')
      return
    }
    
    if (!currentSessionId) {
      await handleNewSession()
    }
    
    // Check if documents are uploaded
    if (documents.length === 0) {
      setError('먼저 문서를 업로드해 주세요.')
      return
    }
    
    try {
      setIsGenerating(true)
      setLoading(true)
      setError(null)
      
      // Add user message
      addMessage({
        role: 'user',
        content: message
      })
      
      // Clear input
      setInputMessage('')
      
      // Send via WebSocket if connected
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'message',
          content: message
        }))
      } else {
        // Fallback to HTTP API
        const controller = new AbortController()
        setAbortController(controller)
        
        const response = await chatAPI.sendMessage(
          currentSessionId,
          message,
          {
            signal: controller.signal,
            onStream: (chunk) => {
              setStreamingContent(prev => prev + chunk)
            }
          }
        )
        
        addMessage({
          role: 'assistant',
          content: response.answer,
          sources: response.sources
        })
        
        setStreamingContent('')
      }
    } catch (error) {
      if (error.name !== 'AbortError') {
        console.error('Failed to send message:', error)
        setError('메시지 전송에 실패했습니다. 다시 시도해 주세요.')
      }
    } finally {
      setIsGenerating(false)
      setLoading(false)
      setAbortController(null)
    }
  }
  
  const handleStopGeneration = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }))
    }
    
    if (abortController) {
      abortController.abort()
    }
    
    setIsGenerating(false)
    setLoading(false)
  }
  
  const handleRetry = async () => {
    const lastUserMessage = messages.filter(m => m.role === 'user').pop()
    if (lastUserMessage) {
      await handleSendMessage(lastUserMessage.content)
    }
  }
  
  // Document handlers
  const handleUploadDocuments = async (files) => {
    try {
      setLoading(true)
      const result = await uploadDocuments(files)
      
      if (result.uploaded.length > 0) {
        setError(null)
        
        // Link documents to current session
        if (currentSessionId) {
          const docIds = result.uploaded.map(d => d.id)
          await updateSession(currentSessionId, {
            document_ids: docIds
          })
        }
      }
      
      if (result.failed.length > 0) {
        setError(`${result.failed.length}개 파일 업로드 실패`)
      }
    } catch (error) {
      console.error('Failed to upload documents:', error)
      setError('문서 업로드에 실패했습니다.')
    } finally {
      setLoading(false)
    }
  }
  
  const handleFileSelect = () => {
    fileInputRef.current?.click()
  }
  
  const handleFileChange = async (event) => {
    const files = Array.from(event.target.files)
    if (files.length > 0) {
      await handleUploadDocuments(files)
    }
    event.target.value = '' // Reset input
  }
  
  // Keyboard handlers
  const handleKeyDown = useCallback((e) => {
    // Ctrl/Cmd + N: New session
    if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
      e.preventDefault()
      handleNewSession()
    }
    
    // Ctrl/Cmd + O: Upload documents
    if ((e.ctrlKey || e.metaKey) && e.key === 'o') {
      e.preventDefault()
      handleFileSelect()
    }
    
    // Escape: Stop generation or clear error
    if (e.key === 'Escape') {
      if (isGenerating) {
        handleStopGeneration()
      } else if (error) {
        setError(null)
      }
    }
  }, [isGenerating, error])
  
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown)
    return () => {
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [handleKeyDown])
  
  return (
    <ErrorBoundary>
      <div className="app-container">
        {/* Header */}
        <header className="app-header">
          <div className="header-content">
            <h1 className="app-title">
              <span className="icon">💬</span>
              RAG 채팅 시스템
            </h1>
            <StatusIndicator status={systemStatus} />
          </div>
        </header>
        
        {/* Main Layout */}
        <div className="app-main">
          {/* Sidebar */}
          <SessionSidebar
            sessions={sessions}
            currentSessionId={currentSessionId}
            documents={documents}
            onNewSession={handleNewSession}
            onSelectSession={handleSelectSession}
            onRenameSession={handleRenameSession}
            onDeleteSession={handleDeleteSession}
            onUploadDocuments={handleFileSelect}
          />
          
          {/* Chat Area */}
          <div className="chat-container">
            {/* Chat Header */}
            <div className="chat-header">
              <h2 className="chat-title">
                {sessions.find(s => s.id === currentSessionId)?.title || '새 대화'}
              </h2>
              <div className="chat-actions">
                {documents.length === 0 && (
                  <button
                    className="btn-upload-prompt"
                    onClick={handleFileSelect}
                  >
                    📤 문서 업로드하기
                  </button>
                )}
                {isGenerating && (
                  <button
                    className="btn-stop"
                    onClick={handleStopGeneration}
                  >
                    ⏹️ 중지
                  </button>
                )}
              </div>
            </div>
            
            {/* Messages */}
            <ChatArea
              messages={messages}
              streamingContent={streamingContent}
              isLoading={isLoading}
              error={error}
              onRetry={handleRetry}
              onClearError={() => setError(null)}
            />
            <div ref={messagesEndRef} />
            
            {/* Input */}
            <MessageInput
              ref={inputRef}
              value={inputMessage}
              onChange={setInputMessage}
              onSend={handleSendMessage}
              disabled={isGenerating}
              placeholder={
                documents.length === 0
                  ? "먼저 문서를 업로드해 주세요..."
                  : isGenerating
                  ? "답변 생성 중..."
                  : "메시지를 입력하세요..."
              }
            />
          </div>
        </div>
        
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.hwp"
          onChange={handleFileChange}
          style={{ display: 'none' }}
        />
        
        {/* Loading overlay */}
        {isLoading && !streamingContent && (
          <LoadingOverlay message="처리 중..." />
        )}
        
        {/* Confirm dialog */}
        {showConfirm && confirmAction && (
          <ConfirmDialog
            title={confirmAction.title}
            message={confirmAction.message}
            onConfirm={() => {
              confirmAction.onConfirm()
              setShowConfirm(false)
              setConfirmAction(null)
            }}
            onCancel={() => {
              setShowConfirm(false)
              setConfirmAction(null)
            }}
          />
        )}
        
        {/* Footer */}
        <footer className="app-footer">
          <div className="footer-content">
            <span className="footer-text">
              RAG Chatbot System v1.0.0 | 폐쇄망/오프라인 환경 지원
            </span>
            <div className="footer-shortcuts">
              <span className="shortcut">Ctrl+N: 새 대화</span>
              <span className="shortcut">Ctrl+O: 문서 업로드</span>
              <span className="shortcut">ESC: 중지/취소</span>
            </div>
          </div>
        </footer>
      </div>
    </ErrorBoundary>
  )
}

export default AppChat
import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { chatAPI } from './services/chatAPI'
import './styles/CleanMedium.css'

function AppSession() {
  // Tab state
  const [activeTab, setActiveTab] = useState('chat')
  
  // Chat state
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [streamStatus, setStreamStatus] = useState('')
  const [editingSessionId, setEditingSessionId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  
  // Document state
  const [documents, setDocuments] = useState([])
  const [selectedDocs, setSelectedDocs] = useState([])
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStatus, setUploadStatus] = useState('')
  const [processingDoc, setProcessingDoc] = useState(null)
  
  // System state
  const [systemStatus, setSystemStatus] = useState({ status: 'checking' })
  const [error, setError] = useState(null)
  
  // Citation popup state
  const [showSourcePopup, setShowSourcePopup] = useState(false)
  const [selectedSource, setSelectedSource] = useState(null)
  
  // Document details state
  const [showDocDetails, setShowDocDetails] = useState(false)
  const [docDetails, setDocDetails] = useState(null)
  const [loadingDetails, setLoadingDetails] = useState(false)
  
  // Refs
  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)
  
  // Initialize
  useEffect(() => {
    checkHealth()
    loadDocuments()
    loadSessions()
  }, [])
  
  // Auto scroll
  useEffect(() => {
    scrollToBottom()
  }, [messages])
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }
  
  const checkHealth = async () => {
    try {
      const response = await axios.get('/api/health')
      setSystemStatus(response.data)
    } catch (error) {
      console.error('Health check failed:', error)
      setSystemStatus({ status: 'unhealthy' })
    }
  }
  
  const loadDocuments = async () => {
    try {
      const response = await axios.get('/api/documents/list')
      setDocuments(response.data)
    } catch (error) {
      console.error('Failed to load documents:', error)
    }
  }
  
  const loadSessions = async () => {
    try {
      const response = await axios.get('/api/chat/sessions')
      setSessions(response.data.sessions || [])
      
      // Create initial session if none exists
      if (!response.data.sessions || response.data.sessions.length === 0) {
        await createNewSession()
      } else if (!currentSessionId) {
        // Select first session
        const firstSession = response.data.sessions[0]
        setCurrentSessionId(firstSession.id)
        await loadSessionMessages(firstSession.id)
      }
    } catch (error) {
      console.error('Failed to load sessions:', error)
    }
  }
  
  const createNewSession = async () => {
    try {
      const response = await axios.post('/api/chat/sessions', {
        title: '새 대화',
        document_ids: documents.map(d => (d.id ? d.id : (d.filename ? d.filename.replace(/\.[^.]+$/, '') : ''))).filter(Boolean)
      })
      
      const newSession = response.data.session
      setSessions(prev => [newSession, ...prev])
      setCurrentSessionId(newSession.id)
      setMessages([])
      setInputMessage('')
      
      return newSession
    } catch (error) {
      console.error('Failed to create session:', error)
      setError('새 대화를 시작할 수 없습니다.')
    }
  }
  
  const selectSession = async (sessionId) => {
    if (sessionId === currentSessionId) return
    
    setCurrentSessionId(sessionId)
    await loadSessionMessages(sessionId)
  }
  
  const loadSessionMessages = async (sessionId) => {
    try {
      const response = await axios.get(`/api/chat/sessions/${sessionId}`)
      setMessages(response.data.session.messages || [])
    } catch (error) {
      console.error('Failed to load session messages:', error)
      setMessages([])
    }
  }
  
  const updateSessionTitle = async (sessionId, newTitle) => {
    try {
      await axios.put(`/api/chat/sessions/${sessionId}`, {
        title: newTitle
      })
      
      setSessions(prev => prev.map(s => 
        s.id === sessionId ? { ...s, title: newTitle } : s
      ))
    } catch (error) {
      console.error('Failed to update session title:', error)
    }
  }
  
  const deleteSession = async (sessionId) => {
    if (!window.confirm('이 대화를 삭제하시겠습니까?')) return
    
    try {
      await axios.delete(`/api/chat/sessions/${sessionId}`)
      
      setSessions(prev => prev.filter(s => s.id !== sessionId))
      
      if (sessionId === currentSessionId) {
        const remainingSessions = sessions.filter(s => s.id !== sessionId)
        if (remainingSessions.length > 0) {
          await selectSession(remainingSessions[0].id)
        } else {
          await createNewSession()
        }
      }
    } catch (error) {
      console.error('Failed to delete session:', error)
      setError('대화를 삭제할 수 없습니다.')
    }
  }
  
  const handleSendMessage = async () => {
    const message = inputMessage.trim()
    if (!message) return
    
    if (!currentSessionId) {
      const newSession = await createNewSession()
      if (!newSession) return
    }
    
    // Add user message
    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsLoading(true)
    setError(null)
    
    try {
      // streaming placeholder
      const placeholder = {
        role: 'assistant',
        content: '',
        sources: [],
        streaming: true,
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, placeholder])
      setStreamStatus('답변 준비 중...')

      const controller = new AbortController()
      const finalResponse = await chatAPI.streamMessage(
        currentSessionId,
        message,
        controller.signal,
        (chunkOrStatus) => {
          if (!chunkOrStatus) return
          if (typeof chunkOrStatus === 'string' && (chunkOrStatus.includes('문서 검색 중') || chunkOrStatus.includes('답변 생성 중'))) {
            setStreamStatus(chunkOrStatus)
            return
          }
          const chunk = chunkOrStatus
          if (typeof chunk !== 'string') return
          setMessages(prev => {
            const updated = [...prev]
            for (let i = updated.length - 1; i >= 0; i--) {
              if (updated[i].role === 'assistant' && updated[i].streaming) {
                updated[i] = { ...updated[i], content: (updated[i].content || '') + chunk }
                break
              }
            }
            return updated
          })
        }
      )

      // finalize
      setMessages(prev => {
        const updated = [...prev]
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].role === 'assistant' && updated[i].streaming) {
            updated[i] = {
              ...updated[i],
              streaming: false,
              content: finalResponse.answer || updated[i].content || '응답을 생성할 수 없습니다.',
              sources: finalResponse.sources || []
            }
            break
          }
        }
        return updated
      })
      setStreamStatus('')
      
      // Update session title if it's the first message
      if (messages.length === 0) {
        await updateSessionTitle(currentSessionId, message.substring(0, 30))
      }
    } catch (error) {
      console.error('Failed to send message:', error)
      const errorMessage = {
        role: 'assistant',
        content: error.response?.data?.detail || '메시지 처리 중 오류가 발생했습니다.',
        error: true,
        timestamp: new Date().toISOString()
      }
      setMessages(prev => {
        const updated = [...prev]
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].role === 'assistant' && updated[i].streaming) {
            updated[i] = { ...errorMessage, streaming: false }
            return updated
          }
        }
        return [...updated, errorMessage]
      })
    } finally {
      setIsLoading(false)
      setStreamStatus('')
    }
  }
  
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }
  
  const handleShowSource = (source) => {
    setSelectedSource(source)
    setShowSourcePopup(true)
  }
  
  const handleCloseSourcePopup = () => {
    setShowSourcePopup(false)
    setSelectedSource(null)
  }
  
  const handleShowDocumentDetails = async (docId) => {
    try {
      setLoadingDetails(true)
      const response = await axios.get(`/api/documents/${docId}/details`)
      setDocDetails(response.data)
      setShowDocDetails(true)
    } catch (error) {
      console.error('Failed to load document details:', error)
      setError('문서 상세 정보를 불러올 수 없습니다.')
    } finally {
      setLoadingDetails(false)
    }
  }
  
  const handleCloseDocDetails = () => {
    setShowDocDetails(false)
    setDocDetails(null)
  }
  
  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files)
    if (files.length === 0) return
    
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })
    
    try {
      setUploadStatus('uploading')
      setUploadProgress(0)
      
      const response = await axios.post('/api/documents/upload-batch', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (progressEvent) => {
          const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total)
          setUploadProgress(percentCompleted)
        }
      })
      
      if (response.data.uploaded?.length > 0) {
        setUploadStatus('processing')
        await loadDocuments()
        setUploadStatus('completed')
        setTimeout(() => {
          setUploadStatus('')
          setUploadProgress(0)
        }, 2000)
      }
    } catch (error) {
      console.error('Upload failed:', error)
      setUploadStatus('error')
      setError('파일 업로드에 실패했습니다.')
      setTimeout(() => {
        setUploadStatus('')
        setUploadProgress(0)
      }, 3000)
    } finally {
      e.target.value = ''
    }
  }
  
  const handleDeleteDocument = async (docId) => {
    if (!window.confirm('이 문서를 삭제하시겠습니까?')) return
    
    try {
      await axios.delete(`/api/documents/${docId}`)
      await loadDocuments()
    } catch (error) {
      console.error('Failed to delete document:', error)
      setError('문서를 삭제할 수 없습니다.')
    }
  }
  
  const handleProcessDocument = async (docId) => {
    try {
      setProcessingDoc(docId)
      // Process document by triggering indexing
      await axios.post('/api/documents/process', {
        doc_ids: [docId]
      })
      await loadDocuments()
      setError(null)
    } catch (error) {
      console.error('Failed to process document:', error)
      setError('문서 처리에 실패했습니다.')
    } finally {
      setProcessingDoc(null)
    }
  }
  
  const handleDeleteAllDocuments = async () => {
    if (!window.confirm('모든 문서를 삭제하시겠습니까? 이 작업은 취소할 수 없습니다.')) return
    
    try {
      for (const doc of documents) {
        await axios.delete(`/api/documents/${doc.id || doc.filename}`)
      }
      await loadDocuments()
      setError(null)
    } catch (error) {
      console.error('Failed to delete all documents:', error)
      setError('문서 전체 삭제에 실패했습니다.')
    }
  }
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl/Cmd + N: New session
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault()
        createNewSession()
      }
      // Ctrl/Cmd + O: Upload documents
      if ((e.ctrlKey || e.metaKey) && e.key === 'o') {
        e.preventDefault()
        fileInputRef.current?.click()
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])
  
  return (
    <div className="app-container">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <h1 className="app-title">
            💬 RAG 채팅 시스템
          </h1>
          <div className="header-tabs">
            <button
              className={`tab-button ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              💬 채팅
            </button>
            <button
              className={`tab-button ${activeTab === 'upload' ? 'active' : ''}`}
              onClick={() => setActiveTab('upload')}
            >
              📤 문서 업로드
            </button>
            <button
              className={`tab-button ${activeTab === 'manage' ? 'active' : ''}`}
              onClick={() => setActiveTab('manage')}
            >
              📁 문서 관리
            </button>
          </div>
          <div className="status-indicator">
            {systemStatus.status === 'healthy' ? (
              <span className="status-healthy">⚫ 정상</span>
            ) : systemStatus.status === 'degraded' ? (
              <span className="status-degraded">⚫ 제한됨</span>
            ) : (
              <span className="status-unhealthy">⚫ Offline</span>
            )}
          </div>
        </div>
      </header>
      
      <div className="app-main">
        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <>
            {/* Sidebar */}
            <div className="sidebar">
              <button 
                className="btn-new-session"
                onClick={createNewSession}
                title="Ctrl+N"
              >
                ➕ 새 대화
              </button>
          
          <div className="session-list">
            <div className="session-list-header">대화 목록</div>
            {sessions.map(session => (
              <div
                key={session.id}
                className={`session-item ${session.id === currentSessionId ? 'active' : ''}`}
                onClick={() => selectSession(session.id)}
              >
                {editingSessionId === session.id ? (
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onBlur={() => {
                      updateSessionTitle(session.id, editTitle)
                      setEditingSessionId(null)
                    }}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        updateSessionTitle(session.id, editTitle)
                        setEditingSessionId(null)
                      }
                    }}
                    onClick={(e) => e.stopPropagation()}
                    autoFocus
                    className="session-title-input"
                  />
                ) : (
                  <div
                    className="session-title"
                    onDoubleClick={() => {
                      setEditingSessionId(session.id)
                      setEditTitle(session.title)
                    }}
                  >
                    {session.title}
                  </div>
                )}
                {session.id === currentSessionId && (
                  <button
                    className="btn-delete-session"
                    onClick={(e) => {
                      e.stopPropagation()
                      deleteSession(session.id)
                    }}
                  >
                    🗑️
                  </button>
                )}
              </div>
            ))}
          </div>
          
              <div className="sidebar-footer">
                <div className="document-count">
                  총 대화: {sessions.length}개
                </div>
                <div className="document-count">
                  문서: {documents.length}개
                </div>
              </div>
            </div>
            
            {/* Main Chat Content */}
            <div className="main-content">
          {/* Messages */}
          <div className="messages-container">
            {documents.length === 0 && (
              <div className="no-documents-notice">
                📁 문서를 먼저 업로드하고 질문해 보세요.
                <label className="upload-label">
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.hwp"
                    onChange={handleFileUpload}
                    style={{ display: 'none' }}
                  />
                  <button className="btn-upload">📤 문서 업로드</button>
                </label>
              </div>
            )}
            
            {messages.length === 0 && documents.length > 0 && (
              <div className="welcome-message">
                💡 사용 팁
                <ul>
                  <li>✓ 문서를 먼저 업로드하면 더 정확한 답변을 받을 수 있습니다</li>
                  <li>✓ 구체적인 질문일수록 좋은 답변을 받을 수 있습니다</li>
                  <li>✓ 대화 제목을 더블클릭하면 수정할 수 있습니다</li>
                  <li>✓ Ctrl+N으로 새 대화를 시작할 수 있습니다</li>
                </ul>
              </div>
            )}
            
            {messages.map((msg, idx) => (
              <div key={idx} className={`message ${msg.role}`}>
                <div className="message-content">
                  {/* Display formatted text if available, otherwise raw content */}
                  {msg.content ? (
                    <div className="message-formatted">
                      {msg.content.split('\n').map((line, idx) => {
                        // Parse different sections
                        if (line.includes('📌 핵심 답변')) {
                          return <div key={idx} className="answer-header">{line}</div>
                        } else if (line.includes('📊 주요 사실')) {
                          return <div key={idx} className="facts-header">{line}</div>
                        } else if (line.includes('📝 상세 설명')) {
                          return <div key={idx} className="details-header">{line}</div>
                        } else if (line.includes('📚 출처')) {
                          return <div key={idx} className="sources-header">{line}</div>
                        } else if (line.trim().startsWith('•') || line.trim().startsWith('-')) {
                          return <div key={idx} className="fact-item">{line}</div>
                        } else if (line.trim().match(/^\[\d+\]/)) {
                          // Parse source line
                          const sourceMatch = line.match(/^\[(\d+)\]\s*(.+?),\s*(\d+)페이지/)
                          if (sourceMatch && msg.sources && msg.sources[parseInt(sourceMatch[1]) - 1]) {
                            const sourceIndex = parseInt(sourceMatch[1]) - 1
                            const source = msg.sources[sourceIndex]
                            return (
                              <button
                                key={idx}
                                className="source-item-inline"
                                onClick={() => handleShowSource(source)}
                                title="클릭하여 원문 보기"
                              >
                                {line}
                              </button>
                            )
                          }
                          return <div key={idx} className="source-item">{line}</div>
                        } else if (line.trim()) {
                          return <div key={idx} className="message-line">{line}</div>
                        } else {
                          return <br key={idx} />
                        }
                      })}
                    </div>
                  ) : (
                    <div className="message-text">{msg.answer || msg.content || msg.text}</div>
                  )}
                </div>
              </div>
            ))}
            
            {isLoading && (
              <div className="message assistant">
                <div className="message-content">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                  {streamStatus && (
                    <div className="stream-status">{streamStatus}</div>
                  )}
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
          
              {/* Input */}
              <div className="input-container">
                <textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="질문을 입력하세요... (Enter로 전송, Shift+Enter로 줄바꿈)"
                  disabled={isLoading}
                  className="message-input"
                  rows={2}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={isLoading || !inputMessage.trim()}
                  className="btn-send"
                  title="Enter"
                >
                  {isLoading ? '⏳' : '전송'}
                </button>
              </div>
            </div>
          </>
        )}
        
        {/* Upload Tab */}
        {activeTab === 'upload' && (
          <div className="upload-container">
            <div className="upload-box">
              <h2>📤 문서 업로드</h2>
              <p className="upload-description">
                PDF, HWP 문서를 업로드하여 RAG 시스템에 추가할 수 있습니다.
                여러 파일을 동시에 선택할 수 있습니다.
              </p>
              
              <div className="upload-area">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.hwp"
                  onChange={handleFileUpload}
                  style={{ display: 'none' }}
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="upload-label">
                  <div className="upload-icon">📁</div>
                  <div className="upload-text">
                    클릭하여 파일 선택
                    <br />
                    <span className="upload-hint">또는 파일을 여기로 드래그</span>
                  </div>
                </label>
              </div>
              
              {uploadStatus && (
                <div className="upload-status">
                  {uploadStatus === 'uploading' && (
                    <>
                      <div className="progress-bar">
                        <div 
                          className="progress-fill"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                      <p>업로드 중... {uploadProgress}%</p>
                    </>
                  )}
                  {uploadStatus === 'processing' && <p>⏳ 문서 처리 중...</p>}
                  {uploadStatus === 'completed' && <p className="success">✅ 업로드 완료!</p>}
                  {uploadStatus === 'error' && <p className="error">❌ 업로드 실패</p>}
                </div>
              )}
              
              <div className="upload-tips">
                <h3>💡 업로드 팁</h3>
                <ul>
                  <li>✓ 지원 형식: PDF, HWP</li>
                  <li>✓ 최대 파일 크기: 100MB</li>
                  <li>✓ 한번에 여러 파일 선택 가능</li>
                  <li>✓ 한글 문서는 자동으로 텍스트 추출</li>
                </ul>
              </div>
            </div>
          </div>
        )}
        
        {/* Document Management Tab */}
        {activeTab === 'manage' && (
          <div className="manage-container">
            <div className="manage-header">
              <h2>📁 문서 관리</h2>
              <div className="manage-actions">
                <div className="manage-stats">
                  총 {documents.length}개 문서
                </div>
                {documents.length > 0 && (
                  <button
                    className="btn-delete-all"
                    onClick={handleDeleteAllDocuments}
                    title="모든 문서 삭제"
                  >
                    🗑️ 전체 삭제
                  </button>
                )}
              </div>
            </div>
            
            {documents.length === 0 ? (
              <div className="no-documents">
                <div className="no-documents-icon">📭</div>
                <p>업로드된 문서가 없습니다.</p>
                <button
                  className="btn-upload-first"
                  onClick={() => setActiveTab('upload')}
                >
                  문서 업로드하기
                </button>
              </div>
            ) : (
              <div className="document-grid">
                {documents.map(doc => (
                  <div key={doc.id || doc.filename} className="document-card">
                    <div className="doc-icon">
                      {doc.filename?.endsWith('.pdf') ? '📄' : '📑'}
                    </div>
                    <div className="doc-info">
                      <h3 className="doc-name">{doc.filename}</h3>
                      <div className="doc-meta">
                        <span>크기: {doc.size ? `${(doc.size / 1024).toFixed(1)}KB` : '알 수 없음'}</span>
                        <span>페이지: {doc.pages || '알 수 없음'}</span>
                      </div>
                      <div className="doc-status">
                        {doc.indexed ? (
                          <span className="status-indexed">✅ 인덱싱 완료</span>
                        ) : processingDoc === doc.id ? (
                          <span className="status-processing">⏳ 처리 중...</span>
                        ) : (
                          <span className="status-pending">⏸️ 대기 중</span>
                        )}
                      </div>
                    </div>
                    <div className="doc-actions">
                      <button
                        className="btn-info"
                        onClick={() => handleShowDocumentDetails(doc.filename)}
                        title="상세 정보"
                      >
                        ℹ️
                      </button>
                      {(!doc.indexed || doc.status === 'pending') && processingDoc !== doc.id && (
                        <button
                          className="btn-process"
                          onClick={() => handleProcessDocument(doc.id || doc.filename)}
                          title="문서 인덱싱"
                        >
                          ⚙️
                        </button>
                      )}
                      <button
                        className="btn-delete"
                        onClick={() => handleDeleteDocument(doc.id || doc.filename)}
                        title="삭제"
                      >
                        🗑️
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.hwp"
        onChange={handleFileUpload}
        style={{ display: 'none' }}
      />
      
      {/* Footer */}
      <footer className="app-footer">
        <div className="footer-content">
          <span>RAG Chatbot System v1.0.0 | 폐쇄망/오프라인 환경 지원</span>
          <span className="shortcuts">
            Ctrl+N: 새 대화 | Ctrl+O: 문서 업로드 | ESC: 중지/취소
          </span>
        </div>
      </footer>
      
      {/* Citation Popup */}
      {showSourcePopup && selectedSource && (
        <div className="citation-popup-overlay" onClick={handleCloseSourcePopup}>
          <div className="citation-popup" onClick={(e) => e.stopPropagation()}>
            <div className="citation-popup-header">
              <h3>📖 출처 상세 정보</h3>
              <button
                className="btn-close-popup"
                onClick={handleCloseSourcePopup}
              >
                ✖
              </button>
            </div>
            <div className="citation-popup-content">
              <div className="citation-info">
                <div className="citation-field">
                  <span className="citation-label">문서:</span>
                  <span className="citation-value">{selectedSource.doc_id || selectedSource.document}</span>
                </div>
                <div className="citation-field">
                  <span className="citation-label">페이지:</span>
                  <span className="citation-value">{selectedSource.page || '전체'}</span>
                </div>
                {selectedSource.score && (
                  <div className="citation-field">
                    <span className="citation-label">관련도:</span>
                    <span className="citation-value">{(selectedSource.score * 100).toFixed(1)}%</span>
                  </div>
                )}
              </div>
              <div className="citation-text">
                <h4>📝 원문 내용</h4>
                <div className="citation-content">
                  {selectedSource.text || selectedSource.content || '원문을 불러올 수 없습니다.'}
                </div>
              </div>
              {selectedSource.highlighted && (
                <div className="citation-highlighted">
                  <h4>✨ 강조 부분</h4>
                  <div className="citation-highlight">
                    {selectedSource.highlighted}
                  </div>
                </div>
              )}
            </div>
            <div className="citation-popup-footer">
              <button
                className="btn-close"
                onClick={handleCloseSourcePopup}
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
      
      {/* Document Details Popup */}
      {showDocDetails && docDetails && (
        <div className="doc-details-overlay" onClick={handleCloseDocDetails}>
          <div className="doc-details-popup" onClick={(e) => e.stopPropagation()}>
            <div className="doc-details-header">
              <h3>📄 문서 상세 정보</h3>
              <button
                className="btn-close-popup"
                onClick={handleCloseDocDetails}
              >
                ✖
              </button>
            </div>
            <div className="doc-details-content">
              <div className="doc-details-info">
                <h4>기본 정보</h4>
                <div className="detail-field">
                  <span className="detail-label">파일명:</span>
                  <span className="detail-value">{docDetails.filename}</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">문서 ID:</span>
                  <span className="detail-value">{docDetails.doc_id}</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">크기:</span>
                  <span className="detail-value">{(docDetails.size / 1024).toFixed(1)} KB</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">청크 수:</span>
                  <span className="detail-value">{docDetails.chunks_count}개</span>
                </div>
                <div className="detail-field">
                  <span className="detail-label">인덱싱 상태:</span>
                  <span className="detail-value">
                    {docDetails.has_index ? '✅ 인덱싱 완료' : '⏸️ 대기 중'}
                  </span>
                </div>
              </div>
              
              {docDetails.directives && docDetails.directives.length > 0 && (
                <div className="doc-details-directives">
                  <h4>📌 지시사항</h4>
                  <div className="directives-list">
                    {docDetails.directives.map((dir, idx) => (
                      <div key={idx} className="directive-item">
                        <div className="directive-title">{dir.제목}</div>
                        <div className="directive-dept">부서: {dir.부서 ? dir.부서.join(', ') : '전체'}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {docDetails.chunks && docDetails.chunks.length > 0 && (
                <div className="doc-details-chunks">
                  <h4>📦 청크 목록 ({docDetails.chunks.length}개)</h4>
                  <div className="chunks-list">
                    {docDetails.chunks.slice(0, 10).map((chunk, idx) => (
                      <div key={idx} className="chunk-item">
                        <div className="chunk-header">
                          <span className="chunk-id">Chunk {idx + 1}</span>
                          <span className="chunk-page">Page {chunk.page}</span>
                          <span className="chunk-type">{chunk.type}</span>
                        </div>
                        <div className="chunk-text">{chunk.text}</div>
                      </div>
                    ))}
                    {docDetails.chunks.length > 10 && (
                      <div className="chunks-more">
                        ... 그리고 {docDetails.chunks.length - 10}개 더
                      </div>
                    )}
                  </div>
                </div>
              )}
              
              {docDetails.processed_text && (
                <div className="doc-details-text">
                  <h4>📝 처리된 텍스트</h4>
                  <div className="processed-text">
                    {docDetails.processed_text}
                  </div>
                </div>
              )}
            </div>
            <div className="doc-details-footer">
              <button
                className="btn-close"
                onClick={handleCloseDocDetails}
              >
                닫기
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default AppSession

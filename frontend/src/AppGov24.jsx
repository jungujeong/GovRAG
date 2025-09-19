import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './styles/Gov24Design.css'
import DocumentDetailsPopup from './components/DocumentDetailsPopup'
import CitationPopup from './components/CitationPopup'
import { chatAPI } from './services/chatAPI'

// Configure axios defaults
axios.defaults.baseURL = 'http://localhost:8000'

function AppGov24() {
  // Tab state (업로드 탭 제거, 채팅과 문서 관리만 유지)
  const [activeTab, setActiveTab] = useState('chat')

  // Chat state
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [editingSessionId, setEditingSessionId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [abortController, setAbortController] = useState(null)
  const [wasInterrupted, setWasInterrupted] = useState(false)
  const [handledRefreshInterrupt, setHandledRefreshInterrupt] = useState(false)
  const [streamStatus, setStreamStatus] = useState('')
  const [deviceId, setDeviceId] = useState(null)

  // Document state
  const [documents, setDocuments] = useState([])
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStatus, setUploadStatus] = useState('')
  const [processingDoc, setProcessingDoc] = useState(null)
  const [isUploading, setIsUploading] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState([])
  const [totalFilesToUpload, setTotalFilesToUpload] = useState(0)

  // System state
  const [systemStatus, setSystemStatus] = useState({ status: 'checking' })
  const [error, setError] = useState(null)

  // Citation popup state
  const [showSourcePopup, setShowSourcePopup] = useState(false)
  const [selectedSource, setSelectedSource] = useState(null)

  // Document details state
  const [showDocDetails, setShowDocDetails] = useState(false)
  const [docDetails, setDocDetails] = useState(null)

  // Refs
  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)

  // 예시 질문 데이터
  const exampleQuestions = [
    "문서에서 가장 중요한 정책은 무엇인가요?",
    "관련 법령이나 규정에 대해 알려주세요",
    "신청 절차나 방법을 설명해주세요",
    "필요한 서류나 준비물이 있나요?",
    "담당 부서나 연락처 정보가 있나요?",
    "관련된 지원 사업이나 혜택이 있나요?"
  ]

  // Initialize
  useEffect(() => {
    const init = async () => {
      await checkHealth()
      await loadDocuments()
      await loadSessionsWithDeviceId()
    }
    init()
  }, [])

  // 새로고침으로 인한 중단 표시 처리
  useEffect(() => {
    const wasLoading = sessionStorage.getItem('wasLoadingBeforeUnload') === 'true'
    const interruptedId = sessionStorage.getItem('interruptedSessionId')
    if (!handledRefreshInterrupt && wasLoading && interruptedId && currentSessionId && currentSessionId === interruptedId) {
      const alreadyNotified = messages.some((m) =>
        m?.metadata?.interrupted === true ||
        m?.metadata?.reason === 'client_disconnect' ||
        m?.metadata?.cause === 'page_refresh' ||
        (typeof m?.content === 'string' && m.content.includes('답변 생성이 중단되었습니다'))
      )
      if (!alreadyNotified) {
        const interruptedMessage = {
          role: 'assistant',
          content: '새로고침으로 인해 답변이 중단되었습니다.',
          timestamp: new Date().toISOString(),
          interrupted: true,
          metadata: { interrupted: true, cause: 'page_refresh' }
        }
        setMessages((prev) => [...prev, interruptedMessage])
      }
      setHandledRefreshInterrupt(true)
      sessionStorage.removeItem('wasLoadingBeforeUnload')
      sessionStorage.removeItem('interruptedSessionId')
    }
  }, [currentSessionId, messages, handledRefreshInterrupt])

  // Handle page refresh/unload
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isLoading && currentSessionId) {
        sessionStorage.setItem('wasLoadingBeforeUnload', 'true')
        sessionStorage.setItem('interruptedSessionId', currentSessionId)
        if (abortController) {
          abortController.abort()
        }
        try {
          if (navigator.sendBeacon) {
            const url = `/api/chat/sessions/${currentSessionId}/interrupt`
            const data = new Blob([JSON.stringify({ reason: 'page_refresh' })], { type: 'application/json' })
            navigator.sendBeacon(url, data)
          }
        } catch (_) {
          // ignore
        }
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload)
      if (abortController) {
        abortController.abort()
      }
    }
  }, [isLoading, abortController, currentSessionId])

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
      const docs = response.data || []

      const docsWithDetails = await Promise.all(
        docs.map(async (doc) => {
          try {
            const detailResponse = await axios.get(`/api/documents/${doc.filename}/details`)
            const hasChunks = (detailResponse.data.stats?.whoosh_chunks > 0 ||
                             detailResponse.data.stats?.chroma_chunks > 0)
            const hasIndex = detailResponse.data.has_index === true

            return {
              ...doc,
              indexed: hasChunks || hasIndex || detailResponse.data.stats?.status === 'indexed',
              status: detailResponse.data.stats?.status || (hasChunks ? 'indexed' : 'pending'),
              chunks: detailResponse.data.stats?.whoosh_chunks || 0
            }
          } catch (error) {
            return {
              ...doc,
              indexed: false,
              status: 'pending',
              chunks: 0
            }
          }
        })
      )

      setDocuments(docsWithDetails)
      return docsWithDetails
    } catch (error) {
      console.error('Failed to load documents:', error)
      return []
    }
  }

  // 디바이스별 고유 ID 생성 또는 가져오기
  const getOrCreateDeviceId = () => {
    let id = localStorage.getItem('deviceId')
    if (!id) {
      const userAgent = navigator.userAgent
      const screenResolution = `${screen.width}x${screen.height}`
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
      const language = navigator.language

      const hashString = `${userAgent}-${screenResolution}-${timezone}-${language}`
      id = btoa(hashString).replace(/[^a-zA-Z0-9]/g, '').substring(0, 32)

      localStorage.setItem('deviceId', id)
    }
    return id
  }

  const loadSessionsWithDeviceId = async () => {
    try {
      const deviceId = getOrCreateDeviceId()
      setDeviceId(deviceId)

      const response = await axios.get('/api/chat/sessions', {
        params: { device_id: deviceId }
      })

      setSessions(response.data.sessions || [])

      const lastSessionId = localStorage.getItem('lastSessionId')
      if (lastSessionId && response.data.sessions.some(s => s.id === lastSessionId)) {
        setCurrentSessionId(lastSessionId)
        await loadSessionMessages(lastSessionId)
      } else if (response.data.sessions.length > 0) {
        const firstSession = response.data.sessions[0]
        setCurrentSessionId(firstSession.id)
        localStorage.setItem('lastSessionId', firstSession.id)
        await loadSessionMessages(firstSession.id)
      } else {
        await createNewSessionWithDeviceId()
      }
    } catch (error) {
      console.error('Failed to load sessions:', error)
    }
  }

  const createNewSessionWithDeviceId = async () => {
    try {
      setWasInterrupted(false)
      sessionStorage.removeItem('wasLoadingBeforeUnload')
      sessionStorage.removeItem('interruptedSessionId')

      const documentIds = documents.length > 0
        ? documents.map(d => (d.id ? d.id : (d.filename ? d.filename.replace(/\.[^.]+$/, '') : ''))).filter(Boolean)
        : []

      const deviceId = getOrCreateDeviceId()

      const response = await axios.post('/api/chat/sessions', {
        title: '새 대화',
        document_ids: documentIds,
        metadata: { device_id: deviceId }
      })

      const newSession = response.data.session
      setSessions(prev => [newSession, ...prev])
      setCurrentSessionId(newSession.id)
      localStorage.setItem('lastSessionId', newSession.id)
      setMessages([])
      setInputMessage('')

      setActiveTab('chat')

      return newSession
    } catch (error) {
      console.error('Failed to create session:', error)
      setError('새 대화를 시작할 수 없습니다.')
    }
  }

  const selectSession = async (sessionId) => {
    if (sessionId === currentSessionId) return

    if (isLoading) {
      setError('답변을 받는 중에는 다른 채팅방으로 이동할 수 없습니다.')
      setTimeout(() => setError(null), 3000)
      return
    }

    setCurrentSessionId(sessionId)
    localStorage.setItem('lastSessionId', sessionId)
    await loadSessionMessages(sessionId)
  }

  const loadSessionMessages = async (sessionId) => {
    try {
      const response = await axios.get(`/api/chat/sessions/${sessionId}`)
      const messages = response.data.session.messages || []

      const filteredMessages = messages.filter(msg => {
        if (msg.interrupted && msg.content === '답변 생성이 중단되었습니다.') {
          return false
        }
        return true
      })

      setMessages(filteredMessages)
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
          await createNewSessionWithDeviceId()
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

    let sessionId = currentSessionId
    if (!sessionId) {
      const newSession = await createNewSessionWithDeviceId()
      if (!newSession) {
        setError('새 대화를 시작할 수 없습니다.')
        return
      }
      sessionId = newSession.id
    }

    const skipDocumentCheck = documents.length === 0

    const currentSession = sessions.find(s => s.id === sessionId)
    if (!skipDocumentCheck && (!currentSession?.document_ids || currentSession.document_ids.length === 0)) {
      if (documents.length > 0) {
        try {
          const documentIds = documents.map(d => (d.id ? d.id : (d.filename ? d.filename.replace(/\.[^.]+$/, '') : ''))).filter(Boolean)
          await axios.put(`/api/chat/sessions/${sessionId}`, {
            document_ids: documentIds
          })
          setSessions(prev => prev.map(s =>
            s.id === sessionId ? { ...s, document_ids: documentIds } : s
          ))
        } catch (error) {
          console.error('Failed to update session documents:', error)
        }
      }
    }

    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    }
    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsLoading(true)
    setError(null)
    setWasInterrupted(false)

    const controller = new AbortController()
    setAbortController(controller)

    try {
      const placeholder = {
        role: 'assistant',
        content: '',
        sources: [],
        streaming: true,
        timestamp: new Date().toISOString()
      }
      setMessages(prev => [...prev, placeholder])
      setStreamStatus('답변 준비 중...')

      const finalResponse = await chatAPI.streamMessage(
        sessionId,
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

      if (finalResponse.metadata?.title_updated && finalResponse.metadata?.new_title) {
        setSessions(prev => prev.map(s =>
          s.id === sessionId ? { ...s, title: finalResponse.metadata.new_title } : s
        ))
      }
    } catch (error) {
      if (axios.isCancel(error)) {
        console.log('Request was cancelled')
      } else {
        console.error('Failed to send/stream message:', error)

        let errorContent = '메시지 처리 중 오류가 발생했습니다.'
        if (error.message?.includes('Network') || error.code === 'ERR_NETWORK') {
          errorContent = '네트워크 오류로 응답이 중단되었습니다. 연결을 확인해 주세요.'
        } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
          errorContent = '응답이 지연되어 시간 초과되었습니다. 다시 시도해 주세요.'
        }
        if (error.response?.data?.detail) {
          errorContent = error.response.data.detail
        } else if (error.response?.status === 400) {
          errorContent = '먼저 문서를 업로드해 주세요.'
        }

        const errorMessage = {
          role: 'assistant',
          content: errorContent,
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
      }
    } finally {
      setIsLoading(false)
      setAbortController(null)
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
      const response = await axios.get(`/api/documents/detail/${docId}`)
      setDocDetails(response.data)
      setShowDocDetails(true)
    } catch (error) {
      console.error('Failed to load document details:', error)
      setError('문서 상세 정보를 불러올 수 없습니다.')
    }
  }

  const handleCloseDocDetails = () => {
    setShowDocDetails(false)
    setDocDetails(null)
  }

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files)
    if (files.length === 0) return

    setIsUploading(true)
    setTotalFilesToUpload(files.length)
    setUploadedFiles([])

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
        setUploadedFiles(response.data.uploaded)
        setUploadStatus('processing')

        for (let i = 0; i < response.data.uploaded.length; i++) {
          const filename = response.data.uploaded[i]
          setUploadStatus(`processing_file_${i + 1}_of_${response.data.uploaded.length}`)

          await new Promise(resolve => setTimeout(resolve, 500))
        }

        const updatedDocuments = await loadDocuments()

        if (currentSessionId && updatedDocuments.length > 0) {
          try {
            const documentIds = updatedDocuments.map(d => (d.id ? d.id : (d.filename ? d.filename.replace(/\.[^.]+$/, '') : ''))).filter(Boolean)
            await axios.put(`/api/chat/sessions/${currentSessionId}`, {
              document_ids: documentIds
            })

            setSessions(prev => prev.map(session =>
              session.id === currentSessionId
                ? { ...session, document_ids: documentIds }
                : session
            ))
          } catch (error) {
            console.error('Failed to update session with documents:', error)
          }
        }

        setUploadStatus('completed')
        setTimeout(() => {
          setUploadStatus('')
          setUploadProgress(0)
          setIsUploading(false)
          setTotalFilesToUpload(0)
          setUploadedFiles([])
        }, 2000)
      }
    } catch (error) {
      console.error('Upload failed:', error)
      setUploadStatus('error')
      setError('파일 업로드에 실패했습니다.')
      setTimeout(() => {
        setUploadStatus('')
        setUploadProgress(0)
        setIsUploading(false)
        setTotalFilesToUpload(0)
        setUploadedFiles([])
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
      await axios.post('/api/documents/process', null, {
        params: { filename: docId }
      })
      setTimeout(async () => {
        await loadDocuments()
      }, 1000)
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

  const handleExampleQuestionClick = (question) => {
    setInputMessage(question)
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault()
        createNewSessionWithDeviceId()
      }
      if ((e.ctrlKey || e.metaKey) && e.key === 'o') {
        e.preventDefault()
        fileInputRef.current?.click()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  return (
    <div className="gov24-app">
      {/* Header */}
      <header className="gov24-header">
        <div className="gov24-header-content">
          <div className="gov24-logo">
            <div className="gov24-logo-icon">📋</div>
            <div className="gov24-logo-text">정부문서 AI</div>
          </div>
          <nav className="gov24-nav">
            <button
              className={`gov24-nav-link ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => !isUploading && !isLoading && setActiveTab('chat')}
              disabled={isUploading || isLoading}
              aria-label="채팅 화면"
            >
              채팅
            </button>
            <button
              className={`gov24-nav-link ${activeTab === 'manage' ? 'active' : ''}`}
              onClick={() => !isUploading && !isLoading && setActiveTab('manage')}
              disabled={isUploading || isLoading}
              aria-label="문서 관리"
            >
              문서 관리
            </button>
          </nav>
          <button
            className="gov24-new-chat-button"
            onClick={createNewSessionWithDeviceId}
            disabled={isUploading || isLoading}
            aria-label="새 대화 시작"
          >
            새 대화
          </button>
        </div>
      </header>

      {/* Error Banner */}
      {error && (
        <div className="gov24-error-banner">
          <span>{error}</span>
          <button onClick={() => setError(null)} aria-label="오류 메시지 닫기">×</button>
        </div>
      )}

      <main className="gov24-main">
        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="gov24-chat-layout">
            {/* Sidebar */}
            <aside className="gov24-sidebar">
              <div className="gov24-sidebar-header">
                <h2 className="gov24-sidebar-title">대화 목록</h2>
                <button
                  className="gov24-new-session-button"
                  onClick={createNewSessionWithDeviceId}
                  disabled={isUploading || isLoading}
                  aria-label="새 대화 추가"
                >
                  + 새 대화
                </button>
              </div>

              <div className="gov24-session-list">
                {sessions.map(session => (
                  <div
                    key={session.id}
                    className={`gov24-session-item ${session.id === currentSessionId ? 'active' : ''} ${isUploading ? 'disabled' : ''}`}
                    onClick={() => !isUploading && selectSession(session.id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        if (!isUploading) selectSession(session.id)
                      }
                    }}
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
                        className="gov24-session-input"
                        aria-label="대화 제목 수정"
                      />
                    ) : (
                      <div
                        className="gov24-session-title"
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
                        className="gov24-session-delete"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (!isLoading) {
                            deleteSession(session.id)
                          }
                        }}
                        disabled={isLoading}
                        aria-label="대화 삭제"
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>

              <div className="gov24-sidebar-footer">
                <div className="gov24-doc-status">
                  <span className="gov24-doc-count">문서 {documents.length}개</span>
                  <span className="gov24-doc-indexed">
                    인덱싱 완료 {documents.filter(d => d.indexed).length}개
                  </span>
                </div>
              </div>
            </aside>

            {/* Content */}
            <div className="gov24-content">
              <div className="gov24-messages" role="log" aria-live="polite" aria-label="대화 내역">
                {/* Empty State with Example Questions */}
                {messages.length === 0 && (
                  <div className="gov24-welcome">
                    <div className="gov24-welcome-header">
                      <h2 className="gov24-welcome-title">정부문서 AI에 오신 것을 환영합니다</h2>
                      <p className="gov24-welcome-text">
                        {documents.length > 0
                          ? "업로드된 문서를 바탕으로 질문해보세요"
                          : "문서를 업로드하고 질문을 시작하세요"
                        }
                      </p>
                    </div>

                    {documents.length === 0 && (
                      <div className="gov24-upload-prompt">
                        <button
                          className="gov24-upload-button"
                          onClick={() => fileInputRef.current?.click()}
                          aria-label="문서 업로드"
                        >
                          📄 문서 업로드하기
                        </button>
                      </div>
                    )}

                    {documents.length > 0 && (
                      <div className="gov24-example-questions">
                        <h3 className="gov24-example-title">예시 질문</h3>
                        <div className="gov24-example-grid">
                          {exampleQuestions.map((question, index) => (
                            <button
                              key={index}
                              className="gov24-example-question"
                              onClick={() => handleExampleQuestionClick(question)}
                              disabled={isLoading}
                              aria-label={`예시 질문: ${question}`}
                            >
                              {question}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Messages */}
                {messages.map((msg, idx) => (
                  <div key={idx} className={`gov24-message ${msg.role} ${msg.error ? 'error' : ''}`}>
                    <div className="gov24-message-content">
                      {msg.content && (
                        <div className="gov24-message-text">
                          <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                              p: ({children}) => {
                                const text = typeof children === 'string' ? children : ''
                                if (text.includes('핵심 답변')) {
                                  return <h3 className="gov24-answer-header">{text.replace(/[📌]/g, '')}</h3>
                                } else if (text.includes('주요 사실')) {
                                  return <h4 className="gov24-facts-header">{text.replace(/[📊]/g, '')}</h4>
                                } else if (text.includes('상세 설명')) {
                                  return <h4 className="gov24-details-header">{text.replace(/[📝]/g, '')}</h4>
                                } else if (text.includes('출처')) {
                                  const hasSources = Array.isArray(msg.sources) && msg.sources.length > 0
                                  if (hasSources) return null
                                  return <h4 className="gov24-sources-header">{text.replace(/[📚]/g, '')}</h4>
                                }
                                return <p className="gov24-paragraph">{children}</p>
                              },
                              strong: ({children}) => <strong className="gov24-bold">{children}</strong>,
                              em: ({children}) => <em className="gov24-italic">{children}</em>,
                              ul: ({children}) => <ul className="gov24-list">{children}</ul>,
                              ol: ({children}) => <ol className="gov24-ordered-list">{children}</ol>,
                              li: ({children}) => <li className="gov24-fact-item">{children}</li>,
                              h1: ({children}) => <h3 className="gov24-heading">{children}</h3>,
                              h2: ({children}) => <h3 className="gov24-heading">{children}</h3>,
                              h3: ({children}) => <h3 className="gov24-heading">{children}</h3>,
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>
                        </div>
                      )}

                      {/* Streaming indicator */}
                      {msg.role === 'assistant' && msg.streaming && (
                        <div className="gov24-streaming-indicator">
                          <div className="gov24-loading-dots">
                            <span></span><span></span><span></span>
                          </div>
                          <span className="gov24-streaming-text">{streamStatus || '답변 생성 중...'}</span>
                        </div>
                      )}

                      {/* Sources */}
                      {msg.sources && msg.sources.length > 0 && (() => {
                        const keyOf = (s) => `${s.doc_id || s.document || ''}-${s.page || ''}-${s.start || s.start_char || ''}-${s.end || s.end_char || ''}`
                        const uniqueSources = Array.from(new Map((msg.sources || []).map(s => [keyOf(s), s])).values())
                        return (
                          <div className="gov24-sources-section">
                            <h4 className="gov24-sources-title">📚 참고 문서</h4>
                            <div className="gov24-sources-list">
                              {uniqueSources.map((source, sourceIdx) => (
                                <button
                                  key={sourceIdx}
                                  className="gov24-source-button"
                                  onClick={() => handleShowSource(source)}
                                  aria-label={`출처 보기: ${source.doc_id || source.document}`}
                                >
                                  <span className="gov24-source-number">{sourceIdx + 1}</span>
                                  <span className="gov24-source-title">
                                    {source.doc_id || source.document}
                                    {source.page && ` (${source.page}쪽)`}
                                  </span>
                                </button>
                              ))}
                            </div>
                          </div>
                        )
                      })()}

                      {/* Message timestamp */}
                      <div className="gov24-message-time">
                        {new Date(msg.timestamp).toLocaleTimeString('ko-KR', {
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                    </div>
                  </div>
                ))}

                {/* Loading indicator when no streaming message */}
                {(() => {
                  const hasStreamingAssistant = messages.some(m => m.role === 'assistant' && m.streaming)
                  return isLoading && !hasStreamingAssistant
                })() && (
                  <div className="gov24-message assistant">
                    <div className="gov24-loading-indicator">
                      <div className="gov24-loading-dots">
                        <span></span><span></span><span></span>
                      </div>
                      <span className="gov24-loading-text">답변을 준비하고 있습니다...</span>
                      <button
                        className="gov24-cancel-button"
                        onClick={async () => {
                          try {
                            if (abortController) {
                              abortController.abort()
                              setWasInterrupted(true)
                              setIsLoading(false)
                              setAbortController(null)
                              setStreamStatus('')

                              const interruptedMessage = {
                                role: 'assistant',
                                content: '답변 생성이 중단되었습니다.',
                                timestamp: new Date().toISOString(),
                                interrupted: true,
                                metadata: { interrupted: true, cause: 'user_action' }
                              }
                              setMessages(prev => [...prev, interruptedMessage])
                            }
                          } catch (error) {
                            console.error('Error aborting request:', error)
                          }
                        }}
                        aria-label="답변 생성 중단"
                      >
                        답변 중단
                      </button>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {/* Input Area */}
              <div className="gov24-input-area">
                {/* File Upload Integration */}
                <div className="gov24-input-actions">
                  <button
                    className="gov24-file-upload-button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isLoading || isUploading}
                    aria-label="파일 업로드"
                    title="PDF 또는 HWP 문서 업로드"
                  >
                    📎
                  </button>
                </div>

                <div className="gov24-input-container">
                  <textarea
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder="궁금한 내용을 질문해주세요..."
                    disabled={isLoading}
                    className="gov24-input"
                    rows={3}
                    aria-label="질문 입력"
                  />
                  <button
                    onClick={handleSendMessage}
                    disabled={isLoading || !inputMessage.trim()}
                    className="gov24-send-button"
                    aria-label="질문 전송"
                  >
                    {isLoading ? '전송 중...' : '전송'}
                  </button>
                </div>

                {/* Upload Progress */}
                {isUploading && (
                  <div className="gov24-upload-progress">
                    <div className="gov24-progress-bar">
                      <div
                        className="gov24-progress-fill"
                        style={{ width: `${uploadProgress}%` }}
                      />
                    </div>
                    <span className="gov24-progress-text">
                      {uploadStatus === 'uploading' && `업로드 중... ${uploadProgress}%`}
                      {uploadStatus === 'processing' && '문서 처리 중...'}
                      {uploadStatus === 'completed' && '업로드 완료!'}
                      {uploadStatus === 'error' && '업로드 실패'}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Document Management Tab */}
        {activeTab === 'manage' && (
          <div className="gov24-manage-container">
            <div className="gov24-manage-header">
              <h2 className="gov24-manage-title">문서 관리</h2>
              <div className="gov24-manage-actions">
                <button
                  className="gov24-upload-docs-button"
                  onClick={() => fileInputRef.current?.click()}
                  aria-label="새 문서 업로드"
                >
                  📄 문서 업로드
                </button>
                {documents.length > 0 && (
                  <button
                    className="gov24-delete-all-button"
                    onClick={handleDeleteAllDocuments}
                    aria-label="모든 문서 삭제"
                  >
                    전체 삭제
                  </button>
                )}
              </div>
            </div>

            {documents.length === 0 ? (
              <div className="gov24-no-documents">
                <div className="gov24-no-docs-icon">📁</div>
                <h3 className="gov24-no-docs-title">업로드된 문서가 없습니다</h3>
                <p className="gov24-no-docs-text">
                  PDF 또는 HWP 문서를 업로드하여 AI와 대화를 시작하세요
                </p>
                <button
                  className="gov24-upload-first-button"
                  onClick={() => fileInputRef.current?.click()}
                  aria-label="첫 번째 문서 업로드"
                >
                  📄 첫 문서 업로드하기
                </button>
              </div>
            ) : (
              <div className="gov24-document-grid">
                {documents.map(doc => (
                  <div key={doc.id || doc.filename} className="gov24-document-card">
                    <div className="gov24-doc-icon">
                      {doc.filename.endsWith('.pdf') ? '📄' : '📝'}
                    </div>
                    <h3 className="gov24-doc-name" title={doc.filename}>
                      {doc.filename}
                    </h3>
                    <div className="gov24-doc-meta">
                      <span className="gov24-doc-size">
                        {doc.size ? `${(doc.size / 1024).toFixed(1)}KB` : '크기 정보 없음'}
                      </span>
                      <span className="gov24-doc-pages">
                        {doc.pages || 0} 페이지
                      </span>
                    </div>
                    <div className="gov24-doc-status">
                      {doc.indexed ? (
                        <span className="gov24-status-indexed">✅ 인덱싱 완료</span>
                      ) : processingDoc === doc.id ? (
                        <span className="gov24-status-processing">⏳ 처리 중</span>
                      ) : (
                        <span className="gov24-status-pending">⏱️ 대기 중</span>
                      )}
                      {doc.chunks > 0 && (
                        <span className="gov24-chunk-count">{doc.chunks}개 청크</span>
                      )}
                    </div>
                    <div className="gov24-doc-actions">
                      <button
                        className="gov24-doc-button gov24-doc-detail"
                        onClick={() => handleShowDocumentDetails(doc.filename)}
                        aria-label={`${doc.filename} 상세 정보 보기`}
                      >
                        상세 정보
                      </button>
                      {(!doc.indexed || doc.status === 'pending') && processingDoc !== doc.id && (
                        <button
                          className="gov24-doc-button gov24-doc-process"
                          onClick={() => handleProcessDocument(doc.id || doc.filename)}
                          aria-label={`${doc.filename} 처리하기`}
                        >
                          처리하기
                        </button>
                      )}
                      <button
                        className="gov24-doc-button gov24-doc-delete"
                        onClick={() => handleDeleteDocument(doc.id || doc.filename)}
                        aria-label={`${doc.filename} 삭제`}
                      >
                        삭제
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.hwp"
        onChange={handleFileUpload}
        style={{ display: 'none' }}
        aria-label="파일 선택"
      />

      {/* Citation Popup */}
      {showSourcePopup && selectedSource && (
        <CitationPopup
          citation={selectedSource}
          onClose={handleCloseSourcePopup}
        />
      )}

      {/* Document Details Popup */}
      {showDocDetails && (
        <DocumentDetailsPopup
          docDetails={docDetails}
          onClose={handleCloseDocDetails}
        />
      )}
    </div>
  )
}

export default AppGov24
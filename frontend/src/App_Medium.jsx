import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import axios from 'axios'
import { chatAPI } from './services/chatAPI'
import './styles/MediumStyle.css'

// Constants
const MAX_MESSAGE_LENGTH = 5000
const MAX_FILE_SIZE = 50 * 1024 * 1024 // 50MB
const API_TIMEOUT = 30000 // 30 seconds
const AUTO_SAVE_INTERVAL = 30000 // 30 seconds
const SESSION_STORAGE_KEY = 'rag_session_state'
const LOCAL_STORAGE_BACKUP_KEY = 'rag_session_backup'

// Keyboard shortcuts
const KEYBOARD_SHORTCUTS = {
  'Ctrl+Enter': 'Send message',
  'Ctrl+N': 'New session',
  'Ctrl+S': 'Save session',
  'Ctrl+D': 'Toggle dark mode',
  'Ctrl+/': 'Show shortcuts',
  'Ctrl+F': 'Search in chat',
  'Ctrl+E': 'Export chat',
  'Escape': 'Close modal',
  '?': 'Show shortcuts (when focused)'
}

function App_Medium() {
  // State management
  const [activeTab, setActiveTab] = useState('chat')
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputMessage, setInputMessage] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [documents, setDocuments] = useState([])
  const [uploadProgress, setUploadProgress] = useState(0)
  const [uploadStatus, setUploadStatus] = useState('')
  const [uploadingFiles, setUploadingFiles] = useState([])
  const [systemStatus, setSystemStatus] = useState({ status: 'checking' })
  const [showSourcePopup, setShowSourcePopup] = useState(false)
  const [selectedSource, setSelectedSource] = useState(null)
  const [editingSessionId, setEditingSessionId] = useState(null)
  const [editTitle, setEditTitle] = useState('')
  const [showDocumentDetails, setShowDocumentDetails] = useState(false)
  const [selectedDocument, setSelectedDocument] = useState(null)
  const [darkMode, setDarkMode] = useState(false)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState([])
  const [showSearch, setShowSearch] = useState(false)
  const [networkStatus, setNetworkStatus] = useState('online')
  const [retryQueue, setRetryQueue] = useState([])
  const [typingIndicator, setTypingIndicator] = useState(false)
  const [messageCharCount, setMessageCharCount] = useState(0)
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [editingMessageId, setEditingMessageId] = useState(null)
  const [editingMessageContent, setEditingMessageContent] = useState('')
  const [showNewMessageIndicator, setShowNewMessageIndicator] = useState(false)
  const [isAtBottom, setIsAtBottom] = useState(true)
  const [pinnedMessages, setPinnedMessages] = useState(new Set())
  const [messageRatings, setMessageRatings] = useState({})
  const [sessionSearchQuery, setSessionSearchQuery] = useState('')
  const [documentSearchQuery, setDocumentSearchQuery] = useState('')
  const [documentTags, setDocumentTags] = useState({})
  const [showStatsDashboard, setShowStatsDashboard] = useState(false)
  const [debugMode, setDebugMode] = useState(false)
  const [showConsoleLog, setShowConsoleLog] = useState(false)
  const [consoleMessages, setConsoleMessages] = useState([])
  const [showApiInspector, setShowApiInspector] = useState(false)
  const [apiRequests, setApiRequests] = useState([])
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [showSessionSwitchWarning, setShowSessionSwitchWarning] = useState(false)
  const [pendingSessionSwitch, setPendingSessionSwitch] = useState(null)
  const [voiceInputSupported, setVoiceInputSupported] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [modelThinkingTime, setModelThinkingTime] = useState(null)
  const [performanceMetrics, setPerformanceMetrics] = useState({})
  const [systemHealth, setSystemHealth] = useState({})

  // Refs
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)
  const fileInputRef = useRef(null)
  const abortControllerRef = useRef(null)
  const autoSaveIntervalRef = useRef(null)
  const recognitionRef = useRef(null)
  const dragCounterRef = useRef(0)

  // Initialize
  useEffect(() => {
    // Check voice input support
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      setVoiceInputSupported(true)
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
      recognitionRef.current = new SpeechRecognition()
      recognitionRef.current.lang = 'ko-KR'
      recognitionRef.current.continuous = false
      recognitionRef.current.interimResults = false
      
      recognitionRef.current.onresult = (event) => {
        const transcript = event.results[0][0].transcript
        setInputMessage(prev => prev + ' ' + transcript)
        setIsRecording(false)
      }
      
      recognitionRef.current.onerror = () => {
        setIsRecording(false)
      }
    }

    // Load dark mode preference
    const savedDarkMode = localStorage.getItem('darkMode') === 'true'
    setDarkMode(savedDarkMode)
    if (savedDarkMode) {
      document.body.classList.add('dark-mode')
    }

    // Network status monitoring
    const handleOnline = () => {
      setNetworkStatus('online')
      processRetryQueue()
    }
    const handleOffline = () => setNetworkStatus('offline')
    
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    // Check for interrupted responses
    const pendingResponse = sessionStorage.getItem('pendingResponse')
    if (pendingResponse) {
      const pending = JSON.parse(pendingResponse)
      setMessages(prev => [...prev, {
        id: `interrupted-${Date.now()}`,
        role: 'system',
        content: '답변이 중단되었습니다.',
        timestamp: new Date().toISOString()
      }])
      sessionStorage.removeItem('pendingResponse')
    }

    // Keyboard shortcuts
    const handleKeyboard = (e) => {
      if (e.ctrlKey || e.metaKey) {
        switch(e.key) {
          case 'n':
            e.preventDefault()
            createNewSession()
            break
          case 's':
            e.preventDefault()
            saveSessionToLocal()
            break
          case 'd':
            e.preventDefault()
            toggleDarkMode()
            break
          case '/':
            e.preventDefault()
            setShowShortcuts(true)
            break
          case 'f':
            e.preventDefault()
            setShowSearch(true)
            break
          case 'e':
            e.preventDefault()
            setShowExportMenu(true)
            break
        }
      } else if (e.key === '?' && !e.target.matches('input, textarea')) {
        setShowShortcuts(true)
      } else if (e.key === 'Escape') {
        setShowShortcuts(false)
        setShowSearch(false)
        setShowExportMenu(false)
        setShowSourcePopup(false)
        setShowDocumentDetails(false)
        setShowUploadModal(false)
        setShowSessionSwitchWarning(false)
      }
    }

    document.addEventListener('keydown', handleKeyboard)

    // Before unload handler
    const handleBeforeUnload = (e) => {
      if (isLoading) {
        sessionStorage.setItem('pendingResponse', JSON.stringify({
          sessionId: currentSessionId,
          timestamp: Date.now()
        }))
        e.preventDefault()
        e.returnValue = ''
      }
    }
    
    window.addEventListener('beforeunload', handleBeforeUnload)

    checkHealth()
    loadDocuments()
    loadSessions()
    recoverFromCrash()

    // Auto-save interval
    autoSaveIntervalRef.current = setInterval(() => {
      saveSessionToLocal()
    }, AUTO_SAVE_INTERVAL)

    // Debug mode console capture
    if (debugMode) {
      const originalLog = console.log
      const originalError = console.error
      const originalWarn = console.warn
      
      console.log = (...args) => {
        originalLog(...args)
        addConsoleMessage('log', args)
      }
      console.error = (...args) => {
        originalError(...args)
        addConsoleMessage('error', args)
      }
      console.warn = (...args) => {
        originalWarn(...args)
        addConsoleMessage('warn', args)
      }
    }

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
      document.removeEventListener('keydown', handleKeyboard)
      window.removeEventListener('beforeunload', handleBeforeUnload)
      if (autoSaveIntervalRef.current) {
        clearInterval(autoSaveIntervalRef.current)
      }
    }
  }, [currentSessionId, isLoading, debugMode])

  // Monitor scroll position
  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container) return

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container
      const atBottom = scrollHeight - scrollTop - clientHeight < 100
      setIsAtBottom(atBottom)
      
      if (atBottom) {
        setShowNewMessageIndicator(false)
      }
    }

    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  // Auto scroll to bottom
  useEffect(() => {
    if (isAtBottom) {
      scrollToBottom()
    } else if (messages.length > 0) {
      setShowNewMessageIndicator(true)
    }
  }, [messages, isAtBottom])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const toggleDarkMode = () => {
    const newDarkMode = !darkMode
    setDarkMode(newDarkMode)
    localStorage.setItem('darkMode', newDarkMode)
    document.body.classList.toggle('dark-mode')
  }

  const saveSessionToLocal = () => {
    if (!currentSessionId) return
    
    const sessionData = {
      sessionId: currentSessionId,
      messages,
      documents,
      timestamp: Date.now()
    }
    
    localStorage.setItem(`${LOCAL_STORAGE_BACKUP_KEY}_${currentSessionId}`, JSON.stringify(sessionData))
  }

  const recoverFromCrash = () => {
    const keys = Object.keys(localStorage).filter(k => k.startsWith(LOCAL_STORAGE_BACKUP_KEY))
    if (keys.length > 0) {
      // Recovery logic here
      console.log('Recovered session data from crash')
    }
  }

  const addConsoleMessage = (type, args) => {
    setConsoleMessages(prev => [...prev.slice(-99), {
      type,
      message: args.map(arg => typeof arg === 'object' ? JSON.stringify(arg) : String(arg)).join(' '),
      timestamp: Date.now()
    }])
  }

  const trackApiRequest = (method, url, data, response, duration) => {
    setApiRequests(prev => [...prev.slice(-49), {
      method,
      url,
      data,
      response,
      duration,
      timestamp: Date.now()
    }])
  }

  const processRetryQueue = async () => {
    if (retryQueue.length === 0) return
    
    for (const item of retryQueue) {
      try {
        await handleSendMessage(item.message, true)
      } catch (error) {
        console.error('Retry failed:', error)
      }
    }
    setRetryQueue([])
  }

  const checkHealth = async () => {
    const startTime = Date.now()
    try {
      const response = await axios.get('/api/health', { timeout: 5000 })
      const duration = Date.now() - startTime
      
      setSystemStatus(response.data)
      setSystemHealth({
        ...response.data,
        responseTime: duration,
        timestamp: Date.now()
      })
      
      if (debugMode) {
        trackApiRequest('GET', '/api/health', null, response.data, duration)
      }
    } catch (error) {
      console.error('Health check failed:', error)
      setSystemStatus({ status: 'unhealthy' })
      setSystemHealth({
        status: 'unhealthy',
        error: error.message,
        timestamp: Date.now()
      })
    }
  }

  const loadDocuments = async () => {
    const startTime = Date.now()
    try {
      const response = await axios.get('/api/documents/list', { timeout: API_TIMEOUT })
      const duration = Date.now() - startTime
      
      setDocuments(response.data)
      
      if (debugMode) {
        trackApiRequest('GET', '/api/documents/list', null, response.data, duration)
      }
      
      setPerformanceMetrics(prev => ({
        ...prev,
        documentsLoadTime: duration
      }))
    } catch (error) {
      console.error('Failed to load documents:', error)
    }
  }

  const loadSessions = async () => {
    const startTime = Date.now()
    try {
      const response = await axios.get('/api/chat/sessions', { timeout: API_TIMEOUT })
      const duration = Date.now() - startTime
      
      setSessions(response.data.sessions || [])
      
      if (debugMode) {
        trackApiRequest('GET', '/api/chat/sessions', null, response.data, duration)
      }
      
      if (!response.data.sessions || response.data.sessions.length === 0) {
        await createNewSession()
      } else if (!currentSessionId) {
        const firstSession = response.data.sessions[0]
        setCurrentSessionId(firstSession.id)
        await loadSessionMessages(firstSession.id)
      }
      
      setPerformanceMetrics(prev => ({
        ...prev,
        sessionsLoadTime: duration
      }))
    } catch (error) {
      console.error('Failed to load sessions:', error)
    }
  }

  const createNewSession = async () => {
    if (isLoading) {
      alert('현재 응답을 생성 중입니다. 완료 후 다시 시도해주세요.')
      return
    }
    
    try {
      const response = await axios.post('/api/chat/sessions', {
        title: '새 대화',
        document_ids: documents.map(d => (d.id ? d.id : (d.filename ? d.filename.replace(/\.[^.]+$/, '') : ''))).filter(Boolean)
      }, { timeout: API_TIMEOUT })
      
      const newSession = response.data.session
      setSessions(prev => [newSession, ...prev])
      setCurrentSessionId(newSession.id)
      setMessages([])
      setInputMessage('')
      
      return newSession
    } catch (error) {
      console.error('Failed to create session:', error)
    }
  }

  const selectSession = async (sessionId) => {
    if (sessionId === currentSessionId) return
    
    if (isLoading) {
      setShowSessionSwitchWarning(true)
      setPendingSessionSwitch(sessionId)
      return
    }
    
    setCurrentSessionId(sessionId)
    await loadSessionMessages(sessionId)
  }

  const confirmSessionSwitch = async () => {
    if (pendingSessionSwitch) {
      // Cancel current request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      setIsLoading(false)
      
      setCurrentSessionId(pendingSessionSwitch)
      await loadSessionMessages(pendingSessionSwitch)
      
      setShowSessionSwitchWarning(false)
      setPendingSessionSwitch(null)
    }
  }

  const loadSessionMessages = async (sessionId) => {
    const startTime = Date.now()
    try {
      setMessages([])
      const response = await axios.get(`/api/chat/sessions/${sessionId}`, { timeout: API_TIMEOUT })
      const duration = Date.now() - startTime
      
      if (debugMode) {
        trackApiRequest('GET', `/api/chat/sessions/${sessionId}`, null, response.data, duration)
      }
      
      const sessionMessages = response.data.session.messages || []
      const uniqueMessages = sessionMessages.reduce((acc, msg) => {
        const key = `${msg.role}-${msg.content}-${msg.timestamp}`
        if (!acc.has(key)) {
          acc.set(key, msg)
        }
        return acc
      }, new Map())
      setMessages(Array.from(uniqueMessages.values()))
    } catch (error) {
      console.error('Failed to load session messages:', error)
      setMessages([])
    }
  }

  const updateSessionTitle = async (sessionId, newTitle) => {
    try {
      await axios.put(`/api/chat/sessions/${sessionId}`, {
        title: newTitle
      }, { timeout: API_TIMEOUT })
      
      setSessions(prev => prev.map(s => 
        s.id === sessionId ? { ...s, title: newTitle } : s
      ))
    } catch (error) {
      console.error('Failed to update session title:', error)
    }
  }

  const deleteSession = async (sessionId) => {
    if (isLoading) {
      alert('현재 응답을 생성 중입니다. 완료 후 다시 시도해주세요.')
      return
    }
    
    if (!confirm('이 대화를 삭제하시겠습니까?')) return
    
    try {
      await axios.delete(`/api/chat/sessions/${sessionId}`, { timeout: API_TIMEOUT })
      
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
    }
  }

  const clearCurrentChat = async () => {
    if (!confirm('현재 대화 내용을 모두 삭제하시겠습니까?')) return
    
    setMessages([])
    if (currentSessionId) {
      try {
        await axios.delete(`/api/chat/sessions/${currentSessionId}/messages`, { timeout: API_TIMEOUT })
      } catch (error) {
        console.error('Failed to clear messages:', error)
      }
    }
  }

  const handleSendMessage = async (messageOverride = null, isRetry = false) => {
    const message = (messageOverride || inputMessage).trim()
    
    if (!message || (isLoading && !isRetry)) return
    
    if (message.length > MAX_MESSAGE_LENGTH) {
      alert(`메시지는 ${MAX_MESSAGE_LENGTH}자를 초과할 수 없습니다.`)
      return
    }
    
    if (!currentSessionId) {
      const newSession = await createNewSession()
      if (!newSession) return
    }
    
    const userMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: message,
      timestamp: new Date().toISOString()
    }
    
    setMessages(prev => {
      const exists = prev.some(msg => 
        msg.role === 'user' && 
        msg.content === message && 
        Math.abs(new Date(msg.timestamp) - new Date()) < 1000
      )
      if (exists) return prev
      return [...prev, userMessage]
    })
    
    setInputMessage('')
    setIsLoading(true)
    setTypingIndicator(true)
    
    const thinkingStartTime = Date.now()
    
    abortControllerRef.current = new AbortController()
    
    try {
      // Streaming placeholder
      setMessages(prev => [...prev, {
        id: `assistant-${Date.now()}`,
        role: 'assistant',
        content: '',
        sources: [],
        streaming: true,
        timestamp: new Date().toISOString()
      }])

      const finalResponse = await chatAPI.streamMessage(
        currentSessionId,
        message,
        abortControllerRef.current.signal,
        (chunkOrStatus) => {
          if (!chunkOrStatus) return
          if (typeof chunkOrStatus === 'string' && (chunkOrStatus.includes('문서 검색 중') || chunkOrStatus.includes('답변 생성 중'))) {
            // optional: set UI status if you have a state
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

      const thinkingTime = Date.now() - thinkingStartTime
      setModelThinkingTime(thinkingTime)

      // finalize
      setMessages(prev => {
        const updated = [...prev]
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].role === 'assistant' && updated[i].streaming) {
            updated[i] = {
              ...updated[i],
              streaming: false,
              content: finalResponse.answer || updated[i].content || '응답을 생성할 수 없습니다.',
              sources: finalResponse.sources || [],
              thinkingTime
            }
            break
          }
        }
        return updated
      })
      
      if (messages.length === 0) {
        await updateSessionTitle(currentSessionId, message.substring(0, 30))
      }
      
      setPerformanceMetrics(prev => ({
        ...prev,
        lastResponseTime: thinkingTime,
        averageResponseTime: prev.averageResponseTime 
          ? (prev.averageResponseTime + thinkingTime) / 2 
          : thinkingTime
      }))
    } catch (error) {
      if (error.name === 'CanceledError') {
        const interruptedMessage = {
          id: `system-${Date.now()}`,
          role: 'system',
          content: '답변이 중단되었습니다.',
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, interruptedMessage])
      } else if (networkStatus === 'offline') {
        setRetryQueue(prev => [...prev, { message, timestamp: Date.now() }])
        const errorMessage = {
          role: 'assistant',
          content: '네트워크 연결이 없습니다. 연결이 복구되면 자동으로 재시도됩니다.',
          error: true,
          timestamp: new Date().toISOString()
        }
        setMessages(prev => [...prev, errorMessage])
      } else {
        console.error('Failed to send message:', error)
        const errorMessage = {
          role: 'assistant',
          content: '메시지 처리 중 오류가 발생했습니다.',
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
      setTypingIndicator(false)
      abortControllerRef.current = null
      sessionStorage.removeItem('pendingResponse')
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

  const handleShowDocumentDetails = async (doc) => {
    try {
      const response = await axios.get(`/api/documents/${doc.id || doc.filename}/details`, { 
        timeout: API_TIMEOUT 
      })
      setSelectedDocument({
        ...doc,
        details: response.data
      })
      setShowDocumentDetails(true)
    } catch (error) {
      console.error('Failed to load document details:', error)
      alert('문서 상세 정보를 불러올 수 없습니다.')
    }
  }

  const handleFileUpload = async (e) => {
    const files = Array.from(e.target.files)
    if (files.length === 0) return
    
    // Block all UI during upload
    setShowUploadModal(true)
    setUploadingFiles(files.map(f => f.name))
    
    const formData = new FormData()
    files.forEach(file => {
      if (file.size > MAX_FILE_SIZE) {
        alert(`${file.name}의 크기가 50MB를 초과합니다.`)
        return
      }
      formData.append('files', file)
    })
    
    try {
      setUploadStatus('uploading')
      setUploadProgress(0)
      
      const response = await axios.post('/api/documents/upload-batch', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
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
          setShowUploadModal(false)
          setUploadingFiles([])
        }, 2000)
      }
    } catch (error) {
      console.error('Upload failed:', error)
      setUploadStatus('error')
      setTimeout(() => {
        setUploadStatus('')
        setUploadProgress(0)
        setShowUploadModal(false)
        setUploadingFiles([])
      }, 3000)
    } finally {
      e.target.value = ''
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleDragEnter = (e) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current++
    if (dragCounterRef.current === 1) {
      document.body.classList.add('drag-active')
    }
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current--
    if (dragCounterRef.current === 0) {
      document.body.classList.remove('drag-active')
    }
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    e.stopPropagation()
    dragCounterRef.current = 0
    document.body.classList.remove('drag-active')
    
    const files = Array.from(e.dataTransfer.files).filter(
      file => file.name.endsWith('.pdf') || file.name.endsWith('.hwp')
    )
    
    if (files.length > 0) {
      const input = fileInputRef.current
      const dt = new DataTransfer()
      files.forEach(file => dt.items.add(file))
      input.files = dt.files
      
      const event = new Event('change', { bubbles: true })
      input.dispatchEvent(event)
    }
  }

  const handleDeleteDocument = async (docId) => {
    if (!confirm('이 문서를 삭제하시겠습니까?')) return
    
    try {
      await axios.delete(`/api/documents/${docId}`, { timeout: API_TIMEOUT })
      await loadDocuments()
    } catch (error) {
      console.error('Failed to delete document:', error)
    }
  }

  const handleEditMessage = (messageId) => {
    const message = messages.find(m => m.id === messageId)
    if (message && message.role === 'user') {
      setEditingMessageId(messageId)
      setEditingMessageContent(message.content)
    }
  }

  const saveEditedMessage = async () => {
    if (!editingMessageId || !editingMessageContent.trim()) return
    
    const messageIndex = messages.findIndex(m => m.id === editingMessageId)
    if (messageIndex === -1) return
    
    const updatedMessages = [...messages]
    updatedMessages[messageIndex] = {
      ...updatedMessages[messageIndex],
      content: editingMessageContent,
      edited: true,
      editedAt: new Date().toISOString()
    }
    
    setMessages(updatedMessages)
    setEditingMessageId(null)
    setEditingMessageContent('')
    
    // Optionally resend to get new response
    if (confirm('수정된 메시지로 새로운 응답을 받으시겠습니까?')) {
      await handleSendMessage(editingMessageContent)
    }
  }

  const togglePinMessage = (messageId) => {
    setPinnedMessages(prev => {
      const newSet = new Set(prev)
      if (newSet.has(messageId)) {
        newSet.delete(messageId)
      } else {
        newSet.add(messageId)
      }
      return newSet
    })
  }

  const rateMessage = (messageId, rating) => {
    setMessageRatings(prev => ({
      ...prev,
      [messageId]: rating
    }))
  }

  const exportChat = (format) => {
    const exportData = {
      sessionId: currentSessionId,
      title: sessions.find(s => s.id === currentSessionId)?.title || 'Untitled',
      messages: messages,
      exportedAt: new Date().toISOString()
    }
    
    let content, filename, type
    
    if (format === 'json') {
      content = JSON.stringify(exportData, null, 2)
      filename = `chat-export-${Date.now()}.json`
      type = 'application/json'
    } else {
      content = messages.map(m => 
        `[${m.role.toUpperCase()}] ${new Date(m.timestamp).toLocaleString('ko-KR')}:\n${m.content}\n`
      ).join('\n---\n\n')
      filename = `chat-export-${Date.now()}.txt`
      type = 'text/plain'
    }
    
    const blob = new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
    
    setShowExportMenu(false)
  }

  const searchInChat = (query) => {
    if (!query) {
      setSearchResults([])
      return
    }
    
    const results = messages.filter(m => 
      m.content.toLowerCase().includes(query.toLowerCase())
    ).map(m => m.id)
    
    setSearchResults(results)
  }

  const toggleVoiceInput = () => {
    if (!voiceInputSupported) {
      alert('음성 입력이 지원되지 않는 브라우저입니다.')
      return
    }
    
    if (isRecording) {
      recognitionRef.current.stop()
      setIsRecording(false)
    } else {
      recognitionRef.current.start()
      setIsRecording(true)
    }
  }

  const handleTabSwitch = (tab) => {
    if (isLoading) {
      alert('현재 응답을 생성 중입니다. 완료 후 다시 시도해주세요.')
      return
    }
    setActiveTab(tab)
  }

  const copyCodeBlock = (code) => {
    navigator.clipboard.writeText(code).then(() => {
      // Show toast notification
      const toast = document.createElement('div')
      toast.className = 'toast-notification'
      toast.textContent = '코드가 복사되었습니다'
      document.body.appendChild(toast)
      setTimeout(() => toast.remove(), 2000)
    })
  }

  const renderMarkdown = (text) => {
    // Simple markdown renderer
    return text
      .replace(/```([^`]+)```/g, '<pre class="code-block"><code>$1</code></pre>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      .replace(/\*([^*]+)\*/g, '<em>$1</em>')
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
      .replace(/\n/g, '<br>')
  }

  // Parse message content
  const parseMessageContent = (content) => {
    if (!content) return null
    
    const lines = content.split('\n')
    const parsed = {
      keyAnswer: '',
      facts: [],
      details: '',
      sources: []
    }
    
    let currentSection = null
    
    lines.forEach(line => {
      if (line.includes('핵심 답변')) {
        currentSection = 'answer'
      } else if (line.includes('주요 사실')) {
        currentSection = 'facts'
      } else if (line.includes('상세 설명')) {
        currentSection = 'details'
      } else if (line.includes('출처')) {
        currentSection = 'sources'
      } else if (line.trim()) {
        switch (currentSection) {
          case 'answer':
            parsed.keyAnswer += line + ' '
            break
          case 'facts':
            if (line.trim().startsWith('•') || line.trim().startsWith('-')) {
              parsed.facts.push(line.trim().substring(1).trim())
            }
            break
          case 'details':
            parsed.details += line + ' '
            break
          case 'sources':
            if (line.trim().match(/^\[\d+\]/)) {
              parsed.sources.push(line.trim())
            }
            break
        }
      }
    })
    
    return parsed
  }

  // Format date for display
  const formatDate = (timestamp) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
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
    } else {
      return date.toLocaleDateString('ko-KR')
    }
  }

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('ko-KR', {
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  const formatThinkingTime = (ms) => {
    if (ms < 1000) return `${ms}ms`
    return `${(ms / 1000).toFixed(1)}초`
  }

  // Filtered sessions based on search
  const filteredSessions = useMemo(() => {
    if (!sessionSearchQuery) return sessions
    return sessions.filter(s => 
      s.title.toLowerCase().includes(sessionSearchQuery.toLowerCase())
    )
  }, [sessions, sessionSearchQuery])

  // Filtered documents based on search
  const filteredDocuments = useMemo(() => {
    if (!documentSearchQuery) return documents
    return documents.filter(d => 
      d.filename.toLowerCase().includes(documentSearchQuery.toLowerCase()) ||
      documentTags[d.id]?.some(tag => 
        tag.toLowerCase().includes(documentSearchQuery.toLowerCase())
      )
    )
  }, [documents, documentSearchQuery, documentTags])

  return (
    <div className={`medium-app ${darkMode ? 'dark' : ''}`}
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Header */}
      <header className="medium-header">
        <div className="medium-container">
          <div className="medium-header-inner">
            <h1 className="medium-logo">Knowledge Base</h1>
            
            <nav className="medium-nav">
              <button
                className={`medium-nav-link ${activeTab === 'chat' ? 'active' : ''}`}
                onClick={() => handleTabSwitch('chat')}
                disabled={isLoading}
              >
                대화
              </button>
              <button
                className={`medium-nav-link ${activeTab === 'upload' ? 'active' : ''}`}
                onClick={() => handleTabSwitch('upload')}
                disabled={isLoading}
              >
                업로드
              </button>
              <button
                className={`medium-nav-link ${activeTab === 'manage' ? 'active' : ''}`}
                onClick={() => handleTabSwitch('manage')}
                disabled={isLoading}
              >
                문서 관리
              </button>
            </nav>
            
            <div className="medium-header-actions">
              <button
                className="medium-icon-btn"
                onClick={toggleDarkMode}
                title="다크 모드 토글"
              >
                {darkMode ? '☀️' : '🌙'}
              </button>
              
              <button
                className="medium-icon-btn"
                onClick={() => setShowShortcuts(true)}
                title="단축키 보기"
              >
                ⌨️
              </button>
              
              <button
                className="medium-icon-btn"
                onClick={() => setShowStatsDashboard(true)}
                title="통계 대시보드"
              >
                📊
              </button>
              
              {debugMode && (
                <button
                  className="medium-icon-btn"
                  onClick={() => setShowConsoleLog(true)}
                  title="콘솔 로그"
                >
                  🐛
                </button>
              )}
              
              <div className="medium-status-indicator">
                <span className={`medium-status-dot ${networkStatus === 'online' ? 'online' : 'offline'}`}></span>
                <span className="medium-status-text">
                  {networkStatus === 'online' ? '온라인' : '오프라인'}
                </span>
              </div>
              
              <div className="medium-doc-count">
                {documents.length}개 문서
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="medium-main">
        {activeTab === 'chat' && (
          <div className="medium-container">
            <div className="medium-layout">
              {/* Sidebar */}
              <aside className="medium-sidebar">
                <div className="medium-sidebar-header">
                  <button 
                    className="medium-btn-primary"
                    onClick={createNewSession}
                    disabled={isLoading}
                  >
                    새 대화
                  </button>
                  
                  <input
                    type="text"
                    placeholder="세션 검색..."
                    value={sessionSearchQuery}
                    onChange={(e) => setSessionSearchQuery(e.target.value)}
                    className="medium-search-input"
                  />
                </div>
                
                <div className="medium-sessions">
                  <h3 className="medium-sessions-title">대화 목록</h3>
                  <div className="medium-sessions-list">
                    {filteredSessions.map(session => (
                      <div
                        key={session.id}
                        className={`medium-session-item ${session.id === currentSessionId ? 'active' : ''} ${isLoading ? 'disabled' : ''}`}
                        onClick={() => !isLoading && selectSession(session.id)}
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
                            className="medium-session-input"
                          />
                        ) : (
                          <>
                            <div 
                              className="medium-session-content"
                              onDoubleClick={(e) => {
                                e.stopPropagation()
                                if (!isLoading) {
                                  setEditingSessionId(session.id)
                                  setEditTitle(session.title)
                                }
                              }}
                            >
                              <div className="medium-session-title">{session.title}</div>
                              <div className="medium-session-meta">{formatDate(session.created_at)}</div>
                            </div>
                            {session.id === currentSessionId && (
                              <button
                                className="medium-session-delete"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  deleteSession(session.id)
                                }}
                                disabled={isLoading}
                                aria-label="삭제"
                              >
                                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                                  <path d="M4 4L12 12M4 12L12 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                                </svg>
                              </button>
                            )}
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="medium-sidebar-footer">
                  <button
                    className="medium-btn-secondary"
                    onClick={clearCurrentChat}
                    disabled={isLoading || messages.length === 0}
                  >
                    현재 대화 지우기
                  </button>
                  
                  <button
                    className="medium-btn-secondary"
                    onClick={() => setShowExportMenu(true)}
                    disabled={messages.length === 0}
                  >
                    대화 내보내기
                  </button>
                </div>
              </aside>

              {/* Chat Area */}
              <div className="medium-chat">
                {showSearch && (
                  <div className="medium-search-bar">
                    <input
                      type="text"
                      placeholder="대화 내용 검색..."
                      value={searchQuery}
                      onChange={(e) => {
                        setSearchQuery(e.target.value)
                        searchInChat(e.target.value)
                      }}
                      autoFocus
                      className="medium-search-input"
                    />
                    <button
                      onClick={() => {
                        setShowSearch(false)
                        setSearchQuery('')
                        setSearchResults([])
                      }}
                      className="medium-search-close"
                    >
                      ✕
                    </button>
                  </div>
                )}
                
                <div className="medium-messages" ref={messagesContainerRef}>
                  {messages.length === 0 && (
                    <div className="medium-empty-chat">
                      <h2 className="medium-empty-title">무엇을 도와드릴까요?</h2>
                      <p className="medium-empty-desc">
                        문서를 업로드하고 질문을 시작해보세요.
                      </p>
                    </div>
                  )}
                  
                  {messages.map((msg, idx) => (
                    <div 
                      key={msg.id || `${msg.role}-${idx}-${msg.timestamp}`} 
                      className={`medium-message ${msg.role} ${searchResults.includes(msg.id) ? 'highlighted' : ''} ${pinnedMessages.has(msg.id) ? 'pinned' : ''}`}
                    >
                      <div className="medium-message-header">
                        <span className="medium-message-time">{formatTime(msg.timestamp)}</span>
                        {msg.edited && <span className="medium-message-edited">(수정됨)</span>}
                        {msg.thinkingTime && (
                          <span className="medium-thinking-time">
                            생각 시간: {formatThinkingTime(msg.thinkingTime)}
                          </span>
                        )}
                        
                        <div className="medium-message-actions">
                          <button
                            onClick={() => togglePinMessage(msg.id)}
                            className="medium-message-action"
                            title={pinnedMessages.has(msg.id) ? '고정 해제' : '고정'}
                          >
                            {pinnedMessages.has(msg.id) ? '📌' : '📍'}
                          </button>
                          
                          {msg.role === 'user' && (
                            <button
                              onClick={() => handleEditMessage(msg.id)}
                              className="medium-message-action"
                              title="편집"
                            >
                              ✏️
                            </button>
                          )}
                          
                          {msg.role === 'assistant' && (
                            <>
                              <button
                                onClick={() => rateMessage(msg.id, 'up')}
                                className={`medium-message-action ${messageRatings[msg.id] === 'up' ? 'active' : ''}`}
                                title="좋아요"
                              >
                                👍
                              </button>
                              <button
                                onClick={() => rateMessage(msg.id, 'down')}
                                className={`medium-message-action ${messageRatings[msg.id] === 'down' ? 'active' : ''}`}
                                title="싫어요"
                              >
                                👎
                              </button>
                            </>
                          )}
                        </div>
                      </div>
                      
                      {msg.role === 'user' ? (
                        <div className="medium-message-user">
                          {editingMessageId === msg.id ? (
                            <div className="medium-message-edit">
                              <textarea
                                value={editingMessageContent}
                                onChange={(e) => setEditingMessageContent(e.target.value)}
                                className="medium-edit-textarea"
                                autoFocus
                              />
                              <div className="medium-edit-actions">
                                <button onClick={saveEditedMessage} className="medium-btn-primary">
                                  저장
                                </button>
                                <button 
                                  onClick={() => {
                                    setEditingMessageId(null)
                                    setEditingMessageContent('')
                                  }}
                                  className="medium-btn-secondary"
                                >
                                  취소
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="medium-message-content" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                          )}
                        </div>
                      ) : msg.role === 'system' ? (
                        <div className="medium-message-system">
                          <div className="medium-message-content">{msg.content}</div>
                        </div>
                      ) : (
                        <div className="medium-message-assistant">
                          {msg.error ? (
                            <div className="medium-message-error">{msg.content}</div>
                          ) : (
                            <>
                              {(() => {
                                const parsed = parseMessageContent(msg.content)
                                if (!parsed) return <div className="medium-message-text" dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
                                
                                return (
                                  <div className="medium-response">
                                    {parsed.keyAnswer && (
                                      <div className="medium-response-answer">
                                        <div dangerouslySetInnerHTML={{ __html: renderMarkdown(parsed.keyAnswer) }} />
                                      </div>
                                    )}
                                    
                                    {parsed.facts.length > 0 && (
                                      <div className="medium-response-facts">
                                        <h4 className="medium-response-label">주요 사실</h4>
                                        <ul className="medium-facts-list">
                                          {parsed.facts.map((fact, i) => (
                                            <li key={i} dangerouslySetInnerHTML={{ __html: renderMarkdown(fact) }} />
                                          ))}
                                        </ul>
                                      </div>
                                    )}
                                    
                                    {parsed.details && (
                                      <div className="medium-response-details">
                                        <h4 className="medium-response-label">상세 설명</h4>
                                        <div dangerouslySetInnerHTML={{ __html: renderMarkdown(parsed.details) }} />
                                      </div>
                                    )}
                                    
                                    {/* Only show sources for real responses, not errors */}
                                    {msg.sources?.length > 0 && !msg.content.includes('질문이 입력되지 않았습니다') && (
                                      <div className="medium-response-sources">
                                        <h4 className="medium-response-label">출처</h4>
                                        <div className="medium-sources-list">
                                          {msg.sources.map((source, i) => (
                                            <button
                                              key={i}
                                              className="medium-source-link"
                                              onClick={() => handleShowSource(source)}
                                              onMouseEnter={(e) => {
                                                // Citation preview on hover
                                                const preview = document.createElement('div')
                                                preview.className = 'citation-preview'
                                                preview.textContent = source.text_snippet || source.text || '미리보기 없음'
                                                e.target.appendChild(preview)
                                              }}
                                              onMouseLeave={(e) => {
                                                const preview = e.target.querySelector('.citation-preview')
                                                if (preview) preview.remove()
                                              }}
                                            >
                                              [{i + 1}] {source.doc_id || source.document}
                                            </button>
                                          ))}
                                        </div>
                                      </div>
                                    )}
                                  </div>
                                )
                              })()}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                  
                  {typingIndicator && (
                    <div className="medium-message assistant">
                      <div className="medium-typing-indicator">
                        <span>모델이 생각하고 있습니다</span>
                        <div className="medium-loading">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                      </div>
                    </div>
                  )}
                  
                  {showNewMessageIndicator && !isAtBottom && (
                    <button
                      className="medium-new-message-indicator"
                      onClick={scrollToBottom}
                    >
                      새 메시지 ↓
                    </button>
                  )}
                  
                  <div ref={messagesEndRef} />
                </div>

                <div className="medium-input-container">
                  <div className="medium-input-wrapper">
                    <textarea
                      value={inputMessage}
                      onChange={(e) => {
                        const value = e.target.value.slice(0, MAX_MESSAGE_LENGTH)
                        setInputMessage(value)
                        setMessageCharCount(value.length)
                      }}
                      onKeyPress={handleKeyPress}
                      placeholder="질문을 입력하세요..."
                      disabled={isLoading}
                      className="medium-input"
                      rows={1}
                      maxLength={MAX_MESSAGE_LENGTH}
                    />
                    
                    <div className="medium-input-actions">
                      <span className="medium-char-count">
                        {messageCharCount}/{MAX_MESSAGE_LENGTH}
                      </span>
                      
                      {voiceInputSupported && (
                        <button
                          onClick={toggleVoiceInput}
                          className={`medium-voice-btn ${isRecording ? 'recording' : ''}`}
                          disabled={isLoading}
                          title="음성 입력"
                        >
                          🎤
                        </button>
                      )}
                      
                      <button
                        onClick={handleSendMessage}
                        disabled={isLoading || !inputMessage.trim()}
                        className="medium-send-btn"
                      >
                        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                          <path d="M2 10L8 4L14 10M8 4V16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" transform="rotate(90 10 10)"/>
                        </svg>
                      </button>
                    </div>
                  </div>
                  
                  {retryQueue.length > 0 && (
                    <div className="medium-retry-indicator">
                      {retryQueue.length}개 메시지 재시도 대기 중...
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'upload' && (
          <div className="medium-container">
            <div className="medium-upload">
              <div className="medium-upload-header">
                <h2 className="medium-upload-title">문서 업로드</h2>
                <p className="medium-upload-desc">
                  PDF, HWP 문서를 업로드하여 지식 베이스에 추가하세요.
                </p>
              </div>

              <div className="medium-upload-zone">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.hwp"
                  onChange={handleFileUpload}
                  style={{ display: 'none' }}
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="medium-upload-label">
                  <svg width="48" height="48" viewBox="0 0 48 48" fill="none" className="medium-upload-icon">
                    <path d="M24 32V16M24 16L18 22M24 16L30 22" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    <path d="M40 28V36C40 38.2091 38.2091 40 36 40H12C9.79086 40 8 38.2091 8 36V28" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  <span className="medium-upload-text">파일을 선택하거나 드래그하세요</span>
                  <span className="medium-upload-hint">PDF, HWP (최대 50MB)</span>
                </label>
              </div>

              {uploadStatus && !showUploadModal && (
                <div className="medium-upload-status">
                  {uploadStatus === 'uploading' && (
                    <>
                      <div className="medium-progress">
                        <div 
                          className="medium-progress-bar"
                          style={{ width: `${uploadProgress}%` }}
                        />
                      </div>
                      <p>업로드 중... {uploadProgress}%</p>
                    </>
                  )}
                  {uploadStatus === 'processing' && <p>문서 처리 중...</p>}
                  {uploadStatus === 'completed' && <p className="success">업로드 완료!</p>}
                  {uploadStatus === 'error' && <p className="error">업로드 실패</p>}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'manage' && (
          <div className="medium-container">
            <div className="medium-documents">
              <div className="medium-documents-header">
                <h2 className="medium-documents-title">문서 관리</h2>
                <p className="medium-documents-desc">
                  등록된 문서를 확인하고 관리할 수 있습니다.
                </p>
                
                <input
                  type="text"
                  placeholder="문서 검색..."
                  value={documentSearchQuery}
                  onChange={(e) => setDocumentSearchQuery(e.target.value)}
                  className="medium-search-input"
                />
              </div>

              {filteredDocuments.length === 0 ? (
                <div className="medium-no-documents">
                  <p>등록된 문서가 없습니다.</p>
                  <button
                    className="medium-btn-primary"
                    onClick={() => setActiveTab('upload')}
                  >
                    문서 업로드하기
                  </button>
                </div>
              ) : (
                <div className="medium-documents-grid">
                  {filteredDocuments.map(doc => (
                    <div key={doc.id || doc.filename} className="medium-document-card">
                      <div className="medium-document-header">
                        <h3 className="medium-document-title">{doc.filename}</h3>
                        <div className="medium-document-actions">
                          <button
                            className="medium-document-action"
                            onClick={() => handleShowDocumentDetails(doc)}
                            title="상세 정보"
                          >
                            ℹ️
                          </button>
                          <button
                            className="medium-document-delete"
                            onClick={() => handleDeleteDocument(doc.id || doc.filename)}
                          >
                            삭제
                          </button>
                        </div>
                      </div>
                      <div className="medium-document-meta">
                        <span>크기: {doc.size ? `${(doc.size / 1024).toFixed(1)}KB` : '알 수 없음'}</span>
                        <span>페이지: {doc.pages || '알 수 없음'}</span>
                        <span>상태: {doc.indexed ? '인덱싱 완료' : '처리 중'}</span>
                        {doc.chunks_count && <span>청크: {doc.chunks_count}개</span>}
                      </div>
                      {documentTags[doc.id] && (
                        <div className="medium-document-tags">
                          {documentTags[doc.id].map((tag, i) => (
                            <span key={i} className="medium-tag">{tag}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Upload Modal */}
      {showUploadModal && (
        <div className="medium-modal-overlay">
          <div className="medium-modal">
            <div className="medium-modal-header">
              <h3 className="medium-modal-title">문서 업로드 중</h3>
            </div>
            <div className="medium-modal-content">
              <div className="medium-upload-progress">
                <div className="medium-progress">
                  <div 
                    className="medium-progress-bar"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
                <p className="medium-progress-text">
                  {uploadStatus === 'uploading' && `업로드 중... ${uploadProgress}%`}
                  {uploadStatus === 'processing' && '문서 처리 중...'}
                  {uploadStatus === 'completed' && '업로드 완료!'}
                  {uploadStatus === 'error' && '업로드 실패'}
                </p>
                {uploadingFiles.length > 0 && (
                  <div className="medium-uploading-files">
                    <h4>업로드 중인 파일:</h4>
                    <ul>
                      {uploadingFiles.map((file, i) => (
                        <li key={i}>{file}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Session Switch Warning */}
      {showSessionSwitchWarning && (
        <div className="medium-modal-overlay">
          <div className="medium-modal">
            <div className="medium-modal-header">
              <h3 className="medium-modal-title">경고</h3>
            </div>
            <div className="medium-modal-content">
              <p>현재 응답을 생성 중입니다. 세션을 전환하면 진행 중인 작업이 취소됩니다.</p>
              <p>계속하시겠습니까?</p>
              <div className="medium-modal-actions">
                <button
                  onClick={confirmSessionSwitch}
                  className="medium-btn-danger"
                >
                  세션 전환
                </button>
                <button
                  onClick={() => {
                    setShowSessionSwitchWarning(false)
                    setPendingSessionSwitch(null)
                  }}
                  className="medium-btn-secondary"
                >
                  취소
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Document Details Modal */}
      {showDocumentDetails && selectedDocument && (
        <div className="medium-modal-overlay" onClick={() => setShowDocumentDetails(false)}>
          <div className="medium-modal large" onClick={(e) => e.stopPropagation()}>
            <div className="medium-modal-header">
              <h3 className="medium-modal-title">문서 상세 정보: {selectedDocument.filename}</h3>
              <button
                className="medium-modal-close"
                onClick={() => setShowDocumentDetails(false)}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
            <div className="medium-modal-content scrollable">
              <div className="medium-document-details">
                <div className="medium-detail-section">
                  <h4>기본 정보</h4>
                  <div className="medium-detail-grid">
                    <div>파일명: {selectedDocument.filename}</div>
                    <div>크기: {selectedDocument.size ? `${(selectedDocument.size / 1024).toFixed(1)}KB` : '알 수 없음'}</div>
                    <div>페이지: {selectedDocument.pages || '알 수 없음'}</div>
                    <div>청크 수: {selectedDocument.chunks_count || '알 수 없음'}</div>
                    <div>인덱싱: {selectedDocument.indexed ? '완료' : '진행 중'}</div>
                    <div>생성일: {formatDate(selectedDocument.created_at)}</div>
                  </div>
                </div>
                
                {selectedDocument.details?.pages && (
                  <div className="medium-detail-section">
                    <h4>페이지별 내용</h4>
                    <div className="medium-pages-content">
                      {selectedDocument.details.pages.map((page, i) => (
                        <details key={i} className="medium-page-detail">
                          <summary>페이지 {i + 1}</summary>
                          <div className="medium-page-text">{page.text}</div>
                        </details>
                      ))}
                    </div>
                  </div>
                )}
                
                {selectedDocument.details?.chunks && (
                  <div className="medium-detail-section">
                    <h4>청크 정보</h4>
                    <div className="medium-chunks-list">
                      {selectedDocument.details.chunks.map((chunk, i) => (
                        <details key={i} className="medium-chunk-detail">
                          <summary>청크 {i + 1} (페이지 {chunk.page})</summary>
                          <div className="medium-chunk-text">{chunk.text}</div>
                          <div className="medium-chunk-meta">
                            <span>시작: {chunk.start_char}</span>
                            <span>끝: {chunk.end_char}</span>
                            <span>토큰: {chunk.tokens}</span>
                          </div>
                        </details>
                      ))}
                    </div>
                  </div>
                )}
                
                {selectedDocument.details?.statistics && (
                  <div className="medium-detail-section">
                    <h4>통계</h4>
                    <div className="medium-detail-grid">
                      <div>총 문자 수: {selectedDocument.details.statistics.total_chars}</div>
                      <div>총 단어 수: {selectedDocument.details.statistics.total_words}</div>
                      <div>평균 청크 크기: {selectedDocument.details.statistics.avg_chunk_size}</div>
                      <div>처리 시간: {selectedDocument.details.statistics.processing_time}ms</div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Citation Popup */}
      {showSourcePopup && selectedSource && (
        <div className="medium-modal-overlay" onClick={() => setShowSourcePopup(false)}>
          <div className="medium-modal" onClick={(e) => e.stopPropagation()}>
            <div className="medium-modal-header">
              <h3 className="medium-modal-title">출처 상세 정보</h3>
              <button
                className="medium-modal-close"
                onClick={() => setShowSourcePopup(false)}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
            <div className="medium-modal-content">
              <div className="medium-citation-info">
                <div className="medium-citation-row">
                  <span className="medium-citation-label">문서</span>
                  <span className="medium-citation-value">
                    {selectedSource.doc_id || selectedSource.document || '알 수 없음'}
                  </span>
                </div>
                <div className="medium-citation-row">
                  <span className="medium-citation-label">페이지</span>
                  <span className="medium-citation-value">
                    {selectedSource.page || '전체'}
                  </span>
                </div>
                {selectedSource.score && (
                  <div className="medium-citation-row">
                    <span className="medium-citation-label">관련도</span>
                    <span className="medium-citation-value">
                      {(selectedSource.score * 100).toFixed(1)}%
                    </span>
                  </div>
                )}
                {selectedSource.start_char && selectedSource.end_char && (
                  <div className="medium-citation-row">
                    <span className="medium-citation-label">위치</span>
                    <span className="medium-citation-value">
                      {selectedSource.start_char} - {selectedSource.end_char}
                    </span>
                  </div>
                )}
              </div>
              
              <div className="medium-citation-text">
                <h4 className="medium-citation-subtitle">원문 내용</h4>
                <div className="medium-citation-content">
                  {selectedSource.text || selectedSource.content || selectedSource.text_snippet || '원문을 불러올 수 없습니다.'}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Keyboard Shortcuts Modal */}
      {showShortcuts && (
        <div className="medium-modal-overlay" onClick={() => setShowShortcuts(false)}>
          <div className="medium-modal" onClick={(e) => e.stopPropagation()}>
            <div className="medium-modal-header">
              <h3 className="medium-modal-title">키보드 단축키</h3>
              <button
                className="medium-modal-close"
                onClick={() => setShowShortcuts(false)}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
            <div className="medium-modal-content">
              <div className="medium-shortcuts-list">
                {Object.entries(KEYBOARD_SHORTCUTS).map(([key, action]) => (
                  <div key={key} className="medium-shortcut-item">
                    <kbd className="medium-kbd">{key}</kbd>
                    <span className="medium-shortcut-desc">{action}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Export Menu */}
      {showExportMenu && (
        <div className="medium-modal-overlay" onClick={() => setShowExportMenu(false)}>
          <div className="medium-modal small" onClick={(e) => e.stopPropagation()}>
            <div className="medium-modal-header">
              <h3 className="medium-modal-title">대화 내보내기</h3>
              <button
                className="medium-modal-close"
                onClick={() => setShowExportMenu(false)}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
            <div className="medium-modal-content">
              <div className="medium-export-options">
                <button
                  onClick={() => exportChat('json')}
                  className="medium-btn-primary"
                >
                  JSON으로 내보내기
                </button>
                <button
                  onClick={() => exportChat('txt')}
                  className="medium-btn-primary"
                >
                  텍스트로 내보내기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Statistics Dashboard */}
      {showStatsDashboard && (
        <div className="medium-modal-overlay" onClick={() => setShowStatsDashboard(false)}>
          <div className="medium-modal large" onClick={(e) => e.stopPropagation()}>
            <div className="medium-modal-header">
              <h3 className="medium-modal-title">통계 대시보드</h3>
              <button
                className="medium-modal-close"
                onClick={() => setShowStatsDashboard(false)}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
            <div className="medium-modal-content">
              <div className="medium-stats-grid">
                <div className="medium-stat-card">
                  <h4>세션 통계</h4>
                  <div>총 세션: {sessions.length}</div>
                  <div>총 메시지: {messages.length}</div>
                  <div>평균 메시지/세션: {sessions.length ? (messages.length / sessions.length).toFixed(1) : 0}</div>
                </div>
                
                <div className="medium-stat-card">
                  <h4>문서 통계</h4>
                  <div>총 문서: {documents.length}</div>
                  <div>인덱싱 완료: {documents.filter(d => d.indexed).length}</div>
                  <div>총 청크: {documents.reduce((sum, d) => sum + (d.chunks_count || 0), 0)}</div>
                </div>
                
                <div className="medium-stat-card">
                  <h4>성능 메트릭</h4>
                  <div>평균 응답 시간: {performanceMetrics.averageResponseTime ? `${formatThinkingTime(performanceMetrics.averageResponseTime)}` : 'N/A'}</div>
                  <div>마지막 응답 시간: {performanceMetrics.lastResponseTime ? `${formatThinkingTime(performanceMetrics.lastResponseTime)}` : 'N/A'}</div>
                  <div>문서 로드 시간: {performanceMetrics.documentsLoadTime ? `${performanceMetrics.documentsLoadTime}ms` : 'N/A'}</div>
                </div>
                
                <div className="medium-stat-card">
                  <h4>시스템 상태</h4>
                  <div>상태: {systemHealth.status || 'Unknown'}</div>
                  <div>응답 시간: {systemHealth.responseTime ? `${systemHealth.responseTime}ms` : 'N/A'}</div>
                  <div>마지막 체크: {systemHealth.timestamp ? formatDate(systemHealth.timestamp) : 'N/A'}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Console Log Viewer (Debug Mode) */}
      {showConsoleLog && debugMode && (
        <div className="medium-modal-overlay" onClick={() => setShowConsoleLog(false)}>
          <div className="medium-modal large" onClick={(e) => e.stopPropagation()}>
            <div className="medium-modal-header">
              <h3 className="medium-modal-title">콘솔 로그</h3>
              <button
                className="medium-modal-close"
                onClick={() => setShowConsoleLog(false)}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
            <div className="medium-modal-content">
              <div className="medium-console-log">
                {consoleMessages.map((msg, i) => (
                  <div key={i} className={`medium-console-message ${msg.type}`}>
                    <span className="medium-console-time">{formatTime(msg.timestamp)}</span>
                    <span className={`medium-console-type ${msg.type}`}>[{msg.type.toUpperCase()}]</span>
                    <span className="medium-console-text">{msg.message}</span>
                  </div>
                ))}
              </div>
              <div className="medium-modal-actions">
                <button
                  onClick={() => setConsoleMessages([])}
                  className="medium-btn-secondary"
                >
                  로그 지우기
                </button>
                <button
                  onClick={() => setShowApiInspector(true)}
                  className="medium-btn-primary"
                >
                  API 인스펙터
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* API Inspector (Debug Mode) */}
      {showApiInspector && debugMode && (
        <div className="medium-modal-overlay" onClick={() => setShowApiInspector(false)}>
          <div className="medium-modal large" onClick={(e) => e.stopPropagation()}>
            <div className="medium-modal-header">
              <h3 className="medium-modal-title">API 인스펙터</h3>
              <button
                className="medium-modal-close"
                onClick={() => setShowApiInspector(false)}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <path d="M5 5L15 15M5 15L15 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
                </svg>
              </button>
            </div>
            <div className="medium-modal-content">
              <div className="medium-api-requests">
                {apiRequests.map((req, i) => (
                  <details key={i} className="medium-api-request">
                    <summary>
                      <span className={`medium-api-method ${req.method.toLowerCase()}`}>{req.method}</span>
                      <span className="medium-api-url">{req.url}</span>
                      <span className="medium-api-duration">{req.duration}ms</span>
                    </summary>
                    <div className="medium-api-details">
                      {req.data && (
                        <div>
                          <h5>Request Data:</h5>
                          <pre>{JSON.stringify(req.data, null, 2)}</pre>
                        </div>
                      )}
                      {req.response && (
                        <div>
                          <h5>Response:</h5>
                          <pre>{JSON.stringify(req.response, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  </details>
                ))}
              </div>
              <div className="medium-modal-actions">
                <button
                  onClick={() => setApiRequests([])}
                  className="medium-btn-secondary"
                >
                  요청 기록 지우기
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App_Medium

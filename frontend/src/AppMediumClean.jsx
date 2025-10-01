import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './styles/MediumDesign.css'
import DocumentDetailsPopup from './components/DocumentDetailsPopup'
import CitationPopup from './components/CitationPopup'
import AnswerWithCitations from './components/AnswerWithCitations'
import SummaryPopup from './components/SummaryPopup'
import { chatAPI } from './services/chatAPI'

// Configure axios defaults
axios.defaults.baseURL = 'http://localhost:8000'

function AppMediumClean() {
  // Tab state
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
  const [summaryDoc, setSummaryDoc] = useState(null) // For summary popup

  // Refs
  const messagesEndRef = useRef(null)
  const fileInputRef = useRef(null)
  
  // Initialize
  useEffect(() => {
    console.log('AppMediumClean component mounted')
    const init = async () => {
      try {
        console.log('Starting initialization...')
        await checkHealth()
        console.log('Health check completed')
        await loadDocuments()  // 먼저 문서를 로드
        console.log('Documents loaded')
        await loadSessionsWithDeviceId()   // 디바이스별 세션 로드
        console.log('Sessions loaded')
        console.log('Initialization complete')
      } catch (error) {
        console.error('Initialization error:', error)
        setError('초기화 중 오류가 발생했습니다.')
      }
    }
    init()
  }, [])
  
  // 새로고침으로 인한 중단 표시 처리
  useEffect(() => {
    const wasLoading = sessionStorage.getItem('wasLoadingBeforeUnload') === 'true'
    const interruptedId = sessionStorage.getItem('interruptedSessionId')
    if (!handledRefreshInterrupt && wasLoading && interruptedId && currentSessionId && currentSessionId === interruptedId) {
      // 중복 표시 방지: 서버가 기록한 중단 메시지 또는 이전에 추가한 알림이 있으면 스킵
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
      // 플래그 정리
      sessionStorage.removeItem('wasLoadingBeforeUnload')
      sessionStorage.removeItem('interruptedSessionId')
    }
  }, [currentSessionId, handledRefreshInterrupt])
  
  // Handle page refresh/unload
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (isLoading && currentSessionId) {
        sessionStorage.setItem('wasLoadingBeforeUnload', 'true')
        sessionStorage.setItem('interruptedSessionId', currentSessionId)
        if (abortController) {
          abortController.abort()
        }
        // 서버가 연결 끊김을 자동 감지하지만, 보강을 위해 비동기 중단 신호도 전송
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
  
  // Auto scroll and persist messages
  useEffect(() => {
    scrollToBottom()
    // Save messages to localStorage for session persistence
    if (currentSessionId && messages.length > 0) {
      localStorage.setItem(`messages_${currentSessionId}`, JSON.stringify(messages))
    }
  }, [messages, currentSessionId])
  
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

      // 각 문서의 상세 정보를 가져와서 인덱싱 상태 확인
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
      return docsWithDetails  // 문서 목록 반환
    } catch (error) {
      console.error('Failed to load documents:', error)
      return []
    }
  }
  
  // 디바이스별 고유 ID 생성 또는 가져오기
  const getOrCreateDeviceId = () => {
    let id = localStorage.getItem('deviceId')
    if (!id) {
      // 브라우저 fingerprint 기반 ID 생성
      const userAgent = navigator.userAgent
      const screenResolution = `${screen.width}x${screen.height}`
      const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone
      const language = navigator.language

      // 간단한 해시 함수로 고유 ID 생성
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

      // 디바이스 ID로 세션 조회
      const response = await axios.get('/api/chat/sessions', {
        params: { device_id: deviceId }
      })

      setSessions(response.data.sessions || [])

      // 이전 세션 복원 또는 새 세션 생성
      const lastSessionId = localStorage.getItem('lastSessionId')
      if (lastSessionId && response.data.sessions.some(s => s.id === lastSessionId)) {
        setCurrentSessionId(lastSessionId)

        // localStorage에서 저장된 메시지 먼저 복원
        const savedMessages = localStorage.getItem(`messages_${lastSessionId}`)
        if (savedMessages) {
          try {
            const parsedMessages = JSON.parse(savedMessages)
            setMessages(parsedMessages)
            console.log('Restored messages from localStorage')
          } catch (e) {
            console.error('Failed to parse saved messages:', e)
          }
        }

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

  const loadSessions = async () => {
    try {
      const response = await axios.get('/api/chat/sessions')
      setSessions(response.data.sessions || [])

      if (!response.data.sessions || response.data.sessions.length === 0) {
        await createNewSession()
      } else if (!currentSessionId) {
        const firstSession = response.data.sessions[0]
        setCurrentSessionId(firstSession.id)
        await loadSessionMessages(firstSession.id)
      }
    } catch (error) {
      console.error('Failed to load sessions:', error)
    }
  }
  
  const createNewSessionWithDeviceId = async () => {
    try {
      // 중단 상태 초기화
      setWasInterrupted(false)
      sessionStorage.removeItem('wasLoadingBeforeUnload')
      sessionStorage.removeItem('interruptedSessionId')

      // 현재 로드된 문서들의 ID 가져오기
      const documentIds = documents.length > 0
        ? documents.map(d => (d.id ? d.id : (d.filename ? d.filename.replace(/\.[^.]+$/, '') : ''))).filter(Boolean)
        : []

      const deviceId = getOrCreateDeviceId()

      console.log('Creating session with device ID:', deviceId)

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

      // 채팅 탭으로 자동 이동
      setActiveTab('chat')

      return newSession
    } catch (error) {
      console.error('Failed to create session:', error)
      setError('새 대화를 시작할 수 없습니다.')
    }
  }

  const createNewSession = async () => {
    try {
      // 중단 상태 초기화
      setWasInterrupted(false)
      sessionStorage.removeItem('wasLoadingBeforeUnload')
      sessionStorage.removeItem('interruptedSessionId')

      // 현재 로드된 문서들의 ID 가져오기
      const documentIds = documents.length > 0
        ? documents.map(d => (d.id ? d.id : (d.filename ? d.filename.replace(/\.[^.]+$/, '') : ''))).filter(Boolean)
        : []

      const deviceId = getOrCreateDeviceId()

      console.log('Creating session with device ID:', deviceId)

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

      // 채팅 탭으로 자동 이동
      setActiveTab('chat')

      return newSession
    } catch (error) {
      console.error('Failed to create session:', error)
      setError('새 대화를 시작할 수 없습니다.')
    }
  }
  
  const selectSession = async (sessionId) => {
    if (sessionId === currentSessionId) return

    // 답변 로딩 중에는 세션 전환 차단
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
      
      // 사용자가 직접 중단한 메시지는 필터링 (페이지 새로고침으로 인한 중단은 표시)
      const filteredMessages = messages.filter(msg => {
        // 사용자가 버튼으로 중단한 경우는 표시하지 않음
        if (msg.interrupted && msg.content === '답변 생성이 중단되었습니다.') {
          return false
        }
        return true
      })

      const normalizedMessages = filteredMessages.map(msg => {
        const formattedText = msg?.metadata?.formatted_text
        const normalizedSources = Array.isArray(msg?.sources)
          ? msg.sources
          : Array.isArray(msg?.metadata?.sources)
            ? msg.metadata.sources
            : []

        return {
          ...msg,
          content: formattedText || msg.content,
          sources: normalizedSources,
        }
      })

      setMessages(normalizedMessages)
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
    
    // 세션 ID 확인 및 새 세션 생성
    let sessionId = currentSessionId
    if (!sessionId) {
      const newSession = await createNewSession()
      if (!newSession) {
        setError('새 대화를 시작할 수 없습니다.')
        return
      }
      sessionId = newSession.id
    }
    
    // 문서 체크 - 문서가 없으면 skip_document_check를 true로 설정
    const skipDocumentCheck = documents.length === 0
    
    // 현재 세션에 문서가 연결되어 있는지 확인
    const currentSession = sessions.find(s => s.id === sessionId)
    if (!skipDocumentCheck && (!currentSession?.document_ids || currentSession.document_ids.length === 0)) {
      // 세션에 문서가 없으면 현재 문서로 업데이트
      if (documents.length > 0) {
        try {
          const documentIds = documents.map(d => (d.id ? d.id : (d.filename ? d.filename.replace(/\.[^.]+$/, '') : ''))).filter(Boolean)
          await axios.put(`/api/chat/sessions/${sessionId}`, {
            document_ids: documentIds
          })
          // 로컬 세션 데이터 업데이트
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
    
    // 새 AbortController 생성
    const controller = new AbortController()
    setAbortController(controller)
    
    try {
      // 스트리밍용 플레이스홀더 메시지 추가
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
          // 상태 업데이트
          if (typeof chunkOrStatus === 'string' && (chunkOrStatus.includes('문서 검색 중') || chunkOrStatus.includes('답변 생성 중'))) {
            setStreamStatus(chunkOrStatus)
            return
          }
          const chunk = chunkOrStatus
          if (typeof chunk !== 'string') return
          setMessages(prev => {
            // 마지막 streaming 메시지 업데이트
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

      // 스트리밍 완료: 마지막 streaming 메시지를 최종화
      setMessages(prev => {
        const updated = [...prev]
        for (let i = updated.length - 1; i >= 0; i--) {
          if (updated[i].role === 'assistant' && updated[i].streaming) {
            updated[i] = {
              ...updated[i],
              streaming: false,
              content: finalResponse.metadata?.formatted_text || finalResponse.answer || updated[i].content || '응답을 생성할 수 없습니다.',
              sources: Array.isArray(finalResponse.sources) ? finalResponse.sources : [],
              metadata: finalResponse.metadata || updated[i].metadata
            }
            break
          }
        }
        return updated
      })
      setStreamStatus('')

      // 제목 업데이트 확인 (서버에서 처리되면 메타데이터에 포함됨)
      if (finalResponse.metadata?.title_updated && finalResponse.metadata?.new_title) {
        // 로컬 상태 즉시 업데이트
        setSessions(prev => prev.map(s =>
          s.id === sessionId ? { ...s, title: finalResponse.metadata.new_title } : s
        ))
        console.log('Title updated:', finalResponse.metadata.new_title)
      }
    } catch (error) {
      // 요청 취소 에러는 별도 처리
      if (axios.isCancel(error)) {
        // 이미 중단 메시지가 추가되었으므로 여기서는 추가하지 않음
        console.log('Request was cancelled')
      } else {
        console.error('Failed to send/stream message:', error)
        console.error('Error details:', error.response?.data)

        let errorContent = '메시지 처리 중 오류가 발생했습니다.'
        // 네트워크/타임아웃/중단 등 예외 상황 세분화
        if (error.message?.includes('Network') || error.code === 'ERR_NETWORK') {
          errorContent = '네트워크 오류로 응답이 중단되었습니다. 연결을 확인해 주세요.'
        } else if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
          errorContent = '응답이 지연되어 시간 초과되었습니다. 다시 시도해 주세요.'
        }
        if (error.response?.data?.detail) {
          errorContent = error.response.data.detail
          console.log('Error detail from server:', errorContent)
        } else if (error.response?.status === 400) {
          // 400 에러의 경우 문서 업로드 관련 메시지 표시
          errorContent = '먼저 문서를 업로드해 주세요.'
        }

        const errorMessage = {
          role: 'assistant',
          content: errorContent,
          error: true,
          timestamp: new Date().toISOString()
        }
        // 스트리밍 플레이스홀더가 있으면 교체, 없으면 추가
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

  // Handle summary popup
  const handleShowSummary = (doc) => {
    // Extract document ID (filename without extension)
    const docId = doc.filename ? doc.filename.replace(/\.[^/.]+$/, "") : (doc.id || "")
    setSummaryDoc({
      id: docId,
      name: doc.filename || docId,
      ...doc
    })
  }

  const handleCloseSummary = () => {
    setSummaryDoc(null)
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
        
        // 각 파일을 순차적으로 처리
        for (let i = 0; i < response.data.uploaded.length; i++) {
          const filename = response.data.uploaded[i]
          setUploadStatus(`processing_file_${i + 1}_of_${response.data.uploaded.length}`)
          
          // 서버에서 인덱싱 하는 동안 대기
          await new Promise(resolve => setTimeout(resolve, 500))
        }
        
        const updatedDocuments = await loadDocuments()
        
        // 현재 세션이 있으면 문서 ID 업데이트
        if (currentSessionId && updatedDocuments.length > 0) {
          try {
            const documentIds = updatedDocuments.map(d => (d.id ? d.id : (d.filename ? d.filename.replace(/\.[^.]+$/, '') : ''))).filter(Boolean)
            await axios.put(`/api/chat/sessions/${currentSessionId}`, {
              document_ids: documentIds
            })
            
            // 로컬 세션 데이터도 업데이트
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
      // Wait a bit for processing to start
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
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault()
        createNewSession()
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
    <div className="medium-app">
      {/* Header */}
      <header className="medium-header">
        <div className="medium-header-content">
          <div className="medium-logo">RAG</div>
          <nav className="medium-nav">
            <button
              className={`medium-nav-link ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => !isUploading && !isLoading && setActiveTab('chat')}
              disabled={isUploading || isLoading}
            >
              채팅
            </button>
            <button
              className={`medium-nav-link ${activeTab === 'upload' ? 'active' : ''}`}
              onClick={() => !isUploading && !isLoading && setActiveTab('upload')}
              disabled={isUploading || isLoading}
            >
              업로드
            </button>
            <button
              className={`medium-nav-link ${activeTab === 'manage' ? 'active' : ''}`}
              onClick={() => !isUploading && !isLoading && setActiveTab('manage')}
              disabled={isUploading || isLoading}
            >
              문서 관리
            </button>
          </nav>
          <button 
            className="medium-cta-button" 
            onClick={createNewSession}
            disabled={isUploading || isLoading}
          >
            새 대화 시작
          </button>
        </div>
      </header>
      
      <main className="medium-main">
        {/* Chat Tab */}
        {activeTab === 'chat' && (
          <div className="medium-layout">
            {/* Sidebar */}
            <aside className="medium-sidebar">
              <div className="medium-sidebar-header">
                <h2 className="medium-sidebar-title">대화 목록</h2>
                <span className="medium-sidebar-count">{sessions.length}</span>
              </div>
              
              <div className="medium-session-list">
                {sessions.map(session => (
                  <div
                    key={session.id}
                    className={`medium-session-item ${session.id === currentSessionId ? 'active' : ''} ${isUploading ? 'disabled' : ''}`}
                    onClick={() => !isUploading && selectSession(session.id)}
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
                      <div
                        className="medium-session-title"
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
                        className="medium-session-delete"
                        onClick={(e) => {
                          e.stopPropagation()
                          if (!isLoading) {
                            deleteSession(session.id)
                          }
                        }}
                        disabled={isLoading}
                      >
                        ×
                      </button>
                    )}
                  </div>
                ))}
              </div>
              
              <div className="medium-sidebar-footer">
                <div className="medium-doc-count">
                  문서 {documents.length}개
                </div>
              </div>
            </aside>
            
            {/* Content */}
            <div className="medium-content">
              <div className="medium-messages">
                {documents.length === 0 && messages.length === 0 && (
                  <div className="medium-empty-state">
                    <h2 className="medium-empty-title">시작하기</h2>
                    <p className="medium-empty-text">
                      문서를 업로드하고 질문을 시작하세요
                    </p>
                    <button
                      className="medium-empty-button"
                      onClick={() => fileInputRef.current?.click()}
                    >
                      문서 업로드
                    </button>
                  </div>
                )}
                
                {messages.map((msg, idx) => (
                  <div key={idx} className={`medium-message ${msg.role}`}>
                    <div className="medium-message-content">
                      {msg.content && (
                        <div className="medium-message-text">
                          {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 ? (
                            // Use AnswerWithCitations for assistant messages with sources
                            <AnswerWithCitations
                              content={msg.content}
                              sources={msg.sources}
                              onCitationClick={handleShowSource}
                            />
                          ) : (
                            // Use regular ReactMarkdown for other messages
                            <ReactMarkdown
                              remarkPlugins={[remarkGfm]}
                              components={{
                                p: ({children}) => {
                                  // Handle section headers
                                  const text = typeof children === 'string' ? children : ''
                                  if (text.includes('핵심 답변')) {
                                    return <h3 className="medium-answer-header">{text.replace(/[📌]/g, '')}</h3>
                                  } else if (text.includes('주요 사실')) {
                                    return <h4 className="medium-facts-header">{text.replace(/[📊]/g, '')}</h4>
                                  } else if (text.includes('상세 설명')) {
                                    return <h4 className="medium-details-header">{text.replace(/[📝]/g, '')}</h4>
                                  } else if (text.includes('출처')) {
                                    const hasSources = Array.isArray(msg.sources) && msg.sources.length > 0
                                    if (hasSources) return null
                                    return <h4 className="medium-sources-header">{text.replace(/[📚]/g, '')}</h4>
                                  }
                                  return <p className="medium-paragraph">{children}</p>
                                },
                                strong: ({children}) => <strong className="medium-bold">{children}</strong>,
                                em: ({children}) => <em className="medium-italic">{children}</em>,
                                ul: ({children}) => <ul className="medium-list">{children}</ul>,
                                ol: ({children}) => <ol className="medium-ordered-list">{children}</ol>,
                                li: ({children}) => <li className="medium-fact-item">{children}</li>,
                                h1: ({children}) => <h3 className="medium-heading">{children}</h3>,
                                h2: ({children}) => <h3 className="medium-heading">{children}</h3>,
                                h3: ({children}) => <h3 className="medium-heading">{children}</h3>,
                              }}
                            >
                              {msg.content}
                            </ReactMarkdown>
                          )}
                        </div>
                      )}

                      {/* Streaming indicator inside assistant placeholder */}
                      {msg.role === 'assistant' && msg.streaming && (
                        <div className="medium-streaming-status">
                          <div className="medium-loading"><span></span><span></span><span></span></div>
                          <div className="medium-streaming-text">{streamStatus || '답변 준비 중...'}</div>
                        </div>
                      )}

                      {/* sources 배열이 있으면 항상 출처 섹션 표시 - AnswerWithCitations를 사용하지 않는 경우에만 */}
                      {false && msg.sources && msg.sources.length > 0 && (() => {
                        // 중복 출처 제거 (문서+페이지+오프셋 기준)
                        const keyOf = (s) => `${s.doc_id || s.document || ''}-${s.page || ''}-${s.start || s.start_char || ''}-${s.end || s.end_char || ''}`
                        const uniqueSources = Array.from(new Map((msg.sources || []).map(s => [keyOf(s), s])).values())
                        return (
                        <div className="medium-sources-section">
                          <h4 className="medium-sources-title">📚 출처 (클릭하여 상세 정보 확인)</h4>
                          <div className="medium-sources-list">
                            {uniqueSources.map((source, sourceIdx) => {
                              const displayIndex = source.display_index || source.index || (sourceIdx + 1)
                              return (
                                <button
                                  key={`source-${sourceIdx}`}
                                  className="medium-source-button"
                                  onClick={() => {
                                    console.log('Source clicked:', source)
                                    handleShowSource(source)
                                  }}
                                  title="클릭하여 상세 정보 보기"
                                  style={{
                                    textDecoration: 'underline',
                                    color: '#1a73e8',
                                    cursor: 'pointer',
                                    padding: '4px 8px',
                                    margin: '2px',
                                    borderRadius: '4px',
                                    transition: 'background-color 0.2s',
                                    ':hover': {
                                      backgroundColor: '#f0f7ff'
                                    }
                                  }}
                                >
                                  🔗 [{displayIndex}] {source.doc_id || source.document || '문서'}
                                  {source.page && ` - ${source.page}페이지`}
                                  {source.text_snippet && (
                                    <span style={{fontSize: '0.9em', color: '#666', marginLeft: '8px'}}>
                                      → 클릭하여 원문 보기
                                    </span>
                                  )}
                                </button>
                              )
                            })}
                          </div>
                        </div>
                        )
                      })()}
                    </div>
                  </div>
                ))}
                
                {(() => {
                  const hasStreamingAssistant = messages.some(m => m.role === 'assistant' && m.streaming)
                  return isLoading && !hasStreamingAssistant
                })() && (
                  <div className="medium-message assistant">
                    <div className="medium-loading">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                    <button 
                      className="medium-cancel-button"
                      onClick={async () => {
                        try {
                          if (abortController) {
                            // 먼저 요청 취소
                            abortController.abort()
                            setWasInterrupted(true)
                            setIsLoading(false)
                            setAbortController(null)
                            setStreamStatus('')
                            
                            // 서버가 연결 끊김을 감지하고 중단 메시지를 저장합니다.
                            // 사용자 경험을 위해 로컬에도 즉시 표시
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
                    >
                      답변 중단
                    </button>
                  </div>
                )}
                
                
                <div ref={messagesEndRef} />
              </div>
              
              <div className="medium-input-container">
                <textarea
                  value={inputMessage}
                  onChange={(e) => setInputMessage(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="질문을 입력하세요..."
                  disabled={isLoading}
                  className="medium-input"
                  rows={2}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={isLoading || !inputMessage.trim()}
                  className="medium-send-button"
                >
                  전송
                </button>
              </div>
            </div>
          </div>
        )}
        
        {/* Upload Tab */}
        {activeTab === 'upload' && (
          <div className="medium-upload-container">
            <div className="medium-upload-box">
              <h2 className="medium-upload-title">문서 업로드</h2>
              <p className="medium-upload-description">
                PDF 및 HWP 문서를 업로드하세요
              </p>
              
              <div className="medium-upload-area">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.hwp"
                  onChange={handleFileUpload}
                  className="medium-file-input"
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="medium-upload-label">
                  <span className="medium-upload-text">파일 선택</span>
                </label>
              </div>
              
              {uploadStatus && (
                <div className="medium-upload-status">
                  {uploadStatus === 'uploading' && (
                    <div className="medium-progress">
                      <div 
                        className="medium-progress-bar"
                        style={{ width: `${uploadProgress}%` }}
                      />
                      <span className="medium-progress-text">{uploadProgress}%</span>
                    </div>
                  )}
                  {uploadStatus === 'processing' && <p>처리 중...</p>}
                  {uploadStatus === 'completed' && <p className="medium-success">완료</p>}
                  {uploadStatus === 'error' && <p className="medium-error">실패</p>}
                </div>
              )}
            </div>
          </div>
        )}
        
        {/* Document Management Tab */}
        {activeTab === 'manage' && (
          <div className="medium-manage-container">
            <div className="medium-manage-header">
              <h2 className="medium-manage-title">문서 관리</h2>
              {documents.length > 0 && (
                <button
                  className="medium-delete-all"
                  onClick={handleDeleteAllDocuments}
                >
                  전체 삭제
                </button>
              )}
            </div>
            
            {documents.length === 0 ? (
              <div className="medium-no-documents">
                <p>업로드된 문서가 없습니다</p>
                <button
                  className="medium-upload-first"
                  onClick={() => setActiveTab('upload')}
                >
                  문서 업로드하기
                </button>
              </div>
            ) : (
              <div className="medium-document-grid">
                {documents.map(doc => (
                  <div key={doc.id || doc.filename} className="medium-document-card">
                    <h3 className="medium-doc-name">{doc.filename}</h3>
                    <div className="medium-doc-meta">
                      <span>{doc.size ? `${(doc.size / 1024).toFixed(1)}KB` : '알 수 없음'}</span>
                      <span>{doc.pages || 0} 페이지</span>
                    </div>
                    <div className="medium-doc-status">
                      {doc.indexed ? (
                        <span className="medium-indexed">인덱싱 완료</span>
                      ) : processingDoc === doc.id ? (
                        <span className="medium-processing">처리 중</span>
                      ) : (
                        <span className="medium-pending">대기 중</span>
                      )}
                    </div>
                    <div className="medium-doc-actions">
                      <button
                        className="medium-doc-button"
                        onClick={() => handleShowDocumentDetails(doc.filename)}
                      >
                        상세
                      </button>
                      <button
                        className="medium-doc-button"
                        onClick={() => handleShowSummary(doc)}
                        title="문서 요약 보기"
                      >
                        요약
                      </button>
                      {(!doc.indexed || doc.status === 'pending') && processingDoc !== doc.id && (
                        <button
                          className="medium-doc-button"
                          onClick={() => handleProcessDocument(doc.id || doc.filename)}
                        >
                          처리
                        </button>
                      )}
                      <button
                        className="medium-doc-button medium-delete"
                        onClick={() => handleDeleteDocument(doc.id || doc.filename)}
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
      />
      
      {/* Citation Popup - Using new component */}
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

      {/* Summary Popup */}
      {summaryDoc && (
        <SummaryPopup
          isOpen={true}
          documentId={summaryDoc.id}
          documentName={summaryDoc.name}
          onClose={handleCloseSummary}
        />
      )}
    </div>
  )
}

export default AppMediumClean

import React, { useState, useEffect, useRef } from 'react'
import SessionManager from './components/SessionManager'
import LargeUploadZone from './components/LargeUploadZone'
import AccessibleChat from './components/AccessibleChat'
import StructuredAnswer from './components/StructuredAnswer'
import DocumentManager from './components/DocumentManager'
import StatusIndicator from './components/StatusIndicator'
import CitationPopup from './components/CitationPopup'
import MessageRenderer from './components/MessageRenderer'
import streamingStore, { useStreamingStore } from './stores/streamingStore'
import serverMonitor, { useServerConnection } from './utils/serverMonitor'
import axios from 'axios'

function App() {
  return (
    <SessionManager>
      <AppContent />
    </SessionManager>
  )
}

function AppContent({ 
  currentSessionId, 
  createNewSession, 
  switchSession, 
  updateDraft,
  resumeSession,
  sessionList 
}) {
  const [systemStatus, setSystemStatus] = useState({
    status: 'checking',
    components: {}
  })
  
  const [currentView, setCurrentView] = useState('chat')
  const [documents, setDocuments] = useState([])
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentTurnId, setCurrentTurnId] = useState(null)
  const [abortController, setAbortController] = useState(null)
  const [selectedCitation, setSelectedCitation] = useState(null)
  const messagesEndRef = useRef(null)

  useEffect(() => {
    checkSystemHealth()
    loadDocuments()
  }, [])

  // 전역 스트리밍 상태
  const streamState = useStreamingStore(currentSessionId)
  
  // 서버 연결 상태 모니터링
  const { isConnected, connectionEvent } = useServerConnection()
  
  // 서버 연결이 끊어지면 모든 작업 중단
  useEffect(() => {
    if (!isConnected && connectionEvent?.type === 'disconnected') {
      // 스트리밍 중단
      if (streamState?.isStreaming) {
        streamingStore.abortStream(currentSessionId)
      }
      
      // 진행중인 요청 중단
      if (abortController) {
        abortController.abort()
        setAbortController(null)
      }
      
      // 로딩 상태 리셋
      setIsLoading(false)
      setIsStreaming(false)
      
      // 시스템 상태 업데이트
      setSystemStatus(prev => ({
        ...prev,
        status: 'offline',
        error: '서버 연결이 끊어졌습니다'
      }))
    } else if (isConnected && connectionEvent?.type === 'reconnected') {
      // 재연결 시 시스템 상태 체크
      checkSystemHealth()
    }
  }, [isConnected, connectionEvent, currentSessionId, streamState, abortController])
  
  // 세션 변경시 메시지 로드 및 스트리밍 상태 복구
  useEffect(() => {
    if (currentSessionId) {
      // 메시지 로드
      loadSessionMessages()
      
      // 스트리밍 상태 확인 및 복구
      const stream = streamingStore.getStream(currentSessionId)
      if (stream && stream.isStreaming) {
        setIsStreaming(true)
        setIsLoading(true)
        
        // 스트리밍 중인 메시지가 있으면 추가
        if (stream.message && !messages.find(m => m.turnId === stream.turnId)) {
          setMessages(prev => [...prev, stream.message])
        }
      } else {
        setIsStreaming(false)
        setIsLoading(false)
      }
    }
  }, [currentSessionId])
  
  // 메시지 추가시 자동 스크롤
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 페이지 로드시 복구 체크 (한 번만)
  useEffect(() => {
    if (currentSessionId && !isLoading) {
      checkAndResume()
    }
  }, [])

  const checkSystemHealth = async () => {
    try {
      const response = await axios.get('/api/health')
      setSystemStatus(response.data)
    } catch (error) {
      console.error('Health check failed:', error)
      setSystemStatus({
        status: 'unhealthy',
        components: {}
      })
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

  const loadSessionMessages = async () => {
    if (!currentSessionId) return
    
    try {
      const response = await axios.get(`/api/sessions/${currentSessionId}`)
      setMessages(response.data.messages || [])
    } catch (error) {
      console.error('Failed to load session messages:', error)
    }
  }

  const checkAndResume = async () => {
    if (!resumeSession) return
    
    const resumeInfo = await resumeSession()
    if (resumeInfo?.draft_state?.pending_request) {
      // 중단된 요청이 있으면 자동 재시도
      const { query } = resumeInfo.draft_state.pending_request
      await handleQuery(query, resumeInfo.draft_state.partial_tokens)
    }
  }

  const handleQuery = async (query, resumeToken = null) => {
    // 이미 처리 중이면 무시
    if (isLoading || isStreaming) {
      console.log('Already processing a query')
      return
    }
    
    // 세션이 없으면 생성 (한 번만)
    let sessionId = currentSessionId
    if (!sessionId) {
      sessionId = await createNewSession(query)
      // 새 세션 생성 후 대기
      await new Promise(resolve => setTimeout(resolve, 100))
    }
    
    setIsLoading(true)
    setIsStreaming(true)
    
    // 턴 ID 생성
    const turnId = Date.now().toString()
    setCurrentTurnId(turnId)
    
    // 사용자 메시지와 빈 어시스턴트 메시지를 한 번에 추가
    const userMessage = { 
      role: 'user', 
      content: query,
      timestamp: new Date().toISOString(),
      turnId: turnId
    }
    
    const assistantMessage = {
      role: 'assistant',
      content: '',
      timestamp: new Date().toISOString(),
      isStreaming: true,
      turnId: turnId
    }
    
    setMessages(prev => [...prev, userMessage, assistantMessage])
    
    // 스트리밍 상태 저장
    streamingStore.startStream(sessionId, turnId, assistantMessage)
    
    // 초안 저장
    updateDraft({
      messages: [...messages, userMessage],
      pending_request: {
        query,
        start_ts: new Date().toISOString(),
        partial_tokens: ''
      }
    })
    
    try {
      // SSE 스트리밍 연결
      const response = await fetch('/api/sessions/message', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          content: query,
          session_id: sessionId,
          stream: true,
          resume_token: resumeToken
        })
      })
      
      if (!response.ok) throw new Error('Failed to send message')
      
      // 스트리밍 처리
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let partialAnswer = ''
      let tokenCount = 0
      
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
                partialAnswer += data.content
                tokenCount++
                
                // 스트맍 상태 업데이트
                streamingStore.updateStream(sessionId, {
                  content: partialAnswer,
                  message: {
                    content: partialAnswer,
                    isStreaming: true
                  }
                })
                
                // 메시지 업데이트 (마지막 어시스턴트 메시지만)
                setMessages(prev => {
                  const newMessages = [...prev]
                  const lastMessage = newMessages[newMessages.length - 1]
                  if (lastMessage.role === 'assistant' && lastMessage.turnId === turnId) {
                    lastMessage.content = partialAnswer
                  }
                  return newMessages
                })
                
                // 200토큰마다 자동 저장
                if (tokenCount % 200 === 0) {
                  updateDraft({
                    messages,
                    pending_request: {
                      query,
                      start_ts: new Date().toISOString(),
                      partial_tokens: partialAnswer
                    }
                  })
                }
              } else if (data.type === 'complete') {
                // 완료 처리
                const finalResponse = data.response
                const finalMessage = {
                  role: 'assistant',
                  content: finalResponse.answer || partialAnswer,
                  sources: finalResponse.sources,
                  key_facts: finalResponse.key_facts,
                  details: finalResponse.details,
                  isStreaming: false,
                  isComplete: true,
                  turnId: turnId
                }
                
                // 스트링 상태 완료
                streamingStore.completeStream(sessionId, finalMessage)
                
                setMessages(prev => {
                  const newMessages = [...prev]
                  const lastMessage = newMessages[newMessages.length - 1]
                  if (lastMessage.role === 'assistant' && lastMessage.turnId === turnId) {
                    Object.assign(lastMessage, finalMessage)
                  }
                  return newMessages
                })
              } else if (data.type === 'done') {
                // 스트맍 완전 종료
                setIsStreaming(false)
                setIsLoading(false)
                
                // 초안 클리어
                updateDraft({
                  messages,
                  pending_request: null
                })
              } else if (data.type === 'abort') {
                // 중단 처리
                console.log('Generation aborted, resume token:', data.resume_token)
                setMessages(prev => {
                  const newMessages = [...prev]
                  const lastMessage = newMessages[newMessages.length - 1]
                  if (lastMessage.role === 'assistant') {
                    lastMessage.content += '\n\n[중단됨]'
                    lastMessage.isStreaming = false
                    lastMessage.isPartial = true
                    lastMessage.resumeToken = data.resume_token
                  }
                  return newMessages
                })
              } else if (data.type === 'error') {
                throw new Error(data.message)
              }
            } catch (e) {
              console.error('Failed to parse SSE data:', e)
            }
          }
        }
      }
    } catch (error) {
      console.error('Query failed:', error)
      
      // 에러 메시지 업데이트 (새로 추가하지 않고 마지막 메시지 업데이트)
      setMessages(prev => {
        const newMessages = [...prev]
        const lastMessage = newMessages[newMessages.length - 1]
        if (lastMessage.role === 'assistant' && lastMessage.turnId === turnId) {
          lastMessage.content = lastMessage.content || '질의 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.'
          lastMessage.error = true
          lastMessage.isStreaming = false
          lastMessage.isComplete = true
        }
        return newMessages
      })
    } finally {
      setIsLoading(false)
      setIsStreaming(false)
      setCurrentTurnId(null)
      setAbortController(null)
    }
  }

  const handleAbort = async () => {
    if (!currentTurnId || !currentSessionId) return
    
    try {
      await axios.post('/api/sessions/abort', {
        session_id: currentSessionId,
        turn_id: currentTurnId
      })
      
      setIsStreaming(false)
    } catch (error) {
      console.error('Failed to abort generation:', error)
    }
  }

  const handleUpload = async (files) => {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })
    
    try {
      const response = await axios.post('/api/documents/upload-batch', formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      })
      
      if (response.data.uploaded.length > 0) {
        alert(`${response.data.uploaded.length}개 파일이 업로드되었습니다.`)
        loadDocuments()
      }
      
      if (response.data.failed.length > 0) {
        alert(`${response.data.failed.length}개 파일 업로드 실패`)
      }
    } catch (error) {
      console.error('Upload failed:', error)
      alert('파일 업로드에 실패했습니다.')
    }
  }

  // 현재 대화의 마지막 응답 찾기
  const getCurrentAnswer = () => {
    const assistantMessages = messages.filter(m => m.role === 'assistant' && !m.error)
    if (assistantMessages.length === 0) return null
    
    const lastMessage = assistantMessages[assistantMessages.length - 1]
    return {
      answer: lastMessage.content,
      key_facts: lastMessage.key_facts || [],
      details: lastMessage.details || '',
      sources: lastMessage.sources || []
    }
  }

  return (
    <div className="flex-1 flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b flex-shrink-0">
        <div className="px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <h1 className="text-2xl font-bold text-gray-900">
              📚 RAG 문서 검색 시스템
            </h1>
            <div className="flex items-center gap-4">
              {/* 서버 연결 상태 */}
              <div className={`flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium ${
                isConnected 
                  ? 'bg-green-100 text-green-800' 
                  : 'bg-red-100 text-red-800'
              }`}>
                <div className={`w-2 h-2 rounded-full ${
                  isConnected ? 'bg-green-500' : 'bg-red-500'
                } ${!isConnected ? 'animate-pulse' : ''}`} />
                {isConnected ? '서버 연결됨' : '서버 연결 끊김'}
              </div>
              <StatusIndicator status={systemStatus} />
            </div>
          </div>
          
          {/* Navigation */}
          <nav className="flex space-x-8 mt-4">
            <button
              onClick={() => setCurrentView('chat')}
              className={`pb-2 px-1 border-b-2 font-medium text-lg ${
                currentView === 'chat'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              💬 질의응답
            </button>
            <button
              onClick={() => setCurrentView('upload')}
              className={`pb-2 px-1 border-b-2 font-medium text-lg ${
                currentView === 'upload'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              📤 문서 업로드
            </button>
            <button
              onClick={() => setCurrentView('documents')}
              className={`pb-2 px-1 border-b-2 font-medium text-lg ${
                currentView === 'documents'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              📁 문서 관리
            </button>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        <div className="px-4 sm:px-6 lg:px-8 py-8">
          {currentView === 'chat' && (
            <div className="flex gap-6">
              {/* 왼쪽: 질문 입력 */}
              <div className="w-1/3">
                <AccessibleChat 
                  onSubmit={handleQuery}
                  isLoading={isLoading}
                  isStreaming={isStreaming}
                  onAbort={handleAbort}
                />
              </div>
              
              {/* 오른쪽: 대화 히스토리 */}
              <div className="flex-1">
                <div className="bg-white rounded-lg shadow-sm h-[600px] flex flex-col">
                  <div className="border-b px-6 py-3 bg-gray-50">
                    <h3 className="text-lg font-semibold text-gray-800">💬 대화 내용</h3>
                  </div>
                  <div className="flex-1 p-6 overflow-y-auto scroll-smooth">
                  {messages.length === 0 ? (
                  <p className="text-gray-500 text-center">
                    새 대화를 시작하세요. 질문을 입력해주세요.
                  </p>
                  ) : (
                    <div className="space-y-3">
                      {/* 중복 제거: turnId로 그룹핑 */}
                      {messages.filter((msg, idx, arr) => {
                        // 중복 제거: 같은 turnId와 role을 가진 첫 번째 메시지만 표시
                        if (!msg.turnId) return true
                        const firstIdx = arr.findIndex(m => m.turnId === msg.turnId && m.role === msg.role)
                        return firstIdx === idx
                      }).map((message, idx) => (
                      <div
                        key={idx}
                        className={`flex ${
                          message.role === 'user' ? 'justify-end' : 'justify-start'
                        }`}
                      >
                        <div
                          className={`px-4 py-3 rounded-lg shadow-sm transition-all relative ${
                            message.role === 'user'
                              ? 'bg-blue-600 text-white ml-auto max-w-[80%]'
                              : message.error
                              ? 'bg-red-50 text-red-800 border border-red-200 mr-auto max-w-[90%]'
                              : message.isStreaming && !message.content
                              ? 'bg-gray-50 border border-gray-200 mr-auto max-w-[90%]'
                              : 'bg-gray-50 text-gray-800 mr-auto max-w-[90%] border border-gray-200'
                          }`}
                        >
                          {/* 역할 레이블 */}
                          {message.role === 'assistant' && (
                            <div className="absolute -top-2 -left-2">
                              <span className="bg-green-500 text-white text-xs px-2 py-1 rounded-full font-medium">
                                AI
                              </span>
                            </div>
                          )}
                          {message.role === 'assistant' && message.isStreaming && !message.isComplete && (
                            <div className="flex items-center gap-2 mb-2">
                              <div className="animate-spin w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full"></div>
                              <span className="text-sm text-blue-600 font-medium">답변 생성 중...</span>
                            </div>
                          )}
                          {message.isStreaming && !message.content && (
                            <div className="space-y-2">
                              <div className="h-4 bg-gray-200 rounded animate-pulse w-3/4"></div>
                              <div className="h-4 bg-gray-200 rounded animate-pulse w-1/2"></div>
                              <div className="h-4 bg-gray-200 rounded animate-pulse w-2/3"></div>
                            </div>
                          )}
                          {(!message.isStreaming || message.content) && (
                            <MessageRenderer 
                              message={message}
                              onCitationClick={(citation) => {
                                // 출처 클릭 핸들러
                                if (typeof citation === 'number') {
                                  // 숫자면 출처 찾기
                                  const source = message.sources?.find(s => 
                                    s.display_index === citation || 
                                    (s.display_index === undefined && message.sources.indexOf(s) === citation - 1)
                                  )
                                  if (source) setSelectedCitation(source)
                                } else {
                                  // 객체면 바로 사용
                                  setSelectedCitation(citation)
                                }
                              }}
                            />
                          )}
                          {message.isPartial && (
                            <button
                              onClick={() => handleQuery(messages[idx - 1]?.content, message.resumeToken)}
                              className="mt-2 text-sm text-blue-600 hover:text-blue-700"
                            >
                              이어서 생성하기
                            </button>
                          )}
                        </div>
                      </div>
                      ))}
                    </div>
                  )}
                  {/* 자동 스크롤 */}
                  <div ref={messagesEndRef} />
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {currentView === 'upload' && (
            <LargeUploadZone 
              onUpload={handleUpload}
            />
          )}
          
          {currentView === 'documents' && (
            <DocumentManager 
              documents={documents}
              onRefresh={loadDocuments}
            />
          )}
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-100 flex-shrink-0">
        <div className="px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-gray-500 text-sm">
            RAG Chatbot System v1.0.0 | 세션 ID: {currentSessionId?.slice(0, 8) || 'N/A'}
          </p>
        </div>
      </footer>
      
      {/* Citation Popup */}
      {selectedCitation && (
        <CitationPopup
          citation={selectedCitation}
          onClose={() => setSelectedCitation(null)}
        />
      )}
    </div>
  )
}

export default App
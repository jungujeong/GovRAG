import React, { useState, useEffect } from 'react'
import LargeUploadZone from './components/LargeUploadZone'
import AccessibleChat from './components/AccessibleChat'
import StructuredAnswer from './components/StructuredAnswer'
import DocumentManager from './components/DocumentManager'
import StatusIndicator from './components/StatusIndicator'
import axios from 'axios'

function App() {
  const [systemStatus, setSystemStatus] = useState({
    status: 'checking',
    components: {}
  })
  
  const [currentView, setCurrentView] = useState('chat') // 'chat', 'upload', 'documents'
  const [documents, setDocuments] = useState([])
  const [currentAnswer, setCurrentAnswer] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    checkSystemHealth()
    loadDocuments()
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

  const handleQuery = async (query) => {
    setIsLoading(true)
    setCurrentAnswer(null)
    
    try {
      const response = await axios.post('/api/query/', {
        query: query,
        limit: 10
      })
      
      setCurrentAnswer(response.data)
    } catch (error) {
      console.error('Query failed:', error)
      setCurrentAnswer({
        answer: '질의 처리 중 오류가 발생했습니다.',
        key_facts: [],
        sources: [],
        error: true
      })
    } finally {
      setIsLoading(false)
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

  return (
    <div className="min-h-screen bg-gray-50 font-korean">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <h1 className="text-2xl font-bold text-gray-900">
              📚 RAG 문서 검색 시스템
            </h1>
            <StatusIndicator status={systemStatus} />
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
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {currentView === 'chat' && (
          <div className="space-y-6">
            <AccessibleChat 
              onSubmit={handleQuery}
              isLoading={isLoading}
            />
            
            {currentAnswer && (
              <StructuredAnswer 
                answer={currentAnswer}
              />
            )}
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
      </main>

      {/* Footer */}
      <footer className="bg-gray-100 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <p className="text-center text-gray-500 text-sm">
            RAG Chatbot System v1.0.0 | 폐쇄망/오프라인 환경 지원
          </p>
        </div>
      </footer>
    </div>
  )
}

export default App
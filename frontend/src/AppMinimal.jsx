import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './styles/MediumDesign.css'

// Configure axios defaults
axios.defaults.baseURL = 'http://localhost:8000'

function AppMinimal() {
  console.log('AppMinimal component rendering')

  const [messages, setMessages] = useState([])
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(false)

  useEffect(() => {
    console.log('AppMinimal mounted')
    checkHealth()
  }, [])

  const checkHealth = async () => {
    try {
      console.log('Checking health...')
      const response = await axios.get('/api/health')
      console.log('Health check response:', response.data)
    } catch (error) {
      console.error('Health check failed:', error)
      setError('시스템 연결 실패')
    }
  }

  return (
    <div className="medium-app">
      <header className="medium-header">
        <div className="medium-header-content">
          <div className="medium-logo">RAG - Minimal Test</div>
        </div>
      </header>

      <main className="medium-main">
        <div className="medium-layout">
          <div className="medium-content">
            <h1>Minimal App Test</h1>
            {error && <p style={{ color: 'red' }}>Error: {error}</p>}
            <p>If you see this, React is rendering properly.</p>
            <p>Loading state: {isLoading ? 'Loading...' : 'Ready'}</p>
            <p>Messages count: {messages.length}</p>
          </div>
        </div>
      </main>
    </div>
  )
}

export default AppMinimal
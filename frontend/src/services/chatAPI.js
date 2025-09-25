import axios from 'axios'

const API_BASE = '/api'

class ChatAPI {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    })
    
    // Request interceptor
    this.client.interceptors.request.use(
      config => {
        // Add auth token if available
        const token = localStorage.getItem('auth_token')
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
        return config
      },
      error => Promise.reject(error)
    )
    
    // Response interceptor
    this.client.interceptors.response.use(
      response => response.data,
      error => {
        const message = error.response?.data?.detail || error.message || '요청 처리 중 오류가 발생했습니다'
        console.error('API Error:', message)
        throw new Error(message)
      }
    )
  }
  
  // Health check
  async checkHealth() {
    return this.client.get('/health')
  }
  
  // Session management
  async createSession(title, documentIds = []) {
    return this.client.post('/chat/sessions', {
      title,
      document_ids: documentIds
    })
  }
  
  async listSessions(page = 1, pageSize = 20) {
    return this.client.get('/chat/sessions', {
      params: { page, page_size: pageSize }
    })
  }
  
  async getSession(sessionId) {
    return this.client.get(`/chat/sessions/${sessionId}`)
  }
  
  async updateSession(sessionId, updates) {
    return this.client.put(`/chat/sessions/${sessionId}`, updates)
  }
  
  async deleteSession(sessionId) {
    return this.client.delete(`/chat/sessions/${sessionId}`)
  }
  
  // Message management
  async sendMessage(sessionId, query, options = {}) {
    const { signal, onStream } = options
    
    if (onStream) {
      // Streaming response
      return this.streamMessage(sessionId, query, signal, onStream)
    } else {
      // Regular response
      return this.client.post(
        `/chat/sessions/${sessionId}/messages`,
        { query },
        { signal }
      )
    }
  }
  
  async streamMessage(sessionId, query, signal, onStream) {
    const response = await fetch(`${API_BASE}/chat/sessions/${sessionId}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ query }),
      signal
    })
    
    if (!response.ok) {
      throw new Error('스트리밍 요청 실패')
    }
    
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let finalResponse = {
      answer: '',
      sources: [],
      metadata: {}
    }
    let errorMessage = null
    
    try {
      while (true) {
        const { done, value } = await reader.read()
        
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() // Keep incomplete line in buffer
        
        for (const line of lines) {
          if (!line.trim()) {
            continue
          }

          try {
            const data = JSON.parse(line)

            if (data.error) {
              errorMessage = data.message || data.error
              finalResponse.answer = errorMessage
              finalResponse.metadata = { ...finalResponse.metadata, error: errorMessage }
              break
            }

            if (data.status) {
              onStream(data.status)
            } else if (typeof data.content === 'string') {
              finalResponse.answer += data.content
              onStream(data.content)
            } else if (data.complete) {
              if (typeof data.answer === 'string') {
                finalResponse.answer = data.answer
              }
              finalResponse.sources = Array.isArray(data.sources) ? data.sources : []
              finalResponse.metadata = data.metadata || {}
            }
          } catch (e) {
            console.error('Failed to parse streaming data:', e)
          }
        }

        if (errorMessage) {
          break
        }
      }
    } finally {
      reader.releaseLock()
    }
    
    if (errorMessage) {
      return finalResponse
    }

    return finalResponse
  }
  
  async clearMessages(sessionId) {
    return this.client.delete(`/chat/sessions/${sessionId}/messages`)
  }
  
  async exportSession(sessionId) {
    return this.client.get(`/chat/sessions/${sessionId}/export`)
  }
  
  async importSession(sessionData) {
    return this.client.post('/chat/sessions/import', sessionData)
  }
}

export const chatAPI = new ChatAPI()

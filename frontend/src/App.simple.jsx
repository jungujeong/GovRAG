import React, { useState } from 'react'
import axios from 'axios'

function App() {
  const [query, setQuery] = useState('')
  const [response, setResponse] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    
    setLoading(true)
    try {
      // Use the correct backend port
      const res = await axios.post('http://localhost:8001/api/query/', { 
        query,
        top_k: 5
      })
      setResponse(res.data)
    } catch (error) {
      console.error('Error:', error)
      setResponse({ error: error.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>RAG Chatbot System</h1>
      
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter your question..."
          style={{ width: '100%', padding: '10px', fontSize: '16px' }}
          disabled={loading}
        />
        <button 
          type="submit" 
          disabled={loading}
          style={{ marginTop: '10px', padding: '10px 20px', fontSize: '16px' }}
        >
          {loading ? 'Loading...' : 'Submit'}
        </button>
      </form>
      
      {response && (
        <div style={{ marginTop: '20px', padding: '20px', background: '#f5f5f5', borderRadius: '5px' }}>
          {response.error ? (
            <div style={{ color: 'red' }}>
              <h3>Error:</h3>
              <p>{response.error}</p>
            </div>
          ) : (
            <>
              <h3>Answer:</h3>
              <p>{response.answer || 'No answer available'}</p>
              
              {response.sources && response.sources.length > 0 && (
                <>
                  <h4>Sources:</h4>
                  <ul>
                    {response.sources.map((source, idx) => (
                      <li key={idx}>
                        {source.doc_id} - Score: {source.score?.toFixed(3)}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

export default App
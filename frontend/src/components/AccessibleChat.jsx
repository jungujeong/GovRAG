import React, { useState, useRef, useEffect } from 'react'

function AccessibleChat({ onSubmit, isLoading }) {
  const [query, setQuery] = useState('')
  const [history, setHistory] = useState([])
  const inputRef = useRef(null)
  
  const handleSubmit = (e) => {
    e.preventDefault()
    
    if (query.trim() && !isLoading) {
      // Add to history
      setHistory([...history, query])
      
      // Submit query
      onSubmit(query)
      
      // Clear input
      setQuery('')
    }
  }
  
  const loadFromHistory = (historicalQuery) => {
    setQuery(historicalQuery)
    inputRef.current?.focus()
  }
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // Ctrl/Cmd + Enter to submit
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        handleSubmit(e)
      }
      
      // Escape to clear
      if (e.key === 'Escape') {
        setQuery('')
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [query])
  
  // Example queries
  const examples = [
    "2024년도 예산 편성 지침의 주요 변경사항은?",
    "탄소중립 관련 예산 규모는?",
    "디지털 전환 예산 증액 비율은?",
    "지방교부세율 변경 내용은?"
  ]
  
  return (
    <div className="space-y-6">
      <div className="card">
        <h2 className="text-2xl font-bold mb-4">질문하기</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label 
              htmlFor="query-input"
              className="block text-lg font-medium text-gray-700 mb-2"
            >
              질문을 입력하세요
            </label>
            
            <textarea
              id="query-input"
              ref={inputRef}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="예: 2024년 예산 변경사항은 무엇입니까?"
              className="input-large min-h-[100px] resize-none"
              disabled={isLoading}
              maxLength={1000}
              aria-describedby="query-help"
            />
            
            <p 
              id="query-help"
              className="mt-2 text-sm text-gray-600"
            >
              {query.length}/1000 글자 | Ctrl+Enter로 전송
            </p>
          </div>
          
          <div className="flex justify-between items-center">
            <button
              type="button"
              onClick={() => setQuery('')}
              className="btn-secondary"
              disabled={isLoading || !query}
            >
              지우기
            </button>
            
            <button
              type="submit"
              className="btn-primary flex items-center space-x-2"
              disabled={isLoading || !query.trim()}
            >
              {isLoading ? (
                <>
                  <span className="animate-spin">⏳</span>
                  <span>처리 중...</span>
                </>
              ) : (
                <>
                  <span>🔍</span>
                  <span>검색</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
      
      {/* Example Queries */}
      <div className="card">
        <h3 className="text-xl font-semibold mb-3">예시 질문</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {examples.map((example, index) => (
            <button
              key={index}
              onClick={() => setQuery(example)}
              className="text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors text-lg"
            >
              <span className="text-blue-600 mr-2">→</span>
              {example}
            </button>
          ))}
        </div>
      </div>
      
      {/* Query History */}
      {history.length > 0 && (
        <div className="card">
          <h3 className="text-xl font-semibold mb-3">최근 검색</h3>
          
          <div className="space-y-2">
            {history.slice(-5).reverse().map((q, index) => (
              <button
                key={index}
                onClick={() => loadFromHistory(q)}
                className="w-full text-left p-3 bg-gray-50 hover:bg-gray-100 rounded-lg transition-colors"
              >
                <span className="text-gray-500 mr-3">🕐</span>
                <span className="text-lg">{q}</span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default AccessibleChat
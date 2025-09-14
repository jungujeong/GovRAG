import { useState, useCallback, useRef } from 'react'

export const useStreamingResponse = () => {
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamedContent, setStreamedContent] = useState('')
  const [streamError, setStreamError] = useState(null)
  
  const abortControllerRef = useRef(null)
  const eventSourceRef = useRef(null)
  
  // SSE 스트리밍 시작
  const startStreaming = useCallback(async (url, options = {}) => {
    try {
      setIsStreaming(true)
      setStreamedContent('')
      setStreamError(null)
      
      // 이전 연결 종료
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      
      // AbortController 생성
      abortControllerRef.current = new AbortController()
      
      // Fetch API를 사용한 SSE 처리
      const response = await fetch(url, {
        method: options.method || 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
          ...options.headers
        },
        body: JSON.stringify(options.body),
        signal: abortControllerRef.current.signal
      })
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        
        // 마지막 줄이 완전하지 않을 수 있으므로 버퍼에 유지
        buffer = lines.pop() || ''
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              handleStreamData(data)
            } catch (err) {
              console.error('Failed to parse SSE data:', err)
            }
          }
        }
      }
      
    } catch (err) {
      if (err.name === 'AbortError') {
        console.log('Streaming aborted')
      } else {
        console.error('Streaming error:', err)
        setStreamError(err.message)
      }
    } finally {
      setIsStreaming(false)
    }
  }, [])
  
  // 스트림 데이터 처리
  const handleStreamData = useCallback((data) => {
    switch (data.type) {
      case 'token':
        setStreamedContent(prev => prev + data.content)
        break
        
      case 'complete':
        setStreamedContent('')
        if (data.response) {
          // 완료 시 콜백 처리
          if (options.onComplete) {
            options.onComplete(data.response)
          }
        }
        break
        
      case 'error':
        setStreamError(data.message)
        setIsStreaming(false)
        break
        
      case 'abort':
        setIsStreaming(false)
        if (data.partial) {
          setStreamedContent(data.partial)
        }
        break
        
      case 'meta':
        // 메타데이터 처리 (진행률, 상태 등)
        if (options.onMeta) {
          options.onMeta(data)
        }
        break
        
      default:
        console.log('Unknown stream data type:', data.type)
    }
  }, [])
  
  // 스트리밍 중단
  const stopStreaming = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    
    setIsStreaming(false)
  }, [])
  
  // EventSource를 사용한 대체 구현
  const startEventSource = useCallback((url, options = {}) => {
    try {
      setIsStreaming(true)
      setStreamedContent('')
      setStreamError(null)
      
      // 이전 연결 종료
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
      
      // EventSource 생성
      eventSourceRef.current = new EventSource(url)
      
      eventSourceRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleStreamData(data)
        } catch (err) {
          console.error('Failed to parse SSE data:', err)
        }
      }
      
      eventSourceRef.current.onerror = (error) => {
        console.error('EventSource error:', error)
        setStreamError('연결이 끊어졌습니다.')
        setIsStreaming(false)
        eventSourceRef.current?.close()
      }
      
      eventSourceRef.current.onopen = () => {
        console.log('EventSource connected')
      }
      
    } catch (err) {
      console.error('Failed to start EventSource:', err)
      setStreamError(err.message)
      setIsStreaming(false)
    }
  }, [handleStreamData])
  
  // 청크 단위로 콘텐츠 반환 (애니메이션용)
  const getAnimatedContent = useCallback((speed = 50) => {
    const [displayedContent, setDisplayedContent] = useState('')
    const intervalRef = useRef(null)
    
    useEffect(() => {
      if (streamedContent.length > displayedContent.length) {
        intervalRef.current = setInterval(() => {
          setDisplayedContent(prev => {
            const nextLength = Math.min(
              prev.length + 1,
              streamedContent.length
            )
            
            if (nextLength === streamedContent.length) {
              clearInterval(intervalRef.current)
            }
            
            return streamedContent.slice(0, nextLength)
          })
        }, speed)
      }
      
      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
        }
      }
    }, [streamedContent])
    
    return displayedContent
  }, [streamedContent])
  
  return {
    startStreaming,
    stopStreaming,
    startEventSource,
    isStreaming,
    streamedContent,
    streamError,
    getAnimatedContent
  }
}
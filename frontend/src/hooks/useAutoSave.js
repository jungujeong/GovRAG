import { useState, useEffect, useCallback, useRef } from 'react'
import axios from 'axios'

export const useAutoSave = (sessionId, messages, inputMessage) => {
  const [lastSaved, setLastSaved] = useState(null)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState(null)
  
  const saveTimerRef = useRef(null)
  const lastSavedDataRef = useRef(null)
  
  // 데이터가 변경되었는지 확인
  const hasChanges = useCallback(() => {
    const currentData = JSON.stringify({ messages, inputMessage })
    return currentData !== lastSavedDataRef.current
  }, [messages, inputMessage])
  
  // 저장 함수
  const save = useCallback(async () => {
    if (!sessionId || !hasChanges()) return
    
    try {
      setIsSaving(true)
      
      const draftData = {
        messages: messages || [],
        pending_request: inputMessage ? {
          content: inputMessage,
          timestamp: new Date().toISOString()
        } : null,
        scroll_position: window.scrollY
      }
      
      await axios.post('/api/sessions/draft/save', {
        session_id: sessionId,
        draft_data: draftData
      })
      
      lastSavedDataRef.current = JSON.stringify({ messages, inputMessage })
      setLastSaved(new Date())
      setError(null)
      
    } catch (err) {
      console.error('Auto-save failed:', err)
      setError('자동 저장 실패')
      // 자동 저장 실패는 조용히 처리 (사용자에게 방해되지 않도록)
    } finally {
      setIsSaving(false)
    }
  }, [sessionId, messages, inputMessage, hasChanges])
  
  // 즉시 저장
  const saveNow = useCallback(async () => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
      saveTimerRef.current = null
    }
    await save()
  }, [save])
  
  // 지연 저장 (디바운스)
  const scheduleSave = useCallback(() => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current)
    }
    
    saveTimerRef.current = setTimeout(() => {
      save()
    }, 2000) // 2초 후 저장
  }, [save])
  
  // 데이터 변경 감지 및 자동 저장
  useEffect(() => {
    if (sessionId && (messages?.length > 0 || inputMessage)) {
      scheduleSave()
    }
    
    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current)
      }
    }
  }, [sessionId, messages, inputMessage, scheduleSave])
  
  // 페이지 언로드 시 저장
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (hasChanges()) {
        // 동기적으로 저장 시도 (비권장이지만 언로드 시에는 필요)
        const draftData = {
          messages: messages || [],
          pending_request: inputMessage ? {
            content: inputMessage,
            timestamp: new Date().toISOString()
          } : null
        }
        
        // sendBeacon을 사용하여 비동기 저장
        const blob = new Blob([JSON.stringify({
          session_id: sessionId,
          draft_data: draftData
        })], { type: 'application/json' })
        
        navigator.sendBeacon('/api/sessions/draft/save', blob)
      }
    }
    
    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [sessionId, messages, inputMessage, hasChanges])
  
  // 정기적인 자동 저장 (30초마다)
  useEffect(() => {
    const interval = setInterval(() => {
      if (hasChanges()) {
        save()
      }
    }, 30000) // 30초
    
    return () => clearInterval(interval)
  }, [save, hasChanges])
  
  // 복원 함수
  const restore = useCallback(async () => {
    if (!sessionId) return null
    
    try {
      const response = await axios.get(`/api/sessions/${sessionId}/resume`)
      if (response.data?.resume_info) {
        return response.data.resume_info
      }
    } catch (err) {
      console.error('Failed to restore session:', err)
    }
    return null
  }, [sessionId])
  
  return {
    saveNow,
    restore,
    lastSaved,
    isSaving,
    error
  }
}
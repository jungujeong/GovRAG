import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

export const useSessionManager = () => {
  const [sessions, setSessions] = useState([])
  const [currentSessionId, setCurrentSessionId] = useState(null)
  const [currentSession, setCurrentSession] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  
  // 세션 목록 로드
  const loadSessions = useCallback(async () => {
    try {
      setLoading(true)
      const response = await axios.get('/api/sessions/list', {
        params: { limit: 100, archived: false }
      })
      
      if (response.data.sessions) {
        setSessions(response.data.sessions)
        
        // 현재 세션이 없으면 첫 번째 세션 선택
        if (!currentSessionId && response.data.sessions.length > 0) {
          const firstSession = response.data.sessions[0]
          setCurrentSessionId(firstSession.session_id)
          await loadSessionDetails(firstSession.session_id)
        }
      }
    } catch (err) {
      console.error('Failed to load sessions:', err)
      setError(err.message || '대화 목록을 불러올 수 없습니다.')
    } finally {
      setLoading(false)
    }
  }, [currentSessionId])
  
  // 세션 상세 정보 로드
  const loadSessionDetails = useCallback(async (sessionId) => {
    try {
      const response = await axios.get(`/api/sessions/${sessionId}`)
      if (response.data) {
        setCurrentSession(response.data)
        return response.data
      }
    } catch (err) {
      console.error('Failed to load session details:', err)
      setError(err.message || '대화를 불러올 수 없습니다.')
      return null
    }
  }, [])
  
  // 새 세션 생성
  const createSession = useCallback(async (initialQuery = null) => {
    try {
      const response = await axios.post('/api/sessions/create', {
        initial_query: initialQuery
      })
      
      if (response.data) {
        const newSession = response.data
        
        // 세션 목록에 추가
        setSessions(prev => [newSession, ...prev])
        
        // 새 세션을 현재 세션으로 설정
        setCurrentSessionId(newSession.session_id)
        setCurrentSession(newSession)
        
        return newSession
      }
    } catch (err) {
      console.error('Failed to create session:', err)
      setError(err.message || '새 대화를 시작할 수 없습니다.')
      throw err
    }
  }, [])
  
  // 세션 선택
  const selectSession = useCallback(async (sessionId) => {
    if (sessionId === currentSessionId) return
    
    try {
      setCurrentSessionId(sessionId)
      const details = await loadSessionDetails(sessionId)
      if (details) {
        setCurrentSession(details)
      }
    } catch (err) {
      console.error('Failed to select session:', err)
      throw err
    }
  }, [currentSessionId, loadSessionDetails])
  
  // 세션 업데이트
  const updateSession = useCallback(async (sessionId, updates) => {
    try {
      const response = await axios.patch(`/api/sessions/${sessionId}`, updates)
      
      if (response.data) {
        // 세션 목록 업데이트
        setSessions(prev => prev.map(s => 
          s.session_id === sessionId 
            ? { ...s, ...updates }
            : s
        ))
        
        // 현재 세션이면 상세 정보도 업데이트
        if (sessionId === currentSessionId) {
          setCurrentSession(prev => ({ ...prev, ...updates }))
        }
        
        return response.data
      }
    } catch (err) {
      console.error('Failed to update session:', err)
      throw err
    }
  }, [currentSessionId])
  
  // 세션 삭제
  const deleteSession = useCallback(async (sessionId) => {
    try {
      await axios.delete(`/api/sessions/${sessionId}`)
      
      // 세션 목록에서 제거
      setSessions(prev => prev.filter(s => s.session_id !== sessionId))
      
      // 현재 세션이 삭제되면 다른 세션 선택
      if (sessionId === currentSessionId) {
        const remainingSessions = sessions.filter(s => s.session_id !== sessionId)
        if (remainingSessions.length > 0) {
          await selectSession(remainingSessions[0].session_id)
        } else {
          setCurrentSessionId(null)
          setCurrentSession(null)
        }
      }
      
      return true
    } catch (err) {
      console.error('Failed to delete session:', err)
      throw err
    }
  }, [currentSessionId, sessions, selectSession])
  
  // 세션 목록 새로고침
  const refreshSessions = useCallback(async () => {
    await loadSessions()
  }, [loadSessions])
  
  // 메시지 추가 (로컬 업데이트)
  const addMessage = useCallback((sessionId, message) => {
    if (sessionId === currentSessionId) {
      setCurrentSession(prev => ({
        ...prev,
        messages: [...(prev?.messages || []), message]
      }))
    }
    
    // 세션 목록의 메시지 카운트 업데이트
    setSessions(prev => prev.map(s => 
      s.session_id === sessionId 
        ? { ...s, message_count: (s.message_count || 0) + 1 }
        : s
    ))
  }, [currentSessionId])
  
  // 초기 로드
  useEffect(() => {
    loadSessions()
  }, [])
  
  // 로컬 스토리지 동기화 (세션 ID 저장)
  useEffect(() => {
    if (currentSessionId) {
      localStorage.setItem('lastSessionId', currentSessionId)
    }
  }, [currentSessionId])
  
  // 페이지 로드 시 마지막 세션 복원
  useEffect(() => {
    const lastSessionId = localStorage.getItem('lastSessionId')
    if (lastSessionId && sessions.some(s => s.session_id === lastSessionId)) {
      selectSession(lastSessionId)
    }
  }, [sessions])
  
  return {
    sessions,
    currentSession,
    currentSessionId,
    loading,
    error,
    createSession,
    selectSession,
    updateSession,
    deleteSession,
    refreshSessions,
    addMessage
  }
}
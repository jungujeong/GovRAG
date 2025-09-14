import { useState, useEffect } from 'react'

/**
 * useLocalStorage - 로컬 스토리지 상태 관리 훅
 */
export function useLocalStorage(key, initialValue) {
  // 초기값 로드
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const item = window.localStorage.getItem(key)
      return item ? JSON.parse(item) : initialValue
    } catch (error) {
      console.error(`Error loading localStorage key "${key}":`, error)
      return initialValue
    }
  })

  // 값 설정 함수
  const setValue = (value) => {
    try {
      // 함수형 업데이트 지원
      const valueToStore = value instanceof Function ? value(storedValue) : value
      setStoredValue(valueToStore)
      window.localStorage.setItem(key, JSON.stringify(valueToStore))
    } catch (error) {
      console.error(`Error setting localStorage key "${key}":`, error)
    }
  }

  return [storedValue, setValue]
}

/**
 * useSessionStorage - 세션 스토리지 상태 관리 훅
 */
export function useSessionStorage(key, initialValue) {
  // 초기값 로드
  const [storedValue, setStoredValue] = useState(() => {
    try {
      const item = window.sessionStorage.getItem(key)
      return item ? JSON.parse(item) : initialValue
    } catch (error) {
      console.error(`Error loading sessionStorage key "${key}":`, error)
      return initialValue
    }
  })

  // 값 설정 함수
  const setValue = (value) => {
    try {
      const valueToStore = value instanceof Function ? value(storedValue) : value
      setStoredValue(valueToStore)
      window.sessionStorage.setItem(key, JSON.stringify(valueToStore))
    } catch (error) {
      console.error(`Error setting sessionStorage key "${key}":`, error)
    }
  }

  return [storedValue, setValue]
}

/**
 * useAutoSave - 자동 저장 훅
 */
export function useAutoSave(data, saveFunction, delay = 2000) {
  useEffect(() => {
    const timer = setTimeout(() => {
      if (data) {
        saveFunction(data)
      }
    }, delay)

    return () => clearTimeout(timer)
  }, [data, saveFunction, delay])
}

/**
 * useRetry - 재시도 로직 훅
 */
export function useRetry(fn, maxRetries = 3, backoff = [500, 2000, 5000]) {
  const [retryCount, setRetryCount] = useState(0)
  const [isRetrying, setIsRetrying] = useState(false)

  const executeWithRetry = async (...args) => {
    let lastError
    
    for (let i = 0; i <= maxRetries; i++) {
      try {
        setIsRetrying(i > 0)
        const result = await fn(...args)
        setRetryCount(0)
        setIsRetrying(false)
        return result
      } catch (error) {
        lastError = error
        setRetryCount(i)
        
        // 429 (Too Many Requests) or 504 (Gateway Timeout)
        if (error.status === 429 || error.status === 504) {
          if (i < maxRetries) {
            const delay = backoff[i] || backoff[backoff.length - 1]
            await new Promise(resolve => setTimeout(resolve, delay))
            continue
          }
        }
        
        // Other errors - don't retry
        break
      }
    }
    
    setIsRetrying(false)
    throw lastError
  }

  return { executeWithRetry, retryCount, isRetrying }
}
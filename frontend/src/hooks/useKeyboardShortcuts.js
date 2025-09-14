import { useEffect } from 'react'

export const useKeyboardShortcuts = (shortcuts) => {
  useEffect(() => {
    const handleKeyDown = (event) => {
      // 입력 필드에서는 단축키 무시
      if (
        event.target.tagName === 'INPUT' ||
        event.target.tagName === 'TEXTAREA' ||
        event.target.contentEditable === 'true'
      ) {
        // Escape는 항상 동작
        if (event.key !== 'Escape') {
          return
        }
      }
      
      // 단축키 조합 생성
      const key = []
      if (event.ctrlKey) key.push('Ctrl')
      if (event.altKey) key.push('Alt')
      if (event.shiftKey) key.push('Shift')
      if (event.metaKey) key.push('Cmd')
      
      // 특수 키 처리
      const keyName = event.key === ' ' ? 'Space' : event.key
      key.push(keyName.length === 1 ? keyName.toUpperCase() : keyName)
      
      const shortcut = key.join('+')
      
      // 단축키 실행
      if (shortcuts[shortcut]) {
        event.preventDefault()
        shortcuts[shortcut](event)
      }
    }
    
    document.addEventListener('keydown', handleKeyDown)
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [shortcuts])
}
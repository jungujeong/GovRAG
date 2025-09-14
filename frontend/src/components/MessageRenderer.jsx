import React from 'react'
import StructuredAnswer from './StructuredAnswer'

function MessageRenderer({ message, onCitationClick }) {
  // 마크다운 렌더링 함수
  const renderMarkdown = (text) => {
    if (!text) return null
    
    // 리스트 처리
    const processLists = (lines) => {
      const result = []
      let currentList = null
      let currentListType = null
      
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        
        // 불릿 리스트 체크
        const bulletMatch = line.match(/^[-*•]\s+(.+)/)
        // 번호 리스트 체크
        const numberMatch = line.match(/^(\d+)\.\s+(.+)/)
        
        if (bulletMatch || numberMatch) {
          const content = bulletMatch ? bulletMatch[1] : numberMatch[2]
          const type = bulletMatch ? 'ul' : 'ol'
          
          if (currentListType !== type) {
            // 이전 리스트 종료
            if (currentList) {
              result.push(
                <ul key={`list-${result.length}`} className="list-disc list-inside space-y-1 my-2">
                  {currentList}
                </ul>
              )
            }
            currentList = []
            currentListType = type
          }
          
          currentList.push(
            <li key={`item-${i}`} className="text-gray-800">
              {processInline(content)}
            </li>
          )
        } else {
          // 리스트가 아닌 경우
          if (currentList) {
            result.push(
              <ul key={`list-${result.length}`} className="list-disc list-inside space-y-1 my-2">
                {currentList}
              </ul>
            )
            currentList = null
            currentListType = null
          }
          
          if (line.trim()) {
            result.push(
              <div key={`line-${i}`} className={i > 0 ? 'mt-2' : ''}>
                {processInline(line)}
              </div>
            )
          }
        }
      }
      
      // 마지막 리스트 처리
      if (currentList) {
        result.push(
          <ul key={`list-${result.length}`} className="list-disc list-inside space-y-1 my-2">
            {currentList}
          </ul>
        )
      }
      
      return result
    }
    
    // 인라인 요소 처리 (bold, italic, code, citation)
    const processInline = (str) => {
      const pattern = /(\[(\d+)\])|(\*\*(.+?)\*\*)|(\*(.+?)\*)|(`(.+?)`)/g
      const parts = []
      let lastIndex = 0
      let match
      
      while ((match = pattern.exec(str)) !== null) {
        // 매치 이전 텍스트 추가
        if (match.index > lastIndex) {
          parts.push(str.substring(lastIndex, match.index))
        }
        
        // 매치된 패턴 처리
        if (match[2]) {
          // 인용 [1]
          const citationNum = parseInt(match[2])
          parts.push(
            <button
              key={match.index}
              onClick={() => onCitationClick && onCitationClick(citationNum)}
              className="inline-flex items-center px-1.5 py-0.5 rounded-md text-blue-600 hover:bg-blue-50 hover:text-blue-700 font-medium cursor-pointer transition-colors"
              title={`출처 ${citationNum} 보기`}
            >
              [{match[2]}]
            </button>
          )
        } else if (match[4]) {
          // Bold **text**
          parts.push(
            <strong key={match.index} className="font-bold">
              {match[4]}
            </strong>
          )
        } else if (match[6]) {
          // Italic *text*
          parts.push(
            <em key={match.index} className="italic">
              {match[6]}
            </em>
          )
        } else if (match[8]) {
          // Code `text`
          parts.push(
            <code key={match.index} className="px-1 py-0.5 bg-gray-100 rounded text-sm font-mono">
              {match[8]}
            </code>
          )
        }
        
        lastIndex = match.index + match[0].length
      }
      
      // 남은 텍스트 추가
      if (lastIndex < str.length) {
        parts.push(str.substring(lastIndex))
      }
      
      return parts.length > 0 ? parts : str
    }
    
    // 줄바꿈 처리 및 리스트 처리
    const lines = text.split('\n')
    return processLists(lines)
  }
  
  // 사용자 메시지
  if (message.role === 'user') {
    return <div className="whitespace-pre-wrap">{message.content}</div>
  }
  
  // 어시스턴트 메시지
  if (message.role === 'assistant') {
    // 완료된 메시지는 구조화된 답변으로 표시
    if (message.isComplete && (message.sources || message.key_facts)) {
      return (
        <StructuredAnswer 
          answer={{
            answer: message.content,
            key_facts: message.key_facts || [],
            details: message.details || '',
            sources: message.sources || []
          }}
          onCitationClick={onCitationClick}
          compact={true}
        />
      )
    }
    
    // 스트리밍 중이거나 일반 텍스트
    return (
      <div className="message-content">
        {renderMarkdown(message.content)}
      </div>
    )
  }
  
  // 에러 메시지
  if (message.error) {
    return (
      <div className="text-red-600">
        {message.content}
      </div>
    )
  }
  
  // 기본
  return <div className="whitespace-pre-wrap">{message.content}</div>
}

export default MessageRenderer
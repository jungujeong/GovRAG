import React from 'react'

function StatusIndicator({ status }) {
  const getStatusColor = () => {
    switch (status.status) {
      case 'healthy':
        return 'status-healthy'
      case 'degraded':
        return 'status-degraded'
      case 'unhealthy':
        return 'status-unhealthy'
      default:
        return 'bg-gray-500'
    }
  }
  
  const getStatusText = () => {
    switch (status.status) {
      case 'healthy':
        return '정상'
      case 'degraded':
        return '제한됨'
      case 'unhealthy':
        return '오류'
      case 'checking':
        return '확인 중...'
      default:
        return '알 수 없음'
    }
  }
  
  return (
    <div className="flex items-center space-x-4">
      {/* Main Status */}
      <div className="flex items-center">
        <span className={`status-dot ${getStatusColor()} animate-pulse`}></span>
        <span className="text-lg font-medium">{getStatusText()}</span>
      </div>
      
      {/* Component Status */}
      {status.components && Object.keys(status.components).length > 0 && (
        <div className="flex items-center space-x-3 text-sm">
          {status.components.ollama !== undefined && (
            <div className="flex items-center">
              <span className={`status-dot ${status.components.ollama ? 'status-healthy' : 'status-unhealthy'}`}></span>
              <span>Ollama</span>
            </div>
          )}
          
          {status.components.retriever !== undefined && (
            <div className="flex items-center">
              <span className={`status-dot ${status.components.retriever ? 'status-healthy' : 'status-unhealthy'}`}></span>
              <span>검색</span>
            </div>
          )}
          
          {status.components.reranker !== undefined && (
            <div className="flex items-center">
              <span className={`status-dot ${status.components.reranker ? 'status-healthy' : 'status-degraded'}`}></span>
              <span>리랭커</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default StatusIndicator
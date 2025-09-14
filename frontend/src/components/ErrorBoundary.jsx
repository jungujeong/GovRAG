import React from 'react'
import './ErrorBoundary.css'

class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0
    }
  }
  
  static getDerivedStateFromError(error) {
    return { hasError: true }
  }
  
  componentDidCatch(error, errorInfo) {
    console.error('Error caught by boundary:', error, errorInfo)
    
    this.setState(prevState => ({
      error,
      errorInfo,
      errorCount: prevState.errorCount + 1
    }))
    
    // 에러 로깅 (프로덕션에서는 에러 추적 서비스로 전송)
    if (process.env.NODE_ENV === 'production') {
      // 에러 추적 서비스로 전송
      this.logErrorToService(error, errorInfo)
    }
  }
  
  logErrorToService = (error, errorInfo) => {
    // 실제로는 Sentry, LogRocket 등으로 전송
    const errorData = {
      message: error.toString(),
      stack: error.stack,
      componentStack: errorInfo.componentStack,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent
    }
    
    // API로 에러 전송
    fetch('/api/errors/log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(errorData)
    }).catch(err => {
      console.error('Failed to log error:', err)
    })
  }
  
  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null
    })
    
    // 페이지 새로고침 (마지막 수단)
    if (this.state.errorCount > 3) {
      window.location.reload()
    }
  }
  
  handleReload = () => {
    window.location.reload()
  }
  
  render() {
    if (this.state.hasError) {
      return (
        <div className="error-boundary">
          <div className="error-container">
            <div className="error-icon">
              <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
                <circle cx="40" cy="40" r="35" stroke="#ef4444" strokeWidth="4"/>
                <path d="M40 25v20m0 5v5" stroke="#ef4444" strokeWidth="4" strokeLinecap="round"/>
              </svg>
            </div>
            
            <h1 className="error-title">앗, 문제가 발생했습니다!</h1>
            
            <p className="error-message">
              예상치 못한 오류가 발생했습니다.<br />
              불편을 드려 죄송합니다.
            </p>
            
            {/* 개발 환경에서만 상세 에러 표시 */}
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="error-details">
                <summary>오류 상세 정보 (개발자용)</summary>
                <pre className="error-stack">
                  {this.state.error.toString()}
                  {this.state.errorInfo?.componentStack}
                </pre>
              </details>
            )}
            
            <div className="error-actions">
              <button
                onClick={this.handleReset}
                className="btn btn-primary"
              >
                다시 시도
              </button>
              
              <button
                onClick={this.handleReload}
                className="btn btn-secondary"
              >
                페이지 새로고침
              </button>
            </div>
            
            <div className="error-help">
              <p>문제가 계속되면 다음을 시도해보세요:</p>
              <ul>
                <li>브라우저 캐시를 삭제하세요</li>
                <li>다른 브라우저를 사용해보세요</li>
                <li>잠시 후 다시 시도하세요</li>
              </ul>
            </div>
            
            {this.state.errorCount > 1 && (
              <div className="error-warning">
                오류가 {this.state.errorCount}번 발생했습니다.
                계속 문제가 발생하면 관리자에게 문의하세요.
              </div>
            )}
          </div>
        </div>
      )
    }
    
    return this.props.children
  }
}

export default ErrorBoundary
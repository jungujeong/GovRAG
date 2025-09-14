import React from 'react'
import './LoadingOverlay.css'

const LoadingOverlay = ({ 
  message = '로딩 중...', 
  showSpinner = true,
  transparent = false,
  fullScreen = true 
}) => {
  return (
    <div className={`loading-overlay ${transparent ? 'transparent' : ''} ${fullScreen ? 'fullscreen' : ''}`}>
      <div className="loading-content">
        {showSpinner && (
          <div className="loading-spinner">
            <div className="spinner-ring"></div>
            <div className="spinner-ring"></div>
            <div className="spinner-ring"></div>
          </div>
        )}
        
        <div className="loading-message">
          {message}
        </div>
        
        <div className="loading-dots">
          <span></span>
          <span></span>
          <span></span>
        </div>
      </div>
    </div>
  )
}

export default LoadingOverlay
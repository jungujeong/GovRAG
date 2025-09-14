/**
 * Server connection monitor
 * Detects server connection status and handles disconnections
 */
class ServerMonitor {
  constructor() {
    this.isConnected = true
    this.checkInterval = null
    this.listeners = new Set()
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
  }

  // Start monitoring
  start() {
    // Initial check
    this.checkConnection()
    
    // Regular health checks every 5 seconds
    this.checkInterval = setInterval(() => {
      this.checkConnection()
    }, 5000)
    
    // Also check on visibility change
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        this.checkConnection()
      }
    })
    
    // Check on online/offline events
    window.addEventListener('online', () => this.checkConnection())
    window.addEventListener('offline', () => this.handleDisconnect())
  }

  // Stop monitoring
  stop() {
    if (this.checkInterval) {
      clearInterval(this.checkInterval)
      this.checkInterval = null
    }
  }

  // Check server connection
  async checkConnection() {
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 3000)
      
      const response = await fetch('http://localhost:8000/api/health', {
        method: 'GET',
        signal: controller.signal
      })
      
      clearTimeout(timeoutId)
      
      if (response.ok) {
        this.handleConnect()
      } else {
        this.handleDisconnect()
      }
    } catch (error) {
      // Server is down or network error - but don't spam console
      // Only log disconnect if we were previously connected
      if (this.isConnected) {
        this.handleDisconnect()
      }
    }
  }

  // Handle successful connection
  handleConnect() {
    const wasDisconnected = !this.isConnected
    this.isConnected = true
    this.reconnectAttempts = 0
    
    if (wasDisconnected) {
      console.log('Server connection restored')
      this.notifyListeners({
        type: 'reconnected',
        isConnected: true
      })
    }
  }

  // Handle disconnection
  handleDisconnect() {
    const wasConnected = this.isConnected
    this.isConnected = false
    
    if (wasConnected) {
      console.log('Server connection lost')
      
      // Notify all listeners
      this.notifyListeners({
        type: 'disconnected',
        isConnected: false
      })
      
      // Cancel all active operations
      this.cancelAllOperations()
      
      // Try to reconnect
      this.attemptReconnect()
    }
  }

  // Cancel all active operations
  cancelAllOperations() {
    // Import streamingStore dynamically to avoid circular dependency
    import('./streamingManager.js').then(({ default: streamingManager }) => {
      if (streamingManager) {
        // Abort all active streams
        streamingManager.abortAllStreams()
      }
    }).catch(console.error)
    
    // Clear any pending requests
    if (window.pendingRequests) {
      window.pendingRequests.forEach(controller => {
        try {
          controller.abort()
        } catch (e) {
          // Ignore errors
        }
      })
      window.pendingRequests.clear()
    }
  }

  // Attempt to reconnect
  async attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('Max reconnection attempts reached')
      this.notifyListeners({
        type: 'reconnect_failed',
        isConnected: false
      })
      return
    }
    
    this.reconnectAttempts++
    console.log(`Reconnection attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts}`)
    
    // Wait before attempting
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts - 1), 10000)
    await new Promise(resolve => setTimeout(resolve, delay))
    
    // Try to reconnect
    await this.checkConnection()
    
    // If still disconnected, try again
    if (!this.isConnected && this.reconnectAttempts < this.maxReconnectAttempts) {
      this.attemptReconnect()
    }
  }

  // Subscribe to connection status changes
  subscribe(listener) {
    this.listeners.add(listener)
    // Immediately notify current status
    listener({
      type: 'status',
      isConnected: this.isConnected
    })
    return () => this.listeners.delete(listener)
  }

  // Notify all listeners
  notifyListeners(event) {
    this.listeners.forEach(listener => {
      try {
        listener(event)
      } catch (error) {
        console.error('Server monitor listener error:', error)
      }
    })
  }

  // Get current connection status
  getStatus() {
    return {
      isConnected: this.isConnected,
      reconnectAttempts: this.reconnectAttempts
    }
  }
}

// Singleton instance
const serverMonitor = new ServerMonitor()

// React hook for using server monitor
import { useState, useEffect } from 'react'

export function useServerConnection() {
  const [isConnected, setIsConnected] = useState(serverMonitor.isConnected)
  const [connectionEvent, setConnectionEvent] = useState(null)
  
  useEffect(() => {
    const unsubscribe = serverMonitor.subscribe((event) => {
      setIsConnected(event.isConnected)
      setConnectionEvent(event)
    })
    
    return unsubscribe
  }, [])
  
  return { isConnected, connectionEvent }
}

// Start monitoring when module loads
serverMonitor.start()

export default serverMonitor
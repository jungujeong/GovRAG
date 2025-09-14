import { useState, useEffect } from 'react'

/**
 * Global streaming state store
 * Manages streaming states across session switches
 */
class StreamingStore {
  constructor() {
    // Map of sessionId -> streamingState
    this.activeStreams = new Map()
    this.listeners = new Set()
  }

  // Start a new stream
  startStream(sessionId, turnId, initialMessage) {
    const streamState = {
      sessionId,
      turnId,
      isStreaming: true,
      isComplete: false,
      message: initialMessage || {
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString(),
        isStreaming: true,
        turnId: turnId
      },
      startTime: Date.now(),
      lastUpdate: Date.now()
    }
    
    this.activeStreams.set(sessionId, streamState)
    this.notifyListeners(sessionId, streamState)
    
    return streamState
  }

  // Update stream content
  updateStream(sessionId, updates) {
    const stream = this.activeStreams.get(sessionId)
    if (!stream) return null
    
    const updatedStream = {
      ...stream,
      ...updates,
      lastUpdate: Date.now()
    }
    
    if (updates.content !== undefined && stream.message) {
      updatedStream.message = {
        ...stream.message,
        content: updates.content
      }
    }
    
    if (updates.message) {
      updatedStream.message = {
        ...stream.message,
        ...updates.message
      }
    }
    
    this.activeStreams.set(sessionId, updatedStream)
    this.notifyListeners(sessionId, updatedStream)
    
    return updatedStream
  }

  // Complete a stream
  completeStream(sessionId, finalMessage) {
    const stream = this.activeStreams.get(sessionId)
    if (!stream) return null
    
    const completedStream = {
      ...stream,
      isStreaming: false,
      isComplete: true,
      message: finalMessage || stream.message,
      endTime: Date.now()
    }
    
    // Keep completed streams for a short time for UI continuity
    this.activeStreams.set(sessionId, completedStream)
    this.notifyListeners(sessionId, completedStream)
    
    // Remove after 5 seconds
    setTimeout(() => {
      if (this.activeStreams.get(sessionId)?.isComplete) {
        this.activeStreams.delete(sessionId)
      }
    }, 5000)
    
    return completedStream
  }

  // Get stream state
  getStream(sessionId) {
    return this.activeStreams.get(sessionId)
  }

  // Check if session has active stream
  hasActiveStream(sessionId) {
    const stream = this.activeStreams.get(sessionId)
    return stream && stream.isStreaming
  }

  // Abort a stream
  abortStream(sessionId) {
    const stream = this.activeStreams.get(sessionId)
    if (!stream) return false
    
    const abortedStream = {
      ...stream,
      isStreaming: false,
      isAborted: true,
      endTime: Date.now()
    }
    
    this.activeStreams.set(sessionId, abortedStream)
    this.notifyListeners(sessionId, abortedStream)
    
    // Clean up after abort
    setTimeout(() => {
      this.activeStreams.delete(sessionId)
    }, 2000)
    
    return true
  }

  // Subscribe to stream updates
  subscribe(listener) {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  // Notify all listeners
  notifyListeners(sessionId, streamState) {
    this.listeners.forEach(listener => {
      try {
        listener(sessionId, streamState)
      } catch (error) {
        console.error('Listener error:', error)
      }
    })
  }

  // Clear all streams
  clearAll() {
    this.activeStreams.clear()
    this.notifyListeners(null, null)
  }

  // Get all active streams
  getAllActiveStreams() {
    return Array.from(this.activeStreams.entries())
      .filter(([_, stream]) => stream.isStreaming)
      .map(([sessionId, stream]) => ({ sessionId, ...stream }))
  }
}

// Singleton instance
const streamingStore = new StreamingStore()

// React hook for using the streaming store
export function useStreamingStore(sessionId) {
  const [streamState, setStreamState] = useState(() => 
    streamingStore.getStream(sessionId)
  )
  
  useEffect(() => {
    // Get initial state
    setStreamState(streamingStore.getStream(sessionId))
    
    // Subscribe to updates
    const unsubscribe = streamingStore.subscribe((updatedSessionId, state) => {
      if (updatedSessionId === sessionId) {
        setStreamState(state)
      }
    })
    
    return unsubscribe
  }, [sessionId])
  
  return streamState
}

export default streamingStore
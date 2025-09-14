/**
 * Global streaming manager to handle SSE connections across tab switches
 */
class StreamingManager {
  constructor() {
    this.activeStreams = new Map() // sessionId:turnId -> {reader, abortController, state}
    this.streamCallbacks = new Map() // sessionId:turnId -> callback
  }

  // 스트리밍 시작
  startStream(sessionId, turnId, callback) {
    const streamKey = `${sessionId}:${turnId}`
    
    // 이미 진행 중인 스트림이 있으면 콜백만 업데이트
    if (this.activeStreams.has(streamKey)) {
      this.streamCallbacks.set(streamKey, callback)
      const stream = this.activeStreams.get(streamKey)
      
      // 현재 상태 즉시 전달
      if (stream.state) {
        callback(stream.state)
      }
      return stream.abortController
    }

    // 새 스트림 시작
    const abortController = new AbortController()
    this.activeStreams.set(streamKey, {
      abortController,
      state: { isStreaming: true, partialAnswer: '', tokenCount: 0 }
    })
    this.streamCallbacks.set(streamKey, callback)
    
    return abortController
  }

  // 스트림 상태 업데이트
  updateStreamState(sessionId, turnId, state) {
    const streamKey = `${sessionId}:${turnId}`
    const stream = this.activeStreams.get(streamKey)
    
    if (stream) {
      stream.state = { ...stream.state, ...state }
      
      // 콜백 호출
      const callback = this.streamCallbacks.get(streamKey)
      if (callback) {
        callback(stream.state)
      }
    }
  }

  // 스트림 완료
  completeStream(sessionId, turnId) {
    const streamKey = `${sessionId}:${turnId}`
    
    this.activeStreams.delete(streamKey)
    this.streamCallbacks.delete(streamKey)
  }

  // 스트림 중단
  abortStream(sessionId, turnId) {
    const streamKey = `${sessionId}:${turnId}`
    const stream = this.activeStreams.get(streamKey)
    
    if (stream && stream.abortController) {
      stream.abortController.abort()
      this.completeStream(sessionId, turnId)
    }
  }

  // 진행 중인 스트림 확인
  hasActiveStream(sessionId, turnId) {
    return this.activeStreams.has(`${sessionId}:${turnId}`)
  }

  // 세션의 모든 스트림 중단
  abortSessionStreams(sessionId) {
    for (const [key, stream] of this.activeStreams.entries()) {
      if (key.startsWith(`${sessionId}:`)) {
        if (stream.abortController) {
          stream.abortController.abort()
        }
        this.activeStreams.delete(key)
        this.streamCallbacks.delete(key)
      }
    }
  }

  // 스트림 상태 가져오기
  getStreamState(sessionId, turnId) {
    const streamKey = `${sessionId}:${turnId}`
    const stream = this.activeStreams.get(streamKey)
    return stream ? stream.state : null
  }

  // 모든 스트림 중단
  abortAllStreams() {
    for (const [key, stream] of this.activeStreams.entries()) {
      if (stream.abortController) {
        stream.abortController.abort()
      }
    }
    this.activeStreams.clear()
    this.streamCallbacks.clear()
  }
}

// 싱글톤 인스턴스
const streamingManager = new StreamingManager()

export default streamingManager
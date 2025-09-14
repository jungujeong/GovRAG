import { create } from 'zustand'

export const useChatStore = create((set, get) => ({
  messages: [],
  isLoading: false,
  streamingContent: '',
  error: null,
  
  // Load messages
  loadMessages: (messages) => {
    set({ messages, error: null })
  },
  
  // Add message
  addMessage: (message) => {
    set(state => ({
      messages: [...state.messages, {
        id: Date.now().toString(),
        timestamp: new Date().toISOString(),
        ...message
      }]
    }))
  },
  
  // Update last message
  updateLastMessage: (updates) => {
    set(state => {
      const newMessages = [...state.messages]
      if (newMessages.length > 0) {
        newMessages[newMessages.length - 1] = {
          ...newMessages[newMessages.length - 1],
          ...updates
        }
      }
      return { messages: newMessages }
    })
  },
  
  // Clear messages
  clearMessages: () => {
    set({ messages: [], error: null })
  },
  
  // Set loading state
  setLoading: (loading) => {
    set({ isLoading: loading })
  },
  
  // Set streaming content
  setStreamingContent: (content) => {
    set({ streamingContent: content })
  },
  
  // Append to streaming content
  appendStreamingContent: (content) => {
    set(state => ({
      streamingContent: state.streamingContent + content
    }))
  },
  
  // Set error
  setError: (error) => {
    set({ error, isLoading: false })
  },
  
  // Clear error
  clearError: () => {
    set({ error: null })
  }
}))
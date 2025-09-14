import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { chatAPI } from '../services/chatAPI'

export const useSessionStore = create(
  persist(
    (set, get) => ({
      sessions: [],
      currentSessionId: null,
      
      // Load sessions from server
      loadSessions: async () => {
        try {
          const response = await chatAPI.listSessions()
          set({ sessions: response.sessions })
          
          // Select first session if none selected
          const state = get()
          if (!state.currentSessionId && response.sessions.length > 0) {
            set({ currentSessionId: response.sessions[0].id })
          }
        } catch (error) {
          console.error('Failed to load sessions:', error)
          throw error
        }
      },
      
      // Create new session
      createSession: async (title) => {
        try {
          const response = await chatAPI.createSession(title)
          const newSession = response.session
          
          set(state => ({
            sessions: [newSession, ...state.sessions],
            currentSessionId: newSession.id
          }))
          
          return newSession
        } catch (error) {
          console.error('Failed to create session:', error)
          throw error
        }
      },
      
      // Select session
      selectSession: (sessionId) => {
        set({ currentSessionId: sessionId })
      },
      
      // Update session
      updateSession: async (sessionId, updates) => {
        try {
          const response = await chatAPI.updateSession(sessionId, updates)
          const updatedSession = response.session
          
          set(state => ({
            sessions: state.sessions.map(s =>
              s.id === sessionId ? updatedSession : s
            )
          }))
          
          return updatedSession
        } catch (error) {
          console.error('Failed to update session:', error)
          throw error
        }
      },
      
      // Delete session
      deleteSession: async (sessionId) => {
        try {
          await chatAPI.deleteSession(sessionId)
          
          set(state => {
            const newSessions = state.sessions.filter(s => s.id !== sessionId)
            let newCurrentId = state.currentSessionId
            
            // If deleted session was current, select another
            if (state.currentSessionId === sessionId) {
              newCurrentId = newSessions.length > 0 ? newSessions[0].id : null
            }
            
            return {
              sessions: newSessions,
              currentSessionId: newCurrentId
            }
          })
        } catch (error) {
          console.error('Failed to delete session:', error)
          throw error
        }
      },
      
      // Clear all sessions
      clearSessions: () => {
        set({
          sessions: [],
          currentSessionId: null
        })
      }
    }),
    {
      name: 'session-storage',
      partialize: (state) => ({
        currentSessionId: state.currentSessionId
      })
    }
  )
)
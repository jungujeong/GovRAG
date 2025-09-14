import { create } from 'zustand'
import { documentAPI } from '../services/documentAPI'

export const useDocumentStore = create((set, get) => ({
  documents: [],
  isUploading: false,
  uploadProgress: 0,
  
  // Load documents
  loadDocuments: async () => {
    try {
      const docs = await documentAPI.listDocuments()
      set({ documents: docs })
      return docs
    } catch (error) {
      console.error('Failed to load documents:', error)
      throw error
    }
  },
  
  // Upload documents
  uploadDocuments: async (files) => {
    set({ isUploading: true, uploadProgress: 0 })
    
    try {
      const result = await documentAPI.uploadBatch(files, (progress) => {
        set({ uploadProgress: progress })
      })
      
      // Reload documents
      await get().loadDocuments()
      
      set({ isUploading: false, uploadProgress: 0 })
      return result
    } catch (error) {
      set({ isUploading: false, uploadProgress: 0 })
      console.error('Failed to upload documents:', error)
      throw error
    }
  },
  
  // Delete document
  deleteDocument: async (docId) => {
    try {
      await documentAPI.deleteDocument(docId)
      
      set(state => ({
        documents: state.documents.filter(d => d.id !== docId)
      }))
    } catch (error) {
      console.error('Failed to delete document:', error)
      throw error
    }
  },
  
  // Clear documents
  clearDocuments: () => {
    set({ documents: [] })
  }
}))
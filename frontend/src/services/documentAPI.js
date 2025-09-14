import axios from 'axios'

const API_BASE = '/api'

class DocumentAPI {
  constructor() {
    this.client = axios.create({
      baseURL: API_BASE,
      timeout: 60000 // Longer timeout for file uploads
    })
  }
  
  async listDocuments() {
    const response = await this.client.get('/documents/list')
    return response.data
  }
  
  async uploadBatch(files, onProgress) {
    const formData = new FormData()
    files.forEach(file => {
      formData.append('files', file)
    })
    
    const response = await this.client.post('/documents/upload-batch', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress) {
          const percentCompleted = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
          onProgress(percentCompleted)
        }
      }
    })
    
    return response.data
  }
  
  async deleteDocument(docId) {
    const response = await this.client.delete(`/documents/${docId}`)
    return response.data
  }
  
  async getDocumentInfo(docId) {
    const response = await this.client.get(`/documents/${docId}/info`)
    return response.data
  }
  
  async searchDocuments(query) {
    const response = await this.client.get('/documents/search', {
      params: { q: query }
    })
    return response.data
  }
}

export const documentAPI = new DocumentAPI()
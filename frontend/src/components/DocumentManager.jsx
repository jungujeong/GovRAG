import React, { useState } from 'react'
import axios from 'axios'
import DocumentDetail from './DocumentDetail'

function DocumentManager({ documents, onRefresh }) {
  const [isDeleting, setIsDeleting] = useState(false)
  const [selectedDoc, setSelectedDoc] = useState(null)
  
  const handleDelete = async (filename) => {
    if (!window.confirm(`정말로 "${filename}"을 삭제하시겠습니까?`)) {
      return
    }
    
    setIsDeleting(true)
    
    try {
      await axios.delete(`/api/documents/${filename}`)
      alert('문서가 삭제되었습니다.')
      onRefresh()
    } catch (error) {
      console.error('Delete failed:', error)
      alert('문서 삭제에 실패했습니다.')
    } finally {
      setIsDeleting(false)
    }
  }
  
  const handleReindex = async () => {
    if (!window.confirm('모든 문서를 다시 인덱싱하시겠습니까? 시간이 오래 걸릴 수 있습니다.')) {
      return
    }
    
    try {
      await axios.post('/api/documents/reindex')
      alert('인덱싱이 시작되었습니다. 백그라운드에서 진행됩니다.')
    } catch (error) {
      console.error('Reindex failed:', error)
      alert('인덱싱 시작에 실패했습니다.')
    }
  }
  
  const handleResetAll = async () => {
    if (!window.confirm('⚠️ 경고: 모든 문서와 인덱스가 완전히 삭제됩니다!\n\n정말로 전체 초기화를 진행하시겠습니까?')) {
      return
    }
    
    if (!window.confirm('다시 한 번 확인합니다. 이 작업은 되돌릴 수 없습니다.\n\n계속하시겠습니까?')) {
      return
    }
    
    setIsDeleting(true)
    
    try {
      const response = await axios.delete('/api/documents/reset/all')
      alert(`전체 초기화 완료:\n- ${response.data.documents_deleted}개 문서 삭제됨\n- 모든 인덱스 초기화됨`)
      onRefresh()
    } catch (error) {
      console.error('Reset all failed:', error)
      alert('전체 초기화에 실패했습니다.')
    } finally {
      setIsDeleting(false)
    }
  }
  
  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / 1024 / 1024).toFixed(1) + ' MB'
  }
  
  const formatDate = (timestamp) => {
    return new Date(timestamp * 1000).toLocaleString('ko-KR')
  }
  
  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-900">
          문서 관리 ({documents.length}개)
        </h2>
        
        <div className="space-x-4">
          <button
            onClick={onRefresh}
            className="btn-secondary"
          >
            🔄 새로고침
          </button>
          
          <button
            onClick={handleReindex}
            className="btn-primary"
          >
            🔧 전체 재인덱싱
          </button>
          
          <button
            onClick={handleResetAll}
            disabled={isDeleting}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isDeleting ? '처리 중...' : '⚠️ 전체 초기화'}
          </button>
        </div>
      </div>
      
      {documents.length === 0 ? (
        <div className="card text-center py-12">
          <p className="text-xl text-gray-500">
            업로드된 문서가 없습니다.
          </p>
          <p className="text-lg text-gray-400 mt-2">
            문서 업로드 탭에서 파일을 추가해주세요.
          </p>
        </div>
      ) : (
        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-lg font-semibold text-gray-900">
                    파일명
                  </th>
                  <th className="px-4 py-3 text-left text-lg font-semibold text-gray-900">
                    유형
                  </th>
                  <th className="px-4 py-3 text-left text-lg font-semibold text-gray-900">
                    크기
                  </th>
                  <th className="px-4 py-3 text-left text-lg font-semibold text-gray-900">
                    수정일
                  </th>
                  <th className="px-4 py-3 text-center text-lg font-semibold text-gray-900">
                    작업
                  </th>
                </tr>
              </thead>
              
              <tbody className="divide-y divide-gray-200">
                {documents.map((doc) => (
                  <tr 
                    key={doc.filename}
                    className="hover:bg-gray-50 transition-colors"
                  >
                    <td className="px-4 py-4">
                      <div className="flex items-center">
                        <span className="text-2xl mr-3">
                          {doc.type === 'PDF' ? '📄' : '📃'}
                        </span>
                        <span className="text-lg font-medium">
                          {doc.filename}
                        </span>
                      </div>
                    </td>
                    
                    <td className="px-4 py-4">
                      <span className={`
                        px-3 py-1 rounded-full text-sm font-medium
                        ${doc.type === 'PDF' 
                          ? 'bg-red-100 text-red-800' 
                          : 'bg-blue-100 text-blue-800'
                        }
                      `}>
                        {doc.type}
                      </span>
                    </td>
                    
                    <td className="px-4 py-4 text-lg">
                      {formatFileSize(doc.size)}
                    </td>
                    
                    <td className="px-4 py-4 text-lg text-gray-600">
                      {formatDate(doc.modified)}
                    </td>
                    
                    <td className="px-4 py-4">
                      <div className="flex justify-center space-x-2">
                        <button
                          onClick={() => setSelectedDoc(doc)}
                          className="text-blue-600 hover:text-blue-800 text-lg font-medium"
                        >
                          상세
                        </button>
                        
                        <span className="text-gray-300">|</span>
                        
                        <button
                          onClick={() => handleDelete(doc.filename)}
                          disabled={isDeleting}
                          className="text-red-600 hover:text-red-800 text-lg font-medium disabled:opacity-50"
                        >
                          삭제
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      
      {/* Document Details Modal */}
      {selectedDoc && (
        <DocumentDetail 
          document={selectedDoc} 
          onClose={() => setSelectedDoc(null)} 
        />
      )}
    </div>
  )
}

export default DocumentManager
import React, { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'

function LargeUploadZone({ onUpload }) {
  const [files, setFiles] = useState([])
  
  const onDrop = useCallback(acceptedFiles => {
    setFiles(acceptedFiles)
  }, [])
  
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/x-hwp': ['.hwp']
    },
    multiple: true
  })
  
  const handleUpload = () => {
    if (files.length > 0) {
      onUpload(files)
      setFiles([])
    }
  }
  
  const removeFile = (index) => {
    setFiles(files.filter((_, i) => i !== index))
  }
  
  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">문서 업로드</h2>
      
      <div
        {...getRootProps()}
        className={`
          border-4 border-dashed rounded-xl p-12 text-center cursor-pointer
          transition-all duration-300
          ${isDragActive 
            ? 'border-blue-500 bg-blue-50' 
            : 'border-gray-300 hover:border-gray-400 bg-white'
          }
        `}
      >
        <input {...getInputProps()} />
        
        <div className="space-y-4">
          <div className="text-6xl">
            📂
          </div>
          
          <p className="text-xl font-medium text-gray-700">
            {isDragActive 
              ? '파일을 여기에 놓으세요'
              : '클릭하거나 파일을 드래그하여 업로드'
            }
          </p>
          
          <p className="text-lg text-gray-500">
            PDF, HWP 파일 지원 (여러 파일 가능)
          </p>
        </div>
      </div>
      
      {files.length > 0 && (
        <div className="card">
          <h3 className="text-xl font-semibold mb-4">
            선택된 파일 ({files.length}개)
          </h3>
          
          <ul className="space-y-2">
            {files.map((file, index) => (
              <li 
                key={index}
                className="flex items-center justify-between p-3 bg-gray-50 rounded-lg"
              >
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">
                    {file.name.endsWith('.pdf') ? '📄' : '📃'}
                  </span>
                  <div>
                    <p className="font-medium text-lg">{file.name}</p>
                    <p className="text-gray-500">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                </div>
                
                <button
                  onClick={() => removeFile(index)}
                  className="text-red-600 hover:text-red-800 text-xl font-bold"
                  aria-label={`${file.name} 제거`}
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
          
          <div className="mt-6 flex justify-end space-x-4">
            <button
              onClick={() => setFiles([])}
              className="btn-secondary"
            >
              초기화
            </button>
            
            <button
              onClick={handleUpload}
              className="btn-primary"
            >
              업로드 시작
            </button>
          </div>
        </div>
      )}
      
      <div className="bg-blue-50 border-l-4 border-blue-400 p-4 rounded">
        <p className="text-lg text-blue-700">
          💡 <strong>팁:</strong> 업로드된 문서는 자동으로 인덱싱되어 검색 가능합니다.
        </p>
      </div>
    </div>
  )
}

export default LargeUploadZone
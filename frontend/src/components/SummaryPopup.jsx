/**
 * SummaryPopup Component
 * 문서 요약을 표시하는 팝업 컴포넌트
 */
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const SummaryPopup = ({ isOpen, onClose, documentId, documentName }) => {
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch summary when popup opens
  useEffect(() => {
    if (isOpen && documentId) {
      fetchSummary();
    } else {
      // Reset state when popup closes
      setSummaryData(null);
      setError(null);
    }
  }, [isOpen, documentId]);

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);

    try {
      console.log(`Fetching summary for document: ${documentId}`);

      const response = await axios.get(
        `http://localhost:8000/api/documents/${encodeURIComponent(documentId)}/summary`,
        {
          timeout: 30000, // 30 second timeout
          headers: {
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.data && response.data.status === 'success') {
        setSummaryData(response.data.data);
      } else {
        throw new Error('Invalid response format');
      }

    } catch (err) {
      console.error('Failed to fetch summary:', err);

      if (err.response?.status === 404) {
        setError('이 문서의 요약이 아직 생성되지 않았습니다. 잠시 후 다시 시도해주세요.');
      } else if (err.response?.status === 503) {
        setError('요약 서비스를 사용할 수 없습니다.');
      } else if (err.code === 'ECONNABORTED') {
        setError('요약을 불러오는 중 시간이 초과되었습니다. 다시 시도해주세요.');
      } else {
        setError(`요약을 불러오는 중 오류가 발생했습니다: ${err.message}`);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = () => {
    fetchSummary();
  };

  const formatDate = (dateString) => {
    try {
      const date = new Date(dateString);
      return date.toLocaleString('ko-KR', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return dateString;
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-auto bg-black bg-opacity-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[80vh] overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-gray-200">
          <div className="flex-1">
            <h2 className="text-xl font-bold text-gray-800 mb-1">
              문서 요약
            </h2>
            <p className="text-sm text-gray-600 truncate">
              {documentName || documentId}
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="px-3 py-1.5 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              title="요약 새로고침"
            >
              {loading ? '새로고침 중...' : '새로고침'}
            </button>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 p-1 rounded-full transition-colors"
              title="닫기"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[60vh]">
          {loading && (
            <div className="text-center py-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
              <p className="mt-4 text-gray-600">요약을 불러오고 있습니다...</p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-red-400 mt-0.5 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                <div>
                  <p className="text-red-800 font-medium">오류 발생</p>
                  <p className="text-red-700 text-sm mt-1">{error}</p>
                  <button
                    onClick={handleRefresh}
                    className="mt-2 text-sm text-red-600 hover:text-red-800 underline"
                  >
                    다시 시도
                  </button>
                </div>
              </div>
            </div>
          )}

          {summaryData && !loading && !error && (
            <div className="space-y-4">
              {/* Summary Content */}
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-gray-800 mb-3">📄 요약 내용</h3>
                <div className="text-gray-700 leading-relaxed whitespace-pre-line">
                  {summaryData.summary}
                </div>
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-4 border-t border-gray-200">
                <div className="bg-blue-50 rounded-lg p-3">
                  <h4 className="text-sm font-semibold text-blue-800 mb-1">생성 일시</h4>
                  <p className="text-blue-700 text-sm">
                    {summaryData.generated_at ? formatDate(summaryData.generated_at) : '정보 없음'}
                  </p>
                </div>

                <div className="bg-green-50 rounded-lg p-3">
                  <h4 className="text-sm font-semibold text-green-800 mb-1">문서 크기</h4>
                  <p className="text-green-700 text-sm">
                    {summaryData.content_length ?
                      `${summaryData.content_length.toLocaleString()}자` :
                      '정보 없음'
                    }
                  </p>
                </div>

                {summaryData.status && (
                  <div className="bg-purple-50 rounded-lg p-3 md:col-span-2">
                    <h4 className="text-sm font-semibold text-purple-800 mb-1">상태</h4>
                    <p className="text-purple-700 text-sm">
                      {summaryData.status === 'completed' ? '✅ 완료' :
                       summaryData.status === 'error' ? '❌ 오류' :
                       summaryData.status}
                    </p>
                  </div>
                )}
              </div>

              {/* File Info */}
              {summaryData.file_name && (
                <div className="bg-gray-50 rounded-lg p-3 border-t border-gray-200 mt-4">
                  <h4 className="text-sm font-semibold text-gray-800 mb-1">원본 파일</h4>
                  <p className="text-gray-700 text-sm font-mono">
                    {summaryData.file_name}
                  </p>
                </div>
              )}
            </div>
          )}

          {!loading && !error && !summaryData && (
            <div className="text-center py-8">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              <p className="mt-2 text-gray-500">요약 정보가 없습니다.</p>
              <button
                onClick={handleRefresh}
                className="mt-2 text-blue-600 hover:text-blue-800 text-sm underline"
              >
                다시 확인
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end items-center p-4 bg-gray-50 border-t border-gray-200">
          <button
            onClick={onClose}
            className="px-4 py-2 text-gray-600 hover:text-gray-800 font-medium transition-colors"
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
};

export default SummaryPopup;
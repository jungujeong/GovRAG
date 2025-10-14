/**
 * SummaryPopup Component
 * 문서 요약을 표시하는 팝업 컴포넌트
 */
import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';

const SummaryPopup = ({ isOpen, onClose, documentId, documentName }) => {
  const [summaryData, setSummaryData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const abortControllerRef = useRef(null);
  const fetchTimeoutRef = useRef(null);
  const isMountedRef = useRef(false);
  const retryCountRef = useRef(0); // Track retry attempts to prevent infinite loops
  const MAX_RETRIES = 2; // Maximum retry attempts

  // Fetch summary when popup opens
  useEffect(() => {
    if (!isOpen || !documentId) {
      // Reset when popup is closed
      isMountedRef.current = false;
      return;
    }

    // Prevent React Strict Mode double-call
    if (isMountedRef.current) {
      console.log('Already mounted, skipping duplicate fetch');
      return;
    }
    isMountedRef.current = true;

    // Reset state for fresh start
    console.log(`Popup opened for document: ${documentId}`);
    setSummaryData(null);
    setError(null);
    setLoading(false);

    // Fetch after a small delay to ensure state is reset
    fetchTimeoutRef.current = setTimeout(() => {
      fetchSummary();
    }, 50);

    return () => {
      // Cleanup on unmount or popup close
      console.log('Cleaning up popup');
      if (fetchTimeoutRef.current) {
        clearTimeout(fetchTimeoutRef.current);
        fetchTimeoutRef.current = null;
      }

      // Cancel ongoing request if exists
      if (abortControllerRef.current) {
        console.log('Canceling ongoing request due to popup close');
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }

      isMountedRef.current = false;
    };
  }, [isOpen, documentId]);

  const fetchSummary = async () => {
    setLoading(true);
    setError(null);

    // Create new AbortController
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      console.log(`Fetching summary for document: ${documentId}`);

      const response = await axios.get(
        `http://localhost:8000/api/documents/summary`,
        {
          params: { doc_id: documentId },
          timeout: 60000, // 1 minute timeout for fetching
          headers: {
            'Content-Type': 'application/json'
          },
          signal: controller.signal
        }
      );

      if (response.data && response.data.status === 'success') {
        const data = response.data.data;

        // Check if summary has error status OR error message
        const summaryText = (data.summary || '').trim();
        const hasError =
          data.status === 'error' ||
          summaryText.length < 20 || // Too short to be a valid summary
          summaryText.includes('오류가 발생했습니다') ||
          summaryText.includes('생성할 수 없습니다') ||
          summaryText.includes('실패') ||
          summaryText.endsWith(':') || // Empty error message ending with colon
          /오류.*:\s*$/.test(summaryText); // Error message with nothing after colon

        if (hasError) {
          // Check if we've exceeded max retries
          if (retryCountRef.current >= MAX_RETRIES) {
            console.log(`Max retries (${MAX_RETRIES}) reached, showing error`);
            setError('요약 생성에 반복적으로 실패했습니다. 재요약 버튼을 눌러 다시 시도해주세요.');
            setSummaryData(null); // Don't show error summary
            retryCountRef.current = 0; // Reset for next time
            return;
          }

          retryCountRef.current++;
          console.log(`Summary has error (attempt ${retryCountRef.current}/${MAX_RETRIES}), auto-regenerating...`);
          // Delete the error summary and regenerate
          await handleGenerate();
          return; // handleGenerate will set the data
        }

        // Success - reset retry count
        retryCountRef.current = 0;
        setSummaryData(data);
      } else {
        throw new Error('Invalid response format');
      }

    } catch (err) {
      // Silently ignore abort errors (popup was closed or request was canceled)
      if (axios.isCancel(err) || err.name === 'CanceledError' || err.name === 'AbortError') {
        console.log('Request was canceled');
        // Don't show error message for canceled requests
        return;
      }

      if (err.response?.status === 404) {
        // Summary doesn't exist - automatically generate it (this is expected, not an error)
        // But check retry count first
        if (retryCountRef.current >= MAX_RETRIES) {
          console.log(`Max retries (${MAX_RETRIES}) reached for 404, showing error`);
          setError('이 문서의 요약이 아직 생성되지 않았습니다. 재요약 버튼을 눌러 생성해주세요.');
          retryCountRef.current = 0; // Reset for next time
          return;
        }

        retryCountRef.current++;
        console.log(`Summary not found (attempt ${retryCountRef.current}/${MAX_RETRIES}), auto-generating...`);
        await handleGenerate();
        return; // handleGenerate will set the data or error
      }

      // Only log actual errors (not 404 which is expected)
      console.error('Failed to fetch summary:', err);

      if (err.response?.status === 503) {
        setError('요약 서비스를 사용할 수 없습니다.');
      } else if (err.code === 'ECONNABORTED') {
        setError('요약을 불러오는 중 시간이 초과되었습니다.');
      } else {
        setError(`요약을 불러오는 중 오류가 발생했습니다: ${err.message}`);
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleRefresh = () => {
    if (!loading) {
      retryCountRef.current = 0; // Reset retry count for manual refresh
      fetchSummary();
    }
  };

  const handleGenerate = async (isManual = false) => {
    if (loading) {
      console.log('Already generating, skipping duplicate request');
      return;
    }

    // Reset retry count only for manual generation
    if (isManual) {
      retryCountRef.current = 0;
    }

    setLoading(true);
    setError(null);

    // Create new AbortController
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      console.log(`Generating summary for document: ${documentId}`);

      // First, delete any existing error summary
      try {
        await axios.delete(
          `http://localhost:8000/api/documents/summary`,
          {
            params: { doc_id: documentId },
            timeout: 5000,
            signal: controller.signal
          }
        );
        console.log('Deleted old summary (if any)');
      } catch (deleteErr) {
        // Silently ignore abort errors
        if (axios.isCancel(deleteErr) || deleteErr.name === 'CanceledError' || deleteErr.name === 'AbortError') {
          console.log('Delete request was canceled');
          // Don't show error message for canceled requests
          return;
        }
        console.log('No old summary to delete or delete failed:', deleteErr.message);
      }

      // Generate new summary
      const response = await axios.post(
        `http://localhost:8000/api/documents/summary`,
        null,
        {
          params: { doc_id: documentId },
          timeout: 180000, // 3 minute timeout for slower computers
          headers: {
            'Content-Type': 'application/json'
          },
          signal: controller.signal
        }
      );

      if (response.data && response.data.status === 'success') {
        const data = response.data.data;

        // Check if generated summary also has error status
        if (data.status === 'error') {
          setError(`요약 생성 실패: ${data.summary}`);
          setSummaryData(null);
        } else {
          // Success - reset retry count
          retryCountRef.current = 0;
          setSummaryData(data);
          setError(null);
        }
      } else {
        throw new Error('Invalid response format');
      }

    } catch (err) {
      // Silently ignore abort errors
      if (axios.isCancel(err) || err.name === 'CanceledError' || err.name === 'AbortError') {
        console.log('Generation was canceled');
        // Don't show error message for canceled requests
        return;
      }

      console.error('Failed to generate summary:', err);

      if (err.response?.status === 503) {
        setError('요약 서비스를 사용할 수 없습니다.');
      } else if (err.code === 'ECONNABORTED') {
        setError('요약 생성 중 시간이 초과되었습니다. 컴퓨터 성능이 느리거나 문서가 클 경우 발생할 수 있습니다. 다시 시도하거나 더 가벼운 모델(qwen3:4b 등)을 사용해주세요.');
      } else {
        setError(`요약 생성 중 오류가 발생했습니다: ${err.message}`);
      }
    } finally {
      setLoading(false);
      abortControllerRef.current = null;
    }
  };

  // Cancel ongoing request
  const handleCancel = () => {
    if (abortControllerRef.current) {
      console.log('User manually canceled the request');
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setLoading(false);
      // Don't set error message, just stop loading
    }
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
              onClick={() => handleGenerate(true)}
              disabled={loading}
              className="px-3 py-1.5 text-sm bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              title="요약 재생성"
            >
              {loading ? '생성 중...' : '재요약'}
            </button>
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
              <p className="mt-4 text-gray-600 font-medium">요약을 생성하고 있습니다...</p>
              <p className="mt-2 text-gray-500 text-sm">
                컴퓨터 사양에 따라 최대 3분 정도 소요될 수 있습니다
              </p>
              <p className="mt-1 text-gray-500 text-sm">
                창을 닫거나 아래 버튼을 클릭하면 중단됩니다
              </p>
              <button
                onClick={handleCancel}
                className="mt-4 px-4 py-2 text-sm bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
              >
                중단
              </button>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
              <div className="flex items-start">
                <svg className="w-5 h-5 text-red-400 mt-0.5 mr-3 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.732-.833-2.5 0L4.268 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
                <div className="flex-1">
                  <p className="text-red-800 font-medium">오류 발생</p>
                  <p className="text-red-700 text-sm mt-1">{error}</p>
                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => handleGenerate(true)}
                      disabled={loading}
                      className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {loading ? '생성 중...' : '요약 생성'}
                    </button>
                    <button
                      onClick={handleRefresh}
                      disabled={loading}
                      className="px-4 py-2 text-sm text-red-600 hover:text-red-800 border border-red-300 rounded disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      다시 시도
                    </button>
                  </div>
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
import React, { useState, useEffect } from 'react';

const MonitoringDashboard = () => {
  const [stats, setStats] = useState(null);
  const [recentQueries, setRecentQueries] = useState([]);
  const [qualityIssues, setQualityIssues] = useState(null);
  const [performanceIssues, setPerformanceIssues] = useState(null);
  const [trends, setTrends] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedDate, setSelectedDate] = useState(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  const fetchData = async () => {
    try {
      setLoading(true);
      const dateParam = selectedDate ? `?date=${selectedDate}` : '';

      // Fetch statistics
      const statsRes = await fetch(`${API_BASE}/admin/logs/statistics${dateParam}`);
      const statsData = await statsRes.json();
      setStats(statsData);

      // Fetch recent queries
      const queriesRes = await fetch(`${API_BASE}/admin/logs/recent?limit=10${selectedDate ? `&date=${selectedDate}` : ''}`);
      const queriesData = await queriesRes.json();
      setRecentQueries(queriesData);

      // Fetch quality issues
      const qualityRes = await fetch(`${API_BASE}/admin/logs/quality-issues${dateParam}`);
      const qualityData = await qualityRes.json();
      setQualityIssues(qualityData);

      // Fetch performance issues
      const perfRes = await fetch(`${API_BASE}/admin/logs/performance-issues${dateParam}`);
      const perfData = await perfRes.json();
      setPerformanceIssues(perfData);

      // Fetch trends
      const trendsRes = await fetch(`${API_BASE}/admin/logs/trends?days=7`);
      const trendsData = await trendsRes.json();
      setTrends(trendsData);

    } catch (error) {
      console.error('Failed to fetch monitoring data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();

    // Auto-refresh every 30 seconds
    let interval;
    if (autoRefresh) {
      interval = setInterval(fetchData, 30000);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [selectedDate, autoRefresh]);

  const formatTime = (ms) => {
    if (ms < 1000) return `${ms.toFixed(0)}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  const formatPercent = (value) => {
    return `${(value * 100).toFixed(1)}%`;
  };

  if (loading && !stats) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-xl text-gray-600">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">RAG 시스템 모니터링</h1>
            <p className="text-gray-600 mt-1">실시간 성능 및 품질 대시보드</p>
          </div>
          <div className="flex gap-4">
            <input
              type="date"
              value={selectedDate || ''}
              onChange={(e) => setSelectedDate(e.target.value || null)}
              className="px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={() => setAutoRefresh(!autoRefresh)}
              className={`px-4 py-2 rounded-lg ${
                autoRefresh ? 'bg-green-500 text-white' : 'bg-gray-300 text-gray-700'
              }`}
            >
              {autoRefresh ? '자동 새로고침 ON' : '자동 새로고침 OFF'}
            </button>
            <button
              onClick={fetchData}
              className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
            >
              새로고침
            </button>
            <button
              onClick={() => window.open(`${API_BASE}/admin/logs/report${selectedDate ? `?date=${selectedDate}` : ''}`, '_blank')}
              className="px-4 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600"
            >
              HTML 리포트
            </button>
          </div>
        </div>

        {stats && (
          <>
            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
              {/* Performance Stats */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  ⚡ 성능 메트릭
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-600">총 질의 수</span>
                    <span className="font-bold text-gray-900">{stats.total_queries}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">평균 응답 시간</span>
                    <span className="font-bold text-gray-900">
                      {formatTime(stats.performance?.avg_total_time_ms || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">평균 검색 시간</span>
                    <span className="font-bold text-gray-900">
                      {formatTime(stats.performance?.avg_search_time_ms || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">평균 생성 시간</span>
                    <span className="font-bold text-gray-900">
                      {formatTime(stats.performance?.avg_generation_time_ms || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">총 토큰 사용</span>
                    <span className="font-bold text-gray-900">
                      {(stats.performance?.total_tokens || 0).toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>

              {/* Quality Stats */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  ✅ 품질 메트릭
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-600">평균 신뢰도</span>
                    <span className={`font-bold ${
                      (stats.quality?.avg_confidence || 0) >= 0.7 ? 'text-green-600' : 'text-yellow-600'
                    }`}>
                      {formatPercent(stats.quality?.avg_confidence || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">고신뢰도 비율</span>
                    <span className="font-bold text-green-600">
                      {formatPercent(stats.quality?.high_confidence_rate || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">평균 출처 수</span>
                    <span className="font-bold text-gray-900">
                      {(stats.quality?.avg_sources_per_query || 0).toFixed(1)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">환각 탐지율</span>
                    <span className={`font-bold ${
                      (stats.quality?.hallucination_rate || 0) === 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {formatPercent(stats.quality?.hallucination_rate || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">일반응답 비율</span>
                    <span className={`font-bold ${
                      (stats.quality?.generic_response_rate || 0) < 0.2 ? 'text-green-600' : 'text-yellow-600'
                    }`}>
                      {formatPercent(stats.quality?.generic_response_rate || 0)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Error Stats */}
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                  🔴 오류 및 이슈
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-600">오류 발생 건수</span>
                    <span className={`font-bold ${
                      (stats.errors?.error_count || 0) === 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {stats.errors?.error_count || 0}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">오류율</span>
                    <span className="font-bold text-gray-900">
                      {formatPercent(stats.errors?.error_rate || 0)}
                    </span>
                  </div>
                  {qualityIssues && (
                    <>
                      <div className="flex justify-between">
                        <span className="text-gray-600">저신뢰도 응답</span>
                        <span className="font-bold text-yellow-600">
                          {qualityIssues.counts?.low_confidence || 0}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">환각 탐지</span>
                        <span className="font-bold text-red-600">
                          {qualityIssues.counts?.hallucinations || 0}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">출처 없음</span>
                        <span className="font-bold text-yellow-600">
                          {qualityIssues.counts?.no_sources || 0}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            {/* Trends Chart */}
            {trends && trends.trends && trends.trends.length > 0 && (
              <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">📈 7일 트렌드</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {trends.trends.map((day, idx) => (
                    <div key={idx} className="border rounded-lg p-4">
                      <div className="text-sm text-gray-600 mb-2">{day.date}</div>
                      <div className="text-2xl font-bold text-gray-900">{day.total_queries}</div>
                      <div className="text-xs text-gray-500">질의</div>
                      <div className="mt-2 space-y-1">
                        <div className="text-xs text-gray-600">
                          신뢰도: <span className="font-semibold">{formatPercent(day.avg_confidence)}</span>
                        </div>
                        <div className="text-xs text-gray-600">
                          응답: <span className="font-semibold">{formatTime(day.avg_response_time_ms)}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Queries */}
            <div className="bg-white rounded-lg shadow-lg p-6 mb-8">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">📝 최근 질의</h3>
              <div className="space-y-3">
                {recentQueries.slice(0, 5).map((query, idx) => {
                  const qual = query.quality_metrics || {};
                  const perf = query.performance_metrics || {};

                  return (
                    <div key={idx} className="border-l-4 border-blue-500 pl-4 py-2 bg-gray-50 rounded">
                      <div className="flex justify-between items-start">
                        <div className="flex-1">
                          <div className="font-medium text-gray-900">{query.query}</div>
                          <div className="text-sm text-gray-500 mt-1">
                            {query.timestamp} | 타입: {query.query_type}
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <span className={`px-2 py-1 text-xs rounded ${
                            qual.confidence_score >= 0.7
                              ? 'bg-green-100 text-green-800'
                              : qual.confidence_score >= 0.4
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-red-100 text-red-800'
                          }`}>
                            신뢰도: {(qual.confidence_score || 0).toFixed(2)}
                          </span>
                          <span className="px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded">
                            {formatTime(perf.total_time_ms || 0)}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Quality Issues */}
            {qualityIssues && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
                <div className="bg-white rounded-lg shadow-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 text-yellow-600">
                    ⚠️ 저신뢰도 응답 ({qualityIssues.counts?.low_confidence || 0})
                  </h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {qualityIssues.low_confidence?.slice(0, 5).map((item, idx) => (
                      <div key={idx} className="text-sm border-l-2 border-yellow-400 pl-3 py-1">
                        <div className="text-gray-900">{item.query}</div>
                        <div className="text-gray-500 text-xs">
                          신뢰도: {(item.confidence || 0).toFixed(2)} | {item.timestamp}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-white rounded-lg shadow-lg p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4 text-red-600">
                    🚨 환각 탐지 ({qualityIssues.counts?.hallucinations || 0})
                  </h3>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {qualityIssues.hallucinations?.slice(0, 5).map((item, idx) => (
                      <div key={idx} className="text-sm border-l-2 border-red-400 pl-3 py-1">
                        <div className="text-gray-900">{item.query}</div>
                        <div className="text-gray-500 text-xs">{item.timestamp}</div>
                        <div className="text-gray-600 text-xs mt-1 italic">
                          {item.response}...
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Performance Issues */}
            {performanceIssues && (
              <div className="bg-white rounded-lg shadow-lg p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  ⏱️ 느린 질의 ({performanceIssues.counts?.slow_queries || 0})
                </h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {performanceIssues.slow_queries?.slice(0, 5).map((item, idx) => (
                    <div key={idx} className="text-sm border-l-2 border-orange-400 pl-3 py-1 bg-orange-50 rounded">
                      <div className="flex justify-between">
                        <div className="text-gray-900">{item.query}</div>
                        <div className="text-orange-600 font-bold">
                          {formatTime(item.total_time_ms)}
                        </div>
                      </div>
                      <div className="text-gray-500 text-xs mt-1">
                        검색: {formatTime(item.search_time_ms)} | 생성: {formatTime(item.generation_time_ms)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default MonitoringDashboard;

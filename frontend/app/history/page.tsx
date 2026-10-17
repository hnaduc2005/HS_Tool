'use client';
import { useEffect, useState } from 'react';
import { api, type Search } from '@/lib/api';
import { HistoryList, type HistoryScope } from '@/components/history-list';
export default function HistoryPage() {
  const [items, setItems] = useState<Search[]>([]);
  const [scope, setScope] = useState<HistoryScope>('all');
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  const [loading, setLoading] = useState(true);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError('');
    if (page === 1) { setItems([]); setHasMore(false); }
    api<Search[]>(`/classification/history?scope=${scope}&page=${page}`, { signal: controller.signal }).then(rows => {
      if (controller.signal.aborted) return;
      setItems(previous => page === 1 ? rows : [...new Map([...previous, ...rows].map(item => [item.id, item])).values()]);
      setHasMore(rows.length === 20);
    }).catch(cause => {
      if (!controller.signal.aborted) setError(cause instanceof Error ? `Không thể tải lịch sử: ${cause.message}` : 'Không thể tải lịch sử. Vui lòng thử lại.');
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [scope, page, refresh]);

  function changeScope(value: HistoryScope) {
    if (value === scope) return;
    setItems([]); setHasMore(false); setLoading(true); setError(''); setScope(value); setPage(1);
  }
  function reload() {
    setLoading(true); setPage(1); setRefresh(value => value + 1);
  }
  return <HistoryList items={items} scope={scope} loading={loading} error={error} hasMore={hasMore}
    onScopeChange={changeScope} onRefresh={reload}
    onRetry={() => { setLoading(true); setRefresh(value => value + 1); }}
    onLoadMore={() => { if (!loading) { setLoading(true); setPage(value => value + 1); } }}/>
}

'use client';

import Link from 'next/link';
import { hasAiServiceFailure, searchCodeLabel, type Search } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export type HistoryScope = 'all' | 'mine' | 'legacy';
type Props = {
  items: Search[];
  scope: HistoryScope;
  loading: boolean;
  error: string;
  hasMore: boolean;
  onScopeChange: (scope: HistoryScope) => void;
  onRetry: () => void;
  onLoadMore: () => void;
  onRefresh: () => void;
};

export function HistoryList({ items, scope, loading, error, hasMore, onScopeChange, onRetry, onLoadMore, onRefresh }: Props) {
  return <main className="mx-auto max-w-5xl px-5 py-12">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <div><h1 className="text-3xl font-bold">Lịch sử tra cứu</h1><p className="mt-2 max-w-2xl text-sm text-slate-500">Các lượt tra cứu của bạn và lịch sử cũ trước khi hệ thống yêu cầu đăng nhập.</p></div>
      <Button variant="outline" disabled={loading} onClick={onRefresh}>Làm mới</Button>
    </div>
    <div role="group" aria-label="Lọc lịch sử tra cứu" className="mt-6 flex flex-wrap gap-2">
      {([['all', 'Tất cả'], ['mine', 'Của tôi'], ['legacy', 'Lịch sử cũ']] as const).map(([value, label]) => <Button key={value} size="sm" variant={scope === value ? 'default' : 'outline'} aria-pressed={scope === value} onClick={() => onScopeChange(value)}>{label}</Button>)}
    </div>
    {scope === 'legacy' && <p className="mt-4 text-sm text-slate-500">Các lượt này chưa gắn với tài khoản vì được lưu trước khi bật đăng nhập.</p>}
    {error && <div role="alert" className="mt-6 rounded-xl border border-red-100 bg-red-50 p-4"><p className="text-sm text-red-700">{error}</p><Button className="mt-3" size="sm" variant="outline" disabled={loading} onClick={onRetry}>Thử lại</Button></div>}
    <div aria-busy={loading} className="mt-7 space-y-3">
      {items.map(item => <Card key={item.id} className="p-5"><div className="flex flex-wrap justify-between gap-3"><div className="min-w-0 flex-1">
        <span className="rounded-full bg-mint px-2 py-1 text-xs font-semibold text-forest">{item.userId === null ? 'Lịch sử cũ' : 'Của tôi'}</span>
        <p className="mt-3 break-words font-semibold">{item.productDescription.slice(0, 130)}</p>
        <p className="mt-2 text-sm text-slate-500">{hasAiServiceFailure(item) ? 'Lỗi kết nối AI' : searchCodeLabel(item)} · {new Date(item.createdAt).toLocaleString('vi-VN')}</p>
      </div><Link href={`/?search=${encodeURIComponent(item.id)}`} className="self-center text-sm font-semibold text-forest hover:underline">Xem kết quả</Link></div></Card>)}
      {!items.length && loading && <p role="status" className="text-sm text-slate-500">Đang tải lịch sử tra cứu…</p>}
      {!items.length && !loading && !error && <p className="text-sm text-slate-500">{scope === 'mine' ? 'Bạn chưa có lượt tra cứu gắn với tài khoản. Chọn “Lịch sử cũ” để xem các lượt trước khi bật đăng nhập.' : scope === 'legacy' ? 'Không có lượt tra cứu cũ chưa gắn tài khoản.' : 'Chưa có lượt tra cứu.'}</p>}
    </div>
    {hasMore && !error && <div className="mt-6 text-center"><Button variant="outline" disabled={loading} onClick={onLoadMore}>{loading ? 'Đang tải…' : 'Xem thêm lịch sử'}</Button></div>}
  </main>;
}

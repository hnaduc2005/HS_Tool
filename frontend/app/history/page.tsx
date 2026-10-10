'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { api, hasAiServiceFailure, searchCodeLabel, type Search } from '@/lib/api';
import { Card } from '@/components/ui/card';
export default function HistoryPage() {
  const [items, setItems] = useState<Search[]>([]); const [error, setError] = useState('');
  useEffect(() => { api<Search[]>('/classification/history').then(setItems).catch(cause => setError(cause.message)); }, []);
  return <main className="mx-auto max-w-5xl px-5 py-12"><h1 className="text-3xl font-bold">Lịch sử tra cứu</h1><p className="mt-2 text-sm text-slate-500">Các lượt tra cứu từ tài khoản của bạn.</p>{error && <p className="mt-6 text-sm text-red-700">{error} · <Link className="underline" href="/auth">Đăng nhập</Link></p>}<div className="mt-7 space-y-3">{items.map(item => <Card key={item.id} className="p-5"><div className="flex flex-wrap justify-between gap-3"><div><p className="font-semibold">{item.productDescription.slice(0, 130)}</p><p className="mt-2 text-sm text-slate-500">{hasAiServiceFailure(item) ? 'Lỗi kết nối AI' : searchCodeLabel(item)} · {new Date(item.createdAt).toLocaleString('vi-VN')}</p></div><Link href={`/?search=${item.id}`} className="text-sm font-semibold text-forest hover:underline">Xem kết quả</Link></div></Card>)}{!items.length && !error && <p className="text-sm text-slate-500">Chưa có lượt tra cứu.</p>}</div></main>;
}

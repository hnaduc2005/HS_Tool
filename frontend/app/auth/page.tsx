'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
export default function AuthPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState(''); const [password, setPassword] = useState(''); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent) { e.preventDefault(); setBusy(true); setError(''); try { const data = await api<{ access_token: string; role: string }>(`/auth/${mode}`, { method: 'POST', body: JSON.stringify({ email, password }) }); sessionStorage.setItem('hs_token', data.access_token); router.push(data.role === 'ADMIN' ? '/admin' : '/history'); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không thể đăng nhập'); } finally { setBusy(false); } }
  return <main className="mx-auto max-w-md px-5 py-16"><Card className="p-8"><h1 className="text-2xl font-bold">{mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}</h1><p className="mt-2 text-sm text-slate-500">Lưu lịch sử tra cứu và gửi phản hồi.</p><form onSubmit={submit} className="mt-7 space-y-4"><div><label className="mb-2 block text-sm font-semibold" htmlFor="email">Email</label><Input id="email" type="email" required value={email} onChange={e => setEmail(e.target.value)}/></div><div><label className="mb-2 block text-sm font-semibold" htmlFor="password">Mật khẩu</label><Input id="password" type="password" minLength={mode === 'register' ? 10 : undefined} required value={password} onChange={e => setPassword(e.target.value)}/></div>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}<Button className="w-full" disabled={busy}>{busy ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : 'Đăng ký'}</Button></form><button className="mt-5 text-sm font-medium text-forest hover:underline" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>{mode === 'login' ? 'Chưa có tài khoản? Đăng ký' : 'Đã có tài khoản? Đăng nhập'}</button></Card></main>;
}

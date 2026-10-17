'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { COMPANY_EMAIL_MESSAGE, isCompanyEmail, loginDestination, type AuthResult } from '@/lib/auth';
import { useAuth } from '@/components/auth-provider';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
export default function AuthPage() {
  const router = useRouter();
  const { signIn } = useAuth();
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    const normalizedEmail = email.trim().toLowerCase();
    if (!isCompanyEmail(normalizedEmail)) { setError(COMPANY_EMAIL_MESSAGE); return; }
    setBusy(true); setError('');
    try {
      const data = await api<AuthResult>(`/auth/${mode}`, { method: 'POST', body: JSON.stringify({ email: normalizedEmail, password }) });
      signIn(data);
      router.replace(loginDestination(new URLSearchParams(window.location.search).get('next'), data.role));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không thể đăng nhập');
    } finally { setBusy(false); }
  }

  return <main className="mx-auto max-w-md px-5 py-16"><Card className="p-8">
    <p className="text-xs font-bold uppercase tracking-wider text-forest">Dành cho nội bộ Unigroup</p>
    <h1 className="mt-2 text-2xl font-bold">{mode === 'login' ? 'Đăng nhập' : 'Tạo tài khoản'}</h1>
    <p id="email-policy" className="mt-2 text-sm text-slate-500">Sử dụng email <strong>@unigroup.com.vn</strong> để đăng nhập và tra cứu mã HS.</p>
    <form onSubmit={submit} className="mt-7 space-y-4">
      <div><label className="mb-2 block text-sm font-semibold" htmlFor="email">Email công ty</label><Input id="email" type="email" autoComplete="email" autoCapitalize="none" spellCheck={false} placeholder="ten.ban@unigroup.com.vn" aria-describedby="email-policy" required disabled={busy} value={email} onChange={e => setEmail(e.target.value)}/></div>
      <div><label className="mb-2 block text-sm font-semibold" htmlFor="password">Mật khẩu</label><Input id="password" type="password" autoComplete={mode === 'register' ? 'new-password' : 'current-password'} minLength={mode === 'register' ? 10 : undefined} required disabled={busy} value={password} onChange={e => setPassword(e.target.value)}/>{mode === 'register' && <p className="mt-2 text-xs text-slate-500">Mật khẩu tài khoản HS Atlas gồm ít nhất 10 ký tự.</p>}</div>
      {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
      <Button className="w-full" disabled={busy}>{busy ? 'Đang xử lý...' : mode === 'login' ? 'Đăng nhập' : 'Đăng ký'}</Button>
    </form>
    <button disabled={busy} className="mt-5 text-sm font-medium text-forest hover:underline disabled:opacity-50" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setPassword(''); setError(''); }}>{mode === 'login' ? 'Chưa có tài khoản? Đăng ký' : 'Đã có tài khoản? Đăng nhập'}</button>
  </Card></main>;
}

'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import Link from 'next/link';
import { api, ApiError } from '@/lib/api';
import { AUTH_EXPIRED_EVENT, AUTH_TOKEN_KEY, type AuthResult, type Session } from '@/lib/auth';
import { Button } from '@/components/ui/button';

type AuthContextValue = {
  session: Session | null;
  signIn: (result: AuthResult) => void;
  signOut: () => void;
};
const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('AuthProvider is required');
  return context;
}

function loginUrl() {
  return `/auth?next=${encodeURIComponent(window.location.pathname + window.location.search)}`;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [checkedPath, setCheckedPath] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const expired = () => {
      setSession(null);
      setCheckedPath(null);
      if (window.location.pathname !== '/auth') router.replace(loginUrl());
    };
    window.addEventListener(AUTH_EXPIRED_EVENT, expired);
    return () => window.removeEventListener(AUTH_EXPIRED_EVENT, expired);
  }, [router]);

  useEffect(() => {
    let active = true;
    const token = sessionStorage.getItem(AUTH_TOKEN_KEY);
    setError('');
    if (!token) {
      setSession(null);
      setCheckedPath(pathname);
      if (pathname !== '/auth') router.replace(loginUrl());
      return;
    }
    api<Session>('/auth/me').then(user => {
      if (active && sessionStorage.getItem(AUTH_TOKEN_KEY) === token) { setSession(user); setCheckedPath(pathname); }
    }).catch(cause => {
      if (!active || (sessionStorage.getItem(AUTH_TOKEN_KEY) !== token && sessionStorage.getItem(AUTH_TOKEN_KEY) !== null)) return;
      setSession(null);
      setCheckedPath(null);
      if (cause instanceof ApiError && [401, 403].includes(cause.status)) {
        sessionStorage.removeItem(AUTH_TOKEN_KEY);
        if (pathname !== '/auth') router.replace(loginUrl());
      } else {
        setError('Không thể kiểm tra đăng nhập. Vui lòng kiểm tra kết nối và thử lại.');
      }
    });
    return () => { active = false; };
  }, [pathname, router, retry]);

  function signIn(result: AuthResult) {
    sessionStorage.setItem(AUTH_TOKEN_KEY, result.access_token);
    setSession(result.user);
    setCheckedPath(pathname);
    setError('');
  }

  function signOut() {
    sessionStorage.removeItem(AUTH_TOKEN_KEY);
    setSession(null);
    setCheckedPath(null);
    router.replace('/auth');
  }

  let content = children;
  if (pathname !== '/auth') {
    if (error) {
      content = <main className="mx-auto max-w-lg px-5 py-16 text-center"><p role="alert" className="text-sm text-red-700">{error}</p><Button className="mt-5" onClick={() => { setCheckedPath(null); setRetry(value => value + 1); }}>Thử lại</Button></main>;
    } else if (!session || checkedPath !== pathname) {
      content = <main className="mx-auto max-w-lg px-5 py-16 text-center text-sm text-slate-500" role="status">Đang kiểm tra đăng nhập…</main>;
    } else if (pathname === '/admin' && session.role !== 'ADMIN') {
      content = <main className="mx-auto max-w-lg px-5 py-16 text-center"><p>Bạn không có quyền quản trị.</p><Link href="/" className="mt-5 inline-block font-semibold text-forest underline">Về trang tra cứu</Link></main>;
    }
  }

  return <AuthContext.Provider value={{ session, signIn, signOut }}>{content}</AuthContext.Provider>;
}

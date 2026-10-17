'use client';

import Link from 'next/link';
import { ScanSearch } from 'lucide-react';
import { useAuth } from '@/components/auth-provider';
import { Button } from '@/components/ui/button';

export function AppHeader() {
  const { session, signOut } = useAuth();
  return <header className="border-b border-line bg-white/90">
    <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-4">
      <Link href="/" className="flex items-center gap-3 text-xl font-bold tracking-tight"><span className="rounded-xl bg-forest p-2 text-white"><ScanSearch size={22}/></span>HS Atlas</Link>
      <nav aria-label="Điều hướng chính" className="flex flex-wrap items-center gap-4 text-sm font-medium text-slate-600">
        {session ? <>
          <Link href="/" className="hover:text-forest">Tra cứu</Link>
          <Link href="/history" className="hover:text-forest">Lịch sử</Link>
          {session.role === 'ADMIN' && <Link href="/admin" className="hover:text-forest">Quản trị</Link>}
          <span className="break-all text-xs text-slate-500">{session.email}</span>
          <Button variant="outline" size="sm" onClick={signOut}>Đăng xuất</Button>
        </> : <Link href="/auth" className="font-semibold text-forest">Đăng nhập</Link>}
      </nav>
    </div>
  </header>;
}

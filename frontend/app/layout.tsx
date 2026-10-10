import type { Metadata } from 'next';
import Link from 'next/link';
import { ScanSearch } from 'lucide-react';
import './globals.css';
export const metadata: Metadata = { title: 'HS Atlas | Tra cứu mã HS có căn cứ', description: 'Tra cứu mã HS bằng dữ liệu, tài liệu và AI' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body><header className="border-b border-line bg-white/90"><div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4"><Link href="/" className="flex items-center gap-3 text-xl font-bold tracking-tight"><span className="rounded-xl bg-forest p-2 text-white"><ScanSearch size={22}/></span>HS Atlas</Link><nav className="flex items-center gap-5 text-sm font-medium text-slate-600"><Link href="/" className="hover:text-forest">Tra cứu</Link><Link href="/history" className="hover:text-forest">Lịch sử</Link><Link href="/admin" className="hover:text-forest">Quản trị</Link></nav></div></header>{children}<footer className="mx-auto max-w-6xl px-5 py-8 text-xs text-slate-500">Kết quả là gợi ý tham khảo. Đối chiếu quy định và chứng từ hiện hành trước khi khai báo.</footer></body></html>;
}

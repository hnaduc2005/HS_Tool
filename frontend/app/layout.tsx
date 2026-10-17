import type { Metadata } from 'next';
import { AuthProvider } from '@/components/auth-provider';
import { AppHeader } from '@/components/app-header';
import './globals.css';
export const metadata: Metadata = { title: 'HS Atlas | Tra cứu mã HS có căn cứ', description: 'Tra cứu mã HS bằng dữ liệu, tài liệu và AI' };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="vi"><body><AuthProvider><AppHeader/>{children}</AuthProvider><footer className="mx-auto max-w-6xl px-5 py-8 text-xs text-slate-500">Kết quả là gợi ý tham khảo. Đối chiếu quy định và chứng từ hiện hành trước khi khai báo.</footer></body></html>;
}

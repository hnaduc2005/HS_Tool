export const AUTH_TOKEN_KEY = 'hs_token';
export const AUTH_EXPIRED_EVENT = 'hs:auth-expired';
export const COMPANY_EMAIL_MESSAGE = 'Chỉ tài khoản email @unigroup.com.vn được phép sử dụng hệ thống.';

export type Session = { sub: string; email: string; role: 'USER' | 'ADMIN' };
export type AuthResult = { access_token: string; role: Session['role']; user: Session };

export function isCompanyEmail(email: string): boolean {
  return /^[^@\s]+@unigroup\.com\.vn$/i.test(email.trim());
}

export function loginDestination(next: string | null, role: Session['role']): string {
  // Only application routes are accepted, including saved-result query strings.
  if (next) {
    try {
      const url = new URL(next, 'https://hs-atlas.invalid');
      if (next.startsWith('/') && url.origin === 'https://hs-atlas.invalid'
        && ['/', '/history', ...(role === 'ADMIN' ? ['/admin'] : [])].includes(url.pathname)) {
        return url.pathname + url.search;
      }
    } catch { /* Fall back to the default application page. */ }
  }
  return role === 'ADMIN' ? '/admin' : '/';
}

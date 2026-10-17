export const COMPANY_EMAIL_MESSAGE = 'Chỉ tài khoản email @unigroup.com.vn được phép sử dụng hệ thống.';

export function isCompanyEmail(email: unknown): email is string {
  return typeof email === 'string' && /^[^@\s]+@unigroup\.com\.vn$/i.test(email.trim());
}

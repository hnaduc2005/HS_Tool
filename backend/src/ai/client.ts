import { HttpException, HttpStatus } from '@nestjs/common';

export async function aiCall<T>(route: string, payload: object, timeoutMs = 120000): Promise<T> {
  const token = process.env.AI_SERVICE_TOKEN;
  if (!token) throw new HttpException({ error: 'AI_SERVICE_UNAVAILABLE', message: 'Chưa cấu hình AI service' }, HttpStatus.SERVICE_UNAVAILABLE);
  try {
    const response = await fetch(`${process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000'}${route}`, {
      method: 'POST', headers: { 'content-type': 'application/json', 'x-service-token': token },
      body: JSON.stringify(payload), signal: AbortSignal.timeout(timeoutMs),
    });
    const body = await response.json() as T & { detail?: string };
    if (response.status === 400 && typeof body.detail === 'string')
      throw new HttpException({ message: body.detail }, HttpStatus.BAD_REQUEST);
    if (!response.ok) throw new Error(body.detail || `AI service HTTP ${response.status}`);
    return body;
  } catch (error) {
    if (error instanceof HttpException) throw error;
    throw new HttpException({ error: 'AI_SERVICE_UNAVAILABLE', message: 'Dịch vụ AI tạm thời không sẵn sàng. Vui lòng thử lại sau hoặc kiểm tra kết nối AI khi khởi động chương trình.' }, HttpStatus.SERVICE_UNAVAILABLE);
  }
}

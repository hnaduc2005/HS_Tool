'use client';
import { useState } from 'react';
import { ThumbsDown, ThumbsUp } from 'lucide-react';
import { api, type Search } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

export function ClassificationFeedback({ result }: { result: Search }) {
  const [incorrect, setIncorrect] = useState(false);
  const [correctCode, setCorrectCode] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  async function send(correct: boolean) {
    setSending(true);
    try {
      await api(`/classification/${result.id}/feedback`, { method: 'POST', body: JSON.stringify({
        is_correct: correct, result_id: result.results[0]?.id,
        correct_hs_code: correctCode.replace(/\D/g, '') || undefined,
      }) });
      setMessage('Đã ghi nhận phản hồi. Cảm ơn bạn.'); setIncorrect(false);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'Không thể gửi phản hồi'); }
    finally { setSending(false); }
  }
  return <Card className="mt-5 p-5">
    <div className="flex flex-wrap items-center justify-between gap-3"><p className="font-semibold">Phản hồi kết quả</p><time className="text-xs text-slate-500">{new Date(result.createdAt).toLocaleString('vi-VN')}</time></div>
    <div className="mt-3 flex flex-wrap items-center gap-3"><span className="text-sm text-slate-600">Kết quả này có đúng không?</span><Button type="button" variant="outline" size="sm" disabled={sending} onClick={() => send(true)}><ThumbsUp size={15}/> Đúng</Button><Button type="button" variant="outline" size="sm" disabled={sending} onClick={() => setIncorrect(true)}><ThumbsDown size={15}/> Không đúng</Button></div>
    {incorrect && <div className="mt-4 flex max-w-md gap-2"><Input aria-label="Mã HS chính xác" placeholder="Mã HS chính xác (nếu biết)" value={correctCode} onChange={e => setCorrectCode(e.target.value)}/><Button type="button" disabled={sending} onClick={() => send(false)}>Gửi</Button></div>}
    {message && <p role="status" className="mt-3 text-xs text-slate-600">{message}</p>}
  </Card>;
}

'use client';
import { useState } from 'react';
import { ChevronDown, Layers3, Loader2, RotateCcw } from 'lucide-react';
import { type BatchItem } from '@/lib/classification-batch';
import { classificationView, formatHsCode } from '@/lib/classification-presentation';
import { ClassificationAnswer } from '@/components/classification-answer';
import { ClassificationFeedback } from '@/components/classification-feedback';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

export function ClassificationBatch({ items, busy, onRetry }: { items: BatchItem[]; busy: boolean; onRetry: (key: string) => void }) {
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set(items.slice(1).map(item => item.key)));
  const done = items.filter(item => item.state === 'done').length;
  const failed = items.filter(item => item.state === 'error').length;
  const finished = done + failed;
  const resultIds = items.flatMap(item => item.result ? [item.result.id] : []);
  function toggle(key: string) {
    setCollapsed(previous => { const next = new Set(previous); if (next.has(key)) next.delete(key); else next.add(key); return next; });
  }
  return <section aria-label="Kết quả nhiều mặt hàng" className="space-y-4">
    <Card className="p-5 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3"><span className="rounded-xl bg-mint p-3 text-forest"><Layers3 size={22}/></span><div><h2 className="text-xl font-bold">Kết quả {items.length} mặt hàng</h2><p className="mt-1 text-sm text-slate-500" role="status">{busy ? `Đã xử lý ${finished}/${items.length}` : `${done} đã phân tích`}{failed > 0 ? ` · ${failed} gặp lỗi` : ''}</p></div></div>
        <div className="flex flex-wrap gap-2"><Button type="button" size="sm" variant="outline" onClick={() => setCollapsed(new Set())}>Mở tất cả</Button><Button type="button" size="sm" variant="outline" onClick={() => setCollapsed(new Set(items.map(item => item.key)))}>Thu gọn tất cả</Button></div>
      </div>
      <div role="progressbar" aria-label="Tiến độ phân tích mặt hàng" aria-valuemin={0} aria-valuemax={items.length} aria-valuenow={finished} className="mt-4 h-2 overflow-hidden rounded-full bg-mint"><div className="h-full rounded-full bg-forest transition-all" style={{ width: `${finished / items.length * 100}%` }}/></div>
      <p className="mt-3 text-xs leading-5 text-slate-500">Mỗi mặt hàng có mã HS, tên khai báo, thuế và căn cứ riêng. Bấm vào tiêu đề để mở hoặc thu gọn.</p>
      {!busy && resultIds.length === items.length && <a className="mt-3 inline-block text-xs font-semibold text-forest underline" href={`/?items=${resultIds.join(',')}`}>Mở lại danh sách kết quả đã lưu</a>}
    </Card>
    {items.map((item, index) => {
      const open = !collapsed.has(item.key);
      const understanding = item.result?.legalAnalysis?.product_understanding;
      const view = item.result ? classificationView(item.result) : undefined;
      const title = understanding?.product_name || item.description.split('\n')[0];
      const model = item.result?.legalAnalysis?.declaration_information?.fields.model_code;
      const status = item.state === 'loading' ? 'Đang phân tích' : item.state === 'waiting' ? 'Đang chờ' : item.state === 'error' ? 'Phân tích gặp lỗi' : view?.completed ? 'Đủ thông tin' : view?.hypotheses.length ? 'Theo giả định' : 'Cần đối chiếu nguồn';
      const codes = view?.separate ? view.hypotheses[0].items!.map(item => formatHsCode(item.code)).join(' / ') + ' (theo giả định)'
        : view?.code ? formatHsCode(view.code) + (view.completed ? '' : ' (theo giả định)') : '';
      return <Card key={item.key} className="overflow-hidden">
        <h3><button type="button" aria-expanded={open} aria-controls={`batch-body-${item.key}`} onClick={() => toggle(item.key)} className="flex w-full items-center gap-3 p-5 text-left transition hover:bg-mint/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-forest md:p-6">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-mint font-bold text-forest">{index + 1}</span>
          <span className="min-w-0 flex-1"><span className="block text-xs font-semibold text-slate-500">Mặt hàng {index + 1}<span className="font-normal sm:hidden"> · {status}</span></span><span className="mt-1 block break-words font-bold text-ink">{title.length > 150 ? title.slice(0, 150) + '…' : title}</span>{model && <span className="mt-1 block break-words text-xs font-medium text-slate-600">Model: {model}</span>}{codes && <span className="mt-2 block text-xl font-bold tracking-tight text-forest">{codes}</span>}</span>
          <span className={`hidden rounded-full px-3 py-1 text-xs font-semibold sm:block ${item.state === 'error' ? 'bg-red-50 text-red-700' : 'bg-paper text-slate-600'}`}>{status}</span>
          {item.state === 'loading' ? <Loader2 aria-label={status} className="shrink-0 animate-spin text-forest" size={20}/> : <ChevronDown className={`shrink-0 text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} size={20}/>}
        </button></h3>
        <div id={`batch-body-${item.key}`} hidden={!open} className="border-t border-line bg-paper/50 p-3 md:p-5">
          <details className="mb-4 rounded-xl border border-line bg-white p-4 text-sm"><summary className="cursor-pointer font-semibold text-slate-600">Mô tả đã nhập</summary><p className="mt-2 whitespace-pre-wrap leading-6 text-slate-600">{item.description}</p></details>
          {item.state === 'waiting' && <p className="px-2 py-4 text-sm text-slate-500">Đang chờ phân tích mặt hàng này…</p>}
          {item.state === 'loading' && <p role="status" className="flex items-center gap-2 px-2 py-4 text-sm text-forest"><Loader2 size={17} className="animate-spin"/> Đang đối chiếu mô tả, danh mục và nguồn pháp lý…</p>}
          {item.state === 'error' && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4"><p className="text-sm text-red-700">{item.error}</p><Button type="button" size="sm" variant="outline" className="mt-3" disabled={busy} onClick={() => onRetry(item.key)}><RotateCcw size={15}/> Thử lại mặt hàng này</Button></div>}
          {item.result && <><ClassificationAnswer result={item.result}/><ClassificationFeedback key={item.result.id} result={item.result}/></>}
        </div>
      </Card>;
    })}
  </section>;
}

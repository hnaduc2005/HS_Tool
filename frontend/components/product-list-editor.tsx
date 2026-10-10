'use client';
import { Plus, Trash2 } from 'lucide-react';
import { type BatchItem, MAX_BATCH_ITEMS } from '@/lib/classification-batch';
import { DeclarationForm } from '@/components/declaration-form';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';

export function ProductListEditor({ items, onChange, needsReview = false }: { items: BatchItem[]; onChange: (items: BatchItem[]) => void; needsReview?: boolean }) {
  function change(key: string, patch: Partial<BatchItem>) { onChange(items.map(item => item.key === key ? { ...item, ...patch } : item)); }
  return <section aria-label="Danh sách mặt hàng" className="mt-4 space-y-3">
    <div className="rounded-xl bg-mint p-4 text-sm text-forest"><p className="font-bold">{needsReview ? 'Nội dung cần kiểm tra cách tách' : `Danh sách ${items.length} mặt hàng`}</p><p className="mt-1 leading-6">{needsReview ? 'Số ô bên dưới chưa xác nhận số mặt hàng. Mô tả gốc được giữ đầy đủ để chia lại. ' : 'Kiểm tra mô tả đã tách; bạn có thể sửa, thêm hoặc xóa. '}Mỗi mặt hàng tối đa 2.000 ký tự, tối đa 10 mặt hàng một lượt.</p></div>
    {items.map((item, index) => <details key={item.key} open className="rounded-xl border border-line bg-paper p-4">
      <summary className="cursor-pointer text-sm font-semibold">Mặt hàng {index + 1}</summary>
      <div className="mt-3"><label htmlFor={`item-description-${item.key}`} className="mb-2 block text-xs font-semibold">Mô tả mặt hàng {index + 1}</label><Textarea id={`item-description-${item.key}`} rows={4} maxLength={2000} required={!item.declaration.vietnamese_name?.trim()} value={item.description} onChange={e => change(item.key, { description: e.target.value })} placeholder="Tên hàng, thành phần, thông số, model, nhãn hiệu, tình trạng…"/>
        <p className={`mt-1 text-right text-xs ${item.description.length > 2000 ? 'text-red-600' : 'text-slate-500'}`}>{item.description.length}/2.000 ký tự</p>
        <DeclarationForm idPrefix={`${item.key}-`} value={item.declaration} onChange={declaration => change(item.key, { declaration })}/>
        {items.length > 1 && <Button type="button" size="sm" variant="ghost" className="mt-3 text-red-600" onClick={() => onChange(items.filter(row => row.key !== item.key))}><Trash2 size={14}/> Xóa mặt hàng</Button>}
      </div>
    </details>)}
    <Button type="button" variant="outline" size="sm" disabled={items.length >= MAX_BATCH_ITEMS} onClick={() => onChange([...items, { key: crypto.randomUUID(), description: '', declaration: {}, state: 'waiting' }])}><Plus size={16}/> Thêm mặt hàng</Button>
  </section>;
}

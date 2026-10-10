import { Card } from '@/components/ui/card';
import type { LegalAnalysis } from '@/lib/api';

function sourceLink(source: string): string | null {
  try {
    const url = new URL(source.match(/https?:\/\/[^\s]+/)?.[0] || source);
    return ['https:', 'http:'].includes(url.protocol) ? url.toString() : null;
  } catch { return null; }
}

function Citations({ ids, numbers }: { ids: string[]; numbers: Record<string, number> }) {
  if (!ids?.length) return null;
  return <span className="ml-1 text-xs text-forest">{ids.filter(id => numbers[id]).map(id => <a key={id} className="ml-1 underline" href={`#legal-source-${id}`} aria-label={`Xem nguồn ${numbers[id]}`}>[{numbers[id]}]</a>)}</span>;
}

export function LegalAnalysisPanel({ analysis }: { analysis?: LegalAnalysis }) {
  if (!analysis?.summary) return <Card className="mt-5 p-6"><h3 className="text-xl font-bold">Giải thích pháp lý</h3><p className="mt-3 text-sm leading-6 text-slate-700">Lượt tra cứu này được lưu trước khi bổ sung giải thích pháp lý. Bấm “Phân tích mã HS” để đối chiếu lại dữ kiện và nguồn hiện có.</p></Card>;
  const sourceNumbers = Object.fromEntries((analysis.references || []).map((ref, i) => [ref.chunk_id, i + 1]));
  return <Card className="mt-5 p-6 md:p-8">
    <h3 className="text-xl font-bold">Giải thích pháp lý</h3>
    <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-700">{analysis.summary}</p>
    {!!analysis.product_facts?.length && <section className="mt-6"><h4 className="font-bold">Dữ kiện hàng hóa được sử dụng</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">{analysis.product_facts.map((fact, i) => <li key={i}>{fact}</li>)}</ul></section>}
    <section className="mt-6"><h4 className="font-bold">Quy định và cách áp dụng</h4>{analysis.legal_steps?.length ? <ol className="mt-3 space-y-4">{analysis.legal_steps.map((step, i) => <li key={i} className="rounded-xl border border-line bg-paper p-4 text-sm leading-6"><p className="font-semibold">{i + 1}. {step.rule}<Citations ids={step.source_chunk_ids} numbers={sourceNumbers}/></p><p className="mt-2 text-slate-700">Áp dụng: {step.application}</p></li>)}</ol> : <p className="mt-2 text-sm text-amber-800">Chưa tìm được điều khoản pháp lý có nguồn kiểm chứng cho trường hợp này.</p>}</section>
    {!!analysis.alternatives?.length && <section className="mt-6"><h4 className="font-bold">Nhóm hoặc mã đã xem xét</h4><ul className="mt-3 space-y-2">{analysis.alternatives.map((item, i) => <li key={`${item.code}-${i}`} className="rounded-xl border border-line p-3 text-sm leading-6"><strong>{item.code}</strong>: {item.reason}<Citations ids={item.source_chunk_ids} numbers={sourceNumbers}/></li>)}</ul></section>}
    <section className="mt-6 rounded-xl bg-mint p-4"><h4 className="font-bold">Kết luận</h4><p className="mt-2 whitespace-pre-wrap text-sm leading-6">{analysis.conclusion}</p></section>
    {!!analysis.limitations?.length && <section className="mt-6"><h4 className="font-bold">Điểm cần xác minh</h4><ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">{analysis.limitations.map((item, i) => <li key={i}>{item}</li>)}</ul></section>}
    <section className="mt-6"><h4 className="font-bold">Nguồn được đối chiếu</h4>{analysis.references?.length ? <div className="mt-3 space-y-3">{analysis.references.map((ref, i) => <details id={`legal-source-${ref.chunk_id}`} key={ref.chunk_id} className="rounded-xl border border-line p-4 text-sm"><summary className="cursor-pointer font-semibold">[{i + 1}] {ref.title}{ref.page ? ` · Trang ${ref.page}` : ''}</summary><p className="mt-2 text-xs text-slate-500">{sourceLink(ref.source) ? <a href={sourceLink(ref.source)!} target="_blank" rel="noopener noreferrer" className="underline">{ref.source}</a> : ref.source}</p><p className="mt-3 whitespace-pre-wrap text-xs leading-6 text-slate-700">{ref.excerpt}</p></details>)}</div> : <p className="mt-2 text-sm text-amber-800">Không có tài liệu đã xác minh trong kho tri thức.</p>}</section>
  </Card>;
}

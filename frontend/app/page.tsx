'use client';
import { useEffect, useState } from 'react';
import { ArrowRight, Check, Layers3, Loader2, Paperclip, Search, ShieldCheck } from 'lucide-react';
import { api, hasAiServiceFailure, type DeclarationInput, type PreparedItems, type Search as SearchRecord } from '@/lib/api';
import { batchError, MAX_BATCH_ITEMS, prepareDraftItems, runClassificationBatch, type BatchItem } from '@/lib/classification-batch';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { ClassificationAnswer } from '@/components/classification-answer';
import { ClassificationFeedback } from '@/components/classification-feedback';
import { ClassificationBatch } from '@/components/classification-batch';
import { ProductListEditor } from '@/components/product-list-editor';
import { DeclarationForm, emptyDeclaration } from '@/components/declaration-form';

const examples = ['Áo thun nam 100% cotton, dệt kim, dùng mặc hằng ngày', 'Máy lọc nước gia đình dùng màng RO', 'Bàn làm việc bằng gỗ'];
const multipleExample = '1. Giấy trang trí phủ PU, QC: 1270MM *30G~45G, dùng dán giả vân gỗ trên bề mặt ván, không nhãn hiệu, hàng mới 100%\n\n2. COMPUTERIZED CROCHET MACHINE\nMACHINE BRAND: YJ\nMODEL: B16 20\nPOWER: 1.5KW';
function newItem(description: string, declaration: DeclarationInput = {}): BatchItem {
  return { key: crypto.randomUUID(), description, declaration, state: 'waiting' };
}

export default function Home() {
  const [description, setDescription] = useState('');
  const [declaration, setDeclaration] = useState<DeclarationInput>(emptyDeclaration);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState('');
  const [result, setResult] = useState<SearchRecord | null>(null);
  const [drafts, setDrafts] = useState<BatchItem[] | null>(null);
  const [batch, setBatch] = useState<BatchItem[]>([]);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [draftNeedsReview, setDraftNeedsReview] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ids = [...new Set((params.get('items') || '').split(',').filter(Boolean))].slice(0, MAX_BATCH_ITEMS);
    if (ids.length) {
      setLoading(true); setPhase('Đang đọc kết quả đã lưu…');
      Promise.all(ids.map(async id => {
        try {
          const record = await api<SearchRecord>(`/classification/${encodeURIComponent(id)}`);
          return { ...newItem(record.legalAnalysis?.declaration_information?.original_description || record.productDescription,
            record.legalAnalysis?.declaration_information?.input || {}), state: 'done' as const, result: record };
        } catch (cause) {
          return { ...newItem(`Kết quả đã lưu ${id}`), state: 'error' as const,
            savedId: id,
            error: cause instanceof Error ? cause.message : 'Không thể đọc kết quả đã lưu.' };
        }
      })).then(records => { setBatch(records); setDrafts(records.filter(row => row.result).map(row => ({ ...row, state: 'waiting', result: undefined }))); })
        .finally(() => { setLoading(false); setPhase(''); });
      return;
    }
    const id = params.get('search');
    if (id) api<SearchRecord>(`/classification/${encodeURIComponent(id)}`).then(record => {
      setDescription(record.legalAnalysis?.declaration_information?.original_description ?? record.productDescription);
      setDeclaration(record.legalAnalysis?.declaration_information?.input || emptyDeclaration);
      if (hasAiServiceFailure(record)) {
        setError('Lượt tra cứu này gặp lỗi kết nối AI. Vui lòng bấm Phân tích mã HS để tra cứu lại.'); return;
      }
      setResult(record);
    }).catch(cause => setError(cause.message));
  }, []);

  async function inputText() {
    let text = description.trim();
    if (file) {
      setPhase('Đang đọc tài liệu…');
      const form = new FormData(); form.append('file', file);
      const extracted = await api<{ text: string }>('/classification/extract', { method: 'POST', body: form });
      text = [text, extracted.text].filter(Boolean).join('\n\n');
    }
    if (!text && declaration.vietnamese_name?.trim()) text = declaration.vietnamese_name.trim();
    return text;
  }
  async function prepare(text: string) {
    if (!text) throw new Error('Nhập mô tả hoặc chọn tài liệu sản phẩm.');
    if (text.length > 20000) throw new Error('Danh sách tối đa 20.000 ký tự. Hãy chia thành các lượt nhỏ hơn.');
    setPhase('Đang nhận diện từng mặt hàng…');
    return api<PreparedItems>('/classification/prepare-items', { method: 'POST', body: JSON.stringify({ description: text }) });
  }
  function updateBatch(key: string, patch: Partial<BatchItem>) {
    setBatch(previous => previous.map(item => item.key === key ? { ...item, ...patch } : item));
  }
  const classifyItem = (item: BatchItem) => api<SearchRecord>('/classification/search', {
    method: 'POST', body: JSON.stringify({ description: item.description, declaration: item.declaration }),
  });
  async function analyze(items: BatchItem[]) {
    const invalid = batchError(items);
    if (invalid) throw new Error(invalid);
    setPhase('Đang phân tích…'); setResult(null);
    if (items.length === 1) {
      setBatch([]); setResult(await classifyItem(items[0])); return;
    }
    const waiting = items.map(item => ({ ...item, state: 'waiting' as const, result: undefined, error: undefined }));
    setBatch(waiting);
    await runClassificationBatch(waiting, classifyItem, updateBatch);
  }
  async function separate() {
    setError(''); setNotice(''); setLoading(true);
    let text = description.trim();
    try {
      text = await inputText();
      const prepared = await prepare(text);
      setDrafts(prepared.items.map(item => newItem(item.description, prepared.items.length === 1 ? declaration : {})));
      setDraftNeedsReview(prepared.needs_review);
      if (prepared.needs_review) setNotice(prepared.message || 'Kiểm tra và chia mô tả dài thành từng mặt hàng trước khi phân tích.');
      else if (prepared.items.length === 1) setNotice('Mô tả đang được nhận diện là một mặt hàng hoặc một bộ sản phẩm. Bạn có thể thêm mặt hàng độc lập bên dưới.');
      if (prepared.items.length > 1 && Object.values(declaration).some(Boolean)) setNotice('Thông tin bổ sung của biểu mẫu một mặt hàng vẫn được giữ ở chế độ mô tả chung. Hãy khai riêng cho từng mặt hàng bên dưới để áp dụng đúng món.');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Không thể tách danh sách.');
      setDrafts([newItem(text, declaration)]);
      setDraftNeedsReview(true);
    } finally { setLoading(false); setPhase(''); }
  }
  async function submit(event: React.FormEvent) {
    event.preventDefault(); setError(''); setNotice(''); setResult(null); setBatch([]); setLoading(true);
    try {
      if (drafts) {
        const prepared = await prepareDraftItems(drafts, prepare);
        setDrafts(prepared.items); setDraftNeedsReview(prepared.needsReview);
        if (prepared.needsReview) { setNotice(prepared.message); return; }
        await analyze(prepared.items); return;
      }
      const prepared = await prepare(await inputText());
      const items = prepared.items.map(item => newItem(item.description, prepared.items.length === 1 ? declaration : {}));
      if (prepared.items.length > 1 || prepared.needs_review) setDrafts(items);
      setDraftNeedsReview(prepared.needs_review);
      if (prepared.needs_review) {
        setNotice(prepared.message || 'Kiểm tra và chia mô tả dài thành từng mặt hàng trước khi phân tích.'); return;
      }
      if (items.length > 1 && Object.values(declaration).some(Boolean)) {
        setNotice('Đã nhận diện nhiều mặt hàng. Hãy bổ sung thông tin riêng cho từng món; biểu mẫu một mặt hàng vẫn được giữ ở chế độ mô tả chung.'); return;
      }
      await analyze(items);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Không thể tra cứu'); }
    finally { setLoading(false); setPhase(''); }
  }
  async function retry(key: string) {
    const item = batch.find(row => row.key === key);
    if (!item) return;
    setLoading(true); setPhase('Đang phân tích lại mặt hàng…');
    try {
      if (item.savedId) {
        updateBatch(key, { state: 'loading', error: undefined });
        try {
          const record = await api<SearchRecord>(`/classification/${encodeURIComponent(item.savedId)}`);
          updateBatch(key, { state: 'done', result: record, savedId: undefined,
            description: record.legalAnalysis?.declaration_information?.original_description || record.productDescription,
            declaration: record.legalAnalysis?.declaration_information?.input || {} });
        } catch (cause) { updateBatch(key, { state: 'error', error: cause instanceof Error ? cause.message : 'Không thể đọc kết quả đã lưu.' }); }
      } else await runClassificationBatch([item], classifyItem, updateBatch);
    }
    finally { setLoading(false); setPhase(''); }
  }
  function example(text: string) { setDescription(text); setDeclaration(emptyDeclaration); setFile(null); setDrafts(null); setDraftNeedsReview(false); setNotice(''); setError(''); }

  return <main className="mx-auto max-w-6xl px-5 pb-16">
    <section className="grid gap-10 py-14 md:grid-cols-[1.15fr_.85fr] md:items-start md:py-20">
      <div className="md:sticky md:top-10">
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-[#c5e3d3] bg-mint px-3 py-1 text-xs font-bold uppercase tracking-wider text-forest"><ShieldCheck size={14}/> Tra cứu có căn cứ</div>
        <h1 className="max-w-2xl text-4xl font-bold leading-tight tracking-tight md:text-6xl">Tìm mã HS phù hợp với <span className="text-forest">hàng hóa của bạn</span></h1>
        <p className="mt-6 max-w-xl text-base leading-7 text-slate-600">Nhập một sản phẩm hoặc danh sách nhiều mặt hàng. Hệ thống phân tích từng mặt hàng, đề xuất mã HS và giải thích cùng nguồn tham khảo.</p>
        <div className="mt-8 flex flex-wrap gap-5 text-sm text-slate-600"><span className="flex items-center gap-2"><Check size={17} className="text-forest"/> Phân tích từng mặt hàng</span><span className="flex items-center gap-2"><Check size={17} className="text-forest"/> Trích dẫn tài liệu</span><span className="flex items-center gap-2"><Check size={17} className="text-forest"/> Phản hồi kết quả</span></div>
      </div>
      <Card className="p-6 md:p-8">
        <div className="mb-6 flex items-center gap-3"><span className="rounded-xl bg-mint p-2 text-forest"><Search size={21}/></span><div><h2 className="font-bold">Mô tả hàng hóa</h2><p className="text-xs text-slate-500">Một hoặc nhiều mặt hàng trong cùng lượt tra cứu</p></div></div>
        <form onSubmit={submit}><fieldset disabled={loading}>
          {drafts ? <>
            <Button type="button" variant="ghost" size="sm" className="mb-2" onClick={() => { setDrafts(null); setNotice(''); }}>← Trở về mô tả chung</Button>
            <ProductListEditor items={drafts} onChange={setDrafts} needsReview={draftNeedsReview}/>
          </> : <>
            <label htmlFor="description" className="mb-2 block text-sm font-semibold">Thông tin sản phẩm</label>
            <Textarea id="description" rows={8} maxLength={20000} value={description} onChange={e => setDescription(e.target.value)} placeholder={'Một sản phẩm: tên hàng, chất liệu, công dụng, thông số…\n\nNhiều mặt hàng: đánh số 1, 2, 3 hoặc cách nhau bằng dòng trống. Giữ model và thông số ngay dưới tên từng món.'}/>
            <p className="mt-2 text-xs leading-5 text-slate-500">Có thể nhập nhiều dòng thông số cho một mặt hàng. Bộ quà tặng hoặc bộ sản phẩm được giữ nguyên để xét quy tắc phân loại.</p>
            <DeclarationForm value={declaration} onChange={setDeclaration}/>
            <div className="mt-4"><label htmlFor="product-file" className="mb-2 block text-sm font-semibold">Tài liệu sản phẩm (tùy chọn)</label><label htmlFor="product-file" className="flex cursor-pointer items-center gap-2 rounded-xl border border-dashed border-line px-4 py-3 text-sm text-slate-500 hover:border-forest"><Paperclip size={17}/>{file?.name || 'Chọn PDF, DOCX, XLSX hoặc TXT (tối đa 10 MB)'}</label><input id="product-file" type="file" accept=".pdf,.docx,.xlsx,.txt" className="sr-only" onChange={e => setFile(e.target.files?.[0] || null)}/></div>
            <Button type="button" variant="outline" className="mt-4 w-full" onClick={separate}><Layers3 size={17}/> Tách / chỉnh danh sách mặt hàng</Button>
          </>}
          <Button type="submit" size="lg" className="mt-5 w-full" disabled={loading || drafts?.length === 0}>{loading ? <><Loader2 size={18} className="animate-spin"/> {phase || 'Đang phân tích…'}</> : <>Phân tích {drafts && drafts.length > 1 ? `${drafts.length} mặt hàng` : 'mã HS'} <ArrowRight size={18}/></>}</Button>
        </fieldset></form>
        <p className="mt-5 text-xs text-slate-500">Các kết quả xuất hiện lần lượt. Có thể mở hoặc thu gọn từng mặt hàng để dễ đối chiếu.</p>
      </Card>
    </section>
    <section className="mb-8"><p className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-500">Thử nhanh với ví dụ</p><div className="flex flex-wrap gap-2">{examples.map(item => <button key={item} disabled={loading} onClick={() => example(item)} className="rounded-full border border-line bg-white px-4 py-2 text-sm text-slate-600 hover:border-forest hover:text-forest disabled:opacity-50">{item}</button>)}<button disabled={loading} onClick={() => example(multipleExample)} className="flex items-center gap-2 rounded-full border border-forest/30 bg-mint px-4 py-2 text-sm font-semibold text-forest disabled:opacity-50"><Layers3 size={15}/> Ví dụ nhiều mặt hàng</button></div></section>
    {error && <div role="alert" className="mb-6 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">{error}</div>}
    {notice && <div role="status" className="mb-6 rounded-xl border border-line bg-mint px-5 py-4 text-sm text-forest">{notice}</div>}
    {batch.length > 0 && <ClassificationBatch key={batch.map(item => item.key).join(',')} items={batch} busy={loading} onRetry={retry}/>}
    {result && <><ClassificationAnswer result={result}/><ClassificationFeedback key={result.id} result={result}/></>}
  </main>;
}

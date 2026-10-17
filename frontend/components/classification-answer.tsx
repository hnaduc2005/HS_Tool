'use client';
import { createContext, useContext } from 'react';
import { Card } from '@/components/ui/card';
import type { Search, Hypothesis, HypothesisItem } from '@/lib/api';
import { DeclarationAnswer } from '@/components/declaration-answer';
import { ClassificationTariff } from '@/components/classification-tariff';
import { classificationView, formatHsCode as hs, missingLabels, scenarioName } from '@/lib/classification-presentation';

const SourcePrefix = createContext('');
function SourceMarks({ ids, numbers }: { ids: string[]; numbers: Record<string, number> }) {
  const prefix = useContext(SourcePrefix);
  return <>{[...new Set(ids)].filter(id => numbers[id]).map(id => <a key={id} className="ml-1 text-xs font-medium text-forest underline" href={`#legal-source-${prefix}${id}`} aria-label={`Xem nguồn ${numbers[id]}`} onClick={() => {
    const sourceDetails = document.getElementById(`legal-source-${prefix}${id}`)?.closest('details');
    if (sourceDetails) sourceDetails.open = true;
  }}>[{numbers[id]}]</a>)}</>;
}

function scenarioItems(item: Hypothesis): HypothesisItem[] {
  return item.classification_mode === 'separate' && item.items?.length ? item.items
    : [{ name: item.label, code: item.code, source_chunk_ids: item.source_chunk_ids, catalog_description: item.catalog_description, tariff_rates: item.tariff_rates }];
}

export function ClassificationAnswer({ result }: { result: Search }) {
  return <SourcePrefix.Provider value={`${result.id}-`}><ClassificationContent result={result}/></SourcePrefix.Provider>;
}

function ClassificationContent({ result }: { result: Search }) {
  const prefix = useContext(SourcePrefix);
  const analysis = result.legalAnalysis;
  const { completed, hypotheses, primary, code, separate, oldShortResult } = classificationView(result);
  const conditional = hypotheses.length > 0;
  const numbers = Object.fromEntries((analysis?.references || []).map((ref, index) => [ref.chunk_id, index + 1]));
  const declaration = analysis?.declaration_information;
  const productName = analysis?.product_understanding?.product_name || result.normalizedProduct?.product_name;
  const name = declaration?.draft_name || analysis?.suggested_name || (typeof productName === 'string' ? productName : 'Tên hàng theo mô tả đã nhập');
  const facts = [...new Set((analysis?.product_understanding?.facts || []).map(fact => fact.value))];
  const missing = missingLabels(result);

  return <Card className="overflow-hidden">
    <header className={`p-6 md:p-8 ${completed || conditional ? 'bg-forest text-white' : 'bg-amber-50 text-ink'}`}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs font-bold uppercase tracking-widest">{completed ? 'Mã HS đề xuất' : conditional ? 'Mã HS theo từng giả định' : 'Kết quả phân tích'}</p>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${completed || conditional ? 'bg-white/20' : 'bg-amber-100'}`}>{completed ? 'Theo thông tin đã khai' : conditional ? `${hypotheses.length} phương án theo phần còn thiếu` : 'Cần đối chiếu thêm nguồn'}</span>
      </div>
      {separate ? <div className="mt-4"><h2 className="text-xl font-bold">Phân loại riêng từng mặt hàng</h2><div className="mt-4 flex flex-wrap gap-5">{scenarioItems(hypotheses[0]).map((item, index) => <div key={index}><p className="text-xs text-white/80">{item.name}</p><p className="mt-1 text-3xl font-bold tracking-tight">{hs(item.code)}</p></div>)}</div></div>
        : <h2 className="mt-3 break-words text-4xl font-bold tracking-tight md:text-5xl">{code ? hs(code) : 'Chưa có phương án mã hợp lệ'}</h2>}
      {conditional && <p className="mt-2 text-sm text-white/80">Phương án ưu tiên · Chọn khi đáp ứng các giả định trong phương án 1.</p>}
      {typeof productName === 'string' && <p className={`mt-4 text-base font-medium ${completed || conditional ? 'text-white/90' : 'text-slate-700'}`}>{productName}</p>}
      {oldShortResult && <p className="mt-3 text-sm">Kết quả cũ chỉ có phân nhóm {primary.hsCode}. Tra cứu lại để đối chiếu mã tám số.</p>}
    </header>

    <aside aria-label="Lưu ý về kết quả AI" className="border-b border-amber-200 bg-amber-50 px-5 py-4 text-sm leading-6 text-amber-950 md:px-8">
      AI có thể mắc lỗi. Hãy kiểm tra thông tin quan trọng
    </aside>

    <div className="space-y-7 p-5 text-sm leading-6 text-slate-700 md:p-8">
      {completed && <>
        <section className="rounded-xl border border-line bg-paper p-5" aria-label="Tên hàng khai báo">
          <h3 className="font-bold text-ink">Tên hàng đề xuất từ sản phẩm nhập vào</h3>
          <p className="mt-2 text-base font-medium leading-7 text-ink">{name}</p>
          <p className="mt-2 text-xs text-slate-500">Ghép tên tiếng Việt, chất liệu, công dụng/thông số, model, nhãn hiệu/xuất xứ và tình trạng theo dữ kiện đã khai.</p>
        </section>
        <section><h3 className="mb-3 text-base font-bold text-ink">Thuế suất</h3><ClassificationTariff code={code} tariff={analysis?.tariff_rates}/></section>
        <section><h3 className="mb-3 text-base font-bold text-ink">Vì sao đề xuất {hs(code)}?</h3>
          <p>{analysis?.summary || primary.reasoning}</p>
          {!!analysis?.legal_steps?.length && <ol className="mt-4 space-y-3">{analysis.legal_steps.map((step, index) => <li key={index} className="border-l-2 border-line pl-4"><p className="font-semibold text-ink">{step.rule}<SourceMarks ids={step.source_chunk_ids} numbers={numbers}/></p><p className="mt-1">{step.application}</p></li>)}</ol>}
        </section>
      </>}

      {conditional && <>
        <section className="rounded-xl border border-line bg-paper p-4">
          <h3 className="font-bold text-ink">Thông tin chung của các phương án</h3>
          <p className="mt-2">{name}</p>
          {!!facts.length && <p className="mt-2 text-xs text-slate-600"><strong>Đã xác định:</strong> {facts.slice(0, 5).join(' · ')}.</p>}
          {!!missing.length && <p className="mt-3"><strong>Cần phân biệt thêm:</strong> {missing.join('; ')}.</p>}
        </section>
        <div className="space-y-5">{hypotheses.map((item, index) => {
          const proposal = scenarioName(analysis, item, index);
          const articles = scenarioItems(item);
          return <section key={`${item.code}-${index}`} aria-label={`Phương án ${index + 1}`} className={`overflow-hidden rounded-2xl border ${index === 0 ? 'border-forest/40' : 'border-line'}`}>
            <div className="flex flex-wrap items-center gap-3 border-b border-line bg-paper px-5 py-4">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-forest text-sm font-bold text-white">{index + 1}</span>
              <h3 className="flex-1 font-bold text-ink">Phương án {index + 1}: {item.label}</h3>
              {index === 0 && <span className="rounded-full bg-mint px-3 py-1 text-xs font-semibold text-forest">Ưu tiên đối chiếu</span>}
            </div>
            <div className="space-y-5 p-5">
              <div className="grid gap-4 md:grid-cols-[.8fr_1.2fr]">
                <div><p className="text-xs font-semibold text-slate-500">{item.classification_mode === 'separate' ? 'Phân loại riêng từng mặt hàng' : 'Mã HS đề xuất theo phương án'}</p>{articles.map((article, articleIndex) => <div className="mt-2" key={articleIndex}>{item.classification_mode === 'separate' && <p className="font-medium">{article.name}</p>}<p className="break-words text-3xl font-bold tracking-tight text-forest md:text-4xl">{hs(article.code)}</p></div>)}</div>
                <div className="rounded-xl bg-amber-50 p-4"><h4 className="font-semibold text-amber-950">Giả định phần còn thiếu</h4><ul className="mt-2 list-disc space-y-1 pl-5">{item.assumptions.map((assumption, i) => <li key={i}>{assumption}</li>)}</ul></div>
              </div>
              <div><h4 className="font-semibold text-ink">Vì sao chọn mã này?</h4><p className="mt-2">{item.reasoning}<SourceMarks ids={item.source_chunk_ids} numbers={numbers}/></p></div>
              <div className="rounded-xl border border-line bg-paper p-4"><h4 className="font-semibold text-ink">Tên hàng theo phương án này</h4>
                {item.classification_mode === 'separate' ? <ul className="mt-2 space-y-2">{articles.map((article, i) => <li key={i}><strong>{hs(article.code)}:</strong> {proposal?.items[i]?.name || article.name}</li>)}</ul>
                  : <p className="mt-2">{proposal?.name || name}</p>}
                <p className="mt-2 text-xs text-slate-500">Tên đề xuất dùng các dữ kiện đã khai và điều kiện giả định của đúng phương án này.</p>
              </div>
              {articles.map((article, i) => <section key={i}><h4 className="mb-3 font-semibold text-ink">Thuế suất{articles.length > 1 ? ` · ${article.name} · ${hs(article.code)}` : ''}</h4><ClassificationTariff code={article.code} tariff={article.tariff_rates} conditional/></section>)}
              <details className="text-xs"><summary className="cursor-pointer font-semibold text-slate-600">Đối chiếu mô tả trong danh mục</summary>{articles.map((article, i) => <p className="mt-2" key={i}><strong>{hs(article.code)}:</strong> {article.catalog_description || 'Xem căn cứ và nguồn của phương án.'}<SourceMarks ids={article.source_chunk_ids} numbers={numbers}/></p>)}</details>
            </div>
          </section>;
        })}</div>
      </>}

      {!completed && !conditional && <section className="rounded-xl border border-amber-200 bg-amber-50 p-4">
        <h3 className="font-semibold text-ink">Phần phân tích đã thực hiện</h3><p className="mt-2">{analysis?.summary || 'Cần đối chiếu thêm tài liệu và nhánh danh mục để đưa ra mã có thể kiểm chứng.'}</p>
        {!!result.missingInformation?.length && <ul className="mt-3 list-disc space-y-1 pl-5">{result.missingInformation.map((item, index) => <li key={index}>{item}</li>)}</ul>}
      </section>}

      {(completed || conditional) && <section>
        <h3 className="text-base font-bold text-ink">Mã HS dễ nhầm</h3>
        {!!analysis?.alternatives?.length ? <div className="mt-3 grid gap-3 md:grid-cols-2">{analysis.alternatives.map((item, index) => <div key={`${item.code}-${index}`} className="rounded-xl border border-line p-4"><p className="text-lg font-bold text-ink">{hs(item.code)}</p><p className="mt-2">{item.reason}<SourceMarks ids={item.source_chunk_ids} numbers={numbers}/></p></div>)}</div>
          : <p className="mt-2 text-slate-500">Chưa có mã dễ nhầm được xác minh cho kết quả này.</p>}
      </section>}

      {analysis?.product_understanding && <details className="border-t border-line pt-4">
        <summary className="cursor-pointer font-semibold text-ink">Mặt hàng được hiểu từ mô tả và chú giải</summary>
        <p className="mt-3">{analysis.product_understanding.meaning}<SourceMarks ids={analysis.product_understanding.definition_source_ids} numbers={numbers}/></p>
        {!!analysis.product_understanding.facts.length && <ul className="mt-3 list-disc space-y-2 pl-5">{analysis.product_understanding.facts.map((fact, index) => <li key={index}>{fact.value} <span className="text-xs text-slate-500">({fact.basis === 'definition' ? 'theo định nghĩa trong chú giải' : 'đã khai trong mô tả'})</span><SourceMarks ids={fact.source_chunk_ids} numbers={numbers}/></li>)}</ul>}
      </details>}
      {!!analysis?.decision_questions?.length && <details className="border-t border-line pt-4">
        <summary className="cursor-pointer font-semibold text-ink">Hệ thống tự phân tích bằng câu hỏi ngắn</summary>
        <ol className="mt-3 space-y-3">{analysis.decision_questions.map((item, index) => <li key={index}><p className="font-semibold">{item.question}</p><p className="mt-1">{item.answer}<SourceMarks ids={item.source_chunk_ids} numbers={numbers}/></p></li>)}</ol>
      </details>}
      {conditional && !!analysis?.legal_steps?.length && <details className="border-t border-line pt-4"><summary className="cursor-pointer font-semibold text-ink">Trình tự đối chiếu pháp lý</summary><ol className="mt-3 space-y-3">{analysis.legal_steps.map((step, index) => <li key={index}><strong>{step.rule}</strong><SourceMarks ids={step.source_chunk_ids} numbers={numbers}/><p className="mt-1">{step.application}</p></li>)}</ol></details>}
      {declaration && <details className="border-t border-line pt-4"><summary className="cursor-pointer font-semibold text-ink">Chi tiết tên hàng và chứng từ chuyên ngành</summary><div className="mt-3"><DeclarationAnswer declaration={declaration} showProposals={false} showName={false}/></div></details>}
      {!!analysis?.references?.length && <details className="border-t border-line pt-4"><summary className="cursor-pointer font-semibold text-ink">Nguồn pháp lý đã đối chiếu · {analysis.references.length} nguồn</summary><div className="mt-3 space-y-3">{analysis.references.map((ref, index) => <div id={`legal-source-${prefix}${ref.chunk_id}`} key={ref.chunk_id} className="scroll-mt-6 rounded-xl border border-line p-4 text-xs"><p className="font-semibold">[{index + 1}] {ref.title}{ref.page ? ` · Trang ${ref.page}` : ''}</p><p className="mt-1 break-words text-slate-500">{ref.source}</p><p className="mt-2 whitespace-pre-wrap leading-5">{ref.excerpt}</p></div>)}</div></details>}
    </div>
  </Card>;
}

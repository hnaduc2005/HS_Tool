import type { TariffRates } from '@/lib/api';
import { displayRate, tariffFor } from '@/lib/classification-presentation';

export function ClassificationTariff({ code, tariff, conditional = false }: { code: string; tariff?: TariffRates | null; conditional?: boolean }) {
  const matched = tariffFor(code, tariff);
  if (!matched) return <p className="rounded-xl bg-paper p-3 text-sm text-slate-600">Chưa có dữ liệu thuế được đối chiếu cho mã này.</p>;
  return <div>
    <p className="mb-3 text-xs text-slate-600">{conditional ? 'Thuế của mã trong phương án này, khi các giả định được xác nhận.' : 'Thuế tra theo đúng mã HS được đề xuất.'}</p>
    <dl className="grid gap-2 sm:grid-cols-3">
      {[['NK ưu đãi (MFN)', matched.mfn], ['NK thông thường', matched.normal], ['GTGT (VAT)', matched.vat]].map(([label, raw]) => <div key={label} className="rounded-xl border border-line bg-paper px-4 py-3">
        <dt className="text-xs font-medium text-slate-600">{label}</dt>
        <dd className="mt-1 text-xl font-bold text-ink">{displayRate(raw)}</dd>
      </div>)}
    </dl>
    {matched.vat === '8/10' && <p className="mt-2 text-xs text-slate-600">Bảng ghi hai mức GTGT; cần xác định hàng thuộc diện giảm thuế tại thời điểm khai báo.</p>}
    <details className="mt-3 text-sm"><summary className="cursor-pointer font-semibold text-forest">Thuế FTA và điều kiện áp dụng</summary>
      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2">{[['ATIGA', matched.atiga], ['ACFTA', matched.acfta], ['AKFTA', matched.akfta]].map(([label, raw]) => <div key={label}><dt className="inline text-slate-600">{label}: </dt><dd className="inline font-semibold">{displayRate(raw)}</dd></div>)}</dl>
      <p className="mt-2 text-xs text-slate-600">Các mức FTA chỉ áp dụng khi đáp ứng xuất xứ và điều kiện của hiệp định tương ứng.</p>
    </details>
    <p className="mt-3 text-xs leading-5 text-slate-500">Nguồn: {matched.source}. Đối chiếu văn bản còn hiệu lực tại ngày đăng ký tờ khai.</p>
  </div>;
}

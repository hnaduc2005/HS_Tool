import type { DeclarationInformation } from '@/lib/api';

const labels = {
  vietnamese_name: 'Tên tiếng Việt', composition_material: 'Thành phần / Chất liệu',
  use_technical: 'Công dụng / Thông số kỹ thuật', model_code: 'Model / Code',
  brand_origin: 'Nhãn hiệu / Xuất xứ', condition: 'Tình trạng',
};
export function DeclarationAnswer({ declaration, showProposals = true, showName = true }: { declaration: DeclarationInformation; showProposals?: boolean; showName?: boolean }) {
  return <section className="rounded-xl border border-line bg-paper p-4">
    {showName && <><h3 className="font-bold text-ink">Tên hàng đề xuất từ sản phẩm nhập vào</h3>
    <p className="mt-1 text-xs text-slate-500">Tên tiếng Việt + Thành phần/Chất liệu + Công dụng/Thông số kỹ thuật + Model/Code + Nhãn hiệu/Xuất xứ + Tình trạng</p>
    <p className="mt-3 font-semibold">Tên hàng theo thông tin đã xác định</p>
    <p className="mt-1 whitespace-pre-wrap">{declaration.draft_name}</p></>}
    {showProposals && !!declaration.proposals?.length && <div className="mt-4 space-y-3"><h4 className="font-semibold">Tên hàng theo từng phương án HS</h4>{declaration.proposals.map((proposal, index) => <div key={`${proposal.code}-${index}`} className="rounded-lg border border-line p-3">
      <p className="text-sm font-semibold">{proposal.label} — {proposal.classification_mode === 'separate' ? 'Phân loại từng mặt hàng' : proposal.code}</p>
      {proposal.classification_mode === 'separate' ? <ul className="mt-1 list-disc pl-5">{proposal.items.map((item, i) => <li key={i}>{item.name} — {item.code}</li>)}</ul> : <p className="mt-1">{proposal.name}</p>}
      <p className="mt-2 text-xs text-amber-900"><strong>Giả định áp dụng:</strong> {proposal.assumptions.join('; ')}.</p>
    </div>)}</div>}
    {!!declaration.missing_fields.length && <p className="mt-3 text-sm text-slate-600">Thông tin cần xác nhận trước khi khai báo: {declaration.missing_fields.map(field => field.label).join('; ')}.</p>}
    <details className="mt-3"><summary className="cursor-pointer text-sm font-semibold">Chi tiết sáu nhóm thông tin</summary><dl className="mt-3 grid gap-3 sm:grid-cols-2">{Object.entries(labels).map(([key, label]) => <div key={key}><dt className="text-xs font-semibold text-slate-500">{label}</dt><dd className={declaration.fields[key as keyof typeof labels] ? '' : 'text-amber-800'}>{declaration.fields[key as keyof typeof labels] || 'Chưa khai'}</dd></div>)}</dl></details>
    {!!declaration.warnings.length && <ul className="mt-3 list-disc space-y-1 pl-5 text-amber-900">{declaration.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}
    <div className="mt-4 border-t border-line pt-3"><h4 className="font-semibold">Đối chiếu chứng từ chuyên ngành</h4>
      {declaration.specialized_document_name && <p className="mt-1"><strong>Tên trên chứng từ:</strong> {declaration.specialized_document_name}</p>}
      <p className={`mt-1 ${declaration.specialized_check === 'matches' ? 'text-forest' : declaration.specialized_check === 'mismatch' ? 'text-amber-900' : 'text-slate-600'}`}>{declaration.specialized_check === 'matches' ? 'Tên đã khớp với tên trên chứng từ bạn nhập.' : declaration.specialized_check === 'mismatch' ? 'Tên chưa khớp. Cần đối chiếu và chỉnh lại trước khi khai báo.' : declaration.specialized_check === 'incomplete' ? 'Cần hoàn thiện các thông tin còn thiếu trước khi đối chiếu tên.' : 'Chưa có tên chứng từ để đối chiếu. Nếu hàng thuộc diện kiểm tra chuyên ngành, nhập tên trên giấy đăng ký kiểm tra tương ứng.'}</p>
    </div>
  </section>;
}

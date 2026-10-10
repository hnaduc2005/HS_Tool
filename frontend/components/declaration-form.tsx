'use client';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { DeclarationInput } from '@/lib/api';

export const emptyDeclaration: DeclarationInput = {};
export function DeclarationForm({ value, onChange, idPrefix = '' }: { value: DeclarationInput; onChange: (value: DeclarationInput) => void; idPrefix?: string }) {
  const update = (key: keyof DeclarationInput, text: string) => onChange({ ...value, [key]: text || undefined });
  return <details className="mt-4 rounded-xl border border-line bg-paper p-4">
    <summary className="cursor-pointer text-sm font-semibold text-ink">Bổ sung thông tin khai báo (nếu có)</summary>
    <p className="mt-3 text-sm text-slate-600">Hệ thống tự đề xuất tên hàng bằng tiếng Việt theo sản phẩm nhập vào và từng phương án HS. Bạn có thể bổ sung các dữ kiện trong hồ sơ ở đây.</p>
    <p className="mt-3 text-xs leading-5 text-slate-600">Tên tiếng Việt + Thành phần/Chất liệu + Công dụng/Thông số kỹ thuật + Model/Code + Nhãn hiệu/Xuất xứ + Tình trạng.</p>
    <p className="mt-2 text-xs leading-5 text-slate-500">Ví dụ: Máy bơm nước ly tâm dùng trong công nghiệp, công suất 5kW, điện áp 380V, Model: PU-500, hiệu Ebara, mới 100%.</p>
    <div className="mt-4 grid gap-3 sm:grid-cols-2">
      <div className="sm:col-span-2"><label htmlFor={`${idPrefix}decl-name`} className="mb-1 block text-xs font-semibold">Tên tiếng Việt</label><Input id={`${idPrefix}decl-name`} maxLength={200} value={value.vietnamese_name || ''} onChange={e => update('vietnamese_name', e.target.value)} placeholder="Máy bơm nước ly tâm"/></div>
      <div className="sm:col-span-2"><label htmlFor={`${idPrefix}decl-material`} className="mb-1 block text-xs font-semibold">Thành phần / Chất liệu</label><Input id={`${idPrefix}decl-material`} maxLength={300} value={value.composition_material || ''} onChange={e => update('composition_material', e.target.value)} placeholder="Thân bằng gang; ghi tỷ lệ nếu là hỗn hợp"/></div>
      <div className="sm:col-span-2"><label htmlFor={`${idPrefix}decl-technical`} className="mb-1 block text-xs font-semibold">Công dụng / Thông số kỹ thuật</label><Textarea id={`${idPrefix}decl-technical`} rows={2} maxLength={500} value={value.use_technical || ''} onChange={e => update('use_technical', e.target.value)} placeholder="Dùng trong công nghiệp, công suất 5kW, điện áp 380V"/></div>
      <div><label htmlFor={`${idPrefix}decl-model`} className="mb-1 block text-xs font-semibold">Model / Code</label><Input id={`${idPrefix}decl-model`} maxLength={150} value={value.model_code || ''} onChange={e => update('model_code', e.target.value)} placeholder="PU-500"/></div>
      <div><label htmlFor={`${idPrefix}decl-condition`} className="mb-1 block text-xs font-semibold">Tình trạng</label><select id={`${idPrefix}decl-condition`} className="h-11 w-full rounded-xl border border-line bg-white px-3 text-sm focus:border-forest" value={value.condition || ''} onChange={e => update('condition', e.target.value)}><option value="">Chưa khai</option><option value="new">Mới 100%</option><option value="used">Đã qua sử dụng</option></select></div>
      <div className="sm:col-span-2"><label htmlFor={`${idPrefix}decl-brand`} className="mb-1 block text-xs font-semibold">Nhãn hiệu / Xuất xứ</label><Input id={`${idPrefix}decl-brand`} maxLength={200} value={value.brand_origin || ''} onChange={e => update('brand_origin', e.target.value)} placeholder="Hiệu Ebara, xuất xứ theo chứng từ"/></div>
      <div className="sm:col-span-2"><label htmlFor={`${idPrefix}decl-specialized`} className="mb-1 block text-xs font-semibold">Tên trên chứng từ chuyên ngành (nếu có)</label><Textarea id={`${idPrefix}decl-specialized`} rows={3} maxLength={1800} value={value.specialized_document_name || ''} onChange={e => update('specialized_document_name', e.target.value)} placeholder="Chép tên trên giấy đăng ký kiểm tra chất lượng, hợp chuẩn hợp quy hoặc kiểm dịch để đối chiếu"/></div>
    </div>
    <p className="mt-3 text-xs text-slate-500">Chỉ ghi dữ kiện có trong hồ sơ; nếu không có model hoặc nhãn hiệu, ghi rõ “không có”. Thiếu thông tin vẫn có thể tra cứu HS theo giả định, nhưng cần hoàn thiện tên trước khi khai báo.</p>
    <details className="mt-3 text-xs text-slate-600"><summary className="cursor-pointer font-semibold">4 điểm cần kiểm tra khi khai tên hàng</summary><ol className="mt-2 list-decimal space-y-2 pl-4"><li>Tránh tên quá chung như “Phụ tùng xe máy”, “Linh kiện máy tính”, “Mỹ phẩm”, “Nông sản”.</li><li>Dịch tên trên Invoice sang tiếng Việt và mô tả chất liệu, đặc điểm; “Plastic Toy” cần ghi rõ là đồ chơi bằng nhựa và loại đồ chơi.</li><li>Ghi rõ “mới 100%” hoặc “đã qua sử dụng”.</li><li>Nếu thuộc diện kiểm tra chuyên ngành, đối chiếu tên hàng với tên trên giấy đăng ký kiểm tra tương ứng.</li></ol></details>
  </details>;
}

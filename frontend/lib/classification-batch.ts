import type { DeclarationInput, PreparedItems, Search } from '@/lib/api';

export type BatchItem = {
  key: string; description: string; declaration: DeclarationInput;
  state: 'waiting' | 'loading' | 'done' | 'error'; result?: Search; error?: string;
  savedId?: string;
};

export const MAX_BATCH_ITEMS = 10;
export function hasNumberedRows(description: string): boolean {
  return [...description.matchAll(/^\s*\d{1,3}[.)][ \t]+(?=\S)/gm)].length >= 2;
}

export async function prepareDraftItems(items: BatchItem[], prepare: (description: string) => Promise<PreparedItems>) {
  const expanded: BatchItem[] = [];
  let needsReview = false;
  let message = '';
  for (const item of items) {
    if (!hasNumberedRows(item.description)) { expanded.push(item); continue; }
    const prepared = await prepare(item.description);
    if (prepared.needs_review) {
      expanded.push(item); needsReview = true;
      message = prepared.message || 'Kiểm tra cách tách danh sách trước khi phân tích.'; continue;
    }
    if (prepared.items.length <= 1) { expanded.push(item); continue; }
    if (Object.values(item.declaration).some(Boolean)) {
      expanded.push(item); needsReview = true;
      message = `Ô mô tả chứa ${prepared.items.length} mặt hàng. Hãy chuyển thông tin bổ sung vào mô tả đúng món rồi xóa biểu mẫu chung của ô này để tách, tránh gán cùng model/chất liệu cho nhiều món.`;
      continue;
    }
    expanded.push(...prepared.items.map((row, index) => ({ key: `${item.key}-${index + 1}`,
      description: row.description, declaration: {}, state: 'waiting' as const })));
  }
  return { items: expanded, needsReview, message };
}

export function batchError(items: Pick<BatchItem, 'description' | 'declaration'>[]): string {
  if (!items.length || items.length > MAX_BATCH_ITEMS) return 'Mỗi lượt phân tích từ 1 đến 10 mặt hàng.';
  for (let i = 0; i < items.length; i++) {
    if (items[i].description.trim().length < 2 && !items[i].declaration.vietnamese_name?.trim()) return `Mặt hàng ${i + 1}: nhập mô tả hoặc bổ sung tên tiếng Việt.`;
    if (items[i].description.length > 2000) return `Mặt hàng ${i + 1}: mô tả tối đa 2.000 ký tự; hãy chia đúng từng mặt hàng.`;
  }
  return '';
}

export async function runClassificationBatch(items: BatchItem[], classify: (item: BatchItem) => Promise<Search>,
  update: (key: string, patch: Partial<BatchItem>) => void): Promise<void> {
  // Limit upstream pressure and show results as each product finishes.
  for (const item of items) {
    update(item.key, { state: 'loading', error: undefined });
    try {
      const result = await classify(item);
      update(item.key, { state: 'done', result });
    } catch (error) {
      update(item.key, { state: 'error', error: error instanceof Error ? error.message : 'Không thể phân tích mặt hàng này.' });
    }
  }
}

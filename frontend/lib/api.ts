import { AUTH_EXPIRED_EVENT, AUTH_TOKEN_KEY } from '@/lib/auth';

export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api';
export type Source = { id: string; page: number | null; relevanceScore: number; document: { id: string; title: string; source: string }; chunk: { content: string } };
export type Result = { id: string; hsCode: string; description: string; confidence: number; reasoning: string; rank: number; sources: Source[] };
export type TariffRates = { code: string; normal: string | null; mfn: string | null; vat: string | null;
  acfta: string | null; atiga: string | null; akfta: string | null; source: string };
export type HypothesisItem = { name: string; code: string; source_chunk_ids: string[]; catalog_description?: string; tariff_rates?: TariffRates | null };
export type Hypothesis = { code: string; label: string; assumptions: string[]; reasoning: string; source_chunk_ids: string[];
  assumed_attributes?: { attribute: string; value: string }[];
  classification_mode?: 'single' | 'separate'; items?: HypothesisItem[]; catalog_description?: string; tariff_rates?: TariffRates | null };
export type DeclarationInput = {
  vietnamese_name?: string; composition_material?: string; use_technical?: string;
  model_code?: string; brand_origin?: string; condition?: 'new' | 'used'; specialized_document_name?: string;
};
export type DeclarationInformation = {
  original_description: string; input: DeclarationInput;
  fields: Record<'vietnamese_name' | 'composition_material' | 'use_technical' | 'model_code' | 'brand_origin' | 'condition', string>;
  draft_name: string; missing_fields: { key: string; label: string }[]; warnings: string[];
  proposals?: { code: string; label: string; name: string; assumptions: string[];
    classification_mode: 'single' | 'separate'; items: { name: string; code: string }[] }[];
  specialized_document_name: string; specialized_check: 'not_provided' | 'matches' | 'mismatch' | 'incomplete';
};
export type LegalAnalysis = {
  summary: string; product_facts: string[];
  product_understanding?: {
    product_name: string; meaning: string; scope: string; missing_attributes: string[]; definition_source_ids: string[];
    facts: { attribute: string; value: string; basis: string; product_quote: string; source_quote: string; source_chunk_ids: string[] }[];
  };
  decision_questions?: { question: string; answer: string; source_chunk_ids: string[] }[];
  legal_steps: { rule: string; application: string; source_chunk_ids: string[] }[];
  alternatives: { code: string; reason: string; source_chunk_ids: string[] }[];
  hypotheses?: Hypothesis[];
  conclusion: string; limitations: string[];
  suggested_name?: string; declaration_details?: string[];
  declaration_information?: DeclarationInformation;
  tariff_rates?: TariffRates | null;
  references: { chunk_id: string; document_id: string; title: string; source: string; page: number | null; excerpt: string }[];
};
export type Search = { id: string; userId?: string | null; productDescription: string; normalizedProduct: Record<string, string | number | string[] | null>; legalAnalysis?: LegalAnalysis; status: string; missingInformation: string[]; createdAt: string; results: Result[] };
export type PreparedItems = { items: { description: string }[]; needs_review: boolean; message: string };
export function searchCodeLabel(search: Search): string {
  const first = search.legalAnalysis?.hypotheses?.[0];
  if (search.results[0]?.hsCode) return search.results[0].hsCode;
  if (first?.classification_mode === 'separate' && first.items?.length) return first.items.map(item => item.code).join(' / ') + ' (theo giả định)';
  if (first?.code) return first.code + ' (theo giả định)';
  return 'Chưa có phương án mã hợp lệ';
}
export function hasAiServiceFailure(search: Search): boolean {
  if (search.legalAnalysis?.legal_steps?.length) return false;
  return [...(search.missingInformation || []), ...(search.legalAnalysis?.limitations || [])]
    .some(note => note.includes('Dịch vụ phân tích') && /không sẵn sàng|chưa sẵn sàng/.test(note));
}
export class ApiError extends Error {
  constructor(message: string, public readonly status: number) { super(message); }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const publicAuth = path === '/auth/login' || path === '/auth/register';
  const token = typeof window === 'undefined' || publicAuth ? null : sessionStorage.getItem(AUTH_TOKEN_KEY);
  const response = await fetch(`${API}${path}`, { cache: 'no-store', ...options, headers: { ...(options.body instanceof FormData ? {} : { 'content-type': 'application/json' }), ...(token ? { authorization: `Bearer ${token}` } : {}), ...options.headers } });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (!publicAuth && typeof window !== 'undefined'
      && (response.status === 401 || (response.status === 403 && body.code === 'EMAIL_DOMAIN_NOT_ALLOWED'))
      && sessionStorage.getItem(AUTH_TOKEN_KEY) === token) {
      sessionStorage.removeItem(AUTH_TOKEN_KEY);
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    throw new ApiError(Array.isArray(body.message) ? body.message.join('. ') : body.message || body.error || `HTTP ${response.status}`, response.status);
  }
  return body as T;
}

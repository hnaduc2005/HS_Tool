import { BadRequestException, Body, Controller, Get, HttpException, HttpStatus, Injectable, NotFoundException, Param, Post, Query, Req, UploadedFile, UseGuards, UseInterceptors } from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { extname } from 'path';
import { Express } from 'express';
import { IsBoolean, IsIn, IsInt, IsObject, IsOptional, IsString, Max, MaxLength, Matches, Min, ValidateNested } from 'class-validator';
import { Type } from 'class-transformer';
import { Prisma } from '@prisma/client';
import { Database } from '../database';
import { AuthRequest, AuthService, UserGuard } from '../auth/auth';
import { HsCodesService, type CatalogHints } from '../hs-codes/hs-codes';
import { tariffRatesFor, type TariffRates } from '../hs-codes/tariff-rates';
import { aiCall } from '../ai/client';
import { LocalDocumentStorage } from '../documents/storage';
import { declarationDescription, declarationInformation, type DeclarationInput, type DeclarationInformation } from './declaration';

class DeclarationDto implements DeclarationInput {
  @IsOptional() @IsString() @MaxLength(200) vietnamese_name?: string;
  @IsOptional() @IsString() @MaxLength(300) composition_material?: string;
  @IsOptional() @IsString() @MaxLength(500) use_technical?: string;
  @IsOptional() @IsString() @MaxLength(150) model_code?: string;
  @IsOptional() @IsString() @MaxLength(200) brand_origin?: string;
  @IsOptional() @IsIn(['new', 'used']) condition?: 'new' | 'used';
  @IsOptional() @IsString() @MaxLength(1800) specialized_document_name?: string;
}
class SearchDto {
  @IsString() @MaxLength(2000) description!: string;
  @IsOptional() @IsObject() @ValidateNested() @Type(() => DeclarationDto) declaration?: DeclarationDto;
}
class PrepareItemsDto {
  @IsString() @MaxLength(20000) description!: string;
}
type HistoryScope = 'all' | 'mine' | 'legacy';
class HistoryQueryDto {
  @IsOptional() @Type(() => Number) @IsInt() @Min(1) @Max(100000) page = 1;
  @IsOptional() @IsIn(['all', 'mine', 'legacy']) scope: HistoryScope = 'all';
}
class FeedbackDto {
  @IsBoolean() is_correct!: boolean;
  @IsOptional() @IsString() @Matches(/^\d{4,8}$/) correct_hs_code?: string;
  @IsOptional() @IsString() @MaxLength(1000) comment?: string;
  @IsOptional() @IsString() result_id?: string;
}
type Candidate = { code: string; description: string; score?: number };
type AiSource = { chunk_id: string; document_id: string; page: number | null; relevance_score: number };
type HypothesisItem = { name: string; code: string; source_chunk_ids: string[]; catalog_description?: string; tariff_rates?: TariffRates | null };
type Hypothesis = {
  code: string; label: string; assumptions: string[]; reasoning: string; source_chunk_ids: string[];
  assumed_attributes?: Array<{ attribute: string; value: string }>;
  classification_mode?: 'single' | 'separate'; items?: HypothesisItem[];
  catalog_description?: string;
  tariff_rates?: TariffRates | null;
};
type LegalAnalysis = {
  summary: string; product_facts: string[];
  product_understanding?: {
    product_name: string; scope: string; meaning: string; missing_attributes: string[]; definition_source_ids: string[];
    facts: Array<{ attribute: string; value: string; basis: string; product_quote: string; source_quote: string; source_chunk_ids: string[] }>;
  };
  decision_questions?: Array<{ question: string; answer: string; source_chunk_ids: string[] }>;
  legal_steps: Array<{ rule: string; application: string; source_chunk_ids: string[] }>;
  alternatives: Array<{ code: string; reason: string; source_chunk_ids: string[] }>;
  hypotheses?: Hypothesis[];
  conclusion: string; limitations: string[];
  suggested_name?: string; declaration_details?: string[]; tariff_rates?: TariffRates | null;
  declaration_information?: DeclarationInformation;
  references?: Array<{ chunk_id: string; document_id: string; title: string; source: string; page: number | null; excerpt: string }>;
};
type AiResult = {
  status: 'COMPLETED' | 'CONDITIONAL' | 'INSUFFICIENT_EVIDENCE';
  normalized_product: Record<string, unknown>;
  missing_information: string[];
  recommended_code?: string;
  reasoning?: string;
  llm_score?: number;
  candidates?: Array<{ code: string; score: number; reasoning: string }>;
  sources?: AiSource[];
  legal_analysis?: LegalAnalysis;
  catalog_hints?: CatalogHints;
};

const requests = new Map<string, number[]>();
function checkRate(key: string) {
  const now = Date.now();
  const recent = (requests.get(key) || []).filter(t => now - t < 60_000);
  if (recent.length >= 10) throw new HttpException('Quá nhiều yêu cầu. Vui lòng thử lại sau.', HttpStatus.TOO_MANY_REQUESTS);
  recent.push(now); requests.set(key, recent);
  if (requests.size > 10000) for (const [k, v] of requests) if (v.at(-1)! < now - 60_000) requests.delete(k);
}

@Injectable()
export class ClassificationService {
  constructor(private readonly db: Database, private readonly hs: HsCodesService, private readonly auth: AuthService) {}
  async prepareItems(description: string, req: AuthRequest) {
    const session = req.session || await this.auth.verify(req);
    checkRate(`prepare:${session.sub}`);
    const text = description.trim();
    if (text.length < 2) throw new BadRequestException('Nhập mô tả hàng hóa từ 2 ký tự.');
    return aiCall<{ items: { description: string }[]; needs_review: boolean; message: string }>(
      '/prepare-items', { description: text }, 120000);
  }
  async search(description: string, req: AuthRequest, declaration: DeclarationInput = {}) {
    const session = req.session || await this.auth.verify(req);
    checkRate(session.sub);
    const input = declarationDescription(description, declaration);
    let hints: CatalogHints = {};
    try { hints = (await aiCall<CatalogHints>('/discover-candidates', { description: input }, 60000)) || {}; }
    catch { /* The rule analysis can still run with lexical candidates or none. */ }
    let candidates = await this.hs.candidates(input, hints) as Candidate[];
    let ai = await aiCall<AiResult>('/classify', { description: input, candidates }, 240000);
    if (ai.status !== 'COMPLETED' && (ai.catalog_hints?.heading_hints?.length || ai.catalog_hints?.queries?.length)) {
      try {
        const refined = await this.hs.candidates(input, ai.catalog_hints) as Candidate[];
        if (refined.some(c => c.code.length === 8)) {
          const refinedAnalysis = await aiCall<AiResult>('/classify', { description: input, candidates: refined }, 240000);
          // A recovery pass may miss a previously supported family or return an
          // incomplete model response. Preserve the usable proposal and its
          // candidate catalog; the source checks below still apply to it.
          if (this.proposalCount(refinedAnalysis, refined) || !this.proposalCount(ai, candidates)) {
            ai = refinedAnalysis;
            candidates = refined;
          }
        }
      } catch {
        ai.missing_information = [...(ai.missing_information || []), 'Chưa hoàn tất lượt đối chiếu bổ sung các nhánh giả định; cần thử lại để kiểm tra thêm mã.'];
      }
    }
    const candidateMap = new Map(candidates.map(c => [c.code, c]));
    const rawSteps = Array.isArray(ai.legal_analysis?.legal_steps) ? ai.legal_analysis.legal_steps : [];
    const rawAlternatives = Array.isArray(ai.legal_analysis?.alternatives) ? ai.legal_analysis.alternatives : [];
    const rawHypotheses = Array.isArray(ai.legal_analysis?.hypotheses) ? ai.legal_analysis.hypotheses : [];
    const rawDecisions = Array.isArray(ai.legal_analysis?.decision_questions) ? ai.legal_analysis.decision_questions : [];
    const rawUnderstanding = ai.legal_analysis?.product_understanding;
    const sourceIds = [...new Set([...(ai.sources || []).map(s => s.chunk_id), ...(rawUnderstanding?.definition_source_ids || []), ...(rawUnderstanding?.facts || []).flatMap(f => f.source_chunk_ids || []), ...rawSteps.flatMap(s => s.source_chunk_ids || []), ...rawAlternatives.flatMap(s => s.source_chunk_ids || []), ...rawHypotheses.flatMap(s => s.source_chunk_ids || []),
      ...rawHypotheses.flatMap(h => (Array.isArray(h.items) ? h.items : []).flatMap(item => item?.source_chunk_ids || [])), ...rawDecisions.flatMap(d => d.source_chunk_ids || [])])];
    const validChunks = sourceIds.length ? await this.db.documentChunk.findMany({
      where: { id: { in: sourceIds }, document: { status: 'READY' } },
      select: { id: true, documentId: true, page: true, content: true, document: { select: { title: true, source: true } } },
    }) : [];
    const sourceMap = new Map(validChunks.map(c => [c.id, c]));
    const sources = (ai.sources || []).filter(s => sourceMap.get(s.chunk_id)?.documentId === s.document_id);
    const verifiedIds = (ids: string[]) => [...new Set((Array.isArray(ids) ? ids : []).filter(id => sourceMap.has(id)))];
    const legalSteps = rawSteps.filter(s => s && typeof s.rule === 'string' && typeof s.application === 'string')
      .map(s => ({ rule: s.rule.slice(0, 1500), application: s.application.slice(0, 2000), source_chunk_ids: verifiedIds(s.source_chunk_ids) }))
      .filter(s => s.rule && s.application && s.source_chunk_ids.length);
    const hypotheses: Hypothesis[] = rawHypotheses.flatMap(h => {
      if (!h || typeof h.code !== 'string' || !/^\d{8}$/.test(h.code) || !candidateMap.has(h.code)
        || typeof h.reasoning !== 'string' || !h.reasoning.trim() || !Array.isArray(h.assumptions)) return [];
      const assumptions = [...new Set(h.assumptions.filter((item): item is string => typeof item === 'string' && !!item.trim()).map(item => item.trim().slice(0, 500)))].slice(0, 6);
      const mode = h.classification_mode === 'separate' ? 'separate' as const : 'single' as const;
      let ids = verifiedIds(h.source_chunk_ids);
      const items: HypothesisItem[] = mode === 'separate' && Array.isArray(h.items) ? h.items.flatMap(item => {
        if (!item || typeof item.name !== 'string' || !item.name.trim() || typeof item.code !== 'string'
          || !/^\d{8}$/.test(item.code) || !candidateMap.has(item.code)) return [];
        const itemIds = verifiedIds(item.source_chunk_ids);
        if (!itemIds.length) return [];
        return [{ name: item.name.trim().slice(0, 150), code: item.code, source_chunk_ids: itemIds,
          catalog_description: candidateMap.get(item.code)!.description, tariff_rates: tariffRatesFor(item.code) }];
      }).slice(0, 6) : [];
      if (mode === 'separate') {
        if (items.length < 2 || items.length !== h.items?.length || h.code !== items[0].code) return [];
        ids = [...new Set([...ids, ...items.flatMap(item => item.source_chunk_ids)])];
      }
      if (!assumptions.length || !ids.length) return [];
      return [{ code: h.code, label: typeof h.label === 'string' ? h.label.slice(0, 200) : 'Giả định phân loại',
        classification_mode: mode, items, catalog_description: candidateMap.get(h.code)!.description,
        assumptions, reasoning: h.reasoning.slice(0, 1800), source_chunk_ids: ids,
        assumed_attributes: Array.isArray(h.assumed_attributes) ? h.assumed_attributes.filter(a => a && typeof a.attribute === 'string' && typeof a.value === 'string').slice(0, 12) : [],
        tariff_rates: mode === 'single' ? tariffRatesFor(h.code) : null }];
    }).slice(0, 6);
    const legalAnalysis: LegalAnalysis = {
      summary: ai.legal_analysis?.summary || 'Chưa đủ căn cứ pháp lý để kết luận.',
      product_facts: Array.isArray(ai.legal_analysis?.product_facts) ? ai.legal_analysis.product_facts : [input],
      ...(rawUnderstanding && typeof rawUnderstanding.product_name === 'string' && typeof rawUnderstanding.meaning === 'string' ? {
        product_understanding: {
          product_name: rawUnderstanding.product_name.slice(0, 300), scope: rawUnderstanding.scope, meaning: rawUnderstanding.meaning.slice(0, 1500),
          missing_attributes: Array.isArray(rawUnderstanding.missing_attributes) ? rawUnderstanding.missing_attributes.slice(0, 20) : [],
          definition_source_ids: verifiedIds(rawUnderstanding.definition_source_ids),
          facts: (Array.isArray(rawUnderstanding.facts) ? rawUnderstanding.facts : []).filter(f => f && typeof f.value === 'string' && typeof f.product_quote === 'string')
            .map(f => ({ ...f, source_chunk_ids: verifiedIds(f.source_chunk_ids) })).slice(0, 20),
        },
      } : {}),
      decision_questions: rawDecisions.filter(d => d && typeof d.question === 'string' && d.question.trim() && typeof d.answer === 'string' && d.answer.trim())
        .map(d => ({ question: d.question.trim().slice(0, 200), answer: d.answer.trim().slice(0, 900), source_chunk_ids: verifiedIds(d.source_chunk_ids) })).slice(0, 8),
      legal_steps: legalSteps,
      alternatives: rawAlternatives.filter(a => a && a.code.length === 8 && candidateMap.has(a.code) && typeof a.reason === 'string')
        .map(a => ({ code: a.code, reason: a.reason, source_chunk_ids: verifiedIds(a.source_chunk_ids) }))
        .filter(a => a.source_chunk_ids.length),
      hypotheses,
      conclusion: ai.legal_analysis?.conclusion || 'Chưa thể xác định mã HS.',
      limitations: Array.isArray(ai.legal_analysis?.limitations) ? ai.legal_analysis.limitations : [],
      suggested_name: typeof ai.legal_analysis?.suggested_name === 'string' ? ai.legal_analysis.suggested_name.slice(0, 700) : '',
      declaration_details: Array.isArray(ai.legal_analysis?.declaration_details)
        ? ai.legal_analysis.declaration_details.filter((item): item is string => typeof item === 'string').slice(0, 8).map(item => item.slice(0, 300)) : [],
      references: validChunks.map(c => ({ chunk_id: c.id, document_id: c.documentId, title: c.document.title,
        source: c.document.source, page: c.page, excerpt: c.content.slice(0, 1800) })),
    };
    const normalizedProduct = { ...(ai.normalized_product || {}) };
    legalAnalysis.declaration_information = declarationInformation(input, declaration, legalAnalysis.product_understanding, hypotheses);
    legalAnalysis.declaration_information.original_description = description.trim();
    legalAnalysis.suggested_name = legalAnalysis.declaration_information.draft_name;
    legalAnalysis.declaration_details = legalAnalysis.declaration_information.missing_fields.map(field => field.label);
    const separate = hypotheses[0]?.classification_mode === 'separate';
    const conditionalCode = separate ? '' : hypotheses[0]?.code
      || (typeof normalizedProduct.provisional_code === 'string' && /^\d{8}$/.test(normalizedProduct.provisional_code)
        && candidateMap.has(normalizedProduct.provisional_code) && legalSteps.length ? normalizedProduct.provisional_code : '');
    if (conditionalCode) normalizedProduct.provisional_code = conditionalCode;
    else delete normalizedProduct.provisional_code;
    if (separate) normalizedProduct.provisional_codes = hypotheses[0].items!.map(item => item.code);
    else delete normalizedProduct.provisional_codes;
    const tariffCode = separate ? undefined : ai.status === 'COMPLETED' ? ai.recommended_code : conditionalCode;
    legalAnalysis.tariff_rates = tariffCode && candidateMap.has(tariffCode) ? tariffRatesFor(tariffCode) : null;
    if (ai.status !== 'COMPLETED' || hypotheses.length || separate || !ai.recommended_code || ai.recommended_code.length !== 8 || !candidateMap.has(ai.recommended_code) || !sources.length || !legalSteps.length) {
      const missing = [...(ai.missing_information || [])];
      if (ai.status === 'COMPLETED' && ai.recommended_code && ai.recommended_code.length !== 8) missing.push('Mã HS đề xuất chưa đủ 8 số để khai báo tại Việt Nam; cần đối chiếu phân nhóm chi tiết trong danh mục.');
      if (!sources.length && ai.status === 'COMPLETED') missing.push('Không có trích dẫn tài liệu hợp lệ cho mã đề xuất.');
      if (!legalSteps.length) missing.push('Chưa xác minh được điều khoản pháp lý cụ thể có trích dẫn hợp lệ.');
      legalAnalysis.limitations = [...new Set([...legalAnalysis.limitations, ...missing])];
      if (ai.status === 'COMPLETED') legalAnalysis.conclusion = 'Chưa đủ căn cứ để chốt mã HS.';
      return this.saveAnalysis(input, session.sub, normalizedProduct, missing.length ? missing : hypotheses.length ? [] : ['Cần bổ sung nguồn tài liệu để đối chiếu'], legalAnalysis);
    }
    const ranked = [{ code: ai.recommended_code, score: ai.llm_score ?? 0.5, reasoning: ai.reasoning || '' }, ...(ai.candidates || []).filter(c => c.code !== ai.recommended_code)]
      .filter(c => c.code.length === 8 && candidateMap.has(c.code)).slice(0, 4);
    const result = await this.db.classificationSearch.create({
      data: {
        userId: session.sub, productDescription: input, normalizedProduct: normalizedProduct as Prisma.InputJsonValue,
        legalAnalysis: legalAnalysis as unknown as Prisma.InputJsonValue,
        status: 'COMPLETED', missingInformation: (ai.missing_information || []) as Prisma.InputJsonValue,
        results: { create: ranked.map((r, i) => ({
          hsCode: r.code, description: candidateMap.get(r.code)!.description,
          confidence: Math.max(0, Math.min(1, Number(r.score) || 0)), reasoning: r.reasoning, rank: i + 1,
          sources: i === 0 ? { create: sources.map(s => ({ documentId: s.document_id, chunkId: s.chunk_id, page: sourceMap.get(s.chunk_id)!.page, relevanceScore: Math.max(0, Math.min(1, Number(s.relevance_score) || 0)) })) } : undefined,
        })) },
      }, include: this.include,
    });
    return result;
  }
  private include = { results: { orderBy: { rank: 'asc' as const }, include: { sources: { include: { document: { select: { id: true, title: true, source: true } }, chunk: { select: { content: true } } } } } } };
  private proposalCount(analysis: AiResult, candidates: Candidate[]) {
    const allowed = new Set(candidates.filter(candidate => candidate.code.length === 8).map(candidate => candidate.code));
    if (!analysis.legal_analysis?.legal_steps?.some(step => step.source_chunk_ids?.length)) return 0;
    if (analysis.status === 'COMPLETED' && analysis.recommended_code && allowed.has(analysis.recommended_code)
      && analysis.sources?.length && !analysis.legal_analysis.hypotheses?.length) return 1;
    return (analysis.legal_analysis.hypotheses || []).filter(hypothesis => allowed.has(hypothesis.code)
      && hypothesis.assumptions?.length && hypothesis.reasoning && hypothesis.source_chunk_ids?.length
      && (hypothesis.classification_mode !== 'separate' || (hypothesis.items?.length && hypothesis.items.every(item => allowed.has(item.code) && item.source_chunk_ids?.length)))).length;
  }
  private saveAnalysis(description: string, userId: string, normalized: object, missing: string[], analysis?: LegalAnalysis) {
    const fallback: LegalAnalysis = analysis || { summary: 'Chưa thể xác định mã HS từ dữ kiện hiện có.', product_facts: [description], legal_steps: [], alternatives: [], conclusion: 'Chưa đủ căn cứ để kết luận mã HS.', limitations: missing, references: [] };
    const conditional = !!fallback.hypotheses?.length && !!fallback.legal_steps.length;
    if (conditional) {
      const first = fallback.hypotheses![0];
      const proposal = first.classification_mode === 'separate' ? first.items!.map(item => `${item.name}: ${item.code}`).join('; ') : `mã ${first.code}`;
      if (/chưa (?:đủ|thể)|không đủ/i.test(fallback.summary)) fallback.summary = `Đề xuất ${fallback.hypotheses!.length} phương án phân loại theo giả định; ưu tiên ${proposal}.`;
      fallback.conclusion = `Theo giả định ưu tiên, đề xuất ${proposal}. ${first.assumptions.join('; ')}. Các phương án khác áp dụng theo giả định được nêu trong bảng.`;
      if (!fallback.decision_questions?.length) fallback.decision_questions = [
        { question: 'Hàng hóa được mô tả là gì?', answer: description.slice(0, 900), source_chunk_ids: [] },
        ...fallback.hypotheses!.map((h, index) => ({ question: `Giả định nào áp dụng cho phương án ${index + 1}?`, answer: h.assumptions.join('; ').slice(0, 900), source_chunk_ids: h.source_chunk_ids })),
      ];
    }
    return this.db.classificationSearch.create({ data: { userId, productDescription: description, normalizedProduct: normalized as Prisma.InputJsonValue,
      legalAnalysis: fallback as unknown as Prisma.InputJsonValue, status: conditional ? 'CONDITIONAL' : 'INSUFFICIENT_EVIDENCE', missingInformation: missing as Prisma.InputJsonValue }, include: this.include });
  }
  async get(id: string, req: AuthRequest) {
    const user = req.session || await this.auth.verify(req);
    const record = await this.db.classificationSearch.findUnique({ where: { id }, include: this.include });
    if (!record || (record.userId && record.userId !== user.sub)) throw new NotFoundException();
    return record;
  }
  async history(req: AuthRequest, page: number, scope: HistoryScope = 'all') {
    const user = req.session || await this.auth.verify(req);
    // Legacy searches were public before login was required. Keep them available
    // to company members without assigning them to an arbitrary account.
    const where: Prisma.ClassificationSearchWhereInput = scope === 'mine' ? { userId: user.sub }
      : scope === 'legacy' ? { userId: null } : { OR: [{ userId: user.sub }, { userId: null }] };
    return this.db.classificationSearch.findMany({ where, orderBy: [{ createdAt: 'desc' }, { id: 'desc' }], skip: (Math.max(1, page) - 1) * 20, take: 20, include: this.include });
  }
  async feedback(id: string, input: FeedbackDto, req: AuthRequest) {
    const user = req.session || await this.auth.verify(req);
    checkRate(`feedback:${user.sub}`);
    const search = await this.db.classificationSearch.findUnique({ where: { id }, include: { results: true } });
    if (!search || (search.userId && search.userId !== user.sub)) throw new NotFoundException();
    if (input.result_id && !search.results.some(r => r.id === input.result_id)) throw new BadRequestException('Kết quả không thuộc lượt tra cứu');
    return this.db.feedback.create({ data: { searchId: id, resultId: input.result_id || search.results[0]?.id, isCorrect: input.is_correct, correctHsCode: input.correct_hs_code, comment: input.comment } });
  }
}

@Controller('classification')
@UseGuards(UserGuard)
export class ClassificationController {
  constructor(private readonly service: ClassificationService, private readonly storage: LocalDocumentStorage) {}
  @Post('extract') @UseInterceptors(FileInterceptor('file', { limits: { fileSize: 10 * 1024 * 1024 } })) async extract(@UploadedFile() file?: Express.Multer.File) {
    const ext = extname(file?.originalname || '').toLowerCase();
    if (!file || !['.pdf', '.docx', '.xlsx', '.txt'].includes(ext) || file.size > 10 * 1024 * 1024) throw new BadRequestException('Tệp không hợp lệ');
    if ((ext === '.pdf' && file.buffer.subarray(0, 5).toString() !== '%PDF-') || (['.docx', '.xlsx'].includes(ext) && file.buffer.subarray(0, 2).toString() !== 'PK') || (ext === '.txt' && file.buffer.includes(0))) throw new BadRequestException('Nội dung tệp không hợp lệ');
    const path = await this.storage.save(file.buffer, ext);
    try { return await aiCall<{ text: string }>('/extract-product', { path }); }
    finally { await this.storage.remove(path); }
  }
  @Post('search') search(@Body() body: SearchDto, @Req() req: AuthRequest) { return this.service.search(body.description, req, body.declaration || undefined); }
  @Post('prepare-items') prepareItems(@Body() body: PrepareItemsDto, @Req() req: AuthRequest) { return this.service.prepareItems(body.description, req); }
  @Get('history') history(@Req() req: AuthRequest, @Query() query: HistoryQueryDto) { return this.service.history(req, query.page, query.scope); }
  @Get(':id') get(@Param('id') id: string, @Req() req: AuthRequest) { return this.service.get(id, req); }
  @Post(':id/feedback') feedback(@Param('id') id: string, @Body() body: FeedbackDto, @Req() req: AuthRequest) { return this.service.feedback(id, body, req); }
}

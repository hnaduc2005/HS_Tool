import { Controller, Get, Injectable, NotFoundException, Param, Query, UseGuards } from '@nestjs/common';
import { Database } from '../database';
import { UserGuard } from '../auth/auth';

function cleanCode(value: string) { return value.replace(/\D/g, ''); }
export type CatalogHints = { queries?: string[]; heading_hints?: string[] };

@Injectable()
export class HsCodesService {
  constructor(private readonly db: Database) {}
  async search(query: string, limit = 20) {
    const text = (query || '').trim().slice(0, 200);
    if (!text) return [];
    const count = Math.min(Math.max(Number(limit) || 20, 1), 50);
    const code = cleanCode(text);
    if (/^[0-9. ]+$/.test(text) && code.length >= 2) {
      return this.db.hsCode.findMany({ where: { isActive: true, code: { startsWith: code } }, orderBy: { code: 'asc' }, take: count });
    }
    return this.db.$queryRawUnsafe<Array<{ id: string; code: string; description: string; level: number; score: number }>>(
      `SELECT id, code, description, level, similarity(description, $1) AS score
       FROM hs_codes WHERE is_active AND (description % $1 OR description ILIKE '%' || $1 || '%')
       ORDER BY score DESC, code ASC LIMIT $2`, text, count,
    );
  }
  async candidates(description: string, hints: CatalogHints = {}) {
    const product = description.toLowerCase();
    const words = description.toLowerCase().match(/[\p{L}\p{N}]+/gu) || [];
    const diningTable = /\bdining\s+table\b|bàn\s+ăn/i.test(product);
    const wood = /\bwood(?:en)?\b|gỗ/i.test(product);
    const firstArticle = product.split(/[,;\n]/)[0];
    const coatedPaper = /(?:giấy|bìa|\bpaper(?:board)?\b)/i.test(firstArticle)
      && !/(?:máy|\bmachine\b|\bprinter\b|ván|\bboard\b)/i.test(firstArticle)
      && /(?:phủ|tráng|tẩm|\bcoated?\b|\bcovered\b)/i.test(firstArticle);
    const hintQueries = [...new Set((Array.isArray(hints.queries) ? hints.queries : []).filter((item): item is string => typeof item === 'string')
      .map(item => item.trim().slice(0, 100)).filter(item => item.length >= 3))].slice(0, 6);
    const hintCodes = [...new Set((Array.isArray(hints.heading_hints) ? hints.heading_hints : []).filter((item): item is string => typeof item === 'string')
      .map(cleanCode).filter(code => [4, 6, 8].includes(code.length)))].slice(0, 4);
    const aliases: Array<[RegExp, string]> = [
      [/áo thun|t-shirt/i, 'áo phông'], [/cotton/i, 'bông'],
      [/giày thể thao/i, 'giày dép thể thao'], [/máy lọc nước/i, 'lọc tinh chế nước'],
      [/điện thoại/i, 'điện thoại thông minh'], [/bàn.*gỗ/i, 'đồ nội thất bằng gỗ'],
      [/túi xách/i, 'túi xách'], [/cà phê/i, 'cà phê rang'],
      [/\bmotor\b|động\s*cơ\s*điện/i, 'động cơ điện'],
      [/crochet.*machine|knitting.*machine|máy dệt móc|máy dệt kim/i, 'máy dệt kim'],
      [/stitch[ -]bonding.*machine|máy khâu đính/i, 'máy khâu đính'],
      [/embroidery.*machine|braiding.*machine|lace[ -]making.*machine|tulle[ -]making.*machine|máy thêu|máy (?:tết dây|dệt ren)/i, 'sản xuất vải tuyn, ren, thêu, trang trí, dây tết'],
      [/tufting.*machine|máy tạo búi/i, 'máy tạo búi'],
      [/\binverter\b|biến tần|nghịch lưu|rectifier|chỉnh lưu|static converter|frequency converter|variable[ -]frequency drive|\bvfd\b/i, 'máy biến đổi tĩnh điện'],
      [/\binverter\b|nghịch lưu/i, 'bộ nghịch lưu'],
      [/\brectifier\b|chỉnh lưu/i, 'bộ chỉnh lưu khác'],
      [/\btransformer\b|máy biến áp/i, 'máy biến điện'],
      [/\binductor\b|cuộn cảm/i, 'cuộn cảm'],
      [/\bballast\b|chấn lưu/i, 'chấn lưu'],
      [/\bvalve\b|van khí nén/i, 'van'],
      [/pneumatic.*valve|valve.*pneumatic|van khí nén/i, 'van dùng trong truyền động dầu thủy lực hoặc khí nén'],
      [/cà\s*vạt|caravat|cravat|\b(?:necktie|ties?)\b/i, 'cà vạt'],
      [/vớ|bít tất|tất chân|\bsocks?\b/i, 'bít tất'],
      [/linh kiện điện tử|mạch điện/i, 'mạch điện tử tích hợp'],
      [/máy bơm|bơm nước/i, 'bơm chất lỏng'], [/đèn led/i, 'đèn bộ đèn'],
    ];
    const ingredientQueries = [
      /tôm/.test(product) && 'tôm',
      /thịt\s*(?:lợn|heo)/.test(product) && 'thịt lợn',
      /cơm|gạo/.test(product) && 'gạo',
    ].filter((value): value is string => Boolean(value));
    const phrases = [...hintQueries, ...aliases.filter(([pattern]) => pattern.test(description)).map(([, query]) => query),
      ...(diningTable ? ['đồ nội thất khác', ...(wood ? ['đồ nội thất bằng gỗ khác'] : [])] : []),
      ...(coatedPaper ? ['giấy và bìa đã tráng, thấm tẩm hoặc phủ bằng plastic', 'giấy, bìa đã tráng'] : []),
      ...ingredientQueries, description.slice(0, 160), words.slice(0, 5).join(' ')].filter(Boolean);
    // An AI eight-digit hint is a search clue, not a verdict. Always retrieve
    // its six-digit siblings so a guessed material cannot hide the residual.
    const declaredFamilies = [
      coatedPaper && '4811',
      /crochet.*machine|knitting.*machine|máy dệt móc|máy dệt kim/i.test(description) && '8447',
      /\binverter\b|biến tần|nghịch lưu|rectifier|chỉnh lưu|static converter|variable[ -]frequency drive|\bvfd\b/i.test(description) && '850440',
      /\bmotor\b|động\s*cơ\s*điện/i.test(description) && '8501',
      /pneumatic.*valve|valve.*pneumatic|van khí nén/i.test(description) && '848120',
    ].filter((code): code is string => Boolean(code));
    const searchCodes = [...new Set([...declaredFamilies, ...hintCodes, ...hintCodes.filter(code => code.length === 8).map(code => code.slice(0, 6))])];
    const hinted = (await Promise.all(searchCodes.map(code => this.db.hsCode.findMany({
      where: { isActive: true, code: { startsWith: code } }, orderBy: { code: 'asc' }, take: 200,
    })))).flatMap((rows, hintIndex) => rows.map(item => ({ ...item,
      score: Math.max(0.55, 0.95 - 0.02 * hintIndex - (item.code === searchCodes[hintIndex] ? 0 : searchCodes[hintIndex].length === 6 ? 0.03 : 0.15)),
    })));
    const code = cleanCode(description);
    const list = [...hinted, ...(await Promise.all(phrases.map(p => this.search(p, 12)))).flat()];
    const scoreOf = (item: typeof list[number]) => 'score' in item ? Number(item.score || 0) : 0;
    if (/^[0-9. ]+$/.test(description.trim()) && code.length >= 2) list.push(...await this.search(code, 25));
    const headings = [...new Map(list.filter(x => x.code.length === 4 || x.code.length === 6)
      .sort((a, b) => scoreOf(b) - scoreOf(a)).map(item => [item.code, item])).values()].slice(0, 5);
    // Retrieve the family before reserving branch leads. Eight early rows can
    // hide a later six-digit mechanism or its non-electric national child.
    for (const heading of headings) list.push(...await this.db.hsCode.findMany({ where: { isActive: true, code: { startsWith: heading.code } }, orderBy: { code: 'asc' }, take: 200 }));
    const byCode = new Map<string, typeof list[number]>();
    for (const item of list) {
      const previous = byCode.get(item.code);
      if (!previous || scoreOf(item) > scoreOf(previous)) byCode.set(item.code, item);
    }
    const ranked = [...byCode.values()].sort((a, b) => scoreOf(b) - scoreOf(a));
    const branches = new Map<string, typeof list>();
    for (const item of ranked.filter(item => item.code.length === 8)) {
      // National eight-digit children can introduce additional power thresholds
      // inside one six-digit subheading. Reserve each range before applying the cap.
      const parents = item.description.split('→').slice(0, -1).map(part => part.replace(/^[\s-]+/, '').trim().replace(/:$/, '').toLowerCase());
      const key = item.code.slice(0, 6) + '|' + parents.join('|');
      const group = branches.get(key) || [];
      group.push(item); branches.set(key, group);
    }
    const branchLeads = [...branches.values()].map(group => group.find(item => /^(?:loại khác|động cơ khác)\s*$/i.test(item.description.split('→').at(-1)!.replace(/^[\s-]+/, '').trim())) || group[0]);
    // Retain siblings of strongly matched six-digit labels before broad search
    // hints fill the budget with unrelated branches. This also keeps specific
    // material cases available alongside the residual at the same level.
    const strongFamilies = ranked.filter(item => [4, 6].includes(item.code.length) && scoreOf(item) >= 0.9).slice(0, 3);
    const familyChildren = strongFamilies.flatMap(parent => ranked.filter(item => item.code.length === 8 && item.code.startsWith(parent.code)).slice(0, 8));
    const familyBranchLeads = branchLeads.filter(item => strongFamilies.some(parent => item.code.startsWith(parent.code)));
    const exactHints = ranked.filter(item => item.code.length === 8 && hintCodes.includes(item.code));
    const declaredLeads = branchLeads.filter(item => declaredFamilies.some(prefix => item.code.startsWith(prefix)));
    const declaredChildren = [...new Map([...declaredLeads, ...ranked.filter(item => item.code.length === 8 && declaredFamilies.some(prefix => item.code.startsWith(prefix)))].map(item => [item.code, item])).values()];
    const priority = [...new Map([...declaredChildren, ...exactHints, ...familyChildren, ...familyBranchLeads, ...branchLeads].map(item => [item.code, item])).values()];
    const reserved = new Set(priority.map(item => item.code));
    const selected = [...priority, ...ranked.filter(item => !reserved.has(item.code))].slice(0, 50);
    const parentCodes = [...new Set(selected.flatMap(item => item.code.length === 8 ? [item.code.slice(0, 4), item.code.slice(0, 6)] : item.code.length === 6 ? [item.code.slice(0, 4)] : []))];
    const parents = parentCodes.length ? await this.db.hsCode.findMany({ where: { code: { in: parentCodes } }, select: { code: true, description: true } }) : [];
    const descriptions = new Map(parents.map(item => [item.code, item.description]));
    return selected.map(item => {
      const hierarchy = item.code.length === 8 ? [item.code.slice(0, 4), item.code.slice(0, 6)] : item.code.length === 6 ? [item.code.slice(0, 4)] : [];
      const description = [...hierarchy.map(parent => descriptions.get(parent)).filter(Boolean), item.description]
        .map(part => String(part).replace(/^[\s-]+/, '').trim()).join(' → ');
      return { ...item, score: scoreOf(item), description };
    });
  }
}

@Controller('hs-codes')
@UseGuards(UserGuard)
export class HsCodesController {
  constructor(private readonly service: HsCodesService, private readonly db: Database) {}
  @Get('search') search(@Query('q') query: string, @Query('limit') limit?: string) { return this.service.search(query, Number(limit || 20)); }
  @Get(':code') async get(@Param('code') code: string) {
    const item = await this.db.hsCode.findUnique({ where: { code: cleanCode(code) } });
    if (!item) throw new NotFoundException();
    return item;
  }
}

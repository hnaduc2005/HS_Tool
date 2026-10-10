import { BadRequestException, Body, ConflictException, Controller, Delete, Get, Injectable, NotFoundException, Param, Patch, Post, Query, Req, UploadedFile, UseGuards, UseInterceptors } from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { IsIn, IsOptional, IsString, Matches, MaxLength, MinLength } from 'class-validator';
import { Express } from 'express';
import { randomUUID } from 'crypto';
import { extname } from 'path';
import { Database } from '../database';
import { AdminGuard } from '../auth/auth';
import { aiCall } from '../ai/client';
import { LocalDocumentStorage } from '../documents/storage';

const accepted = new Set(['.pdf', '.docx', '.xlsx', '.txt']);
const maxBytes = 60 * 1024 * 1024;
function validMagic(file: Express.Multer.File) {
  const ext = extname(file.originalname).toLowerCase();
  const bytes = file.buffer;
  if (ext === '.pdf') return bytes.subarray(0, 5).toString() === '%PDF-';
  if (ext === '.docx' || ext === '.xlsx') return bytes.subarray(0, 2).toString() === 'PK';
  if (ext === '.txt') return !bytes.includes(0);
  return false;
}

class DocumentDto {
  @IsString() @MaxLength(250) title!: string;
  @IsString() @MaxLength(500) source!: string;
  @IsOptional() @IsString() @MaxLength(100) version?: string;
}
class RoleDto { @IsIn(['USER', 'ADMIN']) role!: 'USER' | 'ADMIN'; }
class HsCodeDto {
  @IsString() @Matches(/^\d{4}(\d{2})?(\d{2})?$/) code!: string;
  @IsString() @MinLength(3) @MaxLength(2000) description!: string;
}
class HsDescriptionDto { @IsString() @MinLength(3) @MaxLength(2000) description!: string; }

@Injectable()
export class AdminService {
  constructor(private readonly db: Database, private readonly storage: LocalDocumentStorage) {}
  async upload(input: DocumentDto, file?: Express.Multer.File) {
    if (!file || !accepted.has(extname(file.originalname).toLowerCase()) || !validMagic(file) || file.size > maxBytes) throw new BadRequestException('Chỉ chấp nhận PDF, DOCX, XLSX, TXT tối đa 60 MB');
    const id = randomUUID();
    const path = await this.storage.save(file.buffer, extname(file.originalname).toLowerCase());
    const document = await this.db.document.create({ data: { id, title: input.title.trim(), source: input.source.trim(), version: input.version, documentType: extname(path).slice(1).toUpperCase(), fileUrl: path, status: 'PROCESSING' } });
    void this.index(id, path);
    return document;
  }
  async index(id: string, path: string) {
    try {
      await this.db.document.update({ where: { id }, data: { status: 'PROCESSING', error: null } });
      await aiCall('/index-document', { document_id: id, path }, 10 * 60_000);
      await this.db.document.update({ where: { id }, data: { status: 'READY' } });
    } catch (error) {
      await this.db.document.update({ where: { id }, data: { status: 'FAILED', error: error instanceof Error ? error.message.slice(0, 300) : 'Indexing failed' } }).catch(() => undefined);
    }
  }
  async reindex(id: string) {
    const doc = await this.db.document.findUnique({ where: { id } });
    if (!doc) throw new NotFoundException();
    if (doc.status === 'PROCESSING') throw new ConflictException('Tài liệu đang được lập chỉ mục');
    void this.index(id, doc.fileUrl);
    return { id, status: 'PROCESSING' };
  }
  async remove(id: string) {
    const doc = await this.db.document.findUnique({ where: { id } });
    if (!doc) throw new NotFoundException();
    await this.db.document.delete({ where: { id } });
    await this.storage.remove(doc.fileUrl);
    return { deleted: true };
  }
  async importHs(file?: Express.Multer.File) {
    if (!file || !['.xlsx', '.csv'].includes(extname(file.originalname).toLowerCase()) || file.size > maxBytes) throw new BadRequestException('Chỉ chấp nhận XLSX/CSV tối đa 60 MB');
    if ((extname(file.originalname).toLowerCase() === '.xlsx' && file.buffer.subarray(0, 2).toString() !== 'PK') || (extname(file.originalname).toLowerCase() === '.csv' && file.buffer.includes(0))) throw new BadRequestException('Nội dung tệp không hợp lệ');
    const path = await this.storage.save(file.buffer, extname(file.originalname).toLowerCase());
    try {
      const parsed = await aiCall<{ rows: Array<{ code: string; description: string; level: number; parent_code?: string }> }>('/parse-hs', { path }, 10 * 60_000);
      let count = 0;
      for (let i = 0; i < parsed.rows.length; i += 500) {
        const batch = parsed.rows.slice(i, i + 500);
        count += await this.db.$executeRawUnsafe(`INSERT INTO hs_codes (id, code, description, level, parent_code, provenance)
          SELECT gen_random_uuid(), code, description, level, parent_code, $2
          FROM jsonb_to_recordset($1::jsonb) AS x(code text, description text, level integer, parent_code text)
          ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description, level = EXCLUDED.level,
          parent_code = EXCLUDED.parent_code, provenance = EXCLUDED.provenance`, JSON.stringify(batch), `Imported from ${file.originalname}`);
      }
      return { imported: count };
    } finally { await this.storage.remove(path); }
  }
  dashboard() { return Promise.all([this.db.user.count(), this.db.hsCode.count(), this.db.document.count(), this.db.classificationSearch.count(), this.db.classificationResult.count({ where: { confidence: { lt: 0.75 } } }), this.db.feedback.count()]).then(([users, hsCodes, documents, searches, lowConfidence, feedback]) => ({ users, hsCodes, documents, searches, lowConfidence, feedback })); }
}

@Controller('admin') @UseGuards(AdminGuard)
export class AdminController {
  constructor(private readonly service: AdminService, private readonly db: Database) {}
  @Get('dashboard') dashboard() { return this.service.dashboard(); }
  @Post('documents') @UseInterceptors(FileInterceptor('file', { limits: { fileSize: maxBytes } })) upload(@Body() body: DocumentDto, @UploadedFile() file?: Express.Multer.File) { return this.service.upload(body, file); }
  @Get('documents') documents() { return this.db.document.findMany({ orderBy: { createdAt: 'desc' } }); }
  @Delete('documents/:id') remove(@Param('id') id: string) { return this.service.remove(id); }
  @Post('documents/:id/reindex') reindex(@Param('id') id: string) { return this.service.reindex(id); }
  @Post('hs-codes/import') @UseInterceptors(FileInterceptor('file', { limits: { fileSize: maxBytes } })) importHs(@UploadedFile() file?: Express.Multer.File) { return this.service.importHs(file); }
  @Post('hs-codes') createCode(@Body() body: HsCodeDto) { return this.db.hsCode.upsert({ where: { code: body.code }, create: { code: body.code, description: body.description, level: body.code.length, parentCode: body.code.length > 4 ? body.code.slice(0, -2) : null, provenance: 'Admin manual entry' }, update: { description: body.description, isActive: true, provenance: 'Admin manual entry' } }); }
  @Patch('hs-codes/:code') updateCode(@Param('code') code: string, @Body() body: HsDescriptionDto) { return this.db.hsCode.update({ where: { code }, data: { description: body.description } }); }
  @Delete('hs-codes/:code') disableCode(@Param('code') code: string) { return this.db.hsCode.update({ where: { code }, data: { isActive: false } }); }
  @Get('feedback') feedback() { return this.db.feedback.findMany({ orderBy: { createdAt: 'desc' }, take: 100, include: { search: { select: { productDescription: true } } } }); }
  @Get('history') history() { return this.db.classificationSearch.findMany({ orderBy: { createdAt: 'desc' }, take: 100, include: { results: { orderBy: { rank: 'asc' }, take: 1 } } }); }
  @Get('low-confidence') lowConfidence() { return this.db.classificationResult.findMany({ where: { confidence: { lt: 0.75 } }, orderBy: { confidence: 'asc' }, take: 100, include: { search: { select: { productDescription: true } } } }); }
  @Get('users') users() { return this.db.user.findMany({ select: { id: true, email: true, role: true, createdAt: true }, orderBy: { createdAt: 'desc' } }); }
  @Patch('users/:id/role') async role(@Param('id') id: string, @Body() body: RoleDto, @Req() req: any) {
    if (id === req.session.sub && body.role !== 'ADMIN') throw new BadRequestException('Không thể tự hạ quyền quản trị');
    return this.db.user.update({ where: { id }, data: { role: body.role }, select: { id: true, email: true, role: true } });
  }
}

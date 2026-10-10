import { config } from 'dotenv';
import { resolve, join } from 'path';
import { promises as fs } from 'fs';
import { PrismaClient } from '@prisma/client';
import * as bcrypt from 'bcryptjs';

const root = resolve(__dirname, '../..');
config({ path: join(root, '.env') });
const db = new PrismaClient();
const examples: Array<[string, string]> = [
  ['6109', 'Áo phông, áo ba lỗ (singlet) và các loại áo lót khác, dệt kim hoặc móc'],
  ['610910', 'Áo phông dệt kim từ bông'],
  ['61091010', 'Áo phông dệt kim từ bông dùng cho nam giới hoặc trẻ em trai'],
  ['6404', 'Giày, dép có đế ngoài bằng cao su, plastic, da thuộc hoặc da tổng hợp và mũ giày bằng vật liệu dệt'],
  ['640411', 'Giày, dép thể thao có mũ bằng vật liệu dệt'],
  ['64041190', 'Giày, dép thể thao có mũ bằng vật liệu dệt, loại khác'],
  ['8421', 'Máy và thiết bị lọc hoặc tinh chế chất lỏng hoặc chất khí'],
  ['842121', 'Máy và thiết bị để lọc hoặc tinh chế nước'],
  ['84212111', 'Máy và thiết bị lọc nước sử dụng trong gia đình'],
  ['8517', 'Bộ điện thoại, kể cả điện thoại thông minh'],
  ['85171300', 'Điện thoại thông minh'],
  ['9403', 'Đồ nội thất khác và các bộ phận của chúng'],
  ['94033000', 'Đồ nội thất bằng gỗ loại sử dụng trong văn phòng'],
  ['4202', 'Hòm, vali, túi xách và các vật chứa tương tự'],
  ['0901', 'Cà phê, rang hoặc chưa rang, đã hoặc chưa khử caffeine'],
  ['8542', 'Mạch điện tử tích hợp'],
  ['8413', 'Bơm chất lỏng, có hoặc không lắp thiết bị đo'],
  ['9405', 'Đèn và bộ đèn, kể cả đèn LED'],
];

async function main() {
  const email = process.env.ADMIN_EMAIL?.trim().toLowerCase();
  const password = process.env.ADMIN_PASSWORD;
  if (email && password) {
    if (password.length < 12) throw new Error('ADMIN_PASSWORD must have at least 12 characters');
    await db.user.upsert({ where: { email }, update: { passwordHash: await bcrypt.hash(password, 12), role: 'ADMIN' }, create: { email, passwordHash: await bcrypt.hash(password, 12), role: 'ADMIN' } });
    process.stdout.write(`Admin created: ${email}\n`);
  }
  for (const [code, description] of examples) {
    await db.hsCode.upsert({ where: { code }, update: {}, create: { code, description, level: code.length, parentCode: code.length > 4 ? code.slice(0, code.length - 2) : null, provenance: 'DEMO DATA — illustrative seed; verify against official source' } });
  }
  const storage = resolve(root, process.env.DOCUMENT_STORAGE_PATH || './storage');
  await fs.mkdir(storage, { recursive: true });
  const path = join(storage, 'demo-knowledge.txt');
  await fs.copyFile(join(root, 'docs/demo-knowledge.txt'), path);
  let doc = await db.document.findFirst({ where: { title: 'DEMO DATA — Ví dụ mã HS' } });
  if (!doc) doc = await db.document.create({ data: { title: 'DEMO DATA — Ví dụ mã HS', documentType: 'TXT', source: 'Dữ liệu minh họa của dự án, không phải nguồn pháp lý', fileUrl: path, status: 'PROCESSING' } });
  try {
    const response = await fetch(`${process.env.AI_SERVICE_URL || 'http://127.0.0.1:8000'}/index-document`, { method: 'POST', headers: { 'content-type': 'application/json', 'x-service-token': process.env.AI_SERVICE_TOKEN || '' }, body: JSON.stringify({ document_id: doc.id, path }), signal: AbortSignal.timeout(120000) });
    if (!response.ok) throw new Error(`AI service HTTP ${response.status}`);
    await db.document.update({ where: { id: doc.id }, data: { status: 'READY', error: null } });
    process.stdout.write('Demo document indexed.\n');
  } catch {
    await db.document.update({ where: { id: doc.id }, data: { status: 'FAILED', error: 'Start AI service, configure AI API, then reindex from admin.' } });
    process.stdout.write('Demo document saved but not indexed. Reindex after AI service is ready.\n');
  }
}
main().finally(() => db.$disconnect());

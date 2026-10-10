import { Injectable } from '@nestjs/common';
import { randomUUID } from 'crypto';
import { promises as fs } from 'fs';
import { isAbsolute, join, resolve, sep } from 'path';

export interface DocumentStorage {
  save(data: Buffer, extension: string): Promise<string>;
  remove(path: string): Promise<void>;
}

@Injectable()
export class LocalDocumentStorage implements DocumentStorage {
  private root() {
    const configured = process.env.DOCUMENT_STORAGE_PATH || './storage';
    return isAbsolute(configured) ? resolve(configured) : resolve(__dirname, '../../../', configured);
  }
  async save(data: Buffer, extension: string): Promise<string> {
    const root = this.root();
    await fs.mkdir(root, { recursive: true });
    const path = join(root, `${randomUUID()}${extension}`);
    await fs.writeFile(path, data, { flag: 'wx' });
    return path;
  }
  async remove(path: string) {
    const absolute = resolve(path);
    if (!absolute.startsWith(this.root() + sep)) throw new Error('Unsafe storage path');
    await fs.unlink(absolute).catch((error: NodeJS.ErrnoException) => { if (error.code !== 'ENOENT') throw error; });
  }
}

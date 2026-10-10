import { config } from 'dotenv';
import { resolve } from 'path';
import { PrismaClient } from '@prisma/client';
import * as bcrypt from 'bcryptjs';

config({ path: resolve(__dirname, '../../.env') });

async function main() {
  const email = process.env.ADMIN_EMAIL?.trim().toLowerCase();
  const password = process.env.ADMIN_PASSWORD;
  if (!email || !password || password.length < 12) {
    throw new Error('Set ADMIN_EMAIL and ADMIN_PASSWORD (at least 12 characters).');
  }
  const db = new PrismaClient();
  try {
    const passwordHash = await bcrypt.hash(password, 12);
    await db.user.upsert({
      where: { email },
      create: { email, passwordHash, role: 'ADMIN' },
      update: { passwordHash, role: 'ADMIN' },
    });
    process.stdout.write(`Admin ready: ${email}\n`);
  } finally {
    await db.$disconnect();
  }
}

main().catch((error) => {
  process.stderr.write(`${error instanceof Error ? error.message : 'Admin creation failed'}\n`);
  process.exitCode = 1;
});

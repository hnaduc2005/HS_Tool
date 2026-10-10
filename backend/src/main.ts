import 'reflect-metadata';
import { config } from 'dotenv';
import { resolve } from 'path';
import { NestFactory } from '@nestjs/core';
import { Logger, ValidationPipe } from '@nestjs/common';
import helmet from 'helmet';
import { AppModule } from './module';

async function bootstrap() {
  config({ path: resolve(__dirname, '../../.env') });
  const app = await NestFactory.create(AppModule);
  app.setGlobalPrefix('api');
  app.use(helmet());
  app.enableCors({ origin: process.env.FRONTEND_ORIGIN || 'http://localhost:3000' });
  app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
  const port = Number(process.env.PORT || 3001);
  await app.listen(port, '0.0.0.0');
  new Logger('Bootstrap').log(`API listening on 0.0.0.0:${port}; health check: /api/health`);
}
bootstrap();

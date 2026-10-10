import { Module } from '@nestjs/common';
import { Database } from './database';
import { AuthController, AuthService, UserGuard, AdminGuard } from './auth/auth';
import { HsCodesController, HsCodesService } from './hs-codes/hs-codes';
import { ClassificationController, ClassificationService } from './classification/classification';
import { AdminController, AdminService } from './admin/admin';
import { LocalDocumentStorage } from './documents/storage';

@Module({
  controllers: [AuthController, HsCodesController, ClassificationController, AdminController],
  providers: [Database, LocalDocumentStorage, AuthService, UserGuard, AdminGuard, HsCodesService, ClassificationService, AdminService],
})
export class AppModule {}

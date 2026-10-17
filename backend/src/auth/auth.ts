import { Body, Controller, Get, Injectable, Post, Req, UnauthorizedException, ForbiddenException, ConflictException, CanActivate, ExecutionContext } from '@nestjs/common';
import { Transform } from 'class-transformer';
import { IsEmail, IsString, MinLength } from 'class-validator';
import { Request } from 'express';
import * as bcrypt from 'bcryptjs';
import * as jwt from 'jsonwebtoken';
import { Database } from '../database';
import { COMPANY_EMAIL_MESSAGE, isCompanyEmail } from './email-policy';

export class RegisterDto {
  @Transform(({ value }) => typeof value === 'string' ? value.trim().toLowerCase() : value)
  @IsEmail() email!: string;
  @IsString() @MinLength(10) password!: string;
}
export class LoginDto {
  @Transform(({ value }) => typeof value === 'string' ? value.trim().toLowerCase() : value)
  @IsEmail() email!: string;
  @IsString() password!: string;
}
export type Session = { sub: string; email: string; role: 'USER' | 'ADMIN' };
export type AuthRequest = Request & { session?: Session };

function secret() {
  const value = process.env.JWT_SECRET;
  if (!value || value.length < 32) throw new Error('JWT_SECRET must have at least 32 characters');
  return value;
}

@Injectable()
export class AuthService {
  constructor(private readonly db: Database) {}
  private companyEmail(value: string) {
    const email = value.trim().toLowerCase();
    if (!isCompanyEmail(email)) throw new ForbiddenException({ message: COMPANY_EMAIL_MESSAGE, code: 'EMAIL_DOMAIN_NOT_ALLOWED' });
    return email;
  }
  async register(input: RegisterDto) {
    const email = this.companyEmail(input.email);
    if (await this.db.user.findUnique({ where: { email } })) throw new ConflictException('Email đã tồn tại');
    const user = await this.db.user.create({ data: { email, passwordHash: await bcrypt.hash(input.password, 12) } });
    return this.token(user.id, email, user.role);
  }
  async login(input: LoginDto) {
    const email = this.companyEmail(input.email);
    const user = await this.db.user.findUnique({ where: { email } });
    if (!user || !(await bcrypt.compare(input.password, user.passwordHash))) throw new UnauthorizedException('Sai email hoặc mật khẩu');
    return this.token(user.id, email, user.role);
  }
  private token(id: string, email: string, role: 'USER' | 'ADMIN') {
    const user: Session = { sub: id, email, role };
    return { access_token: jwt.sign(user, secret(), { expiresIn: '12h', algorithm: 'HS256' }), role, user };
  }
  async verify(req: AuthRequest): Promise<Session> {
    const header = req.headers.authorization;
    if (!header?.startsWith('Bearer ')) throw new UnauthorizedException('Vui lòng đăng nhập để sử dụng hệ thống.');
    let id: string;
    try {
      const payload = jwt.verify(header.slice(7), secret(), { algorithms: ['HS256'] });
      if (typeof payload === 'string' || typeof payload.sub !== 'string' || !payload.sub) throw new Error('invalid token');
      id = payload.sub;
    } catch { throw new UnauthorizedException('Phiên đăng nhập không hợp lệ hoặc đã hết hạn.'); }
    // Read current account data so old tokens cannot bypass domain or role changes.
    const user = await this.db.user.findUnique({ where: { id }, select: { id: true, email: true, role: true } });
    if (!user) throw new UnauthorizedException('Tài khoản không còn tồn tại.');
    const email = this.companyEmail(user.email);
    return { sub: user.id, email, role: user.role };
  }
}

@Injectable()
export class UserGuard implements CanActivate {
  constructor(private readonly auth: AuthService) {}
  async canActivate(context: ExecutionContext) {
    const req = context.switchToHttp().getRequest<AuthRequest>();
    req.session = await this.auth.verify(req);
    return true;
  }
}
@Injectable()
export class AdminGuard implements CanActivate {
  constructor(private readonly auth: AuthService) {}
  async canActivate(context: ExecutionContext) {
    const req = context.switchToHttp().getRequest<AuthRequest>();
    req.session = await this.auth.verify(req);
    if (req.session?.role !== 'ADMIN') throw new ForbiddenException();
    return true;
  }
}

@Controller('auth')
export class AuthController {
  constructor(private readonly auth: AuthService) {}
  @Post('register') register(@Body() body: RegisterDto) { return this.auth.register(body); }
  @Post('login') login(@Body() body: LoginDto) { return this.auth.login(body); }
  @Get('me') me(@Req() req: AuthRequest) { return this.auth.verify(req); }
}

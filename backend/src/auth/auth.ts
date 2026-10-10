import { Body, Controller, Get, Injectable, Post, Req, UnauthorizedException, ForbiddenException, ConflictException, UseGuards, CanActivate, ExecutionContext } from '@nestjs/common';
import { IsEmail, IsString, MinLength } from 'class-validator';
import { Request } from 'express';
import * as bcrypt from 'bcryptjs';
import * as jwt from 'jsonwebtoken';
import { Database } from '../database';

export class RegisterDto {
  @IsEmail() email!: string;
  @IsString() @MinLength(10) password!: string;
}
export class LoginDto {
  @IsEmail() email!: string;
  @IsString() password!: string;
}
export type Session = { sub: string; role: 'USER' | 'ADMIN' };
export type AuthRequest = Request & { session?: Session };

function secret() {
  const value = process.env.JWT_SECRET;
  if (!value || value.length < 32) throw new Error('JWT_SECRET must have at least 32 characters');
  return value;
}

@Injectable()
export class AuthService {
  constructor(private readonly db: Database) {}
  async register(input: RegisterDto) {
    const email = input.email.trim().toLowerCase();
    if (await this.db.user.findUnique({ where: { email } })) throw new ConflictException('Email đã tồn tại');
    const user = await this.db.user.create({ data: { email, passwordHash: await bcrypt.hash(input.password, 12) } });
    return this.token(user.id, user.role);
  }
  async login(input: LoginDto) {
    const user = await this.db.user.findUnique({ where: { email: input.email.trim().toLowerCase() } });
    if (!user || !(await bcrypt.compare(input.password, user.passwordHash))) throw new UnauthorizedException('Sai email hoặc mật khẩu');
    return this.token(user.id, user.role);
  }
  private token(id: string, role: 'USER' | 'ADMIN') {
    return { access_token: jwt.sign({ sub: id, role }, secret(), { expiresIn: '12h' }), role };
  }
  verify(req: AuthRequest, required = false): Session | undefined {
    const header = req.headers.authorization;
    if (!header) {
      if (required) throw new UnauthorizedException();
      return undefined;
    }
    if (!header.startsWith('Bearer ')) throw new UnauthorizedException();
    try {
      const session = jwt.verify(header.slice(7), secret()) as Session;
      if (!session.sub || !['USER', 'ADMIN'].includes(session.role)) throw new Error('invalid token');
      return session;
    } catch { throw new UnauthorizedException(); }
  }
}

@Injectable()
export class UserGuard implements CanActivate {
  constructor(private readonly auth: AuthService) {}
  canActivate(context: ExecutionContext) {
    const req = context.switchToHttp().getRequest<AuthRequest>();
    req.session = this.auth.verify(req, true);
    return true;
  }
}
@Injectable()
export class AdminGuard implements CanActivate {
  constructor(private readonly auth: AuthService) {}
  canActivate(context: ExecutionContext) {
    const req = context.switchToHttp().getRequest<AuthRequest>();
    req.session = this.auth.verify(req, true);
    if (req.session?.role !== 'ADMIN') throw new ForbiddenException();
    return true;
  }
}

@Controller('auth')
export class AuthController {
  constructor(private readonly auth: AuthService) {}
  @Post('register') register(@Body() body: RegisterDto) { return this.auth.register(body); }
  @Post('login') login(@Body() body: LoginDto) { return this.auth.login(body); }
  @Get('me') me(@Req() req: AuthRequest) { return this.auth.verify(req, true); }
}

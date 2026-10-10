import * as React from 'react';
import { cn } from '@/lib/utils';
export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => <input ref={ref} className={cn('h-11 w-full rounded-xl border border-line bg-white px-4 text-sm text-ink outline-none placeholder:text-slate-400 focus:border-forest focus:ring-2 focus:ring-forest/10', className)} {...props} />);
Input.displayName = 'Input';

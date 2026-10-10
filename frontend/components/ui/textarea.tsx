import * as React from 'react';
import { cn } from '@/lib/utils';
export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(({ className, ...props }, ref) => <textarea ref={ref} className={cn('w-full rounded-xl border border-line bg-white px-4 py-3 text-sm text-ink outline-none placeholder:text-slate-400 focus:border-forest focus:ring-2 focus:ring-forest/10', className)} {...props} />);
Textarea.displayName = 'Textarea';

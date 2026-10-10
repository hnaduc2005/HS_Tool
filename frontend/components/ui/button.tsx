import * as React from 'react';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '@/lib/utils';
const styles = cva('inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-forest/40', { variants: { variant: { default: 'bg-forest text-white hover:bg-[#10523e]', outline: 'border border-line bg-white text-ink hover:bg-mint', ghost: 'text-ink hover:bg-mint', danger: 'bg-red-50 text-red-700 hover:bg-red-100' }, size: { default: 'h-11 px-5 text-sm', sm: 'h-9 px-3 text-sm', lg: 'h-12 px-6 text-base' } }, defaultVariants: { variant: 'default', size: 'default' } });
type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof styles> & { asChild?: boolean };
export const Button = React.forwardRef<HTMLButtonElement, Props>(({ className, variant, size, asChild, ...props }, ref) => { const Component = asChild ? Slot : 'button'; return <Component className={cn(styles({ variant, size }), className)} ref={ref} {...props} />; });
Button.displayName = 'Button';

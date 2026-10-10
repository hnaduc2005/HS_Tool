import type { Config } from 'tailwindcss';
const config: Config = { content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'], theme: { extend: { colors: { ink: '#162a24', paper: '#f7f8f4', forest: '#176951', mint: '#e0f3e9', line: '#dce4dd' }, boxShadow: { panel: '0 18px 50px rgba(24, 56, 42, .08)' } } }, plugins: [] };
export default config;

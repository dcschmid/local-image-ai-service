import { defineConfig } from 'astro/config';
export default defineConfig({ output: 'static', base: '/studio', build: { assets: 'assets' } });

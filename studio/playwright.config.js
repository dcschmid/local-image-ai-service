import { defineConfig } from '@playwright/test';
export default defineConfig({ testDir: './tests', use: { browserName: 'firefox', baseURL: 'http://127.0.0.1:7861', viewport: { width: 1440, height: 1080 } }, workers: 1 });

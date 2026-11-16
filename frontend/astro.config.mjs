import { defineConfig } from 'astro/config';
import tailwindcss from '@tailwindcss/vite';
import { loadEnv } from 'vite';

const mode = process.env.NODE_ENV === 'development' ? 'development' : 'production';
const fileEnv = loadEnv(mode, process.cwd(), 'PUBLIC_');
const env = (name) => (process.env[name] ?? fileEnv[name] ?? '').trim();

const base = env('PUBLIC_BASE_PATH');
const apiUrl = env('PUBLIC_API_URL');
const missing = [];
if (!base) missing.push('PUBLIC_BASE_PATH');
if (!apiUrl) missing.push('PUBLIC_API_URL');
if (missing.length > 0) {
  throw new Error(`Missing required build variable(s): ${missing.join(', ')}. See frontend/.env.example.`);
}

export default defineConfig({
  output: 'static',
  base,
  trailingSlash: 'always',
  build: { format: 'directory' },
  vite: {
    plugins: [tailwindcss()],
    define: {
      'import.meta.env.PUBLIC_API_URL': JSON.stringify(apiUrl),
      'import.meta.env.PUBLIC_RESURRECT_TIMEOUT_MS': JSON.stringify(
        env('PUBLIC_RESURRECT_TIMEOUT_MS') || '120000',
      ),
    },
  },
});

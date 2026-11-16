/// <reference types="astro/client" />

interface ImportMetaEnv {
  readonly PUBLIC_BASE_PATH: string;
  readonly PUBLIC_API_URL: string;
  readonly PUBLIC_RESURRECT_TIMEOUT_MS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

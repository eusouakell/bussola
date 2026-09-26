/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_BUSSOLA_MODO?: string;
  readonly VITE_ADK_APP?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

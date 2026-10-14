/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The Django back end's address when the app is hosted separately; empty when Django serves the app. */
  readonly VITE_API_ORIGIN?: string;
}

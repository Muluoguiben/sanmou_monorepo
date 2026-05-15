import type { RuntimeConfig } from "./types";

declare global {
  interface Window {
    sanmou?: {
      getRuntimeConfig: () => Promise<RuntimeConfig>;
    };
  }
}

export {};

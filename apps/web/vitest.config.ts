import { defineConfig } from "vitest/config";

// tsconfig says jsx "preserve" for Next; vitest has no Next compiler, so the view tests compile JSX here.
export default defineConfig({ esbuild: { jsx: "automatic" } });

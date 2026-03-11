/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    testTimeout: 20000,
    setupFiles: './src/test-setup.ts',
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'lcov'],
      reportsDirectory: './coverage',
      reportOnFailure: true,
      include: ['src/hooks/**/*.{ts,tsx}', 'src/components/**/*.tsx', 'src/services/**/*.ts'],
      exclude: ['**/*.test.ts', '**/*.test.tsx', '**/node_modules/**', 'src/test-setup.ts'],
      thresholds: {
        statements: 90,
        // branches à 80% (non 90%) : v8 instrumente les branches TypeScript compilées
        // (optional chaining ?., nullish coalescing ??, etc.) qui gonflent le total.
        // Couverture mesurée : 84.79% — décision acceptée en story 55-8 (code review 2026-03-02).
        branches: 80,
        functions: 90,
        lines: 90,
      },
    },
  },
});

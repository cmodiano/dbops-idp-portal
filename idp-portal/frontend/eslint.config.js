import js from '@eslint/js'
import globals from 'globals'
import react from 'eslint-plugin-react'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import security from 'eslint-plugin-security'
import standards from './eslint-plugin-standards/index.js'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    plugins: {
      react,
      security,
      standards,
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      // Security plugin rules (Story 15.1)
      'security/detect-buffer-noassert': 'warn',
      'security/detect-child-process': 'warn',
      'security/detect-disable-mustache-escape': 'warn',
      'security/detect-eval-with-expression': 'error',
      'security/detect-new-buffer': 'warn',
      'security/detect-no-csrf-before-method-override': 'warn',
      'security/detect-non-literal-fs-filename': 'warn',
      // detect-non-literal-regexp disabled: dynamic RegExp from user-defined patterns
      // (glob matching, parameter validation) is a core feature, not a vulnerability (Story 26.15)
      'security/detect-non-literal-regexp': 'off',
      'security/detect-non-literal-require': 'warn',
      // detect-object-injection disabled: generates false positives on all dynamic
      // property access (e.g. obj[key]) which is standard JS/TS pattern (Story 26.15)
      'security/detect-object-injection': 'off',
      'security/detect-possible-timing-attacks': 'warn',
      'security/detect-pseudoRandomBytes': 'warn',
      'security/detect-unsafe-regex': 'error',

      // React security rules (XSS prevention)
      'react/no-danger': 'error',
      'react/no-danger-with-children': 'error',

      // Additional security-focused rules
      'no-eval': 'error',
      'no-implied-eval': 'error',
      'no-new-func': 'error',
      'no-script-url': 'error',

      // React Compiler rules (react-hooks plugin v5+) — disabled for progressive adoption
      // These rules target React Compiler optimization hints, not correctness issues.
      // Enable progressively as codebase adopts React Compiler (Story 26.15)
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/preserve-manual-memoization': 'off',
      'react-hooks/purity': 'off',
      'react-hooks/immutability': 'off',
      'react-hooks/refs': 'off',
      'react-hooks/globals': 'off',

      // Structured logging enforcement (Story 17.7)
      'no-console': 'error',

      // Allow _ prefix for intentionally unused variables (e.g. destructuring to omit a prop)
      '@typescript-eslint/no-unused-vars': ['error', {
        vars: 'all',
        args: 'after-used',
        ignoreRestSiblings: true,
        varsIgnorePattern: '^_',
        argsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
      }],

      // Frontend standards enforcement (Story 17.16)
      'standards/no-antd-internal-imports': 'error',
      'standards/require-app-useapp': 'error',
      'standards/no-class-components': 'error',
    },
  },
  // Relaxed rules for test files
  // Justification: Tests need console spies, mock types (any), and setup variables
  {
    files: ['**/*.test.{ts,tsx}', '**/*.spec.{ts,tsx}'],
    rules: {
      'no-console': 'off',
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-unsafe-function-type': 'off',
    },
  },
])

# Configuration des linters — IDP Portal

> Story 26.15 — Dernière mise à jour : 2026-02-13

## Vue d'ensemble

| Linter | Cible | Config | Baseline Story 26.15 |
|--------|-------|--------|----------------------|
| **Ruff** | Backend Python | `django_backend/pyproject.toml` | 0 warning, 0 erreur |
| **ESLint** | Frontend TypeScript/React | `frontend/eslint.config.js` | 0 erreur, 0 warning |
| **mypy** | Backend Python (types) | `django_backend/pyproject.toml` | 80 erreurs (baseline stable, 0 nouvelle) |

## Backend — Ruff

**Exécution :** `cd idp-portal/django_backend && .venv/bin/python -m ruff check .`

**Auto-fix :** `ruff check --fix .` (corrige F401 unused imports, etc.)

### Règles actives

Configurées dans `pyproject.toml` section `[tool.ruff]`. Règles par défaut de Ruff incluant :

- **F401** — Imports inutilisés (auto-fixable)
- **F841** — Variables locales assignées mais non utilisées (unsafe-fix: préfixe `_`)
- **E402** — Import pas en haut de fichier
- **F541** — f-string sans placeholder
- **F811** — Redéfinition d'un nom non utilisé

### Exclusions documentées

| Fichier | Règle | Justification |
|---------|-------|---------------|
| `integrations/tests/test_validation.py` (3 occurrences) | F401 `# noqa: F401` | Import `jsonschema` utilisé pour vérifier la disponibilité (`try/except ImportError`) |

## Frontend — ESLint

**Exécution :** `cd idp-portal/frontend && npx eslint .`

### Configuration

Fichier : `frontend/eslint.config.js` (flat config ESLint 9+)

**Plugins actifs :**
- `@eslint/js` — Règles JavaScript core
- `typescript-eslint` — Règles TypeScript
- `eslint-plugin-react` — Règles React
- `eslint-plugin-react-hooks` — Règles hooks React
- `eslint-plugin-react-refresh` — Fast refresh Vite
- `eslint-plugin-security` — Détection vulnérabilités (Story 15.1)
- `eslint-plugin-standards` — Règles custom (Story 17.16)

### Règles désactivées avec justification

| Règle | Justification |
|-------|---------------|
| `security/detect-object-injection` | Faux positifs sur tout accès dynamique `obj[key]` — pattern JS/TS standard |
| `security/detect-non-literal-regexp` | RegExp dynamiques nécessaires pour glob matching, validation paramètres |
| `react-hooks/set-state-in-effect` | Règle React Compiler — adoption progressive |
| `react-hooks/preserve-manual-memoization` | Règle React Compiler — adoption progressive |
| `react-hooks/purity` | Règle React Compiler — adoption progressive |
| `react-hooks/immutability` | Règle React Compiler — adoption progressive |
| `react-hooks/refs` | Règle React Compiler — adoption progressive |
| `react-hooks/globals` | Règle React Compiler — adoption progressive |

### Règles relaxées pour fichiers de test

| Règle | Justification |
|-------|---------------|
| `no-console` → `off` | Tests utilisent `console.spy`, assertions sur console |
| `@typescript-eslint/no-explicit-any` → `off` | Mocks et types de test utilisent `any` fréquemment |
| `@typescript-eslint/no-unsafe-function-type` → `off` | Type `Function` utilisé dans mocks |

### Exclusions inline documentées

| Fichier | Règle(s) désactivée(s) | Justification |
|---------|------------------------|---------------|
| `ErrorBoundary.tsx` | `standards/no-class-components`, `react-refresh/only-export-components`, `react-hooks/error-boundaries` | React Error Boundaries **requièrent** une classe (`componentDidCatch`). Le try/catch JSX est le pattern fallback-of-fallback. Référence: [React docs](https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary) |
| `executionRenderers.tsx` | `react-refresh/only-export-components` | Fichier utilitaire exportant plusieurs composants de rendu |
| `iconHelpers.tsx` | `react-refresh/only-export-components` | Fichier utilitaire exportant composant + helpers |
| `ProfileForm.tsx` | `react-refresh/only-export-components` (inline) | Export d'une fonction utilitaire `detectTargetsMode` |
| `HorizontalFilters.tsx` | `react-refresh/only-export-components` (inline) | Export de constante `IMPACT_OPTIONS` |
| `workflowExport.test.ts` | `@typescript-eslint/no-require-imports` (inline) | `require()` nécessaire pour test de compatibilité CommonJS |

### Règles custom (Story 17.16)

| Règle | Description |
|-------|-------------|
| `standards/no-antd-internal-imports` | Interdit imports internes Ant Design (`antd/es/...`) |
| `standards/require-app-useapp` | Require `App.useApp()` pour modals/notifications |
| `standards/no-class-components` | Interdit class components (hors Error Boundaries) |

## Backend — mypy

**Exécution :** `cd idp-portal/django_backend && .venv/bin/python -m mypy .`

### Configuration

Fichier : `pyproject.toml` section `[tool.mypy]`

**Stratégie :** Mode permissif globalement, strict par module (Story 17-9)

### Baseline

| Date | Erreurs | Contexte |
|------|---------|----------|
| Story 17-9 | 89 | Introduction mypy |
| Story 22-19 | 29 | -67% réduction |
| Story 26-15 | 80 | Stable (0 nouvelle erreur — augmentation due aux refactorings Epic 26) |

**Objectif :** Ne pas introduire de nouvelles erreurs mypy. La réduction progressive est gérée par Story 26-16.

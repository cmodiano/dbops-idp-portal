# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

## API Types Structure

API types are organized by domain under `src/types/api/`:

```
src/types/
├── api.ts                  # Re-export for backward compatibility (deprecated)
└── api/
    ├── index.ts            # Barrel re-export of all domain types
    ├── common.ts           # ApiResponse, PaginatedResponse, ApiError, PaginationInfo
    ├── catalog.ts          # Actions, workflows, steps, parameters, impact rules
    ├── executions.ts       # Executions, steps, dashboard stats, filters
    ├── profiles.ts         # Profiles, RBAC permissions (actions & targets)
    ├── integrations.ts     # Integrations, auth flows
    ├── audit.ts            # Audit trail entries, filters
    ├── analytics.ts        # Analytics, reporting, comparisons, exports
    ├── scheduled.ts        # Scheduled executions, recurring patterns, cron
    ├── inventory.ts        # Inventory items
    └── remediation.ts      # Remediation rules, suggestions, actions
```

**Imports recommandes :**

```typescript
// Import direct par domaine (recommande pour le nouveau code)
import type { ActionResponse } from '../types/api/catalog';
import type { ExecutionResponse } from '../types/api/executions';

// Import barrel (toujours supporte)
import type { ActionResponse, ExecutionResponse } from '../types/api';
```

## Admin Page Structure

`AdminPage.tsx` is a lightweight orchestrator that delegates each tab to a dedicated panel component under `pages/admin/`:

```
src/pages/
├── AdminPage.tsx              # Orchestrator (~75 LOC) — Tabs container
└── admin/
    ├── index.ts               # Barrel export
    ├── ActionsAdminPanel.tsx   # Actions tab (CRUD, filters, cascade deactivation)
    ├── actionsColumns.tsx      # Table column definitions for Actions
    ├── ProfilesAdminPanel.tsx  # Profiles tab (CRUD, YAML import/export)
    ├── IntegrationsAdminPanel.tsx # Integrations tab (CRUD)
    ├── CategoriesAdminPanel.tsx   # Categories tab (wrapper)
    ├── MetricsAdminPanel.tsx      # Metrics tab (lazy-loaded dashboard)
    └── FeatureFlagsAdminPanel.tsx  # Feature Flags tab (lazy-loaded)
```

**Adding a new admin tab:**
1. Create `<Name>AdminPanel.tsx` in `pages/admin/`
2. Export it from `pages/admin/index.ts`
3. Add a new tab item in `AdminPage.tsx` Tabs items array
4. Pass `notification` (and `modal` if needed) from `App.useApp()` as props

## Error Boundary

`ErrorBoundary` captures unhandled React render errors and displays a user-friendly fallback UI (Ant Design `Result`). Integrated in `AppLayout` around `<Outlet />` so page-level errors are caught without crashing the entire application.

```tsx
// Default usage (already in AppLayout)
<ErrorBoundary>
  <Suspense fallback={<Spin />}>
    <Outlet />
  </Suspense>
</ErrorBoundary>

// Custom fallback
<ErrorBoundary fallback={(error, resetError) => <MyErrorUI error={error} onReset={resetError} />}>
  <MyComponent />
</ErrorBoundary>
```

**Behavior:** Errors are logged via `logger.error()` with stack trace and componentStack. Users see French-language error message with "Recharger la page" and "Retour à l'accueil" buttons.

**Note:** Error Boundaries only catch render errors. Event handler errors, async errors, and API errors are handled by try-catch and `api_client.ts`.

## Tests

**Baseline (2026-02-13):** 2018 tests / 147 fichiers — 100% pass, ~124s, 76.22% couverture lignes.

Voir [TESTING.md](TESTING.md) pour les details complets (stack, commandes, limitations connues).

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

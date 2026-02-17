# Guide de contribution Frontend

Ce document fournit les instructions pour contribuer au frontend IDP Portal.

## Setup environnement de développement

### Prérequis

- Node.js 20+ (LTS recommandé)
- npm 10+
- Git

### Installation

```bash
# Cloner le repository
git clone <repository-url>
cd idp-portal/frontend

# Installer les dépendances
npm install

# Copier le fichier d'environnement
cp .env.development .env.local
```

### Configuration .env.local

```env
# Backend API URL (via proxy Vite)
VITE_API_URL=/api/v1

# DEV: Bypass SAML authentication (utilise un user mock DBOPS)
VITE_DEV_AUTH=true
```

### Démarrer le serveur de développement

```bash
npm run dev
# → http://localhost:5173
```

Le proxy Vite redirige automatiquement `/api/*` vers `http://localhost:8000`.

---

## Scripts disponibles

| Commande | Description |
|----------|-------------|
| `npm run dev` | Serveur de développement avec HMR |
| `npm run build` | Build de production |
| `npm run preview` | Preview du build de production |
| `npm run test` | Exécuter tous les tests |
| `npm run test:watch` | Tests en mode watch |
| `npm run lint` | Vérification ESLint |

---

## Conventions de code

### Nommage

| Type | Convention | Exemple |
|------|------------|---------|
| Composants | PascalCase | `ActionCard.tsx` |
| Pages | PascalCase + Page | `CatalogPage.tsx` |
| Hooks | camelCase + use | `useDebounce.ts` |
| Services | snake_case + _service | `catalog_service.ts` |
| Types | PascalCase | `ExecutionResponse` |
| Utils | camelCase | `cronHelper.ts` |
| Tests | même nom + .test | `ActionCard.test.tsx` |
| Constantes | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |

### Structure de fichier composant

```typescript
// 1. Imports React et librairies
import { useState, useCallback } from 'react';
import { Button, Card } from 'antd';

// 2. Imports locaux (relatifs)
import { useAuth } from '../../contexts/AuthContext';
import { fetchCatalogActions } from '../../services/catalog_service';
import type { CatalogAction } from '../../types/api';

// 3. Types et interfaces
interface ActionCardProps {
  action: CatalogAction;
  onExecute: (id: number) => void;
}

// 4. Composant
export function ActionCard({ action, onExecute }: ActionCardProps) {
  const [loading, setLoading] = useState(false);

  const handleClick = useCallback(() => {
    onExecute(action.id);
  }, [action.id, onExecute]);

  return (
    <Card>
      <h3>{action.name}</h3>
      <Button onClick={handleClick} loading={loading}>
        Exécuter
      </Button>
    </Card>
  );
}
```

### Règles TypeScript

```typescript
// ✅ Typer explicitement les props
interface Props {
  name: string;
  optional?: boolean;
}

// ✅ Utiliser les types API existants
import type { ExecutionResponse } from '../types/api';

// ✅ Préférer interface pour les objets
interface User {
  id: number;
  name: string;
}

// ✅ Type pour les unions
type Status = 'pending' | 'running' | 'completed';

// ❌ Éviter any
const data: any = response;

// ✅ Utiliser unknown si type inconnu
const data: unknown = response;
if (typeof data === 'object' && data !== null) {
  // ...
}
```

### Règles Ant Design 6

> Ces règles sont appliquées automatiquement par ESLint (`eslint-plugin-standards/`).
> Voir [`FRONTEND-STANDARDS.md`](../../frontend/FRONTEND-STANDARDS.md) pour la référence complète.

```typescript
// ❌ INTERDIT - imports internes (standards/no-antd-internal-imports)
import { ColumnsType } from 'antd/es/table';

// ✅ CORRECT - exports publics
import type { TableProps } from 'antd';

// ❌ INTERDIT - message/notification direct (standards/require-app-useapp)
import { message } from 'antd';
message.error('Erreur');

// ✅ CORRECT - via App.useApp()
const { message } = App.useApp();
message.error('Erreur');

// ❌ INTERDIT - class components (standards/no-class-components)
class MyComponent extends React.Component { ... }

// ✅ CORRECT - function components
function MyComponent() { ... }
```

---

## Guides pas-à-pas

### Comment ajouter une nouvelle page

1. **Créer le fichier page**

```typescript
// src/pages/MyNewPage.tsx
import { Typography } from 'antd';

export default function MyNewPage() {
  return (
    <div style={{ padding: 24 }}>
      <Typography.Title level={2}>Ma nouvelle page</Typography.Title>
    </div>
  );
}
```

2. **Ajouter la route dans App.tsx**

```typescript
// src/App.tsx
const MyNewPage = lazy(() => import('./pages/MyNewPage'));

// Dans les Routes
<Route path="/my-new-page" element={<MyNewPage />} />
```

3. **Ajouter la navigation (optionnel)**

```typescript
// src/components/layout/TopNav.tsx
const NAV_ITEMS = [
  // ... existing items
  { key: 'my-new-page', path: '/my-new-page', label: 'Ma Page', icon: <StarOutlined /> },
];
```

4. **Créer le test**

```typescript
// src/pages/MyNewPage.test.tsx
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router';
import MyNewPage from './MyNewPage';

describe('MyNewPage', () => {
  it('should render page title', () => {
    render(
      <BrowserRouter>
        <MyNewPage />
      </BrowserRouter>
    );
    expect(screen.getByText('Ma nouvelle page')).toBeInTheDocument();
  });
});
```

---

### Comment ajouter un nouveau composant

1. **Créer le composant dans le bon dossier**

```typescript
// src/components/catalog/MyComponent.tsx
import { Card } from 'antd';

interface MyComponentProps {
  title: string;
  onAction: () => void;
}

export function MyComponent({ title, onAction }: MyComponentProps) {
  return (
    <Card title={title}>
      <button onClick={onAction}>Action</button>
    </Card>
  );
}
```

2. **Exporter dans index.ts**

```typescript
// src/components/catalog/index.ts
export { MyComponent } from './MyComponent';
```

3. **Créer le test**

```typescript
// src/components/catalog/MyComponent.test.tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MyComponent } from './MyComponent';

describe('MyComponent', () => {
  it('should render title', () => {
    render(<MyComponent title="Test" onAction={vi.fn()} />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });

  it('should call onAction when clicked', async () => {
    const onAction = vi.fn();
    render(<MyComponent title="Test" onAction={onAction} />);

    await userEvent.click(screen.getByRole('button'));

    expect(onAction).toHaveBeenCalled();
  });
});
```

---

### Comment ajouter un nouveau service API

1. **Créer le fichier service**

```typescript
// src/services/my_service.ts
import { apiFetch, apiFetchRaw } from './api_client';
import type { MyType } from '../types/api';

export async function fetchMyData(): Promise<MyType[]> {
  return apiFetch<MyType[]>('/my-endpoint');
}

export async function createMyData(data: MyTypeCreate): Promise<MyType> {
  return apiFetch<MyType>('/my-endpoint', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

2. **Ajouter les types dans api.ts**

```typescript
// src/types/api.ts

// Ajouter les interfaces
export interface MyType {
  id: number;
  name: string;
  created_at: string;
}

export interface MyTypeCreate {
  name: string;
}
```

3. **Créer le test**

```typescript
// src/services/my_service.test.ts
import { vi } from 'vitest';
import { fetchMyData, createMyData } from './my_service';
import * as apiClient from './api_client';

vi.mock('./api_client');

describe('my_service', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should fetch my data', async () => {
    vi.mocked(apiClient.apiFetch).mockResolvedValue([
      { id: 1, name: 'Test' },
    ]);

    const result = await fetchMyData();

    expect(apiClient.apiFetch).toHaveBeenCalledWith('/my-endpoint');
    expect(result).toHaveLength(1);
  });
});
```

---

### Comment ajouter un custom hook

1. **Créer le hook**

```typescript
// src/hooks/useMyHook.ts
import { useState, useEffect, useCallback } from 'react';

interface UseMyHookResult {
  data: string[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useMyHook(param: string): UseMyHookResult {
  const [data, setData] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Appel API
      const result = await fetchMyData(param);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Erreur');
    } finally {
      setLoading(false);
    }
  }, [param]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { data, loading, error, refetch: fetchData };
}
```

2. **Créer le test**

```typescript
// src/hooks/useMyHook.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { useMyHook } from './useMyHook';
import * as myService from '../services/my_service';

vi.mock('../services/my_service');

describe('useMyHook', () => {
  it('should fetch data on mount', async () => {
    vi.mocked(myService.fetchMyData).mockResolvedValue(['a', 'b']);

    const { result } = renderHook(() => useMyHook('test'));

    expect(result.current.loading).toBe(true);

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });

    expect(result.current.data).toEqual(['a', 'b']);
    expect(result.current.error).toBeNull();
  });
});
```

---

### Comment ajouter un test pour un composant existant

1. **Analyser le composant** pour identifier les comportements à tester :
   - Rendu initial
   - Interactions utilisateur
   - États de chargement/erreur
   - Props conditionnels

2. **Créer le fichier de test**

```typescript
// src/components/catalog/ExistingComponent.test.tsx
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { vi } from 'vitest';
import { ExistingComponent } from './ExistingComponent';

// Mock des dépendances si nécessaire
vi.mock('../../services/catalog_service');

// Helper pour wrapper avec App (si useApp() utilisé)
function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

describe('ExistingComponent', () => {
  const defaultProps = {
    id: 1,
    name: 'Test',
    onSubmit: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('should render with required props', () => {
      renderWithApp(<ExistingComponent {...defaultProps} />);
      expect(screen.getByText('Test')).toBeInTheDocument();
    });

    it('should show loading state', () => {
      renderWithApp(<ExistingComponent {...defaultProps} loading />);
      expect(screen.getByRole('progressbar')).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('should call onSubmit when form submitted', async () => {
      renderWithApp(<ExistingComponent {...defaultProps} />);

      await userEvent.click(screen.getByRole('button', { name: 'Submit' }));

      expect(defaultProps.onSubmit).toHaveBeenCalled();
    });
  });

  describe('error handling', () => {
    it('should display error message', () => {
      renderWithApp(<ExistingComponent {...defaultProps} error="Something went wrong" />);
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });
  });
});
```

---

## Processus de review

### Checklist PR Frontend

Avant de soumettre une PR, vérifier :

- [ ] Pas de `class Component`
- [ ] Pas d'import depuis `antd/es/*`
- [ ] `message` et `notification` via `App.useApp()`
- [ ] `modal.confirm` via `App.useApp().modal`
- [ ] Types Table extraits depuis `TableProps<T>`
- [ ] Tests passent (`npm run test`)
- [ ] ESLint clean (`npm run lint`)
- [ ] Pas de warning Ant Design dépréciation dans la console
- [ ] Tests ajoutés pour les nouveaux composants/hooks

### Process de review

1. **Créer une branche feature**
   ```bash
   git checkout -b feature/my-feature
   ```

2. **Développer avec tests**
   ```bash
   npm run test:watch
   ```

3. **Vérifier avant commit**
   ```bash
   npm run lint
   npm run test
   ```

4. **Créer la PR**
   - Description claire du changement
   - Screenshots si UI modifié
   - Référence à la story/issue

5. **Review**
   - Au moins 1 approbation requise
   - Tous les tests doivent passer
   - ESLint doit passer

---

## Maintenir la documentation

### Quand mettre à jour la documentation

- Ajout d'un nouveau pattern ou convention
- Modification de la structure des dossiers
- Ajout de nouvelles dépendances majeures
- Changement d'API ou de comportement

### Comment mettre à jour

1. Modifier le fichier approprié dans `docs/frontend/`
2. Inclure des exemples de code à jour
3. Mentionner la mise à jour dans la PR

### Fichiers de documentation

| Fichier | Contenu |
|---------|---------|
| `folder-structure.md` | Structure des dossiers |
| `components.md` | Composants principaux |
| `state-management.md` | Contexts et hooks |
| `routing.md` | Routes et navigation |
| `api-integration.md` | Services et types API |
| `design-system.md` | Theming et Ant Design |
| `testing.md` | Stratégie de test |
| `contributing.md` | Guide de contribution |
| `README.md` | Vue d'ensemble |

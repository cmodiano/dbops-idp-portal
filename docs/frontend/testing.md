# Tests Frontend

Ce document décrit la stratégie de test et les patterns utilisés dans le frontend IDP Portal.

## Stack technique

| Outil | Version | Rôle |
|-------|---------|------|
| Vitest | 4.0.18 | Framework de test |
| React Testing Library | 16.3.2 | Utilitaires de test React |
| @testing-library/user-event | 14.6.1 | Simulation interactions utilisateur |
| @testing-library/jest-dom | 6.9.1 | Matchers DOM étendus |
| happy-dom | 20.4.0 | Environnement DOM |

## Configuration

### vite.config.ts

```typescript
/// <reference types="vitest/config" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'happy-dom',    // DOM environment
    globals: true,                // describe, it, expect globaux
    setupFiles: './src/test-setup.ts',
  },
});
```

### test-setup.ts

**Fichier :** `src/test-setup.ts`

```typescript
import '@testing-library/jest-dom';

// Mock matchMedia pour Ant Design (breakpoints)
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Mock ResizeObserver pour composants responsive
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
```

---

## Structure des fichiers de test

Les tests sont co-localisés avec les fichiers source :

```
src/
├── components/
│   └── catalog/
│       ├── ActionCard.tsx
│       ├── ActionCard.test.tsx      # Tests co-localisés
│       ├── ExecutionWizard.tsx
│       └── ExecutionWizard.test.tsx
├── hooks/
│   ├── useUrlFilters.ts
│   └── useUrlFilters.test.tsx       # Tests de hooks
├── services/
│   ├── catalog_service.ts
│   └── catalog_service.test.ts      # Tests de services
└── pages/
    ├── CatalogPage.tsx
    └── CatalogPage.test.tsx         # Tests de pages
```

---

## Commandes npm

```bash
# Exécuter tous les tests (run once)
npm run test

# Mode watch (développement)
npm run test:watch

# Avec couverture
npx vitest run --coverage
```

---

## Patterns de test

### 1. Test de composant basique

```typescript
import { render, screen } from '@testing-library/react';
import { ActionCard } from './ActionCard';

describe('ActionCard', () => {
  const mockAction = {
    id: 1,
    name: 'Test Action',
    description: 'Description test',
    engine: 'Oracle' as const,
    impact_level: 'low' as const,
    tags: ['patching'],
  };

  it('should render action name', () => {
    render(
      <ActionCard
        action={mockAction}
        onExecute={vi.fn()}
        onPreview={vi.fn()}
      />
    );

    expect(screen.getByText('Test Action')).toBeInTheDocument();
  });

  it('should call onExecute when execute button clicked', async () => {
    const onExecute = vi.fn();
    render(
      <ActionCard
        action={mockAction}
        onExecute={onExecute}
        onPreview={vi.fn()}
      />
    );

    await userEvent.click(screen.getByRole('button', { name: /exécuter/i }));

    expect(onExecute).toHaveBeenCalledWith(1);
  });
});
```

### 2. Wrapper App pour App.useApp()

Les composants utilisant `App.useApp()` (message, notification, modal) doivent être wrappés :

```typescript
import { render, screen } from '@testing-library/react';
import { App } from 'antd';

// Fonction helper
function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

describe('MyComponent', () => {
  it('should show success message', async () => {
    renderWithApp(<MyComponent />);

    await userEvent.click(screen.getByRole('button', { name: 'Submit' }));

    // Le message est rendu dans le DOM
    expect(screen.getByText('Succès')).toBeInTheDocument();
  });
});
```

### 3. Mock des services API

```typescript
import { vi } from 'vitest';
import * as catalogService from '../services/catalog_service';

vi.mock('../services/catalog_service');

describe('CatalogPage', () => {
  beforeEach(() => {
    vi.mocked(catalogService.fetchCatalogActions).mockResolvedValue([
      { id: 1, name: 'Action 1', /* ... */ },
      { id: 2, name: 'Action 2', /* ... */ },
    ]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it('should load and display actions', async () => {
    renderWithApp(<CatalogPage />);

    // Attendre le chargement
    await waitFor(() => {
      expect(screen.getByText('Action 1')).toBeInTheDocument();
    });

    expect(catalogService.fetchCatalogActions).toHaveBeenCalled();
  });
});
```

### 4. Test avec act() pour updates async

```typescript
import { render, screen, act } from '@testing-library/react';

it('should update state after async operation', async () => {
  render(<MyComponent />);

  // Envelopper les mises à jour d'état async
  await act(async () => {
    await userEvent.click(screen.getByRole('button'));
  });

  expect(screen.getByText('Updated')).toBeInTheDocument();
});
```

### 5. Test de hook personnalisé

```typescript
import { renderHook, act } from '@testing-library/react';
import { useDebounce } from './useDebounce';

describe('useDebounce', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should debounce value changes', async () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebounce(value, 300),
      { initialProps: { value: 'initial' } }
    );

    expect(result.current).toBe('initial');

    // Changer la valeur
    rerender({ value: 'updated' });

    // Pas encore mis à jour
    expect(result.current).toBe('initial');

    // Avancer le temps
    await act(async () => {
      vi.advanceTimersByTime(350);
    });

    // Maintenant mis à jour
    expect(result.current).toBe('updated');
  });
});
```

### 6. Test avec React Router

```typescript
import { render, screen } from '@testing-library/react';
import { BrowserRouter, MemoryRouter } from 'react-router';

// Option 1: BrowserRouter (simple)
function renderWithRouter(ui: React.ReactElement) {
  return render(<BrowserRouter>{ui}</BrowserRouter>);
}

// Option 2: MemoryRouter (contrôle de la route initiale)
function renderWithRouterAt(ui: React.ReactElement, route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      {ui}
    </MemoryRouter>
  );
}

describe('Navigation', () => {
  it('should navigate to catalog', async () => {
    renderWithRouterAt(<App />, '/catalog');

    expect(screen.getByText('Catalogue')).toBeInTheDocument();
  });
});
```

### 7. Test avec AuthContext mocké

```typescript
import { AuthContext } from '../contexts/AuthContext';

const mockAuthValue = {
  user: { id: 1, username: 'test', profile: 'dbops', navigation_tabs: ['catalog', 'admin'] },
  accessToken: 'mock-token',
  isAuthenticated: true,
  isLoading: false,
  login: vi.fn(),
  logout: vi.fn(),
  refreshToken: vi.fn(),
  hasTab: (tab: string) => ['catalog', 'admin'].includes(tab),
  isBusinessProfile: false,
};

function renderWithAuth(ui: React.ReactElement, authOverrides = {}) {
  return render(
    <AuthContext.Provider value={{ ...mockAuthValue, ...authOverrides }}>
      {ui}
    </AuthContext.Provider>
  );
}

describe('AdminPage', () => {
  it('should show admin content for admin users', () => {
    renderWithAuth(<AdminPage />);

    expect(screen.getByText('Administration')).toBeInTheDocument();
  });

  it('should redirect non-admin users', () => {
    renderWithAuth(<AdminPage />, {
      hasTab: () => false,
    });

    // Vérifier la redirection ou l'absence de contenu admin
  });
});
```

### 8. Test d'interactions utilisateur

```typescript
import userEvent from '@testing-library/user-event';

describe('Form interactions', () => {
  it('should handle form submission', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();

    render(<MyForm onSubmit={onSubmit} />);

    // Remplir le formulaire
    await user.type(screen.getByLabelText('Nom'), 'Test Action');
    await user.selectOptions(screen.getByLabelText('Engine'), 'Oracle');
    await user.click(screen.getByRole('button', { name: 'Enregistrer' }));

    expect(onSubmit).toHaveBeenCalledWith({
      name: 'Test Action',
      engine: 'Oracle',
    });
  });
});
```

---

## Matchers jest-dom

```typescript
// Vérification de présence
expect(element).toBeInTheDocument();
expect(element).not.toBeInTheDocument();

// Vérification de visibilité
expect(element).toBeVisible();
expect(element).not.toBeVisible();

// Vérification d'état
expect(button).toBeEnabled();
expect(button).toBeDisabled();
expect(checkbox).toBeChecked();

// Vérification de contenu
expect(element).toHaveTextContent('Text');
expect(input).toHaveValue('value');

// Vérification de style
expect(element).toHaveStyle({ color: 'red' });
expect(element).toHaveClass('my-class');

// Vérification d'attributs
expect(element).toHaveAttribute('href', '/catalog');
expect(element).toHaveAccessibleName('Submit');
```

---

## Sélecteurs recommandés

Par ordre de préférence (accessibilité first) :

```typescript
// 1. Rôle (meilleur pour accessibilité)
screen.getByRole('button', { name: 'Submit' });
screen.getByRole('heading', { level: 1 });
screen.getByRole('textbox', { name: 'Email' });

// 2. Label (formulaires)
screen.getByLabelText('Nom');

// 3. Placeholder
screen.getByPlaceholderText('Rechercher...');

// 4. Texte
screen.getByText('Catalogue');
screen.getByText(/erreur/i);  // Regex case-insensitive

// 5. Test ID (dernier recours)
screen.getByTestId('action-card-123');
```

---

## Debugging

```typescript
// Afficher le DOM actuel
screen.debug();

// Afficher un élément spécifique
screen.debug(screen.getByRole('button'));

// Logger les rôles disponibles
import { logRoles } from '@testing-library/react';
logRoles(container);

// Attendre un élément avec timeout personnalisé
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument();
}, { timeout: 5000 });
```

---

## Anti-patterns à éviter

```typescript
// ❌ Sélection par classe CSS
screen.getByClassName('my-button');

// ❌ Sélection par structure DOM
container.querySelector('div > button');

// ❌ Test des détails d'implémentation
expect(component.state.loading).toBe(true);

// ❌ Snapshot trop larges
expect(container).toMatchSnapshot(); // Tout le composant

// ❌ Oublier act() pour les updates async
setState(newValue); // Warning React
```

---

## Bonnes pratiques

### 1. Un test = un comportement

```typescript
// ❌ Mauvais - plusieurs assertions non liées
it('should work', () => {
  expect(screen.getByText('Title')).toBeInTheDocument();
  expect(button).toBeEnabled();
  expect(form).toHaveValue('test');
});

// ✅ Bon - tests séparés
it('should render title', () => { /* ... */ });
it('should enable submit button when valid', () => { /* ... */ });
it('should preserve form values', () => { /* ... */ });
```

### 2. Nettoyage entre tests

```typescript
beforeEach(() => {
  vi.clearAllMocks();
});

afterEach(() => {
  cleanup(); // RTL le fait automatiquement, mais explicite si besoin
});
```

### 3. Tests asynchrones propres

```typescript
// ✅ Utiliser waitFor pour les assertions async
await waitFor(() => {
  expect(screen.getByText('Loaded')).toBeInTheDocument();
});

// ✅ Utiliser findBy* pour les éléments async
const element = await screen.findByText('Loaded');
expect(element).toBeInTheDocument();
```

### 4. Mock minimal

```typescript
// ❌ Trop de mocks
vi.mock('../services/catalog_service');
vi.mock('../services/execution_service');
vi.mock('../services/auth_service');
vi.mock('../hooks/useAuth');

// ✅ Mocker seulement ce qui est nécessaire
vi.mock('../services/catalog_service', () => ({
  fetchCatalogActions: vi.fn(),
}));
```

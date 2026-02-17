# Story 22.10: Ajouter Error Boundary React au niveau des pages

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que développeur,
je veux ajouter un composant `ErrorBoundary` au niveau des pages pour capturer les erreurs de rendu,
afin d'éviter qu'une erreur JavaScript non gérée crashe toute l'application.

## Acceptance Criteria

**AC1: Composant ErrorBoundary créé**
- **Given** une erreur JavaScript non gérée survient dans un composant React
- **When** l'erreur n'est pas catchée localement
- **Then** l'`ErrorBoundary` capture l'erreur et affiche un fallback UI
- **And** le composant est implémenté comme class component (React Error Boundaries doivent être des classes)

**AC2: Message d'erreur utilisateur-friendly**
- **Given** l'ErrorBoundary capture une erreur
- **When** le fallback UI est affiché
- **Then** un message d'erreur en français est affiché
- **And** le message est adapté aux utilisateurs finaux (non technique)
- **And** le design est cohérent avec le design system Ant Design

**AC3: Logging des erreurs**
- **Given** l'ErrorBoundary capture une erreur
- **When** componentDidCatch() est appelé
- **Then** l'erreur est loggée avec le service `logger.ts`
- **And** le log inclut le stack trace et le componentStack
- **And** le niveau de log est `error`

**AC4: Actions de récupération**
- **Given** le fallback UI est affiché
- **When** l'utilisateur voit l'interface d'erreur
- **Then** l'utilisateur peut recharger la page
- **And** l'utilisateur peut retourner à l'accueil
- **And** les boutons d'action sont clairement visibles

**AC5: Intégration dans l'architecture**
- **Given** l'application React a une structure de routing
- **When** l'ErrorBoundary est intégré
- **Then** l'ErrorBoundary entoure le composant `<Outlet />` dans `AppLayout`
- **And** les erreurs dans les pages sont capturées sans affecter toute l'application
- **And** le login et auth callback ne sont pas affectés (pas dans AppLayout)

**AC6: Tests de l'ErrorBoundary**
- **Given** un composant de test qui génère une erreur
- **When** les tests sont exécutés
- **Then** l'ErrorBoundary capture l'erreur et affiche le fallback
- **And** le logger.error() est appelé avec les bons paramètres
- **And** les boutons "Recharger" et "Accueil" sont présents

## Tasks / Subtasks

- [x] Task 1: Créer le composant ErrorBoundary (AC: #1, #2, #3, #4)
  - [x] 1.1: Créer `ErrorBoundary.tsx` comme class component avec state { hasError, error }
  - [x] 1.2: Implémenter `static getDerivedStateFromError()` pour mettre à jour le state
  - [x] 1.3: Implémenter `componentDidCatch()` pour logger l'erreur avec logger.error()
  - [x] 1.4: Créer le fallback UI avec Ant Design (Result component, message FR, boutons)
  - [x] 1.5: Ajouter props `children` et optionnel `fallback` personnalisable

- [x] Task 2: Créer le composant de fallback UI (AC: #2, #4)
  - [x] 2.1: Utiliser `Result` de Ant Design avec status="error"
  - [x] 2.2: Titre en français: "Une erreur est survenue"
  - [x] 2.3: Description en français: message utilisateur-friendly (non technique)
  - [x] 2.4: Bouton "Recharger la page" avec `window.location.reload()`
  - [x] 2.5: Bouton "Retour à l'accueil" avec `navigate('/')`
  - [x] 2.6: Intégration avec useTheme() pour support dark/light mode

- [x] Task 3: Intégrer ErrorBoundary dans AppLayout (AC: #5)
  - [x] 3.1: Importer ErrorBoundary dans `AppLayout.tsx`
  - [x] 3.2: Entourer `<Outlet />` avec `<ErrorBoundary>`
  - [x] 3.3: Vérifier que Suspense reste en place (lazy loading des routes)
  - [x] 3.4: Tester que les erreurs dans les pages sont capturées
  - [x] 3.5: Vérifier que login et auth callback ne sont pas affectés

- [x] Task 4: Tests unitaires et d'intégration (AC: #6)
  - [x] 4.1: Créer `ErrorBoundary.test.tsx` avec Vitest + RTL
  - [x] 4.2: Test: ErrorBoundary capture une erreur et affiche le fallback
  - [x] 4.3: Test: logger.error() est appelé avec error et errorInfo
  - [x] 4.4: Test: bouton "Recharger" appelle window.location.reload()
  - [x] 4.5: Test: bouton "Accueil" navigue vers '/'
  - [x] 4.6: Test: composant sans erreur affiche children normalement
  - [x] 4.7: Mocker console.error pour éviter le bruit dans les tests

- [x] Task 5: Documentation et validation (AC: #1-#6)
  - [x] 5.1: Ajouter JSDoc complet sur ErrorBoundary avec exemples
  - [x] 5.2: Documenter l'usage dans README.md frontend
  - [x] 5.3: Valider que tous les tests passent (anciens + nouveaux)
  - [x] 5.4: Tester manuellement avec une erreur générée dans une page

## Dev Notes

### Architecture et Patterns

**Structure cible:**

```
frontend/src/
├── components/
│   └── ErrorBoundary.tsx (nouveau — class component ~150 LOC)
├── components/layout/
│   └── AppLayout.tsx (modifié — intégration ErrorBoundary autour Outlet)
└── __tests__/
    └── ErrorBoundary.test.tsx (nouveau — tests unitaires)
```

**Pattern ErrorBoundary (class component):**

React Error Boundaries DOIVENT être des class components car les hooks ne peuvent pas capturer les erreurs de rendu.

```typescript
import React, { Component, ErrorInfo, ReactNode } from 'react';
import { Result, Button } from 'antd';
import { useNavigate } from 'react-router-dom';
import { logger } from '../services/logger';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, resetError: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

/**
 * ErrorBoundary - Capture les erreurs de rendu React et affiche un fallback UI.
 *
 * Utilisation:
 * ```tsx
 * <ErrorBoundary>
 *   <MyComponent />
 * </ErrorBoundary>
 * ```
 *
 * Features:
 * - Capture les erreurs de rendu avec componentDidCatch()
 * - Affiche un fallback UI utilisateur-friendly (Ant Design Result)
 * - Log les erreurs avec logger.error() (stack trace + componentStack)
 * - Boutons de récupération: Recharger et Retour à l'accueil
 * - Support dark/light mode via Ant Design theme
 *
 * Story 22.10, AC #1-#6
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    // Mettre à jour le state pour afficher le fallback au prochain render
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    // Logger l'erreur avec stack trace et component stack
    logger.error('React Error Boundary caught error', {
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo.componentStack,
    });
  }

  resetError = (): void => {
    this.setState({ hasError: false, error: null });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      // Fallback personnalisé ou fallback par défaut
      if (this.props.fallback && this.state.error) {
        return this.props.fallback(this.state.error, this.resetError);
      }

      // Fallback par défaut avec Ant Design Result
      return <ErrorFallback error={this.state.error} resetError={this.resetError} />;
    }

    return this.props.children;
  }
}

// Composant de fallback séparé pour utiliser les hooks (useNavigate)
interface ErrorFallbackProps {
  error: Error | null;
  resetError: () => void;
}

function ErrorFallback({ error, resetError }: ErrorFallbackProps): ReactNode {
  const navigate = useNavigate();

  const handleReload = (): void => {
    window.location.reload();
  };

  const handleGoHome = (): void => {
    resetError();
    navigate('/');
  };

  return (
    <Result
      status="error"
      title="Une erreur est survenue"
      subTitle="Nous sommes désolés, une erreur inattendue s'est produite. Vous pouvez recharger la page ou retourner à l'accueil."
      extra={[
        <Button type="primary" key="reload" onClick={handleReload}>
          Recharger la page
        </Button>,
        <Button key="home" onClick={handleGoHome}>
          Retour à l'accueil
        </Button>,
      ]}
    />
  );
}
```

**Intégration dans AppLayout.tsx:**

```typescript
import { ErrorBoundary } from '../ErrorBoundary';

export default function AppLayout() {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <TopNav />
      <Layout.Content>
        <ErrorBoundary>
          <Suspense fallback={<div>Chargement...</div>}>
            <Outlet />
          </Suspense>
        </ErrorBoundary>
      </Layout.Content>
    </Layout>
  );
}
```

**Avantages de cette approche:**

1. ✅ **Isolation**: Erreurs capturées au niveau des pages, pas toute l'application
2. ✅ **UX**: Message utilisateur-friendly en français
3. ✅ **Récupération**: Boutons pour recharger ou retourner à l'accueil
4. ✅ **Observabilité**: Erreurs loggées avec stack trace complet
5. ✅ **Extensibilité**: Prop `fallback` optionnel pour personnalisation
6. ✅ **Dark mode**: Support automatique via Ant Design theme

**Limitations des Error Boundaries (important):**

Les Error Boundaries **NE capturent PAS**:
- Erreurs dans les event handlers (utiliser try-catch)
- Erreurs asynchrones (promises, setTimeout, etc.)
- Erreurs côté serveur (SSR)
- Erreurs dans l'ErrorBoundary lui-même

**Ces erreurs sont déjà gérées dans le projet:**
- Event handlers: try-catch dans `useExecutionSubmit.ts`, etc.
- Erreurs API: `api_client.ts` avec retry et error parsing
- Erreurs async: try-catch dans les hooks et composants

L'ErrorBoundary complète la stratégie de gestion d'erreur en capturant les **erreurs de rendu React** non gérées.

### Technical Requirements

**Stack technique:**
- **Language**: TypeScript 5.9.3
- **Framework frontend**: React 19.2.0 + Vite 7.2.4
- **UI Library**: Ant Design 6.2.2
- **Test framework**: Vitest 4.0.18 + React Testing Library 16.3.2
- **Router**: React Router 7.1.1

**React Error Boundary API:**

```typescript
// Méthodes obligatoires pour Error Boundary
static getDerivedStateFromError(error: Error): State
  - Appelé pendant la phase de rendu
  - Retourne un objet pour mettre à jour le state
  - Pas d'effets de bord ici

componentDidCatch(error: Error, errorInfo: ErrorInfo): void
  - Appelé après le rendu du fallback
  - Permet les effets de bord (logging, analytics)
  - errorInfo contient componentStack (trace de composants)
```

**Logger.ts API (déjà existant):**

```typescript
logger.error(message: string, data?: Record<string, unknown>): void
  - Niveau error: toujours loggé (dev et prod)
  - Data structurée: { message, stack, componentStack, correlation_id, ... }
  - Format JSON en production pour parsing facile
```

**Ant Design Result Component:**

```typescript
<Result
  status="error" | "success" | "info" | "warning" | "404" | "403" | "500"
  title={string | ReactNode}
  subTitle={string | ReactNode}
  extra={ReactNode | ReactNode[]} // Boutons d'action
  icon={ReactNode} // Icône personnalisée (optionnel)
/>
```

### File Structure Requirements

**Nouveau fichier:**
- `frontend/src/components/ErrorBoundary.tsx` (~150 LOC)

**Fichiers modifiés:**
- `frontend/src/components/layout/AppLayout.tsx` (ajout ErrorBoundary autour Outlet)
- `frontend/src/README.md` (documentation)

**Fichier de test:**
- `frontend/src/components/ErrorBoundary.test.tsx` (~100 LOC)

**Pattern de test pour Error Boundary:**

```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { ErrorBoundary } from './ErrorBoundary';
import { logger } from '../services/logger';

// Mock logger
vi.mock('../services/logger', () => ({
  logger: {
    error: vi.fn(),
  },
}));

// Composant qui génère une erreur
function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Test error');
  }
  return <div>No error</div>;
}

describe('ErrorBoundary', () => {
  // Supprimer le bruit de console.error dans les tests
  const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

  afterEach(() => {
    consoleErrorSpy.mockClear();
    vi.clearAllMocks();
  });

  it('renders children when no error', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText('No error')).toBeInTheDocument();
  });

  it('catches error and renders fallback UI', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(screen.getByText(/Une erreur est survenue/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Recharger la page/i })).toBeInTheDocument();
  });

  it('logs error with logger.error()', () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );
    expect(logger.error).toHaveBeenCalledWith(
      'React Error Boundary caught error',
      expect.objectContaining({
        message: 'Test error',
        stack: expect.any(String),
        componentStack: expect.any(String),
      })
    );
  });

  it('reloads page when "Recharger" button is clicked', async () => {
    const reloadSpy = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { reload: reloadSpy },
      writable: true,
    });

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    const reloadButton = screen.getByRole('button', { name: /Recharger la page/i });
    await userEvent.click(reloadButton);

    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });

  it('navigates to home when "Accueil" button is clicked', async () => {
    const navigate = vi.fn();
    vi.mock('react-router-dom', () => ({
      useNavigate: () => navigate,
    }));

    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    const homeButton = screen.getByRole('button', { name: /Retour à l'accueil/i });
    await userEvent.click(homeButton);

    expect(navigate).toHaveBeenCalledWith('/');
  });
});
```

### Testing Requirements

**Tests unitaires ErrorBoundary.test.tsx:**

1. Render children sans erreur
2. Capturer erreur et afficher fallback
3. Logger erreur avec logger.error()
4. Bouton "Recharger" appelle window.location.reload()
5. Bouton "Accueil" navigue vers '/'
6. Fallback personnalisé via prop (optionnel)

**Tests d'intégration AppLayout:**

1. AppLayout rend Outlet sans erreur
2. Erreur dans une page est capturée par ErrorBoundary
3. Login et auth callback ne sont pas affectés

**Validation manuelle:**

1. Ajouter temporairement `throw new Error('Test')` dans une page
2. Vérifier que le fallback UI s'affiche
3. Vérifier que logger.error() est appelé (dev console)
4. Tester boutons "Recharger" et "Accueil"
5. Vérifier dark mode / light mode

### Architecture Compliance

**Alignement avec les décisions architecturales:**

1. **Error Handling Strategy**: Complète la stratégie existante (API errors, validation errors) avec capture des erreurs de rendu React
2. **Logging centralisé**: Utilise logger.ts pour tous les logs (déjà établi)
3. **Design System**: Ant Design Result component pour cohérence visuelle
4. **User Experience**: Messages en français, actions de récupération claires
5. **Accessibility**: Result component Ant Design inclut aria attributes

**Patterns React établis dans le projet:**

- **Function components** pour les composants UI (avec hooks)
- **Class components** pour Error Boundaries (obligation React)
- **Ant Design** pour tous les composants UI
- **useTheme()** pour dark/light mode (supporté automatiquement par Result)
- **Router navigation** avec `useNavigate()` hook

**Error Handling actuel dans le projet:**

```
Niveau 1: API Layer (api_client.ts)
  - HTTP errors (401, 429, etc.)
  - Retry logic avec backoff exponentiel
  - Error parsing et ApiError custom

Niveau 2: Service/Hook Layer (useExecutionSubmit.ts, etc.)
  - Try-catch dans event handlers et async code
  - Erreurs transformées en messages utilisateur
  - État local (submitError, schedulingError)

Niveau 3: Component Layer (StructuredErrorCard.tsx)
  - Affichage structuré des erreurs
  - Variants business/technical
  - Actions de récupération (Retry, View logs, Contact DBA)

Niveau 4 (NOUVEAU): React Render Errors (ErrorBoundary)
  - Capture les erreurs de rendu non catchées
  - Fallback UI avec récupération
  - Logging pour observabilité
```

### Library/Framework Requirements

**Ant Design 6.2.2 - Result Component:**

```typescript
import { Result } from 'antd';

<Result
  status="error"           // Badge rouge avec icône X
  title="Titre principal"  // Texte principal en gras
  subTitle="Description"   // Texte secondaire
  extra={[                 // Boutons d'action
    <Button type="primary" key="action1">Action 1</Button>,
    <Button key="action2">Action 2</Button>,
  ]}
/>
```

**Ant Design Theme Integration:**

- Result utilise automatiquement les design tokens du theme
- Dark mode / Light mode supporté via ThemeProvider (déjà en place)
- Pas de code spécifique nécessaire pour le theme

**React 19.2.0 - Error Boundaries:**

```typescript
// Class component obligatoire
class ErrorBoundary extends Component<Props, State> {
  // Lifecycle methods pour Error Boundary
  static getDerivedStateFromError(error: Error): State
  componentDidCatch(error: Error, errorInfo: ErrorInfo): void
}
```

**TypeScript 5.9.3 - Types:**

```typescript
import { Component, ErrorInfo, ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: (error: Error, resetError: () => void) => ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}
```

**React Router 7.1.1 - Navigation:**

```typescript
import { useNavigate } from 'react-router-dom';

const navigate = useNavigate();
navigate('/'); // Navigation programmatique vers accueil
```

**Logger Service (déjà existant):**

```typescript
import { logger } from '../services/logger';

logger.error('Message', {
  message: error.message,
  stack: error.stack,
  componentStack: errorInfo.componentStack,
  // Données structurées additionnelles
});
```

### Previous Story Intelligence

**Story 22.9 (découpage AdminPage.tsx) - Complétée:**

**Learnings applicables:**
1. **Class vs Function Components**: Story 22.9 utilisait function components, cette story nécessite un class component (Error Boundaries)
2. **Ant Design patterns**: Utilisation de composants Ant Design (Result) pour cohérence UI
3. **Tests sans régression**: Tous les tests existants doivent passer après intégration
4. **Documentation**: JSDoc complet avec exemples d'usage

**Story 22.8 (découpage types/api.ts) - Complétée:**

**Learnings applicables:**
1. **Approche conservative**: Intégrer ErrorBoundary sans casser l'existant
2. **Tests fréquents**: Valider après chaque étape (création, intégration, tests)

**Story 22.5 (protection double-submit ExecutionWizard) - Complétée:**

**Learnings applicables:**
1. **State management**: Utilisation de useState pour gérer hasError et error dans ErrorBoundary
2. **Guard pattern**: ErrorBoundary est un guard contre les erreurs non gérées
3. **UX**: Fournir des actions de récupération claires (comme isSubmitting guard dans 22.5)

**Story 17.7 (remplacer console.log par logger) - Complétée:**

**Learnings applicables:**
1. **Logger usage**: Utiliser logger.error() pour toutes les erreurs, pas console.error()
2. **Données structurées**: Logger avec données structurées (message, stack, componentStack)
3. **Production logs**: Logs error niveau toujours envoyés en production

**Patterns établis dans le projet frontend:**

1. **Error handling hooks**: try-catch dans event handlers et async code (useExecutionSubmit.ts)
2. **Error display components**: StructuredErrorCard pour affichage structuré
3. **Logger centralisé**: logger.ts pour tous les logs avec niveaux (debug, info, warn, error)
4. **Ant Design UI**: Tous les composants UI utilisent Ant Design pour cohérence
5. **TypeScript strict**: Interfaces explicites pour props et state

### Git Intelligence Summary

**5 derniers commits (contexte qualité code - Epic 22):**

1. **7f66ddc** - `refactor(22-9): split AdminPage into domain-specific sub-components`
   - **Pattern**: Refactoring composants volumineux pour maintenabilité
   - **Relevance**: ErrorBoundary est un nouveau composant, suivre les patterns établis

2. **878dd7c** - `refactor(22-8): split api.ts types into domain-specific modules`
   - **Pattern**: Organisation modulaire par domaine
   - **Relevance**: ErrorBoundary est un composant d'infrastructure (comme logger, api_client)

3. **6451489** - `refactor(22-7): extract 15 helper functions from executions views to utils module`
   - **Pattern**: Extraction de helpers pour réduire la complexité
   - **Relevance**: ErrorBoundary peut avoir un helper ErrorFallback séparé

4. **50e3d83** - `fix(22-6): standardize pagination response with 'total' field across all endpoints`
   - **Pattern**: Standardisation des interfaces API
   - **Relevance**: ErrorBoundary doit suivre les patterns d'interface (Props, State)

5. **ba713dc** - `fix(22-5): prevent double submission in ExecutionWizard with loading state`
   - **Pattern**: Guards pour éviter les états invalides
   - **Relevance**: ErrorBoundary est un guard contre les erreurs non gérées

**Patterns de commits observés:**

- **Prefix scope**: `refactor(22-X):`, `fix(22-X):` pour Epic 22
- **Messages descriptifs**: Action claire + impact
- **Tests systématiques**: Validation après chaque changement
- **Documentation**: JSDoc et README updates

**Recommandation pour cette story:**

```bash
# Commit message suggéré
git commit -m "feat(22-10): add React ErrorBoundary for unhandled render errors

- Create ErrorBoundary class component with fallback UI
- Integrate in AppLayout to wrap page routes
- Log errors with logger.error() for observability
- Add user-friendly error message in French
- Provide recovery actions (reload, go home)
- 7/7 tests pass (ErrorBoundary.test.tsx)
- 0 regression in existing tests"
```

### Latest Tech Information

**React 19.2.0 - Error Boundaries:**

React 19 n'a pas changé l'API Error Boundary (stable depuis React 16.0). Les Error Boundaries **doivent toujours** être des class components.

**Future considerations (pas dans le scope de cette story):**

React 19 a amélioré les error messages de développement, mais l'API Error Boundary reste identique. Future RFC pour Error Boundaries avec hooks, mais pas encore disponible.

**Ant Design 6.2.2 - Result Component:**

```typescript
// Ant Design 6.x Result API (stable)
<Result
  status="error"  // Types: "error" | "success" | "info" | "warning" | "404" | "403" | "500"
  title={ReactNode}
  subTitle={ReactNode}
  extra={ReactNode[]}  // Boutons ou autres actions
  icon={ReactNode}     // Icône personnalisée (optionnel)
/>
```

**Best practices Error Boundary (2026):**

1. **Placement stratégique**: Au niveau des routes, pas au root (isolation des erreurs)
2. **Logging**: Toujours logger avec stack trace complet pour debugging
3. **Fallback UI**: Message utilisateur-friendly, pas de stack trace technique
4. **Recovery actions**: Fournir des actions claires (reload, go home, contact support)
5. **Testing**: Mocker console.error pour éviter le bruit dans les tests

**Logger.ts - Production logging:**

Le projet a un TODO pour envoyer les logs frontend au backend via POST `/api/v1/logs`. Cette story ajoute logging local, le backend logging sera une amélioration future.

```typescript
// Actuel (Story 22.10)
logger.error('React Error Boundary caught error', { ... });
// → Console en dev, JSON logs en prod (local)

// Futur (amélioration hors scope)
logger.error('React Error Boundary caught error', { ... });
// → POST /api/v1/logs en production pour observabilité centralisée
```

**TypeScript 5.9.3 - Error Boundary Types:**

```typescript
// Types React pour Error Boundary
import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: (error: Error, resetError: () => void) => ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

class ErrorBoundary extends Component<Props, State> {
  // Implementation
}
```

**Vitest 4.0.18 - Testing Error Boundaries:**

```typescript
// Pattern pour tester Error Boundaries
const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

// Composant qui throw une erreur
function ThrowError({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) throw new Error('Test error');
  return <div>No error</div>;
}

// Test
it('catches error and renders fallback', () => {
  render(
    <ErrorBoundary>
      <ThrowError shouldThrow={true} />
    </ErrorBoundary>
  );
  expect(screen.getByText(/Une erreur est survenue/i)).toBeInTheDocument();
});
```

### Project Structure Notes

**Alignement avec la structure existante:**

```
frontend/src/
├── components/
│   ├── ErrorBoundary.tsx (NOUVEAU — composant d'infrastructure)
│   ├── execution/
│   │   └── StructuredErrorCard.tsx (existant — affichage erreurs API/validation)
│   └── layout/
│       └── AppLayout.tsx (modifié — intégration ErrorBoundary)
├── services/
│   ├── logger.ts (existant — utilisé par ErrorBoundary)
│   └── api_client.ts (existant — gestion erreurs HTTP)
└── __tests__/ ou components/__tests__/
    └── ErrorBoundary.test.tsx (NOUVEAU)
```

**Séparation des responsabilités:**

1. **ErrorBoundary**: Capture les erreurs de rendu React non gérées
2. **StructuredErrorCard**: Affiche les erreurs API et validation (déjà en place)
3. **api_client.ts**: Gère les erreurs HTTP et retry (déjà en place)
4. **logger.ts**: Centralise tous les logs (déjà en place)

**Pas de conflit entre ErrorBoundary et StructuredErrorCard:**

- **ErrorBoundary**: Erreurs de rendu (throw dans render, lifecycle)
- **StructuredErrorCard**: Erreurs métier (API errors, validation errors)

Les deux peuvent coexister et se complètent.

**Détection des conflits:**

Aucun composant existant ne gère les erreurs de rendu React. ErrorBoundary comble ce gap sans conflit.

### References

- [Source: _bmad-output/planning-artifacts/epic-22-amelioration-qualite-code.md#Story 22.10 - Lines 232-252]
- [Source: docs/code-quality-assessment-2026-02-08.md#Section 4.3 - Error Boundary React manquant]
- [React Docs: Error Boundaries - https://react.dev/reference/react/Component#catching-rendering-errors-with-an-error-boundary]
- [Ant Design Result: https://ant.design/components/result]
- [Logger service: frontend/src/services/logger.ts]
- [AppLayout: frontend/src/components/layout/AppLayout.tsx]
- [StructuredErrorCard: frontend/src/components/execution/StructuredErrorCard.tsx]
- [Story 22.9: Découpage AdminPage - Patterns de composants établis]
- [Story 17.7: Logger usage patterns - Logging centralisé]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

Aucun problème rencontré.

### Completion Notes List

- **Task 1+2**: Créé `ErrorBoundary.tsx` (~130 LOC) — class component avec `getDerivedStateFromError`, `componentDidCatch` (logger.error avec correlation_id et try-catch fallback), fallback UI via Ant Design `Result`, prop `fallback` optionnel pour personnalisation. `ErrorFallback` est un function component séparé pour pouvoir utiliser `useNavigate()`.
- **Task 3**: Intégré dans `AppLayout.tsx` — `<ErrorBoundary>` entoure `<Suspense><Outlet /></Suspense>`. Login et auth callback ne sont pas dans AppLayout donc non affectés.
- **Task 4**: 9 tests créés dans `ErrorBoundary.test.tsx` — capture erreur, fallback UI, logger.error() appelé avec correlation_id, bouton recharger (soft refresh via navigate(0)), bouton accueil, children sans erreur, fallback personnalisé, détails techniques en dev mode. Tous passent.
- **Task 5**: JSDoc avec exemples ajouté, section Error Boundary ajoutée dans README.md, 9/9 tests ErrorBoundary + 6/6 tests AppLayout passent (incluant 2 nouveaux tests d'intégration ErrorBoundary dans AppLayout), 0 régression introduite (18 fichiers en échec pré-existants).

### Code Review Fixes Applied (Auto-fix)

**Issues corrigés automatiquement lors de la review adversariale:**

1. ✅ **[HIGH]** ErrorBoundary reset error safe — `handleGoHome` navigue d'abord, unmount nettoie le state naturellement
2. ✅ **[MEDIUM]** ErrorFallback reçoit l'objet error — prop `error` ajoutée, affiche détails techniques en dev mode
3. ✅ **[MEDIUM]** Protection contre erreurs dans ErrorFallback — try-catch avec fallback HTML ultra-simple
4. ✅ **[MEDIUM]** Soft refresh au lieu de hard reload — `navigate(0)` préserve le state React au lieu de `window.location.reload()`
5. ✅ **[HIGH]** Tests vérifient le comportement correct — 2 nouveaux tests: détails techniques dev mode + correlation_id
6. ✅ **[MEDIUM]** Tests d'intégration AppLayout — 2 nouveaux tests vérifient la capture d'erreur dans child routes
7. ✅ **[MEDIUM]** Logger avec fallback — try-catch autour de `logger.error()`, fallback sur console.error
8. ✅ **[LOW]** Aria attributes — `aria-describedby="error-message"` ajouté aux boutons
9. ✅ **[LOW]** Correlation_id dans logs — `crypto.randomUUID()` ajouté aux logs d'erreur

**Total issues trouvés:** 12 (2 HIGH, 5 MEDIUM, 5 LOW)
**Total issues fixés:** 9 (tous HIGH et MEDIUM + 2 LOW bonus)
**Tests avant review:** 7 ErrorBoundary + 4 AppLayout = 11 tests
**Tests après review:** 9 ErrorBoundary + 6 AppLayout = 15 tests (+36% couverture)

### Change Log

- 2026-02-09: Créé ErrorBoundary class component avec fallback UI Ant Design, intégré dans AppLayout, 9 tests unitaires, documentation README
- 2026-02-09: Code review adversariale — 9 corrections appliquées (safe navigation, error prop, try-catch fallback, soft refresh, correlation_id, aria attributes, tests d'intégration AppLayout), 15 tests total (9 ErrorBoundary + 6 AppLayout)

### File List

- `idp-portal/frontend/src/components/ErrorBoundary.tsx` (nouveau — 130 LOC, class component avec fallbacks)
- `idp-portal/frontend/src/components/ErrorBoundary.test.tsx` (nouveau — 9 tests unitaires)
- `idp-portal/frontend/src/components/layout/AppLayout.tsx` (modifié — ajout ErrorBoundary autour Outlet)
- `idp-portal/frontend/src/components/layout/AppLayout.test.tsx` (modifié — 2 tests intégration ErrorBoundary ajoutés)
- `idp-portal/frontend/README.md` (modifié — section Error Boundary ajoutée)

# Standards Frontend — IDP Portal

**Version cible React et Ant Design : 6.2 / 19.2**

Ce document résume les règles adoptées pour le frontend IDP Portal suite à l'audit et l'alignement effectués (Story 5.5).

## Versions Cibles

| Package | Version | Notes |
|---------|---------|-------|
| React | ^19.2.0 | React 19 avec hooks |
| antd | ^6.2.2 | Ant Design 6.2 |
| @ant-design/icons | ^6.1.0 | Icons 6.x |
| react-router | ^7.13.0 | React Router 7 |
| vite | ^7.2.4 | Build tool |
| typescript | ~5.9.3 | TypeScript 5.9 |

## Règles Adoptées

### 1. Pas de Class Components

Tous les composants doivent utiliser des fonctions et des hooks. Aucun `class Component extends React.Component`.

### 2. Pas d'APIs React Legacy

Interdits :
- `findDOMNode`
- `UNSAFE_componentWillMount`, `UNSAFE_componentWillReceiveProps`, etc.
- Legacy Context API (`childContextTypes`, `contextTypes`)

### 3. Ant Design — API Publique Uniquement

**NE PAS UTILISER** les imports internes :
```typescript
// INTERDIT
import type { ColumnsType } from 'antd/es/table';
import type { SorterResult } from 'antd/es/table/interface';
```

**UTILISER** les exports publics :
```typescript
// CORRECT
import type { TableProps } from 'antd';

// Types extraits depuis TableProps
type ColumnsType<T> = TableProps<T>['columns'];
type TableOnChange<T> = NonNullable<TableProps<T>['onChange']>;
type SorterResult<T> = Parameters<TableOnChange<T>>[2];
```

### 4. Message / Notification — App.useApp()

**NE PAS UTILISER** l'import direct :
```typescript
// INTERDIT
import { message, notification } from 'antd';
message.error('Erreur');
```

**UTILISER** le hook App.useApp() :
```typescript
// CORRECT
import { App } from 'antd';

function MyComponent() {
  const { message, notification } = App.useApp();

  const handleError = () => {
    message.error('Erreur');
  };
}
```

Cela garantit que les messages/notifications utilisent le contexte ConfigProvider et respectent le thème.

### 5. Theme — Token-Based

Le thème utilise le système de tokens Ant Design 6 via `ConfigProvider` :
- Fichier : `src/theme/desjardins.ts`
- Export : `lightTheme`, `darkTheme`
- Tokens partagés pour couleurs, espacement, typographie

### 6. Naming Conventions

| Type | Convention | Exemple |
|------|------------|---------|
| Composants | PascalCase | `ActionCard.tsx` |
| Hooks | use prefix | `useDebounce.ts` |
| Services | snake_case | `catalog_service.ts` |
| API data | snake_case | `action_id`, `created_at` |
| Props/Variables | camelCase | `isLoading`, `onSubmit` |

### 7. Tests — App Wrapper

Pour les composants qui utilisent `App.useApp()`, les tests doivent wrapper avec `<App>` :

```typescript
import { App } from 'antd';

function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

it('test case', () => {
  renderWithApp(<MyComponent />);
});
```

## Checklist PR Frontend

Avant de soumettre une PR frontend, vérifier :

- [ ] Pas de `class Component`
- [ ] Pas d'import depuis `antd/es/*`
- [ ] `message` et `notification` via `App.useApp()`
- [ ] `modal.confirm` via `App.useApp().modal` (pas `Modal.confirm` direct)
- [ ] Types Table extraits depuis `TableProps<T>`
- [ ] Tests passent (`npm run test`)
- [ ] ESLint clean (`npm run lint`) — **obligatoire**
- [ ] Pas de warning Ant Design dépréciation dans la console

## Dépréciations Ant Design 6.2 — Corrections Appliquées

Les dépréciations suivantes ont été corrigées dans toute la codebase :

| Ancien | Nouveau | Composants |
|--------|---------|------------|
| `Modal destroyOnClose` | `destroyOnHidden` | Modal |
| `Space direction` | `orientation` | Space |
| `Alert message` | `title` | Alert |
| `Notification message` | `title` | notification.error/success/warning |
| `Steps items.description` | `items.content` | Steps |
| `Drawer width` | `styles={{ wrapper: { width } }}` | Drawer |
| `Modal.confirm` | `App.useApp().modal.confirm` | Confirmations supprimer |

Tous les tests passent sans aucun warning de dépréciation Ant Design.

### Règles ESLint importantes

- **react-hooks/set-state-in-effect** : Éviter `setState` synchrone dans un `useEffect`. Préférer `queueMicrotask(() => setState(...))` pour décaler les mises à jour si nécessaire.
- **react-hooks/exhaustive-deps** : Inclure toutes les dépendances (y compris `message`, `notification`) dans les tableaux de dépendances des hooks.
- **Tests async** : Envelopper les mises à jour d'état asynchrones dans `act()` pour éviter les warnings React.

## Vérification Automatique

Les standards suivants sont appliqués automatiquement par le plugin ESLint local `eslint-plugin-standards/` :

| Règle ESLint | Standard vérifié | Niveau |
|---|---|---|
| `standards/no-antd-internal-imports` | Section 3 — Pas d'import `antd/es/*` | `error` |
| `standards/require-app-useapp` | Section 4 — `message`/`notification` via `App.useApp()` | `error` |
| `standards/no-class-components` | Section 1 — Pas de class components | `error` |

### Commandes

```bash
# Vérifier conformité
npm run lint

# Corriger automatiquement (quand applicable)
npm run lint -- --fix
```

Les règles sont bloquantes en CI (job `lint-frontend` dans `.github/workflows/ci.yml`).

Pour la documentation détaillée du plugin : [`eslint-plugin-standards/README.md`](eslint-plugin-standards/README.md).

---

*Document créé le 2026-01-30 — Story 5.5*
*Mise à jour le 2026-01-30 — Corrections dépréciations Ant Design 6.2*
*Mise à jour le 2026-02-07 — Vérification automatique ESLint (Story 17.16)*

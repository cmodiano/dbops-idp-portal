# eslint-plugin-standards

Plugin ESLint local pour vérifier la conformité aux standards définis dans `FRONTEND-STANDARDS.md`.

## Règles

### `standards/no-antd-internal-imports`

Interdit les imports depuis `antd/es/*` (APIs internes). Utiliser l'API publique `import { ... } from 'antd'`.

**Exemples :**

```typescript
// INTERDIT
import type { ColumnsType } from 'antd/es/table';
import type { DefaultOptionType } from 'antd/es/select';

// CORRECT
import type { TableProps } from 'antd';
type ColumnsType<T> = TableProps<T>['columns'];
```

### `standards/require-app-useapp`

Interdit l'import direct de `message` et `notification` depuis `'antd'`. Utiliser `App.useApp()`.

**Note:** `Modal` component (déclaratif `<Modal>`) est autorisé. Seul `Modal.confirm()` (impératif) nécessite `App.useApp().modal.confirm()`, mais cette vérification est manuelle (voir PR template).

**Exemples :**

```typescript
// INTERDIT
import { message, notification } from 'antd';
message.success('Hello');

// CORRECT
import { App, Modal } from 'antd';  // Modal component OK
const { message, notification, modal } = App.useApp();
message.success('Hello');
modal.confirm({ title: 'Confirm?' });  // Imperative modal via useApp
```

### `standards/no-class-components`

Interdit les class components React. Utiliser des function components avec hooks.

**Exemples :**

```typescript
// INTERDIT
class MyComponent extends React.Component { ... }
class MyComponent extends Component { ... }

// CORRECT
function MyComponent() { ... }
const MyComponent = () => { ... };
```

## Intégration

Le plugin est intégré dans `eslint.config.js` :

```javascript
import standardsPlugin from './eslint-plugin-standards/index.js';

// dans la config...
plugins: { standards: standardsPlugin },
rules: {
  'standards/no-antd-internal-imports': 'error',
  'standards/require-app-useapp': 'error',
  'standards/no-class-components': 'error',
},
```

## Tests

```bash
npx vitest run eslint-plugin-standards/
```

## Maintenance

Lors d'une mise à jour majeure d'Ant Design, vérifier que les règles restent pertinentes et les mettre à jour si nécessaire.

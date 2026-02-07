## Description

<!-- Décrivez brièvement les changements apportés -->

## Type de changement

- [ ] Nouvelle fonctionnalité
- [ ] Correction de bug
- [ ] Refactoring
- [ ] Documentation
- [ ] Autre : ___

## Frontend Standards Checklist

> Référence : [`FRONTEND-STANDARDS.md`](../idp-portal/frontend/FRONTEND-STANDARDS.md)

**Vérifications automatiques (ESLint)** — ces règles sont bloquantes en CI :

- [x] `standards/no-antd-internal-imports` — Pas d'import depuis `antd/es/*`
- [x] `standards/require-app-useapp` — `message`/`notification` via `App.useApp()`
- [x] `standards/no-class-components` — Pas de class components
- [x] `no-console` — Pas de `console.log` (utiliser `logger`)

**Vérifications manuelles :**

- [ ] Types Table extraits depuis `TableProps<T>` (pas `antd/es/table`)
- [ ] `modal.confirm` via `App.useApp().modal` (pas `Modal.confirm` direct)
- [ ] Naming conventions respectées (PascalCase composants, camelCase hooks/props)
- [ ] Tests passent (`npm run test`)
- [ ] Pas de warning Ant Design dépréciation dans la console

## Tests

- [ ] Tests unitaires ajoutés/mis à jour
- [ ] Tests existants passent sans régression
- [ ] `npm run lint` passe
- [ ] `npm run build` passe

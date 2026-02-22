# Story 34.2 : Quick wins Frontend — notification, status, Ant Design

Status: done

<!-- Réf: CODEBASE-REVIEW.md §15 SOLID-FE-5, SOLID-FE-10, §16 BUG-FE-1b/2b -->

## Story

En tant que développeur frontend,
je veux corriger quatre dettes techniques ciblées (DIP api_client, DRY status mapping, props Ant Design dépréciées),
afin d'améliorer la maintenabilité, la conformité SOLID et l'alignement sur Ant Design 6.2.

## Contexte

Cette story couvre les **quick wins frontend prioritaires** (epic 34, issues SOLID-FE-5, SOLID-FE-10, BUG-FE-1b/2b) identifiés dans le CODEBASE-REVIEW du 2026-02-21 :

- **SOLID-FE-5 [HIGH]** — `api_client.ts` importe `notification` directement depuis `'antd'` (ligne 1). La couche transport API ne devrait **pas** dépendre du système de notification UI. Crée une dépendance bidirectionnelle entre service et UI.
- **SOLID-FE-10 [MEDIUM]** — Mapping status→couleur/label dupliqué indépendamment dans :
  - `ExecutionTimeline.tsx` (l.24–30) : constante `STATUS_COLOR` pour `ExecutionStepStatus` (PENDING/RUNNING/COMPLETED/FAILED/SKIPPED)
  - `AuditPage.tsx` (l.61–66) : constante `STATUS_CONFIG` pour statuts audit (success/failed/running/unknown)
  - `pages/executions/executionsColumns.tsx` : **déjà correct** — utilise `renderStatusIndicator()` de `executionRenderers.tsx`
- **BUG-FE-1b [HIGH]** — `notification.warning({ message: ... })` et `notification.error({ message: ... })` dans `api_client.ts` (l.182, l.213) : la prop `message:` est dépréciée en Ant Design 6.2, doit être `title:`. (Corrigé conjointement avec SOLID-FE-5.)
- **BUG-FE-2b [HIGH]** — `<Alert message=...>` → `<Alert title=...>` : **aucune occurrence trouvée** lors de la recherche pré-story. Vérification de confirmation requise.

## Acceptance Criteria

### AC1 — SOLID-FE-5 : Injection callback notification dans api_client.ts
- `api_client.ts` **ne contient plus** `import { notification } from 'antd'`
- Une fonction `setNotificationCallback(fn)` est exportée, analogue à `setAuthAccessors`
- Sans appel à `setNotificationCallback`, le comportement par défaut est **no-op** (aucune erreur runtime)
- Le composant possédant le contexte Ant Design (ex: `AppLayout.tsx`) appelle `setNotificationCallback` avec `notification` issu de `App.useApp()`

### AC2 — BUG-FE-1b : Props `title:` dans les appels notification
- Dans les deux appels `notification.warning` et `notification.error` (devenus callbacks), la clé dépréciée `message:` est remplacée par `title:`
- `description:` et `duration:` restent inchangés

### AC3 — BUG-FE-2b : Vérification `<Alert message=`
- `grep -r '<Alert message=' frontend/src/` → 0 occurrence
- Si des occurrences existent : les corriger en `title=`
- Résultat documenté dans les Completion Notes

### AC4 — SOLID-FE-10 : Utility `execution-status.ts`
- Fichier `frontend/src/utils/execution-status.ts` créé
- Il exporte `STEP_STATUS_COLOR : Record<ExecutionStepStatus, string>` — migré depuis `ExecutionTimeline.tsx`
- Il exporte `AUDIT_STATUS_CONFIG : Record<string, { color: string; label: string }>` — migré depuis `AuditPage.tsx`
- `ExecutionTimeline.tsx` importe `STEP_STATUS_COLOR` depuis le nouveau module et supprime sa définition locale
- `AuditPage.tsx` importe `AUDIT_STATUS_CONFIG` depuis le nouveau module et supprime sa définition locale
- Les noms locaux peuvent être aliasés à l'import pour minimiser les modifications (ex: `import { STEP_STATUS_COLOR as STATUS_COLOR } from ...`)

### AC5 — Tests
- `pnpm test` : 0 régression dans les suites concernées
- Nouveaux tests : au moins 1 test unitaire pour `setNotificationCallback` (callback appelé avec bons args sur 503 DB_UNAVAILABLE)
- `tsc --noEmit` : 0 nouvelle erreur TypeScript
- `pnpm lint` : 0 nouvelle violation ESLint

## Tasks / Subtasks

- [x] **Task 1 — SOLID-FE-5 + BUG-FE-1b : Refactoriser api_client.ts** (AC: #1, #2)
  - [x] 1.1 Lire `frontend/src/services/api_client.ts` lignes 1–230 (état actuel complet)
  - [x] 1.2 Supprimer `import { notification } from 'antd'` (ligne 1)
  - [x] 1.3 Déclarer type `NotifyFn` et variable `_notify: NotifyFn = () => {}`
  - [x] 1.4 Exporter `setNotificationCallback(fn: NotifyFn): void` (même pattern que `setAuthAccessors`)
  - [x] 1.5 Remplacer `notification.warning({ message: ..., description: ..., duration: ... })` (ex-l.182) par `_notify('warning', { title: ..., description: ..., duration: ... })`
  - [x] 1.6 Remplacer `notification.error({ message: ..., description: ..., duration: ... })` (ex-l.213) par `_notify('error', { title: ..., description: ..., duration: ... })`
  - [x] 1.7 Vérifier `grep -n "from 'antd'" frontend/src/services/api_client.ts` → 0 résultat ✅

- [x] **Task 2 — Wiring setNotificationCallback dans le composant racine** (AC: #1)
  - [x] 2.1 Localiser le composant qui possède le contexte `App` Ant Design (chercher `App.useApp()` dans `AppLayout.tsx` ou `App.tsx`)
  - [x] 2.2 Importer `setNotificationCallback` depuis `../services/api_client`
  - [x] 2.3 Appeler `setNotificationCallback` avec le `notification` issu de `App.useApp()` (dans un `useEffect` ou directement au niveau du composant selon le pattern existant)
  - [x] 2.4 Vérifier que le wiring est cohérent avec `setAuthAccessors` dans `AuthContext.tsx`

- [x] **Task 3 — BUG-FE-2b : Vérification Alert dépréciée** (AC: #3)
  - [x] 3.1 Lancer `grep -r '<Alert message=' frontend/src/` → noter le résultat
  - [x] 3.2 Si occurrences trouvées : corriger chaque `message=` en `title=`
  - [x] 3.3 Documenter le résultat dans les Completion Notes

- [x] **Task 4 — SOLID-FE-10 : Créer execution-status.ts** (AC: #4)
  - [x] 4.1 Lire `ExecutionTimeline.tsx` lignes 24–31 : copier `STATUS_COLOR` exact
  - [x] 4.2 Lire `AuditPage.tsx` lignes 61–66 : copier `STATUS_CONFIG` exact
  - [x] 4.3 Créer `frontend/src/utils/execution-status.ts` avec exports `STEP_STATUS_COLOR` et `AUDIT_STATUS_CONFIG`
  - [x] 4.4 Dans `ExecutionTimeline.tsx` : importer `STEP_STATUS_COLOR as STATUS_COLOR` depuis le nouveau module ; supprimer la définition locale
  - [x] 4.5 Dans `AuditPage.tsx` : importer `AUDIT_STATUS_CONFIG as STATUS_CONFIG` depuis le nouveau module ; supprimer la définition locale
  - [x] 4.6 Vérifier `grep -n "const STATUS_COLOR\|const STATUS_CONFIG" ExecutionTimeline.tsx AuditPage.tsx` → 0 définition locale ✅

- [x] **Task 5 — Tests** (AC: #5)
  - [x] 5.1 Localiser `api_client.test.ts` — ajouter test : `setNotificationCallback` → callback invoqué sur 503 DB_UNAVAILABLE avec les bons args `('warning', { title: ..., description: ..., duration: ... })`
  - [x] 5.2 Ajouter test : sans `setNotificationCallback` (défaut no-op), pas d'erreur lors d'un 503
  - [x] 5.3 Lancer `pnpm test` → 0 régression (52/52 api_client tests + 92/92 fichiers modifiés)
  - [x] 5.4 `pnpm tsc --noEmit` → 0 nouvelle erreur

### Review Follow-ups (AI)

- [ ] [AI-Review][LOW] Exporter `NotifyFn` depuis `api_client.ts` pour permettre aux consommateurs de typer leurs mocks sans `Parameters<typeof setNotificationCallback>[0]` [api_client.ts:3-7]
- [ ] [AI-Review][LOW] Ajouter `: void` à `setAuthAccessors` pour cohérence avec `setNotificationCallback` [api_client.ts:38]
- [ ] [AI-Review][LOW] Implémenter ou convertir en story le TODO 429 notification — l'infrastructure `_notify` est maintenant en place [api_client.ts:157-159]
- [ ] [AI-Review][LOW] Ajouter tests unitaires pour `execution-status.ts` : vérifier les valeurs HEX et labels (ex: `expect(STEP_STATUS_COLOR.COMPLETED).toBe('#10B981')`) [execution-status.ts]
- [ ] [AI-Review][LOW] Corriger la description du test no-op : remplacer "without setNotificationCallback" par "with explicit no-op callback" pour clarté sémantique [api_client.test.ts:873]

## Dev Notes

### ⚠️ Pattern EXISTANT à reproduire — `setAuthAccessors` dans api_client.ts

Le pattern d'injection de dépendance est déjà en place dans `api_client.ts` pour l'authentification :

```typescript
// Lignes 24–34 (existant)
let _getAccessToken: (() => string | null) = () => null;
let _onRefreshNeeded: (() => Promise<string | null>) = async () => null;

export function setAuthAccessors(
  getToken: () => string | null,
  refreshFn: () => Promise<string | null>,
): void {
  _getAccessToken = getToken;
  _onRefreshNeeded = refreshFn;
}
```

Et dans `AuthContext.tsx` (l.144–146) :
```typescript
useEffect(() => {
  setAuthAccessors(() => tokenRef.current, refreshTokenFn);
}, [accessToken, refreshTokenFn]);
```

**Reproduire ce pattern pour la notification.** Le type recommandé :

```typescript
type NotifyFn = (
  type: 'warning' | 'error',
  config: { title: string; description: string; duration?: number },
) => void;

let _notify: NotifyFn = () => {};

export function setNotificationCallback(fn: NotifyFn): void {
  _notify = fn;
}
```

### ⚠️ État actuel de api_client.ts — appels à corriger

Ligne 1 (à supprimer) :
```typescript
import { notification } from 'antd';
```

Lignes 181–187 (à remplacer) :
```typescript
notification.warning({
  message: 'Service temporairement indisponible',
  description: 'Nouvelle tentative en cours...',
  duration: Math.ceil(delay / 1000) + 2,
});
```

Lignes 213–217 (à remplacer) :
```typescript
notification.error({
  message: 'Base de données temporairement indisponible',
  description: 'Base de données temporairement indisponible après bascule. Veuillez réessayer dans quelques instants.',
  duration: 8,
});
```

### ⚠️ Wiring setNotificationCallback — Localisation

Le composant doit être rendu **à l'intérieur** d'un `<App>` Ant Design pour que `App.useApp()` fonctionne. Chercher :
- `frontend/src/components/AppLayout.tsx` — probable candidat
- `frontend/src/App.tsx` — alternative

Exemple de wiring :
```typescript
// Dans AppLayout.tsx ou App.tsx
import { App as AntApp } from 'antd';
import { setNotificationCallback } from '../services/api_client';

function Inner() {
  const { notification } = AntApp.useApp();
  useEffect(() => {
    setNotificationCallback((type, config) => notification[type](config));
  }, [notification]);
  // ...
}
```

### ⚠️ SOLID-FE-10 — Types distincts, noms distincts dans execution-status.ts

| Source | Clés | Type TypeScript | Export dans execution-status.ts |
|--------|------|-----------------|----------------------------------|
| `ExecutionTimeline.tsx` STATUS_COLOR | PENDING, RUNNING, COMPLETED, FAILED, SKIPPED | `Record<ExecutionStepStatus, string>` | `STEP_STATUS_COLOR` |
| `AuditPage.tsx` STATUS_CONFIG | success, failed, running, unknown | `Record<string, { color: string; label: string }>` | `AUDIT_STATUS_CONFIG` |

**Ne pas confondre** avec les statuts d'exécution déjà centralisés dans `executionRenderers.tsx` (`STATUS_BADGE_CONFIG`, `STATUS_CONFIG` pour `ExecutionStatusType`). Ce sont des domaines différents — ne pas toucher `executionRenderers.tsx`.

`ExecutionStepStatus` est défini dans `types/api/executions.ts` ligne 81 :
```typescript
export type ExecutionStepStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'SKIPPED';
```

### Contenu exact à migrer dans execution-status.ts

Depuis `ExecutionTimeline.tsx` (l.24–30) :
```typescript
const STATUS_COLOR: Record<ExecutionStepStatus, string> = {
  PENDING: '#9CA3AF',
  RUNNING: '#3B82F6',
  COMPLETED: '#10B981',
  FAILED: '#EF4444',
  SKIPPED: '#9CA3AF',
};
```

Depuis `AuditPage.tsx` (l.61–66) :
```typescript
const STATUS_CONFIG: Record<string, { color: string; label: string }> = {
  success: { color: 'success', label: 'Succès' },
  failed: { color: 'error', label: 'Échec' },
  running: { color: 'processing', label: 'En cours' },
  unknown: { color: 'default', label: 'Inconnu' },
};
```

### Structure des fichiers concernés

```
frontend/src/
  services/
    api_client.ts            ← SOLID-FE-5 + BUG-FE-1b (l.1, l.182, l.213)
    api_client.test.ts       ← Tests à enrichir (Task 5.1/5.2)
  components/
    AppLayout.tsx            ← Probable wiring setNotificationCallback (Task 2)
    execution/
      ExecutionTimeline.tsx  ← SOLID-FE-10 (l.24–30, STATUS_COLOR à supprimer)
  pages/
    AuditPage.tsx            ← SOLID-FE-10 (l.61–66, STATUS_CONFIG à supprimer)
  utils/
    execution-status.ts      ← NOUVEAU fichier (Task 4)
    executionRenderers.tsx   ← NE PAS MODIFIER (déjà centralisé pour ExecutionStatusType)
  types/
    api/
      executions.ts          ← ExecutionStepStatus déjà défini l.81
  contexts/
    AuthContext.tsx           ← Référence pattern setAuthAccessors (l.144–146)
```

### Vérification BUG-FE-2b

Recherche effectuée avant la création de cette story : `grep -r '<Alert message=' frontend/src/` → **0 occurrence**. Le bug semble déjà résolu par Story 30.13. La Task 3 est uniquement une confirmation.

### Tech stack et contraintes

- React 18, TypeScript strict, Ant Design 6.2 — [Source: docs/frontend-implementation.md]
- **Ant Design 6.2** : `notification.*(title:)` est la prop correcte ; `message:` est dépréciée ([Source: antd/es/notification/useNotification.js deprecation mapping])
- `App.useApp()` doit être appelé **à l'intérieur** d'un composant enfant de `<App>` Ant Design
- Le no-op par défaut (`_notify = () => {}`) est essentiel pour que les tests unitaires de `api_client.test.ts` fonctionnent sans mocker Ant Design

### Contexte git récent

- `585ead9 feat(34-1): quick-wins backend — DI queryset chaining & validation DRY` — Story précédente de la même série
- `fa39f92 feat(33-5): SRP — découper ActionForm et ActionWizard` — Découpage frontend de référence
- `ec7a77b feat(33-4): DIP — injection de dépendances pour les services principaux` — Pattern DI de référence (côté backend)

### Commandes de test recommandées

```bash
# Depuis le répertoire frontend
cd /Users/cyrille/Documents/Dev/test/idp-portal/frontend

# Tests ciblés api_client
pnpm test src/services/api_client.test.ts

# Tests ExecutionTimeline et AuditPage
pnpm test src/components/execution/ExecutionTimeline
pnpm test src/pages/AuditPage

# Suite complète
pnpm test

# Type check
pnpm tsc --noEmit

# Lint
pnpm lint
```

### Project Structure Notes

- Tous les fichiers modifiés sont frontend uniquement — 0 risque de régression backend
- Aucune migration DB, aucun changement d'API publique
- `execution-status.ts` n'importe que depuis `types/` — aucune dépendance circulaire possible
- La conformité Ant Design 6.2 est déjà validée (Stories 26.15, 30.13) — cette story ferme les 2 derniers cas résiduels BUG-FE-1b/2b

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-5] — DIP api_client notification
- [Source: idp-portal/CODEBASE-REVIEW.md#SOLID-FE-10] — DRY status mapping
- [Source: idp-portal/CODEBASE-REVIEW.md§16] — BUG-FE-1b/2b résidus props dépréciées Ant Design
- [Source: _bmad-output/planning-artifacts/epic-34-codebase-review-restant-fev-2026.md#Story-34.2]
- [Source: idp-portal/frontend/src/services/api_client.ts] — l.1 (import antd), l.182/213 (notification calls)
- [Source: idp-portal/frontend/src/contexts/AuthContext.tsx] — l.144–146 (pattern setAuthAccessors à reproduire)
- [Source: idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx] — l.24–30 (STATUS_COLOR)
- [Source: idp-portal/frontend/src/pages/AuditPage.tsx] — l.61–66 (STATUS_CONFIG)
- [Source: idp-portal/frontend/src/types/api/executions.ts] — l.81 (ExecutionStepStatus)
- [Source: idp-portal/frontend/src/utils/executionRenderers.tsx] — STATUS_BADGE_CONFIG/STATUS_CONFIG (ne pas toucher)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

- **AC1 (SOLID-FE-5)** : `import { notification } from 'antd'` supprimé de `api_client.ts`. Pattern DIP `setNotificationCallback` ajouté, analogue à `setAuthAccessors`. No-op par défaut.
- **AC2 (BUG-FE-1b)** : Les deux appels notification convertis de `{ message: }` vers `{ title: }` conformément à Ant Design 6.2.
- **AC3 (BUG-FE-2b)** : `grep -r '<Alert message=' frontend/src/` → **0 occurrence** confirmée. Bug déjà résolu par Story 30.13.
- **AC4 (SOLID-FE-10)** : `execution-status.ts` créé avec `STEP_STATUS_COLOR` et `AUDIT_STATUS_CONFIG`. Importé dans `ExecutionTimeline.tsx` (alias `STATUS_COLOR`) et `AuditPage.tsx` (alias `STATUS_CONFIG`). Définitions locales supprimées.
- **AC5 (Tests)** : 52/52 tests `api_client.test.ts` passent. 2 nouveaux tests `setNotificationCallback` ajoutés. Tests `ExecutionTimeline` (34/34) et `AppLayout` (6/6) sans régression. `tsc --noEmit` : 0 erreur. Lint : 0 nouvelle violation dans les fichiers modifiés.
- **Wiring** : `AppLayout.tsx` câble le callback via `App.useApp()` dans un `useEffect`, pattern cohérent avec `setAuthAccessors`.

### File List

- `idp-portal/frontend/src/services/api_client.ts` — SOLID-FE-5 + BUG-FE-1b : suppression import antd, ajout NotifyFn/setNotificationCallback, props title
- `idp-portal/frontend/src/services/api_client.test.ts` — Tests mis à jour (callback vs spy antd), 2 nouveaux tests AC5
- `idp-portal/frontend/src/components/layout/AppLayout.tsx` — Wiring setNotificationCallback via App.useApp() + cleanup useEffect (code-review fix M1)
- `idp-portal/frontend/src/utils/execution-status.ts` — NOUVEAU : STEP_STATUS_COLOR + AUDIT_STATUS_CONFIG
- `idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx` — Import STEP_STATUS_COLOR, suppression définition locale
- `idp-portal/frontend/src/pages/AuditPage.tsx` — Import AUDIT_STATUS_CONFIG, suppression définition locale
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Mise à jour statut story (code-review fix M2)

### Change Log

- 2026-02-22 : Story 34.2 implémentée — DIP notification api_client (SOLID-FE-5), props title Ant Design 6.2 (BUG-FE-1b), vérification BUG-FE-2b (0 occurrence), centralisation status mapping (SOLID-FE-10)
- 2026-02-22 : Code review — 2 issues MEDIUM corrigés (M1: cleanup useEffect AppLayout.tsx, M2: sprint-status.yaml dans File List), 5 action items LOW créés → statut : done

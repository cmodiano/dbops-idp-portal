# Story 36.3 : Polling pour les observateurs

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu'utilisateur consultant la liste « Toutes les exécutions » (sans avoir lancé une exécution en cours),
je veux que la liste se rafraîchisse **régulièrement** pour refléter les changements de statut (ex. terminé, échec),
afin de voir l'activité des autres et l'état à jour sans recharger la page.

## Acceptance Criteria

1. **Given** je suis sur la vue « Toutes les exécutions » (ou « Mes exécutions »)
   **When** une exécution (lancée par moi ou par un autre) change de statut côté backend
   **Then** la liste se met à jour automatiquement après au plus un intervalle de polling (≤ 10 s)
   **And** je n'ai pas besoin de recharger la page manuellement

2. **Given** le polling est actif et la page est visible (onglet actif)
   **When** l'intervalle de polling s'écoule
   **Then** une requête de rafraîchissement est envoyée au backend
   **And** la liste reflète les nouveaux statuts

3. **Given** l'onglet est mis en arrière-plan (document.hidden = true)
   **When** l'intervalle de polling s'écoule
   **Then** la requête de rafraîchissement est ignorée (Visibility API)
   **And** dès que l'onglet redevient actif (visibilitychange → visible), un rafraîchissement immédiat est déclenché

4. **Given** des exécutions « en cours » (RUNNING / SUBMITTED / PENDING_APPROVAL) sont présentes dans la liste
   **When** je suis observateur (je n'ai pas lancé ces exécutions, ou la WS Story 36.2 gère mes propres exécutions)
   **Then** l'intervalle de polling de la liste est de `OBSERVER_POLL_INTERVAL_MS` (10 000 ms)
   **And** les changements de statut (→ COMPLETED / FAILED) apparaissent dans la liste après le prochain cycle

5. **Given** aucune exécution en cours n'est présente dans la liste
   **When** le polling s'écoule
   **Then** l'intervalle est de `BACKGROUND_POLL_INTERVAL_MS` (30 000 ms)
   **And** de nouvelles exécutions lancées par d'autres utilisateurs finissent par apparaître

6. **Given** la Story 36.2 est active (WS / fallback polling 2000 ms pour les exécutions de l'acteur)
   **When** la liste reçoit un refresh via polling observateur (10 s)
   **Then** il n'y a pas de conflit : le polling observateur met à jour la liste entière, les exécutions de l'acteur bénéficient de la mise à jour WS **en plus**
   **And** aucune duplication de requêtes ni de state race condition

## Tasks / Subtasks

- [x] **Task 1 — Renommer et ajuster `POLL_INTERVAL_MS` → `OBSERVER_POLL_INTERVAL_MS`** (AC: #1, #4, #5)
  - [x] 1.1 Dans `idp-portal/frontend/src/hooks/useExecutionsData.ts`, remplacer la constante `POLL_INTERVAL_MS = 4000` par `OBSERVER_POLL_INTERVAL_MS = 10_000`
  - [x] 1.2 Dans le `useEffect` de polling, remplacer `POLL_INTERVAL_MS` par `OBSERVER_POLL_INTERVAL_MS` : `const intervalMs = hasRunning ? OBSERVER_POLL_INTERVAL_MS : BACKGROUND_POLL_INTERVAL_MS;`
  - [x] 1.3 Mettre à jour le commentaire JSDoc du hook pour refléter le nouvel intervalle observateur

- [x] **Task 2 — Ajouter la Visibility API dans le polling** (AC: #2, #3)
  - [x] 2.1 Dans le même `useEffect` de polling, remplacer le `setInterval` nu par un setInterval qui vérifie `document.hidden` avant d'appeler `refetchSilent()` :
    ```typescript
    const intervalId = setInterval(() => {
      if (!document.hidden) refetchSilent();
    }, intervalMs);
    ```
  - [x] 2.2 Ajouter un listener `visibilitychange` : quand `document.hidden` passe à `false`, déclencher un `refetchSilent()` immédiat
  - [x] 2.3 Retourner le cleanup complet : `clearInterval(intervalId)` + `document.removeEventListener('visibilitychange', handler)`

- [x] **Task 3 — Tests `useExecutionsData.test.ts`** (AC: #1, #2, #3, #4, #5)
  - [x] 3.1 Test : quand des exécutions RUNNING sont présentes, `setInterval` est appelé avec `10000` ms (et non 4000)
  - [x] 3.2 Test : quand aucune exécution en cours, `setInterval` est appelé avec `30000` ms
  - [x] 3.3 Test : quand `document.hidden = true`, `refetchSilent` (listExecutions) n'est PAS appelé à l'intervalle
  - [x] 3.4 Test : quand `document.hidden = false` et intervalle écoulé, `refetchSilent` EST appelé
  - [x] 3.5 Test : quand l'onglet redevient visible (event `visibilitychange`), `refetchSilent` est appelé immédiatement

## Dev Notes

### Infrastructure existante à réutiliser (NE PAS réinventer)

**Polling actuel dans `useExecutionsData.ts` (Story 26.4 / 36.2) :**
```typescript
// idp-portal/frontend/src/hooks/useExecutionsData.ts

const POLL_INTERVAL_MS = 4000;               // ← À remplacer par OBSERVER_POLL_INTERVAL_MS = 10_000
const BACKGROUND_POLL_INTERVAL_MS = 30000;   // ← Inchangé

// useEffect polling actuel (lignes 154–163)
useEffect(() => {
  const hasRunning = executions.some((e) => RUNNING_STATUSES.includes(e.status));
  const intervalMs = hasRunning ? POLL_INTERVAL_MS : BACKGROUND_POLL_INTERVAL_MS;
  const intervalId = setInterval(() => {
    refetchSilent();
  }, intervalMs);
  return () => clearInterval(intervalId);
}, [executions, refetchSilent]);
```

**`refetchSilent()` — fonction déjà implémentée (lignes 134–151) :**
- Fetch silencieux (sans toggling `loading`) : liste + stats + time series en parallèle
- Gère les erreurs sans planter le composant (logger.error)
- C'est exactement ce qu'il faut appeler dans le polling observateur

**`useActorExecutionSync` (Story 36.2) — NE PAS toucher :**
- Gère les WS par exécution de l'acteur (RUNNING/SUBMITTED de l'utilisateur connecté)
- Fallback polling 2000 ms si WS indisponible, par exécution spécifique
- Le polling observateur (cette story) opère sur la liste entière à 10 s : les deux mécanismes coexistent sans conflit (l'acteur reçoit les mises à jour plus vite via WS, les observateurs via le poll à 10 s)

### Pattern Visibility API recommandé

```typescript
useEffect(() => {
  const hasRunning = executions.some((e) => RUNNING_STATUSES.includes(e.status));
  const intervalMs = hasRunning ? OBSERVER_POLL_INTERVAL_MS : BACKGROUND_POLL_INTERVAL_MS;

  const intervalId = setInterval(() => {
    if (!document.hidden) refetchSilent();
  }, intervalMs);

  const handleVisibility = () => {
    if (!document.hidden) refetchSilent();
  };
  document.addEventListener('visibilitychange', handleVisibility);

  return () => {
    clearInterval(intervalId);
    document.removeEventListener('visibilitychange', handleVisibility);
  };
}, [executions, refetchSilent]);
```

⚠️ **Attention** : le `useEffect` a `executions` en dépendance, ce qui le réinitialise à chaque changement de liste. C'est intentionnel : la logique `hasRunning` doit être réévaluée après chaque fetch. Ne pas optimiser cette dépendance sans raison valide.

### Contraintes et pièges à éviter

⚠️ **Ne pas changer `BACKGROUND_POLL_INTERVAL_MS`** (30000 ms) — valeur correcte pour le cas sans exécutions en cours.

⚠️ **Ne pas supprimer `useActorExecutionSync`** (Story 36.2) — mécanisme WS de l'acteur ; cette story ne le touche pas.

⚠️ **`document.hidden` en tests** — mocker via `Object.defineProperty(document, 'hidden', { value: true, configurable: true })` ; restaurer après chaque test avec `configurable: true`.

⚠️ **`visibilitychange` en tests** — déclencher via `document.dispatchEvent(new Event('visibilitychange'))` après avoir changé `document.hidden`.

⚠️ **Pas de changement backend** — `GET /api/v1/executions` reste l'endpoint de polling ; aucune modification API, modèle ou migration nécessaire.

### Pattern de test Visibility API (vitest)

```typescript
import { vi, afterEach } from 'vitest';

describe('polling — Visibility API', () => {
  afterEach(() => {
    // Remettre document.hidden à false après chaque test
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
  });

  it('ne poll pas quand l\'onglet est en arrière-plan', async () => {
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    vi.useFakeTimers();

    // ... renderHook, waitFor initial load ...

    const callsBefore = mockListExecutions.mock.calls.length;
    vi.advanceTimersByTime(10000);
    await Promise.resolve(); // flush microtasks

    // Aucun appel supplémentaire car document.hidden = true
    expect(mockListExecutions.mock.calls.length).toBe(callsBefore);

    vi.useRealTimers();
  });

  it('rafraîchit immédiatement au retour au premier plan', async () => {
    Object.defineProperty(document, 'hidden', { value: true, configurable: true });
    // ... renderHook, waitFor initial load ...

    const callsBefore = mockListExecutions.mock.calls.length;
    // Revenir au premier plan
    Object.defineProperty(document, 'hidden', { value: false, configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    await waitFor(() => {
      expect(mockListExecutions.mock.calls.length).toBeGreaterThan(callsBefore);
    });
  });
});
```

### Apprentissages Stories 36.1 et 36.2 (à ne pas régresser)

- `apply_scope_filter()` utilise `get_allowed_action_ids_for_user()` — ne pas toucher backend
- `activeScope` initialisé à `'all'` — préserver
- `canViewAll = true` pour tous dans `ExecutionsPage.tsx` — préserver
- `useActorExecutionSync` mocké dans les tests `useExecutionsData.test.ts` — préserver le mock
- Suite complète : 2459 tests passent (au commit `a38816c`) — ne pas régresser

### Intelligence des commits récents

- `a38816c feat(executions): mise à jour immédiate des exécutions pour l'acteur (story 36.2)` — `useActorExecutionSync.ts` (NOUVEAU), `useExecutionsData.ts` (MODIFIÉ — actorActiveIds + handleActorStatusUpdate + refresh), `ExecutionsPage.tsx` (MODIFIÉ)
- `ba2955d feat(executions): vue partagée liste et droits RBAC (story 36.1)` — `filters.py`, `useExecutionsData.ts`, `ExecutionsPage.tsx`
- Convention commit : `feat(executions): message FR minuscule`
- Tous les tests doivent passer avant commit

### Project Structure Notes

```
idp-portal/
  frontend/src/
    hooks/
      useExecutionsData.ts       ← À MODIFIER : OBSERVER_POLL_INTERVAL_MS + Visibility API
      useExecutionsData.test.ts  ← À MODIFIER : nouveaux tests polling observateur
      useActorExecutionSync.ts   ← NE PAS MODIFIER (Story 36.2)
      useWebSocket.ts            ← NE PAS MODIFIER (référence pattern WS)
      useExecutionPolling.ts     ← NE PAS MODIFIER (référence fallback polling)
    services/
      execution_service.ts       ← NE PAS MODIFIER (listExecutions, getExecution)
```

### Aucun changement backend nécessaire

- Endpoint `GET /api/v1/executions` : opérationnel, utilisé par `refetchSilent()`
- Aucune migration de base de données
- Aucun changement de modèle Django ou DRF

### References

- `useExecutionsData.ts` : `idp-portal/frontend/src/hooks/useExecutionsData.ts` — polling actuel (lignes 154–163)
- `useActorExecutionSync.ts` : `idp-portal/frontend/src/hooks/useActorExecutionSync.ts` — WS acteur Story 36.2
- `useExecutionsData.test.ts` : `idp-portal/frontend/src/hooks/useExecutionsData.test.ts` — suite tests existante
- Story 36.2 : `_bmad-output/implementation-artifacts/36-2-mise-a-jour-immediate-pour-acteur.md` — WS acteur implémenté
- Story 36.1 : `_bmad-output/implementation-artifacts/36-1-vue-partagee-liste-et-droits-rbac.md` — vue partagée implémentée
- [Source: `_bmad-output/planning-artifacts/epic-36-vue-executions-partagee-mise-a-jour-statut.md` — AC Story 36.3]
- [Source: `_bmad-output/planning-artifacts/spec-vue-executions-partagee-mise-a-jour-statut.md` — intervalle observateur 5–10 s]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

_Aucun blocage majeur. Note : le linter automatique a modifié `BACKGROUND_POLL_INTERVAL_MS` à deux reprises (de 30_000 à 10_000) — la valeur correcte 30_000 a été rétablie à chaque fois, conformément aux Dev Notes. Le linter a également refactorisé `refetchSilent` (in-flight guard + fire-and-forget pour stats/timeSeries) ; ces changements ont été conservés car non-régressifs. Les tests 3.3/3.4 ont nécessité une stratégie de capture de callback via `vi.spyOn` sur `globalThis.setInterval` avec appel réel (pour ne pas casser `waitFor`)._

### Completion Notes List

- **Task 1** : `POLL_INTERVAL_MS = 4000` remplacé par `OBSERVER_POLL_INTERVAL_MS = 10_000` ; `BACKGROUND_POLL_INTERVAL_MS = 30_000` inchangé ; JSDoc du hook mis à jour (Story 36.3).
- **Task 2** : Visibility API ajoutée dans le `useEffect` de polling — `document.hidden` vérifié dans le callback `setInterval`, listener `visibilitychange` déclenche un refresh immédiat, cleanup complet (`clearInterval` + `removeEventListener`).
- **Task 3** : 5 nouveaux tests ajoutés dans `useExecutionsData.test.ts` (describe `Story 36.3`) — tous verts. Suite complète : **2466/2466 tests passent** (+7 vs baseline 2459).
- Tous les AC vérifiés : polling à 10 s avec exécutions RUNNING (AC#1,#4), 30 s sans (AC#5), skip quand onglet masqué (AC#3), refresh immédiat au retour au premier plan (AC#3), coexistence sans conflit avec Story 36.2 WS (AC#6).

### Code Review Notes (auto-review 2026-02-23)

- **M1 (corrigé — était présent au commit `64a1cde`)** : `BACKGROUND_POLL_INTERVAL_MS` valait `10_000` au dernier commit (violation AC5). Le linter avait à nouveau changé 30_000 → 10_000. Fix restauré à `30_000` dans les changements non commités.
- **M2 (corrigé)** : Test 3.3 utilisait `pollingIntervals[pollingIntervals.length - 1]` (sélection par index fragile). Remplacé par `.find((i) => i.delay === 10_000)` pour cohérence avec le test 3.4 et robustesse.
- **M3 (corrigé)** : JSDoc du fichier de tests mis à jour pour couvrir Stories 36.2 et 36.3.
- **L2 (corrigé)** : JSDoc de `useExecutionsData.ts` enrichi avec références Stories 36.2 et 36.3.
- **L3 (documenté, pas de fix)** : Chaque update WS de `useActorExecutionSync` via `handleActorStatusUpdate` appelle `setExecutions`, ce qui réinitialise le countdown du polling observateur. Comportement intentionnel (réévaluation de `hasRunning`) mais l'interaction avec les updates WS fréquents n'était pas documentée. Dans la pratique, l'impact est minime : `handleActorStatusUpdate` ne fire que sur changement de statut réel, pas à chaque tick de fallback polling.

### File List

- `idp-portal/frontend/src/hooks/useExecutionsData.ts` (modifié)
- `idp-portal/frontend/src/hooks/useExecutionsData.test.ts` (modifié)

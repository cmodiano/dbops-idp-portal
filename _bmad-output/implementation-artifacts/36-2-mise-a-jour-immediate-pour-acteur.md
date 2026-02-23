# Story 36.2 : Mise à jour immédiate pour l'acteur

Status: in-progress

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu'utilisateur qui vient de lancer une exécution,
je veux voir le statut de cette exécution se mettre à jour **immédiatement** (soumis → en cours → terminé / échec),
afin de savoir sans attendre si mon action a démarré et quel est son résultat.

## Acceptance Criteria

1. **Given** je viens de lancer une exécution (wizard ou catalogue)
   **When** je reste sur la vue Exécutions (liste ou détail)
   **Then** le statut de mon exécution se met à jour sans rechargement de page
   **And** le délai perçu est immédiat (< 2–3 s après réception du callback backend, via WebSocket ou poll dédié)

2. **Given** mon exécution est « en cours » (RUNNING ou SUBMITTED)
   **When** le backend reçoit un changement de statut (étape, terminé, échec)
   **Then** l'UI reflète ce changement dès réception du message WebSocket `/ws/executions/{id}` ou au prochain poll dédié
   **And** si la vue détail (Epic 19, `ExecutionDetailDrawer`) est ouverte pour cette exécution, elle se met aussi à jour

3. **Given** je n'ai pas lancé l'exécution affichée
   **When** je consulte la liste
   **Then** la mise à jour de cette exécution peut suivre le mécanisme « observateur » (Story 36.3), pas nécessairement temps réel

4. **Given** mon exécution vient d'être soumise via le wizard
   **When** la liste des exécutions s'affiche
   **Then** ma nouvelle exécution apparaît immédiatement dans la liste sans attendre le prochain cycle de polling
   **And** la souscription WebSocket pour cette exécution démarre immédiatement

5. **Given** le WebSocket `/ws/executions/{id}` est indisponible ou tombe en erreur
   **When** mon exécution est en cours
   **Then** un fallback par polling court (2000 ms) s'active pour cette exécution spécifique
   **And** le polling s'arrête dès que l'exécution atteint un statut terminal (COMPLETED, FAILED, CANCELLED, REJECTED)

## Tasks / Subtasks

- [ ] **Task 1 — Nouveau hook `useActorExecutionSync.ts`** (AC: #1, #2, #5)
  - [ ] 1.1 Créer `idp-portal/frontend/src/hooks/useActorExecutionSync.ts`
  - [ ] 1.2 Signature : `useActorExecutionSync(executionIds: number[], onStatusUpdate: (id: number, status: string, data?: Partial<ExecutionResponse>) => void): void`
  - [ ] 1.3 Pour chaque `executionId`, ouvrir une connexion WebSocket vers `/ws/executions/${executionId}` en réutilisant le pattern auth de `useWebSocket.ts` : `ws.onopen → ws.send({type:'auth', token})` ; ne pas mettre le token en URL
  - [ ] 1.4 Sur `execution_complete` → appeler `onStatusUpdate(id, data.status ?? 'COMPLETED', data)` puis fermer la WS (statut terminal)
  - [ ] 1.5 Sur `execution_failed` → appeler `onStatusUpdate(id, 'FAILED', {status:'FAILED', error_message: data.error_message})` puis fermer la WS
  - [ ] 1.6 Sur erreur WS (code ≠ 4001) → activer fallback polling 2000 ms sur `GET /api/v1/executions/${id}` ; arrêt sur statut terminal ; ne pas relancer après code 4001 (auth failure)
  - [ ] 1.7 Synchroniser `wsRefs` (Map<number, WebSocket>) quand `executionIds` change : créer WS pour les nouveaux IDs, fermer et supprimer pour les IDs disparus
  - [ ] 1.8 Cleanup `useEffect` retour : fermer toutes les WS ouvertes et annuler tous les intervalles polling actifs

- [ ] **Task 2 — Intégrer dans `useExecutionsData.ts`** (AC: #1, #2, #3, #4)
  - [ ] 2.1 Importer `useAuth` (déjà disponible) pour obtenir `user.id` (type `number | undefined`)
  - [ ] 2.2 Calculer `actorActiveIds` via `useMemo` : filtrer `executions` par `e.user_id === user?.id && ['RUNNING','SUBMITTED'].includes(e.status)`, extraire `.map(e => e.id)`
  - [ ] 2.3 Implémenter `handleActorStatusUpdate` via `useCallback` : `setExecutions(prev => prev.map(e => e.id === id ? {...e, status, ...(data ?? {})} : e))`
  - [ ] 2.4 Appeler `useActorExecutionSync(actorActiveIds, handleActorStatusUpdate)` dans le hook
  - [ ] 2.5 Exposer une fonction `refresh()` publique qui relance `fetchExecutions()` (pour le trigger post-wizard)
  - [ ] 2.6 ⚠️ Ne pas supprimer le fast polling existant (4000 ms sur `hasActiveExecutions`) — il reste actif pour les cas sans WS et servira aux observateurs (Story 36.3)

- [ ] **Task 3 — Trigger refresh post-wizard dans `ExecutionsPage.tsx`** (AC: #4)
  - [ ] 3.1 Dans le callback `onSuccess` du wizard (déjà existant), appeler `refresh()` exposé par `useExecutionsData`
  - [ ] 3.2 Vérifier que `ExecutionWizard.onSuccess` reçoit bien l'objet `ExecutionCreateResponse` contenant `execution_id`
  - [ ] 3.3 Si `execution_id` est disponible à la fermeture du wizard, l'injecter dans le state local pour que `actorActiveIds` le détecte immédiatement (avant même le prochain poll)

- [ ] **Task 4 — Tests `useActorExecutionSync.test.ts`** (AC: #1, #2, #5)
  - [ ] 4.1 Créer `idp-portal/frontend/src/hooks/useActorExecutionSync.test.ts`
  - [ ] 4.2 Test : connexion WS créée pour chaque `executionId` fourni (mock `WebSocket` global)
  - [ ] 4.3 Test : `execution_complete` → `onStatusUpdate(id, 'COMPLETED', ...)` appelé + WS fermée
  - [ ] 4.4 Test : `execution_failed` → `onStatusUpdate(id, 'FAILED', {...})` appelé + WS fermée
  - [ ] 4.5 Test : WS erreur (code ≠ 4001) → fallback polling 2000 ms activé via `setInterval` mock
  - [ ] 4.6 Test : WS erreur code 4001 → aucun reconnect, aucun polling
  - [ ] 4.7 Test : quand un ID quitte `executionIds`, sa WS est fermée
  - [ ] 4.8 Test : unmount → toutes les WS fermées, tous les intervalles annulés

- [ ] **Task 5 — Tests `useExecutionsData.test.ts`** (AC: #1, #3, #4)
  - [ ] 5.1 Test : `actorActiveIds` contient uniquement les exécutions de l'utilisateur courant en RUNNING/SUBMITTED (pas celles d'autres users)
  - [ ] 5.2 Test : `handleActorStatusUpdate(1, 'COMPLETED')` → l'exécution #1 dans la liste passe à COMPLETED
  - [ ] 5.3 Test : `refresh()` relance `listExecutions` (mock api vérifié appelé une seconde fois)

- [ ] **Task 6 — Tests `ExecutionsPage.test.tsx`** (AC: #4)
  - [ ] 6.1 Test : après fermeture réussie du wizard (`onSuccess` callback), `refresh()` de `useExecutionsData` est appelé

## Dev Notes

### Infrastructure existante à réutiliser (NE PAS réinventer)

**WebSocket backend — aucun changement nécessaire :**
- `ExecutionConsumer` — `idp-portal/django_backend/executions/consumers.py`
  - Route : `/ws/executions/(?P<execution_id>[0-9]+)$`
  - Channel group : `execution_{execution_id}` (join dans `connect()` avant auth pour éviter race condition)
  - Messages diffusés : `step_update`, `execution_complete`, `execution_failed`, `log_update`, `status_update`
  - Hérite de `AuthenticatedWebSocketConsumer` : accept immédiat → attente `{type:"auth", token}` → vérification JWT
  - Code 4001 = auth failure (ne pas reconnecter)

**Pattern auth WS (copier de `useWebSocket.ts`) :**
```typescript
// NE PAS mettre le token en URL (Story 22.13)
const ws = new WebSocket(buildWsUrl(`/ws/executions/${id}`));
ws.onopen = () => ws.send(JSON.stringify({ type: 'auth', token: getToken() }));
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'execution_complete') { /* ... */ }
  if (data.type === 'execution_failed')   { /* ... */ }
};
ws.onerror = () => startFallbackPolling(id);
// Ne pas reconnecter si ws.close.code === 4001
```

**Polling fallback — copier de `useExecutionPolling.ts` :**
```typescript
// idp-portal/frontend/src/hooks/useExecutionPolling.ts
// TERMINAL_STATUSES = ['COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED']
// interval = 2500ms (adapter à 2000ms pour l'acteur)
// Arrêt automatique sur statut terminal + isMountedRef pour éviter memory leaks
```

**useWebSocket.ts pour référence complète :**
- `idp-portal/frontend/src/hooks/useWebSocket.ts`
- Gère reconnect 2000ms, state `isAuthenticated`, incremental step updates
- ⚠️ Ce hook est conçu pour la VUE DÉTAIL (retourne `steps`, `execution`, `loading`). Ne pas l'utiliser directement pour la liste — créer `useActorExecutionSync` qui ne gère que le statut global.

**useExecutionsData.ts — état actuel (Story 36.1) :**
- `idp-portal/frontend/src/hooks/useExecutionsData.ts`
- Fast polling 4000 ms si `hasActiveExecutions` (RUNNING/SUBMITTED/PENDING_APPROVAL)
- Slow polling 30000 ms sinon
- `activeScope` initialisé à `'all'` (changement Story 36.1)
- ⚠️ `user_id` est disponible dans `ExecutionResponse` (champ `user_id: number`) depuis Story 36.1 (colonne « Utilisateur »)
- ⚠️ `useAuth()` déjà importé (ou accessible) dans le fichier — vérifier l'import exact

### Pattern complet `useActorExecutionSync`

```typescript
import { useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/hooks/useAuth'; // adapter selon import réel
import { getExecution } from '@/services/execution_service';
import { ExecutionResponse } from '@/types/api/executions';

const TERMINAL_STATUSES = ['COMPLETED', 'FAILED', 'CANCELLED', 'REJECTED'];
const FALLBACK_POLL_INTERVAL_MS = 2000;

function buildWsUrl(path: string): string {
  // Même logique que useWebSocket.ts
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${window.location.host}${path}`;
}

export function useActorExecutionSync(
  executionIds: number[],
  onStatusUpdate: (id: number, status: string, data?: Partial<ExecutionResponse>) => void
): void {
  const { getToken } = useAuth();
  const wsMap = useRef<Map<number, WebSocket>>(new Map());
  const pollMap = useRef<Map<number, ReturnType<typeof setInterval>>>(new Map());
  const isMountedRef = useRef(true);

  const startFallbackPolling = useCallback((id: number) => {
    if (pollMap.current.has(id)) return;
    const interval = setInterval(async () => {
      if (!isMountedRef.current) return;
      try {
        const execution = await getExecution(id);
        if (!isMountedRef.current) return;
        onStatusUpdate(id, execution.status, execution);
        if (TERMINAL_STATUSES.includes(execution.status)) {
          clearInterval(interval);
          pollMap.current.delete(id);
        }
      } catch { /* silencieux */ }
    }, FALLBACK_POLL_INTERVAL_MS);
    pollMap.current.set(id, interval);
  }, [onStatusUpdate]);

  const openWs = useCallback((id: number) => {
    const ws = new WebSocket(buildWsUrl(`/ws/executions/${id}`));
    wsMap.current.set(id, ws);

    ws.onopen = () => {
      const token = getToken();
      if (token) ws.send(JSON.stringify({ type: 'auth', token }));
    };

    ws.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(event.data as string);
        if (data.type === 'execution_complete') {
          onStatusUpdate(id, data.status ?? 'COMPLETED', data);
          ws.close();
          wsMap.current.delete(id);
        } else if (data.type === 'execution_failed') {
          onStatusUpdate(id, 'FAILED', { status: 'FAILED', error_message: data.error_message });
          ws.close();
          wsMap.current.delete(id);
        }
      } catch { /* JSON invalide ignoré */ }
    };

    ws.onclose = (event) => {
      wsMap.current.delete(id);
      // 4001 = auth failure → ne pas reconnecter ni poller
      if (event.code === 4001) return;
      // Autre erreur → fallback polling
      if (isMountedRef.current) startFallbackPolling(id);
    };

    ws.onerror = () => {
      ws.close(); // onclose gérera le fallback
    };
  }, [getToken, onStatusUpdate, startFallbackPolling]);

  useEffect(() => {
    // Ouvrir WS pour les nouveaux IDs
    executionIds.forEach(id => {
      if (!wsMap.current.has(id) && !pollMap.current.has(id)) {
        openWs(id);
      }
    });

    // Fermer WS/polling pour les IDs qui ont quitté la liste
    wsMap.current.forEach((ws, id) => {
      if (!executionIds.includes(id)) {
        ws.close();
        wsMap.current.delete(id);
      }
    });
    pollMap.current.forEach((interval, id) => {
      if (!executionIds.includes(id)) {
        clearInterval(interval);
        pollMap.current.delete(id);
      }
    });
  }, [executionIds, openWs]);

  // Cleanup total au démontage
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      wsMap.current.forEach(ws => ws.close());
      wsMap.current.clear();
      pollMap.current.forEach(interval => clearInterval(interval));
      pollMap.current.clear();
    };
  }, []);
}
```

### Intégration dans `useExecutionsData.ts`

```typescript
// Après les imports existants
import { useActorExecutionSync } from './useActorExecutionSync';

// Dans le hook, après la définition de executions / setExecutions :
const { user } = useAuth();

const actorActiveIds = useMemo(
  () =>
    executions
      .filter(e => e.user_id === user?.id && ['RUNNING', 'SUBMITTED'].includes(e.status))
      .map(e => e.id),
  [executions, user?.id]
);

const handleActorStatusUpdate = useCallback(
  (id: number, status: string, data?: Partial<ExecutionResponse>) => {
    setExecutions(prev =>
      prev.map(e => e.id === id ? { ...e, status, ...(data ?? {}) } : e)
    );
  },
  []
);

useActorExecutionSync(actorActiveIds, handleActorStatusUpdate);

// Exposer refresh() pour le trigger post-wizard
const refresh = useCallback(() => {
  fetchExecutions(); // fonction déjà définie dans le hook
}, [fetchExecutions]);

return { executions, ..., refresh }; // ajouter refresh au return
```

### Trigger post-wizard dans `ExecutionsPage.tsx`

```typescript
// Déstructurer refresh depuis useExecutionsData
const { executions, refresh, ... } = useExecutionsData(filters, canApprove);

// Dans le handler onSuccess du wizard (déjà existant) :
const handleWizardSuccess = useCallback(() => {
  setWizardVisible(false);
  refresh(); // rafraîchissement immédiat
}, [refresh]);
```

### Contraintes et pièges à éviter

⚠️ **Ne pas mettre le token JWT dans l'URL WebSocket** — Story 22.13. Toujours en 1er message `{type:'auth', token}`.

⚠️ **`executionIds` comme dépendance `useEffect`** — utiliser une comparaison stable (`JSON.stringify` ou `useMemo`) pour éviter des re-créations de WS à chaque render. Voir le pattern dans `useWebSocket.ts`.

⚠️ **`user_id` dans `ExecutionResponse`** — vérifier le type exact dans `idp-portal/frontend/src/types/api/executions.ts`. Peut être `user_id: number` ou `user_id: string` selon le serializer Django. Adapter la comparaison en conséquence.

⚠️ **`getExecution` dans le fallback polling** — `idp-portal/frontend/src/services/execution_service.ts`, fonction `getExecution(id: number): Promise<ExecutionResponse>`. Déjà disponible.

⚠️ **`useAuth` chemin d'import** — vérifier le chemin exact utilisé dans `ExecutionsPage.tsx` et `useExecutionsData.ts` pour cohérence (ex: `@/hooks/useAuth`, `@/context/AuthContext`, etc.).

⚠️ **Ne pas supprimer le polling existant (4000ms/30000ms)** — il reste nécessaire pour les observateurs (Story 36.3) et comme filet de sécurité global.

### Aucun changement backend nécessaire

- `/ws/executions/{id}` → `ExecutionConsumer` : opérationnel
- Broadcasts `execution_complete`, `execution_failed` : déjà implémentés par le moteur d'exécution
- `GET /api/v1/executions/{id}` : disponible pour le fallback polling
- Auth WS : `AuthenticatedWebSocketConsumer` déjà en production

### Apprentissages Story 36.1 (à ne pas régresser)

- `apply_scope_filter()` utilise `get_allowed_action_ids_for_user()` — ne pas toucher
- `activeScope` initialisé à `'all'` dans `useExecutionsData.ts` — préserver
- `canViewAll = true` pour tous dans `ExecutionsPage.tsx` — préserver
- 51 backend + 78 frontend tests passent — ne pas les casser

### Intelligence des commits récents

- `ba2955d feat(executions): vue partagée liste et droits RBAC (story 36.1)` — fichiers modifiés : `filters.py`, `test_utils.py`, `ExecutionsPage.tsx`, `ExecutionsTabs.tsx`, `ExecutionsTabs.test.tsx`, `ExecutionsPage.test.tsx`, `useExecutionsData.ts`
- Convention commit : `feat(scope): message FR minuscule`
- Tous les tests doivent passer avant commit

### Project Structure Notes

```
idp-portal/
  frontend/src/
    hooks/
      useWebSocket.ts              ← Référence : pattern WS auth + reconnect (NE PAS modifier)
      useExecutionPolling.ts       ← Référence : pattern fallback polling (NE PAS modifier)
      useExecutionsData.ts         ← À MODIFIER : +useActorExecutionSync + refresh()
      useActorExecutionSync.ts     ← NOUVEAU : hook WS statut acteur
    pages/
      ExecutionsPage.tsx           ← À MODIFIER : trigger refresh post-wizard
    services/
      execution_service.ts         ← Référence : getExecution() (NE PAS modifier)
    types/api/
      executions.ts                ← Vérifier type user_id dans ExecutionResponse
```

### References

- `useWebSocket.ts` : `idp-portal/frontend/src/hooks/useWebSocket.ts` — pattern WS auth + messages
- `useExecutionPolling.ts` : `idp-portal/frontend/src/hooks/useExecutionPolling.ts` — pattern fallback polling
- `useExecutionsData.ts` : `idp-portal/frontend/src/hooks/useExecutionsData.ts` — liste + polling actuel
- `execution_service.ts` : `idp-portal/frontend/src/services/execution_service.ts` — `getExecution(id)`
- `ExecutionConsumer` : `idp-portal/django_backend/executions/consumers.py` — WS backend
- `AuthenticatedWebSocketConsumer` : `idp-portal/django_backend/core/consumers.py` — base WS
- Routing WS : `idp-portal/django_backend/idp_backend/routing.py`
- Story 36.1 : `_bmad-output/implementation-artifacts/36-1-vue-partagee-liste-et-droits-rbac.md`
- [Source: `_bmad-output/planning-artifacts/epic-36-vue-executions-partagee-mise-a-jour-statut.md` — AC Story 36.2]
- [Source: `_bmad-output/planning-artifacts/spec-vue-executions-partagee-mise-a-jour-statut.md` — Spec acteur < 2–3 s]
- [Source: `idp-portal/frontend/src/hooks/useWebSocket.ts` — pattern auth WS message-based]
- [Source: `idp-portal/django_backend/executions/consumers.py` — broadcasts ExecutionConsumer]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List

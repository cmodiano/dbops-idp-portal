# Story 37.3 : Frontend — Passer engine_type aux appels inventaire

Status: done

## Story

En tant qu'utilisateur lançant une action (ex. Oracle),
je veux que les listes inventaire (serveurs, instances, bases) ne proposent que des éléments de la technologie de l'action,
afin de ne pas choisir par erreur un serveur ou une base d'une autre technologie.

## Acceptance Criteria

1. **Given** la fonction `fetchInventoryItems(type, environment?, options?)`
   **When** `options.engine_type` est fourni (ex. `'Oracle'`)
   **Then** le paramètre `engine_type` est ajouté à la query string de l'URL pour les types `servers`, `instances` et `databases`
   **And** la clé de cache (mémoire `apiKey` et sessionStorage `cacheKey`) prend en compte `engine_type` pour éviter des hits incorrects

2. **Given** le wizard d'exécution charge des listes inventaire pour une action avec `engine` défini
   **When** `useTargetInventory` reçoit le `engineType` de l'action (ex. `'Oracle'`, `'SQL Server'`)
   **Then** les appels `fetchInventoryItems` pour `servers`, `instances` et `databases` passent `engine_type` dans les options
   **And** les listes affichées sont filtrées côté backend par cette technologie

3. **Given** l'action n'a pas d'engine (null ou vide) ou est un workflow conteneur
   **Then** `engine_type` n'est pas envoyé (comportement actuel : toutes technologies)
   **And** pas de régression pour les actions sans moteur

4. **Given** `engine_type` change (ex. ouverture d'un wizard pour une action différente)
   **Then** le cache inventaire est invalidé de la même façon que pour un changement d'`environment`
   **And** les données rechargées correspondent à la nouvelle technologie

## Tasks / Subtasks

- [x] Task 1 : `execution_service.ts` — Étendre `options` et la construction de l'URL (AC: #1, #3)
  - [x] 1.1 Étendre le type de `options` : `{ server_names?: string[]; engine_type?: string }` dans la signature de `fetchInventoryItems`
  - [x] 1.2 Dans la construction de `queryParams`, ajouter : `if (options?.engine_type) queryParams.set('engine_type', options.engine_type);` — ne pas conditionner sur le `type` (le backend gère le cas `environments` avec zéro filtre)
  - [x] 1.3 Ajouter le suffixe `engine_type` à la clé `cacheKey` : `const engineTypeSuffix = options?.engine_type ? `_et_${options.engine_type}` : '';` et l'insérer après `serverNamesSuffix`
  - [x] 1.4 Vérifier que `apiKey` (clé mémoire) est déjà construit à partir de `params` (qui inclut maintenant `engine_type`) — donc aucune modification supplémentaire nécessaire

- [x] Task 2 : `useTargetInventory.ts` — Recevoir `engineType` et l'inclure dans les options (AC: #2, #3, #4)
  - [x] 2.1 Ajouter `engineType?: string | null` à l'interface `UseTargetInventoryOptions` avec un commentaire Story 37.3
  - [x] 2.2 Ajouter `engineType = null` au destructuring du hook
  - [x] 2.3 Ajouter un ref `lastEngineTypeRef` pour tracker le changement (analogue à `lastServerNamesRef`)
  - [x] 2.4 Dans le `useEffect` de chargement inventaire : détecter `engineTypeChanged = lastEngineTypeRef.current !== engineType` et mettre à jour le ref
  - [x] 2.5 Dans la logique `needsRefetch` : ajouter `|| engineTypeChanged` pour tous les types (`servers`, `instances`, `databases`)
  - [x] 2.6 Dans l'appel `fetchInventoryItems`, passer `engine_type: engineType || undefined` dans les options pour tous les types (servers, instances, databases) — fusionner avec l'objet `options` existant pour les instances/databases
  - [x] 2.7 Ajouter `engineType` aux dépendances du `useEffect` (après `selectedServerNames`)
  - [x] 2.8 En mode DEV, logger le changement d'engine_type pour debugging (cohérence avec le log server_names)

- [x] Task 3 : `useExecutionWizardState.ts` — Passer `action.engine` à `useTargetInventory` (AC: #2, #3)
  - [x] 3.1 Dans l'appel `useTargetInventory({...})`, ajouter `engineType: action?.engine ?? null`

- [x] Task 4 : Tests (AC: #1–#4)
  - [x] 4.1 `execution_service.test.ts` — `test_fetch_inventory_items_engine_type_in_url` : vérifier que `engine_type` apparaît dans la query string générée
  - [x] 4.2 `execution_service.test.ts` — `test_fetch_inventory_items_cache_key_includes_engine_type` : vérifier que `cacheKey` diffère quand `engine_type` change
  - [x] 4.3 `execution_service.test.ts` — `test_fetch_inventory_items_no_engine_type_no_param` : vérifier que sans `engine_type` l'URL est inchangée (régression AC3)
  - [x] 4.4 `useTargetInventory.test.ts` — `test_engine_type_passed_to_fetch_servers` : vérifier que `fetchInventoryItems` est appelé avec `engine_type` pour `servers`
  - [x] 4.5 `useTargetInventory.test.ts` — `test_engine_type_passed_to_fetch_instances` : vérifier que `fetchInventoryItems` est appelé avec `engine_type` pour `instances`
  - [x] 4.6 `useTargetInventory.test.ts` — `test_engine_type_change_invalidates_cache` : simuler un changement d'engineType → vérifier rechargement
  - [x] 4.7 `useTargetInventory.test.ts` — `test_no_engine_type_no_filter` : action sans engine → `fetchInventoryItems` appelé sans `engine_type` (AC3)

## Dev Notes

### Contexte et dépendances

Story 37.3 s'appuie sur Story 37.2 (done) :
- Les APIs `/inventory/instances/` et `/inventory/databases/` acceptent désormais le paramètre `engine_type`
- L'API `/inventory/servers/` acceptait déjà `engine_type` avant la story 37.2
- C'est une extension purement frontend — aucune modification backend requise

### Analyse du code actuel

#### `fetchInventoryItems` — signature actuelle (execution_service.ts lignes 385–507)

```typescript
export async function fetchInventoryItems(
  type: 'databases' | 'servers' | 'instances' | 'environments',
  environment?: string,
  /** Story 23.6 - Optional server names to filter instances/databases. */
  options?: { server_names?: string[] }
): Promise<InventoryItem[]>
```

**Construction URL actuelle (lignes 391–404) :**
```typescript
const queryParams = new URLSearchParams();
if (environment) queryParams.set('environment', environment);
if (options?.server_names && options.server_names.length > 0) {
  queryParams.set('server_names', options.server_names.join(','));
}
const params = queryParams.toString() ? `?${queryParams.toString()}` : '';
const serverNamesSuffix = options?.server_names && options.server_names.length > 0
  ? `_${options.server_names.join(',')}`
  : '';
const cacheKey = `inventory_cache_${type}${environment ? `_${environment}` : ''}${serverNamesSuffix}`;
const apiKey = `${type}${params}`;
```

**Transformation Story 37.3 :**
```typescript
// Type étendu
options?: { server_names?: string[]; engine_type?: string }

// Construction URL
const queryParams = new URLSearchParams();
if (environment) queryParams.set('environment', environment);
if (options?.server_names && options.server_names.length > 0) {
  queryParams.set('server_names', options.server_names.join(','));
}
// Story 37.3 - Pass engine_type for servers/instances/databases
if (options?.engine_type) queryParams.set('engine_type', options.engine_type);
const params = queryParams.toString() ? `?${queryParams.toString()}` : '';

// Cache key (Story 37.3 - include engine_type)
const serverNamesSuffix = options?.server_names && options.server_names.length > 0
  ? `_${options.server_names.join(',')}`
  : '';
const engineTypeSuffix = options?.engine_type ? `_et_${options.engine_type}` : '';
const cacheKey = `inventory_cache_${type}${environment ? `_${environment}` : ''}${serverNamesSuffix}${engineTypeSuffix}`;
const apiKey = `${type}${params}`; // Inchangé — params inclut déjà engine_type
```

#### `useTargetInventory` — hook actuel (useTargetInventory.ts lignes 1–163)

**Options actuelles (lignes 16–24) :**
```typescript
export interface UseTargetInventoryOptions {
  open: boolean;
  actionId?: number;
  currentStep: number;
  parameterFields: Array<{ inventorySource?: 'databases' | 'servers' | 'instances' }>;
  environment: string | null;
  /** Names of servers selected at step 1, used to filter instances/databases (Story 23.6). */
  selectedServerNames?: string[];
}
```

**Appel fetchInventoryItems actuel (lignes 125–133) :**
```typescript
const validServerNames = selectedServerNames.filter(name => typeof name === 'string' && name.trim().length > 0);
const options = (source === 'instances' || source === 'databases')
  ? { server_names: validServerNames }
  : undefined;
const items = await fetchInventoryItems(source, environment, options);
```

**Transformation Story 37.3 :**
```typescript
export interface UseTargetInventoryOptions {
  open: boolean;
  actionId?: number;
  currentStep: number;
  parameterFields: Array<{ inventorySource?: 'databases' | 'servers' | 'instances' }>;
  environment: string | null;
  /** Names of servers selected at step 1, used to filter instances/databases (Story 23.6). */
  selectedServerNames?: string[];
  /** Story 37.3 - Engine type of the action to filter inventory by technology. */
  engineType?: string | null;
}

// Dans le hook :
export function useTargetInventory({
  open,
  currentStep,
  parameterFields,
  environment,
  selectedServerNames = [],
  engineType = null,         // Story 37.3
}: UseTargetInventoryOptions): UseTargetInventoryReturn {
  // ...
  // Story 37.3 - Track previous engineType for cache invalidation
  const lastEngineTypeRef = useRef<string | null>(null);

  // Dans useEffect :
  const engineTypeChanged = lastEngineTypeRef.current !== engineType;
  if (engineTypeChanged) {
    lastEngineTypeRef.current = engineType;
    if (import.meta.env.DEV) {
      logger.debug('[useTargetInventory] Cache invalidation: engine_type changed', {
        previous: lastEngineTypeRef.current,
        current: engineType,
        environment,
      });
    }
  }

  // needsRefetch : ajouter engineTypeChanged pour tous les types
  const needsRefetch = envChanged || serverNamesChanged || engineTypeChanged;
  // (car engine_type affecte servers aussi, pas seulement instances/databases)

  // Appel fetchInventoryItems — passer engine_type pour tous les types inventaire
  const engineTypeOption = engineType ? { engine_type: engineType } : {};
  const validServerNames = selectedServerNames.filter(
    name => typeof name === 'string' && name.trim().length > 0
  );
  const options = (source === 'instances' || source === 'databases')
    ? { server_names: validServerNames, ...engineTypeOption }
    : { ...engineTypeOption };  // Pour servers : pas de server_names
  // Note: passer undefined si options est vide évite un objet vide dans l'appel
  const finalOptions = Object.keys(options).length > 0 ? options : undefined;
  const items = await fetchInventoryItems(source, environment, finalOptions);

  // Dépendances useEffect : ajouter engineType
  }, [open, currentStep, parameterFields, environment, selectedServerNames, engineType]);
```

#### `useExecutionWizardState` — lignes 220–228

**Appel actuel :**
```typescript
const { environmentsCache, inventoryData, inventoryWarnings, loadingInventory } = useTargetInventory({
  open,
  actionId: action?.id,
  currentStep,
  parameterFields,
  environment: envForInventory,
  selectedServerNames,
});
```

**Ajout Story 37.3 :**
```typescript
const { environmentsCache, inventoryData, inventoryWarnings, loadingInventory } = useTargetInventory({
  open,
  actionId: action?.id,
  currentStep,
  parameterFields,
  environment: envForInventory,
  selectedServerNames,
  engineType: action?.engine ?? null,  // Story 37.3 - Filter inventory by action's engine
});
```

### Normalisation des codes engine

**Valeur envoyée :** `action.engine` est de type `ActionEngine = 'Oracle' | 'SQL Server' | 'DB2' | string` (catalog.ts ligne 14).

**Aucune transformation requise :** Le backend effectue une comparaison `UPPER(srv.ENGINE_COL) = UPPER(:p_engine_type)` (story 37.2, query_executor.py). Les valeurs `'Oracle'`, `'SQL Server'`, `'DB2'` sont transmises telles quelles.

**Cas null/undefined :** Si `action.engine` est `null`, `engineType` sera `null`, et `engine_type` ne sera pas ajouté à la query string (AC3 respecté).

### Cas particulier : type `environments`

La fonction `fetchInventoryItems` pour `environments` suit un chemin spécial (lignes 407–422 de execution_service.ts) qui délègue à `fetchEnvironments()` sans appel API direct. Ce type n'est **pas** concerné par `engine_type` et le hook `useTargetInventory` ne fait jamais `fetchInventoryItems('environments', ...)` — ce chargement se fait dans un `useEffect` séparé (lignes 52–68). Aucune modification requise pour ce cas.

### Structure des tests

**Fichiers de test :**
- `frontend/src/services/execution_service.test.ts` — tâches 4.1–4.3
- `frontend/src/hooks/useTargetInventory.test.ts` — tâches 4.4–4.7

**Pattern de test pour execution_service.test.ts :**
```typescript
describe('fetchInventoryItems - engine_type', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear module-level cache
    vi.resetModules();
  });

  it('adds engine_type to query string when provided', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ data: [] });
    vi.mocked(apiFetchRaw).mockImplementation(mockFetch);

    await fetchInventoryItems('instances', 'dev', { engine_type: 'Oracle' });

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('engine_type=Oracle')
    );
  });

  it('cache key differs when engine_type changes', async () => {
    // Two calls with same type/env but different engine_type
    // Should NOT share cache
    const mockFetch = vi.fn().mockResolvedValue({ data: [{ id: '1', name: 'test', environment: null }] });
    vi.mocked(apiFetchRaw).mockImplementation(mockFetch);

    await fetchInventoryItems('servers', 'dev', { engine_type: 'Oracle' });
    await fetchInventoryItems('servers', 'dev', { engine_type: 'SQL Server' });

    // Both should have triggered a fetch (no cache sharing)
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('no engine_type in URL when not provided', async () => {
    const mockFetch = vi.fn().mockResolvedValue({ data: [] });
    vi.mocked(apiFetchRaw).mockImplementation(mockFetch);

    await fetchInventoryItems('servers', 'dev');

    const calledUrl = mockFetch.mock.calls[0][0] as string;
    expect(calledUrl).not.toContain('engine_type');
  });
});
```

**Pattern de test pour useTargetInventory.test.ts :**
```typescript
it('passes engine_type to fetchInventoryItems for servers', async () => {
  const mockFetch = vi.fn().mockResolvedValue([]);
  vi.mocked(fetchInventoryItems).mockImplementation(mockFetch);

  renderHook(() => useTargetInventory({
    open: true,
    currentStep: 1,
    parameterFields: [{ inventorySource: 'servers' }],
    environment: 'dev',
    selectedServerNames: [],
    engineType: 'Oracle',
  }));

  await waitFor(() => {
    expect(mockFetch).toHaveBeenCalledWith(
      'servers',
      'dev',
      expect.objectContaining({ engine_type: 'Oracle' })
    );
  });
});

it('does not send engine_type when engineType is null', async () => {
  const mockFetch = vi.fn().mockResolvedValue([]);
  vi.mocked(fetchInventoryItems).mockImplementation(mockFetch);

  renderHook(() => useTargetInventory({
    open: true,
    currentStep: 1,
    parameterFields: [{ inventorySource: 'servers' }],
    environment: 'dev',
    selectedServerNames: [],
    engineType: null,
  }));

  await waitFor(() => {
    const opts = mockFetch.mock.calls[0]?.[2];
    expect(opts?.engine_type).toBeUndefined();
  });
});
```

### Project Structure Notes

**Fichiers à modifier :**
- `frontend/src/services/execution_service.ts` (tâches 1.1–1.4) — signature + URL + cache key
- `frontend/src/hooks/useTargetInventory.ts` (tâches 2.1–2.8) — options + ref + effect + appel
- `frontend/src/hooks/useExecutionWizardState.ts` (tâche 3.1) — passer `action.engine`

**Fichiers de test :**
- `frontend/src/services/execution_service.test.ts` (tâches 4.1–4.3)
- `frontend/src/hooks/useTargetInventory.test.ts` (tâches 4.4–4.7)

**Aucune modification requise :**
- `frontend/src/types/api/catalog.ts` — `ActionEngine` déjà défini
- `frontend/src/services/reference_service.ts` — `fetchEngines()` non concerné
- `frontend/src/components/catalog/ExecutionWizard.tsx` — pas d'imports directs (délègue via useExecutionWizardState)
- `frontend/src/contexts/WizardExecutionContext.tsx` — `engine_type` n'a pas à être exposé dans le contexte (c'est un détail de fetch)

### Compatibilité ascendante

- Les appels existants sans `engine_type` continuent à fonctionner exactement comme avant (AC3)
- `engineType` dans `UseTargetInventoryOptions` est optionnel avec défaut `null`
- `engine_type` dans les options de `fetchInventoryItems` est optionnel
- Les tests existants ne passent pas `engineType` → comportement inchangé

### References

- `frontend/src/services/execution_service.ts` lignes 385–507 (`fetchInventoryItems`)
- `frontend/src/hooks/useTargetInventory.ts` lignes 1–163 (hook complet)
- `frontend/src/hooks/useExecutionWizardState.ts` lignes 220–228 (appel useTargetInventory)
- `frontend/src/types/api/catalog.ts` ligne 14 (`ActionEngine`)
- `_bmad-output/implementation-artifacts/37-2-filtre-engine-type-instances-databases-backend.md` — story précédente (backend)
- `_bmad-output/planning-artifacts/epic-37-inventaire-environnement-serveur-colonne-engine.md` — Story 37.3 AC complets

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

(aucun)

### Completion Notes List

- **Task 1** : `execution_service.ts` — Type options étendu avec `engine_type?: string`. Ajout `queryParams.set('engine_type', ...)` dans la construction URL. Ajout `engineTypeSuffix` dans `cacheKey`. `apiKey` inchangé (inclut déjà `engine_type` via `params`).
- **Task 2** : `useTargetInventory.ts` — Interface étendue avec `engineType?: string | null`. Destructuring avec défaut `null`. Ref `lastEngineTypeRef` pour invalidation cache. Détection `engineTypeChanged` dans `useEffect`. `needsRefetch` simplifié : `envChanged || serverNamesChanged || engineTypeChanged` pour tous les types. Appel `fetchInventoryItems` passe `engine_type` pour tous les types inventaire. `engineType` ajouté aux deps du `useEffect`. Log DEV cohérent avec pattern `server_names`.
- **Task 3** : `useExecutionWizardState.ts` — Ajout `engineType: action?.engine ?? null` dans l'appel `useTargetInventory`.
- **Task 4** : 7 tests Story 37.3 ajoutés (3 dans `execution_service.test.ts`, 4 dans `useTargetInventory.test.ts`). 2 tests existants mis à jour (`ExecutionWizard.test.tsx` x5 occurrences, `ExecutionWizard.story23_6.test.tsx` x1) pour accepter `engine_type` dans les options — comportement correct car les actions mock ont `engine: 'Oracle'`. Suite complète : **2474/2474 tests** ✓.

### Senior Developer Review (AI)

**Reviewer:** Claude — 2026-02-23
**Outcome:** Approuvé avec corrections

**Findings et fixes appliqués :**

- **[MEDIUM] `useTargetInventory.ts` — DEV log `previous` affiche la nouvelle valeur (x2)**
  `lastEngineTypeRef.current` et `lastServerNamesRef.current` étaient mis à jour avant la lecture de `previous` dans les logs DEV. Fix : capture de la valeur précédente dans une variable locale avant mise à jour du ref.

- **[MEDIUM] `useTargetInventory.test.ts` — Couverture `databases` manquante pour AC2 et AC3**
  Ajout de `test_engine_type_passed_to_fetch_databases` (AC2) et `test_no_engine_type_databases` (AC3).

**Suite de tests :** 24/24 ✓

### File List

- `idp-portal/frontend/src/services/execution_service.ts`
- `idp-portal/frontend/src/hooks/useTargetInventory.ts`
- `idp-portal/frontend/src/hooks/useExecutionWizardState.ts`
- `idp-portal/frontend/src/services/__tests__/execution_service.test.ts`
- `idp-portal/frontend/src/hooks/useTargetInventory.test.ts`
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.test.tsx`
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.story23_6.test.tsx`

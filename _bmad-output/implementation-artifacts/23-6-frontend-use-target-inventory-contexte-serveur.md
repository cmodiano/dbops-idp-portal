# Story 23.6: Frontend — useTargetInventory + contexte serveur

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu'utilisateur exécutant une action,
je veux que les listes déroulantes de paramètres (instances ou bases de données) n'affichent que les éléments liés au(x) serveur(s) que j'ai sélectionné(s) à l'étape 1,
afin de simplifier la sélection et éviter de choisir une instance/DB incompatible avec le serveur cible.

## Acceptance Criteria

**Given** une action avec un paramètre `source: 'inventory', inventory_type: 'instances'`
**When** l'utilisateur a sélectionné un ou plusieurs serveurs à l'étape 1 du wizard
**Then** à l'étape 2, la liste déroulante du paramètre instance n'affiche que les instances liées à ces serveurs
**And** le même comportement s'applique pour `inventory_type: 'databases'`

### AC1 : Passer selectedServerNames à useTargetInventory

**Given** ExecutionWizard à l'étape 2 (paramètres) avec serveur(s) sélectionné(s) à l'étape 1
**When** le hook `useTargetInventory` est appelé
**Then** il reçoit un nouveau paramètre `selectedServerNames: string[]` contenant les noms des serveurs sélectionnés
**And** si `selectedTargets` contient `[{name: 'srv01', environment: 'dev'}, {name: 'srv02', environment: 'dev'}]`, alors `selectedServerNames = ['srv01', 'srv02']`
**And** si aucun serveur n'est sélectionné (mode manual sans target list), `selectedServerNames = []`

**Implémentation** :
- Dans `ExecutionWizard.tsx`, calculer `selectedServerNames` depuis `effectiveTargetNames` ou `selectedTargets`
- Passer `selectedServerNames` au hook `useTargetInventory` via l'interface `UseTargetInventoryOptions`
- Type : `selectedServerNames?: string[]` (optionnel pour rétrocompatibilité)

### AC2 : Appeler fetchInventoryItems avec server_names pour instances/databases

**Given** `useTargetInventory` avec `inventorySource === 'instances'` ou `'databases'`
**When** le hook charge les données inventaire
**Then** il appelle `fetchInventoryItems(source, environment, { server_names: selectedServerNames })`
**And** le paramètre `server_names` est envoyé en query string vers l'API backend : `?server_names=srv01,srv02`
**And** pour `inventorySource === 'servers'`, le comportement reste inchangé (pas de `server_names`)

**Implémentation** :
- Modifier `useTargetInventory.ts` ligne 96 : `fetchInventoryItems(source, environment, { server_names: selectedServerNames })`
- Modifier `execution_service.ts` `fetchInventoryItems` pour accepter `options?: { server_names?: string[] }`
- Construire query string : `?environment=${env}&server_names=${options.server_names.join(',')}`
- Tests : vérifier appel API avec query params corrects

### AC3 : Backend API supporte server_names query param (référence Story 23.3)

**Given** Story 23.3 (done) a implémenté API `/api/v1/inventory/instances` et `/databases`
**When** le frontend appelle ces endpoints avec `?server_names=srv01,srv02`
**Then** le backend filtre les résultats pour ne retourner que les instances/databases liées à srv01 ou srv02
**And** si `server_names` est absent, retourner toutes les instances/databases de l'environnement (comportement actuel)
**And** si `server_names` est vide, retourner liste vide (pas d'instances/DB sans serveur défini)

**Note** : AC3 est un rappel de Story 23.3 déjà implémentée. Pas de travail backend dans cette story, seulement vérifier la compatibilité frontend.

**Files backend (référence)** :
- `django_backend/inventory/views.py` : InventoryInstancesView, InventoryDatabasesView
- `django_backend/inventory/services.py` : InventoryService.list_instances, list_databases
- Tests backend : `django_backend/inventory/tests/test_inventory_api.py`

### AC4 : Affichage conditionnel dans renderFieldInput

**Given** `renderFieldInput` reçoit un champ avec `inventorySource === 'instances'` ou `'databases'`
**When** le composant est rendu
**Then** le Select affiche les items filtrés par serveur (depuis `inventoryData[source]`)
**And** si `selectedServerNames` est vide et `inventorySource !== 'servers'`, afficher un message d'aide : "Sélectionnez d'abord un serveur à l'étape 1"
**And** si `inventoryData[source]` est vide après filtrage, afficher "Aucune donnée disponible pour les serveurs sélectionnés"

**Implémentation** :
- `renderFieldInput.tsx` : déjà implémenté dans Story 23.5, vérifier compatibilité
- Ajouter Alert info si `selectedServerNames.length === 0` et `inventorySource !== 'servers'`
- Texte : "Veuillez d'abord sélectionner un serveur à l'étape 1 pour afficher les {instances|bases de données} disponibles"

### AC5 : Loading state et cache invalidation

**Given** l'utilisateur change de serveur à l'étape 1
**When** il retourne à l'étape 2 (ou change d'environnement/serveur)
**Then** les listes instances/databases sont rechargées avec les nouveaux `server_names`
**And** le cache `inventoryData` est invalidé si `selectedServerNames` change
**And** un loading spinner est affiché pendant le rechargement

**Implémentation** :
- Dans `useTargetInventory`, ajouter `selectedServerNames` aux dépendances useEffect qui charge inventaire
- Invalider cache si `prev_selectedServerNames !== current_selectedServerNames`
- Utiliser `loadingInventory` state existant pour spinner
- Tests : vérifier rechargement quand selectedServerNames change

### AC6 : Gestion edge cases

**Given** l'utilisateur utilise le wizard
**When** des cas limites surviennent
**Then** :
- Si `selectedServerNames = []` et `inventorySource === 'instances'`, afficher message aide (AC4) + liste vide
- Si API retourne erreur 400 (ex. server_names invalides), afficher message d'erreur générique inventaire
- Si `selectedServerNames` contient des noms inexistants (ex. serveur supprimé), backend retourne liste vide (pas d'erreur)
- Si multi-sélection serveurs (srv01, srv02) avec certains serveurs sans instances, retourner uniquement instances des serveurs qui en ont
- Mode `manual` target input : `selectedServerNames = []`, comportement AC4 s'applique

**Tests** :
- Test selectedServerNames vide → message aide affiché
- Test API erreur → message erreur générique
- Test multi-sélection avec un serveur sans instances → liste partielle
- Test mode manual → selectedServerNames vide

### AC7 : Rétrocompatibilité actions sans inventaire

**Given** une action avec paramètres `source: 'manual'` (ou sans `source`)
**When** le wizard est ouvert
**Then** le comportement reste inchangé (Input text standard)
**And** `useTargetInventory` ne charge aucune donnée inventaire
**And** `selectedServerNames` n'a aucun impact sur les champs manuels

**Tests** :
- Test action sans paramètre inventaire → pas d'appel fetchInventoryItems
- Test action mixte (1 param inventory + 1 param manual) → uniquement inventory source appelle API

### AC8 : UX — Aide contextuelle et clarté

**Given** l'interface du wizard à l'étape 2
**When** un paramètre instance/database est affiché
**Then** :
- Le label du champ est clair : "Nom de l'instance" ou "Base de données"
- Si liste vide après filtrage serveur, afficher "Aucune {instance|base} disponible pour les serveurs sélectionnés"
- Si `selectedServerNames` vide, afficher Alert info (AC4) avec icône InfoCircle
- Utiliser Ant Design empty state `notFoundContent` pour liste vide
- Tooltip ou help text optionnel : "Cette liste est filtrée selon le(s) serveur(s) choisi(s) à l'étape précédente"

**Implémentation** :
- `renderFieldInput.tsx` : Alert Ant Design avec `type="info"`, `showIcon`, `closable={false}`
- Message : "Veuillez d'abord sélectionner un serveur à l'étape 1 pour afficher les {instances|bases de données} disponibles."
- `notFoundContent` : "Aucune {instance|base de données} disponible pour les serveurs sélectionnés"

### AC9 : Tests unitaires frontend

**Given** la nouvelle fonctionnalité de filtrage par serveur
**When** les tests sont exécutés
**Then** ils couvrent :

**useTargetInventory tests** :
- Hook reçoit `selectedServerNames` et le passe à `fetchInventoryItems`
- Rechargement quand `selectedServerNames` change (cache invalidé)
- Pas de rechargement si `selectedServerNames` inchangé (cache valide)
- `selectedServerNames = []` → appel API sans `server_names` param

**execution_service tests** :
- `fetchInventoryItems('instances', 'dev', { server_names: ['srv01', 'srv02'] })` → query string `?server_names=srv01,srv02`
- `fetchInventoryItems('servers', 'dev')` → pas de `server_names` param (inchangé)
- `fetchInventoryItems('databases', 'dev', { server_names: [] })` → query string `?server_names=`

**renderFieldInput tests** :
- Champ instances + `selectedServerNames = []` → Alert info affiché
- Champ instances + `selectedServerNames = ['srv01']` → Select avec items filtrés, pas d'Alert
- Champ servers → comportement inchangé (pas d'Alert même si selectedServerNames vide)
- Liste vide après filtrage → `notFoundContent` affiché

**ExecutionWizard integration tests** :
- Étape 1 : sélectionner srv01 → étape 2 → appel API instances avec `?server_names=srv01`
- Étape 1 : multi-sélection srv01, srv02 → étape 2 → appel API avec `?server_names=srv01,srv02`
- Étape 1 : mode manual (pas de liste) → étape 2 → Alert info affiché pour champs instances

**Couverture** : ≥ 85% pour composants modifiés (useTargetInventory, renderFieldInput, execution_service)

### AC10 : Documentation inline et commentaires

**Given** les fichiers modifiés (useTargetInventory, execution_service, renderFieldInput)
**When** un développeur lit le code
**Then** :
- Commentaire JSDoc sur `selectedServerNames` expliquant son rôle : "Noms des serveurs sélectionnés à l'étape 1, utilisés pour filtrer les instances/databases"
- Commentaire dans `fetchInventoryItems` : "Story 23.6 - server_names filter for instances/databases"
- Commentaire dans `renderFieldInput` : "Story 23.6 - Help message when no server selected for instance/database fields"
- README ou doc utilisateur (optionnel) : expliquer que les listes instance/DB dépendent du serveur choisi

**Implémentation** :
- JSDoc complet sur nouvelles propriétés
- Inline comments pour logique spécifique Story 23.6
- Pas de doc utilisateur requise (optionnel)

## Tasks / Subtasks

- [x] Task 1 : Étendre types TypeScript pour selectedServerNames (AC1, AC10)
  - [x] 1.1 : Modifier `useTargetInventory.ts` — ajouter `selectedServerNames?: string[]` à `UseTargetInventoryOptions`
  - [x] 1.2 : JSDoc sur `selectedServerNames` : "Names of servers selected at step 1, used to filter instances/databases"
  - [x] 1.3 : Modifier `execution_service.ts` — étendre `fetchInventoryItems` avec `options?: { server_names?: string[] }`
  - [x] 1.4 : JSDoc sur `options.server_names` : "Optional server names to filter instances/databases (Story 23.6)"
  - [x] 1.5 : Types vérifiés par compilation TypeScript (build passe)

- [x] Task 2 : Calculer selectedServerNames dans ExecutionWizard (AC1)
  - [x] 2.1 : Dans `ExecutionWizard.tsx`, créer `useMemo` pour calculer `selectedServerNames` depuis `effectiveTargetNames`
  - [x] 2.2 : `selectedServerNames = effectiveTargetNames` (déjà liste de noms de serveurs)
  - [x] 2.3 : Passer `selectedServerNames` au hook `useTargetInventory` via options
  - [x] 2.4 : Si `effectiveTargetNames` vide, `selectedServerNames = []`
  - [x] 2.5 : Tests : vérifier calcul correct avec selectedTargets, pattern mode, manual mode

- [x] Task 3 : Modifier useTargetInventory pour passer server_names (AC2, AC5)
  - [x] 3.1 : Extraire `selectedServerNames` depuis `UseTargetInventoryOptions`
  - [x] 3.2 : Dans useEffect qui charge inventaire (ligne 62+), ajouter `selectedServerNames` aux dépendances
  - [x] 3.3 : Invalider cache si `selectedServerNames` change : `lastServerNamesRef.current !== selectedServerNames`
  - [x] 3.4 : Passer `selectedServerNames` à `fetchInventoryItems(source, environment, { server_names: selectedServerNames })`
  - [x] 3.5 : Condition : seulement si `source === 'instances'` ou `source === 'databases'` (pas pour `'servers'`)
  - [x] 3.6 : Tests : 5 tests (server_names passé, rechargement sur changement, cache valide si inchangé, servers source inchangé, empty server_names)

- [x] Task 4 : Étendre fetchInventoryItems pour server_names query param (AC2)
  - [x] 4.1 : Modifier `execution_service.ts` signature : `fetchInventoryItems(source, environment?, options?)`
  - [x] 4.2 : Construire query string : si `options?.server_names` existe et non vide, ajouter `&server_names=${options.server_names.join(',')}`
  - [x] 4.3 : URL finale : `/api/v1/inventory/${source}?environment=${env}&server_names=srv01,srv02`
  - [x] 4.4 : Si `server_names` vide, ne pas ajouter le param (ou `&server_names=`)
  - [x] 4.5 : Tests : 4 tests (query string avec server_names, sans server_names, servers source inchangé, empty array)

- [x] Task 5 : Modifier renderFieldInput pour Alert helper (AC4, AC8)
  - [x] 5.1 : Dans `renderFieldInput.tsx`, ajouter prop `selectedServerNames?: string[]`
  - [x] 5.2 : Si `field.inventorySource === 'instances'` ou `'databases'` ET `selectedServerNames.length === 0`, afficher Alert info
  - [x] 5.3 : Alert Ant Design : `<Alert type="info" showIcon closable={false} message="Veuillez d'abord sélectionner un serveur..." />`
  - [x] 5.4 : Message dynamique : `instances` → "instances", `databases` → "bases de données"
  - [x] 5.5 : Select `notFoundContent` : "Aucune {instance|base de données} disponible pour les serveurs sélectionnés"
  - [x] 5.6 : Tests : 4 tests (Alert affiché si empty servers + instances, pas d'Alert si servers selected, servers source pas d'Alert, notFoundContent)

- [x] Task 6 : Passer selectedServerNames à ParametersFormStep et renderFieldInput (AC4)
  - [x] 6.1 : Modifier `ParametersFormStep.tsx` pour accepter `selectedServerNames` prop
  - [x] 6.2 : Passer `selectedServerNames` à `renderFieldInput` lors du rendu des champs
  - [x] 6.3 : Interface `ParametersFormStepProps` : ajouter `selectedServerNames?: string[]`
  - [x] 6.4 : ExecutionWizard passe `selectedServerNames` à `ParametersFormStep`
  - [x] 6.5 : Tests : vérifier propagation selectedServerNames → ParametersFormStep → renderFieldInput

- [x] Task 7 : Gestion edge cases (AC6)
  - [x] 7.1 : Test selectedServerNames vide + inventorySource instances → Alert affiché + liste vide
  - [x] 7.2 : Test API erreur 400 (server_names invalides) → message erreur générique (logger.error + notification ou try/catch existant)
  - [x] 7.3 : Test multi-sélection serveurs avec certains sans instances → liste partielle retournée (backend gère déjà)
  - [x] 7.4 : Test mode manual target → selectedServerNames = [] → Alert affiché
  - [x] 7.5 : Logging avec logger.warn si `selectedServerNames` vide et `inventorySource !== 'servers'`
  - [x] 7.6 : 5 tests edge cases

- [x] Task 8 : Rétrocompatibilité et tests (AC7)
  - [x] 8.1 : Test action sans paramètre inventaire → useTargetInventory ne charge rien
  - [x] 8.2 : Test action paramètre `source: 'manual'` → Input text affiché, pas d'appel fetchInventoryItems
  - [x] 8.3 : Test action mixte (inventory + manual) → seulement inventory source appelle API
  - [x] 8.4 : Vérifier aucune régression sur actions existantes (tests ExecutionWizard existants passent)
  - [x] 8.5 : 3 tests rétrocompatibilité

- [x] Task 9 : Tests unitaires useTargetInventory (AC9)
  - [x] 9.1 : Test hook reçoit selectedServerNames et passe à fetchInventoryItems
  - [x] 9.2 : Test rechargement quand selectedServerNames change (cache invalidé)
  - [x] 9.3 : Test pas de rechargement si selectedServerNames inchangé (cache valide)
  - [x] 9.4 : Test selectedServerNames = [] → appel API sans server_names param
  - [x] 9.5 : Test source='servers' → pas de server_names param même si selectedServerNames fourni
  - [x] 9.6 : 5 tests dans `useTargetInventory.test.ts`

- [x] Task 10 : Tests unitaires execution_service (AC9)
  - [x] 10.1 : Test fetchInventoryItems('instances', 'dev', { server_names: ['srv01', 'srv02'] }) → query string `?server_names=srv01,srv02`
  - [x] 10.2 : Test fetchInventoryItems('servers', 'dev') → pas de server_names param
  - [x] 10.3 : Test fetchInventoryItems('databases', 'dev', { server_names: [] }) → query string `?server_names=` ou omis
  - [x] 10.4 : Test fetchInventoryItems('instances', 'dev') sans options → pas de server_names param (rétrocompat)
  - [x] 10.5 : 4 tests dans `execution_service.test.ts`

- [x] Task 11 : Tests unitaires renderFieldInput (AC9)
  - [x] 11.1 : Test champ instances + selectedServerNames = [] → Alert info affiché
  - [x] 11.2 : Test champ instances + selectedServerNames = ['srv01'] → Select rendu, pas d'Alert
  - [x] 11.3 : Test champ servers + selectedServerNames = [] → pas d'Alert (comportement inchangé)
  - [x] 11.4 : Test liste vide après filtrage → notFoundContent affiché
  - [x] 11.5 : Test champ databases + selectedServerNames vide → Alert affiché
  - [x] 11.6 : 5 tests dans `renderFieldInput.test.ts`

- [x] Task 12 : Tests intégration ExecutionWizard (AC9)
  - [x] 12.1 : Test étape 1 sélectionner srv01 → étape 2 → appel API instances avec `?server_names=srv01`
  - [x] 12.2 : Test multi-sélection srv01, srv02 → appel API avec `?server_names=srv01,srv02`
  - [x] 12.3 : Test mode manual (pas de liste serveurs) → Alert info affiché pour champs instances
  - [x] 12.4 : Test changement serveur étape 1 → retour étape 2 → rechargement inventaire
  - [x] 12.5 : 4 tests dans `ExecutionWizard.integration.test.tsx` (ou fichier existant)

- [x] Task 13 : Documentation et commentaires (AC10)
  - [x] 13.1 : JSDoc complet sur `UseTargetInventoryOptions.selectedServerNames`
  - [x] 13.2 : JSDoc sur `fetchInventoryItems options.server_names`
  - [x] 13.3 : Inline comment dans useTargetInventory useEffect : "Story 23.6 - Invalidate cache if selected servers change"
  - [x] 13.4 : Inline comment dans renderFieldInput : "Story 23.6 - Show help message when no server selected for instance/database fields"
  - [x] 13.5 : Inline comment dans execution_service query string : "Story 23.6 - Add server_names filter for instances/databases"
  - [x] 13.6 : README ou doc utilisateur (optionnel, décision de ne pas créer OK)

## Dev Notes

### Contexte architectural

**Référence** : docs/inventaire-multi-tables-ux-cibles.md §6, Stories 23.1-23.5 (done), Epic 23

**Architecture inventaire multi-tables (Stories 23.1-23.3 done)** :
- Backend : InventoryService.list_instances, list_databases avec filtres `environment` et `server_name` (ou `server_names` array)
- Backend : API GET /api/v1/inventory/{instances|databases}?environment=...&server_names=srv01,srv02
- Format réponse : `{ data: [{ name, environment, ... }] }`
- Story 23.3 (done) : Backend déjà implémenté avec support `server_names` query param

**Wizard d'exécution actuel** :
- ExecutionWizard (frontend/src/components/catalog/ExecutionWizard.tsx) : 3 étapes
- Étape 1 : TargetSelectionStep — sélection serveurs (selectedTargets)
- Étape 2 : ParametersFormStep — rendu dynamique via useDynamicForm + renderFieldInput
- Étape 3 : ConfirmationStep — révision avant soumission
- `effectiveTargetNames` (ligne 184) : calculé depuis selectedTargets, resolvedPatternTargets, ou manualTargetInput

**useTargetInventory hook actuel (Story 17.2, refactored Story 20.4)** :
- Charge inventaire par environnement uniquement : `fetchInventoryItems(source, environment)`
- Pas de filtrage par serveur → toutes les instances/databases de l'environnement
- Cache par source + environment (lastInventoryEnvRef)
- Loading state `loadingInventory` pour spinner
- Interface `UseTargetInventoryOptions` : `open`, `actionId`, `currentStep`, `parameterFields`, `environment`

**fetchInventoryItems (execution_service.ts)** :
- Signature actuelle : `fetchInventoryItems(source: string, environment?: string): Promise<InventoryItem[]>`
- Appelle `/api/v1/inventory/${source}?environment=${env}`
- Gestion cache sessionStorage (INVENTORY_UNAVAILABLE fallback)

**renderFieldInput (Story 23.5)** :
- Reçoit `field`, `inventoryData`, `inventoryWarnings`, `loadingInventory`
- Si `field.inventorySource` présent, rendu Select avec données inventaire
- Select peuplé par `inventoryData[field.inventorySource]`
- Pas de filtrage par serveur actuellement → **problème à résoudre dans Story 23.6**

**Flow actuel (Story 23.5)** :
1. Admin configure paramètre : `source: 'inventory', inventory_type: 'instances'`
2. ExecutionWizard étape 1 : utilisateur sélectionne srv01, srv02
3. ExecutionWizard étape 2 : useDynamicForm détecte `inventorySource: 'instances'`
4. useTargetInventory charge : `fetchInventoryItems('instances', 'dev')` → **toutes les instances de dev**
5. renderFieldInput affiche Select avec **toutes** les instances (pas filtré par srv01, srv02)

**Flow cible (Story 23.6)** :
1. ExecutionWizard étape 1 : utilisateur sélectionne srv01, srv02
2. ExecutionWizard calcule `selectedServerNames = ['srv01', 'srv02']`
3. ExecutionWizard passe `selectedServerNames` à useTargetInventory
4. useTargetInventory charge : `fetchInventoryItems('instances', 'dev', { server_names: ['srv01', 'srv02'] })`
5. API backend : `/api/v1/inventory/instances?environment=dev&server_names=srv01,srv02`
6. renderFieldInput affiche Select avec **seulement instances liées à srv01 ou srv02**

### Fichiers à modifier

**Modifier** :
- `frontend/src/hooks/useTargetInventory.ts` : Ajouter `selectedServerNames` param, invalider cache si change, passer à fetchInventoryItems
- `frontend/src/services/execution_service.ts` : Étendre fetchInventoryItems avec `options?: { server_names?: string[] }`, construire query string
- `frontend/src/components/catalog/ExecutionWizard.tsx` : Calculer `selectedServerNames` depuis `effectiveTargetNames`, passer à useTargetInventory
- `frontend/src/components/catalog/ParametersFormStep.tsx` : Accepter `selectedServerNames` prop, passer à renderFieldInput
- `frontend/src/components/catalog/renderFieldInput.tsx` : Accepter `selectedServerNames` prop, afficher Alert si vide pour instances/databases

**Créer/Modifier tests** :
- `frontend/src/hooks/__tests__/useTargetInventory.test.ts` : +5 tests Story 23.6
- `frontend/src/services/__tests__/execution_service.test.ts` : +4 tests Story 23.6
- `frontend/src/components/catalog/__tests__/renderFieldInput.test.tsx` : +5 tests Story 23.6
- `frontend/src/components/catalog/__tests__/ExecutionWizard.integration.test.tsx` : +4 tests Story 23.6 (ou fichier existant)

### Patterns de code

**Extension UseTargetInventoryOptions** :
```typescript
// frontend/src/hooks/useTargetInventory.ts
export interface UseTargetInventoryOptions {
  open: boolean;
  actionId?: number;
  currentStep: number;
  parameterFields: Array<{ inventorySource?: 'databases' | 'servers' | 'instances' }>;
  environment: string | null;
  // Story 23.6 - Filter instances/databases by selected servers
  selectedServerNames?: string[];
}
```

**Calcul selectedServerNames dans ExecutionWizard** :
```typescript
// frontend/src/components/catalog/ExecutionWizard.tsx (ligne ~190)
const selectedServerNames = useMemo((): string[] => {
  return effectiveTargetNames; // déjà liste de noms de serveurs
}, [effectiveTargetNames]);

// Passer au hook useTargetInventory
const { inventoryData, loadingInventory, inventoryWarnings, environmentsCache } = useTargetInventory({
  open,
  actionId: action?.id,
  currentStep,
  parameterFields,
  environment: derivedEnvironment,
  selectedServerNames, // Story 23.6
});
```

**useTargetInventory avec server_names** :
```typescript
// frontend/src/hooks/useTargetInventory.ts (ligne ~62, useEffect inventaire)
export function useTargetInventory({
  open,
  currentStep,
  parameterFields,
  environment,
  selectedServerNames = [], // Story 23.6
}: UseTargetInventoryOptions): UseTargetInventoryReturn {
  // ... existing state ...
  const lastServerNamesRef = useRef<string[] | null>(null);

  // Load inventory data for fields that need it (only on step 2 with environment selected)
  useEffect(() => {
    if (!open || currentStep !== 1 || !environment) return;

    const sourcesToLoad = new Set<'databases' | 'servers' | 'instances'>();
    parameterFields.forEach((field) => {
      if (field.inventorySource) {
        sourcesToLoad.add(field.inventorySource);
      }
    });

    if (sourcesToLoad.size === 0) return;

    const envChanged = lastInventoryEnvRef.current !== environment;
    // Story 23.6 - Invalidate cache if selected servers change
    const serverNamesChanged = JSON.stringify(lastServerNamesRef.current) !== JSON.stringify(selectedServerNames);

    if (envChanged) {
      lastInventoryEnvRef.current = environment;
    }
    if (serverNamesChanged) {
      lastServerNamesRef.current = selectedServerNames;
    }

    const toFetch: Array<'databases' | 'servers' | 'instances'> = [];
    const cached: Record<string, InventoryItem[]> = {};

    sourcesToLoad.forEach((source) => {
      if (!envChanged && !serverNamesChanged && inventoryData[source] && inventoryData[source].length > 0) {
        cached[source] = inventoryData[source];
      } else {
        toFetch.push(source);
      }
    });

    if (toFetch.length === 0) return;

    setLoadingInventory(true);
    Promise.all(
      toFetch.map(async (source) => {
        try {
          // Story 23.6 - Pass server_names for instances/databases
          const options = (source === 'instances' || source === 'databases')
            ? { server_names: selectedServerNames }
            : undefined;

          const items = await fetchInventoryItems(source, environment, options);
          setInventoryWarnings((prev) => ({ ...prev, [source]: false }));
          return [source, items] as const;
        } catch (err: unknown) {
          // ... existing error handling ...
        }
      })
    )
      .then((results) => {
        const data: Record<string, InventoryItem[]> = { ...cached };
        results.forEach(([source, items]) => {
          data[source] = items;
        });
        setInventoryData(data);
      })
      .finally(() => setLoadingInventory(false));
  }, [open, currentStep, parameterFields, environment, inventoryData, selectedServerNames]); // Story 23.6 - Add selectedServerNames dependency

  return {
    environmentsCache,
    inventoryData,
    inventoryWarnings,
    loadingInventory,
  };
}
```

**fetchInventoryItems avec server_names** :
```typescript
// frontend/src/services/execution_service.ts
export async function fetchInventoryItems(
  source: 'environments' | 'databases' | 'servers' | 'instances',
  environment?: string,
  // Story 23.6 - Optional server names to filter instances/databases
  options?: { server_names?: string[] }
): Promise<InventoryItem[]> {
  let url = `/api/v1/inventory/${source}`;
  const params = new URLSearchParams();

  if (environment) {
    params.append('environment', environment);
  }

  // Story 23.6 - Add server_names filter for instances/databases
  if (options?.server_names && options.server_names.length > 0) {
    params.append('server_names', options.server_names.join(','));
  }

  if (params.toString()) {
    url += `?${params.toString()}`;
  }

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getToken()}`,
    },
  });

  if (!response.ok) {
    // ... existing error handling ...
  }

  const data = await response.json();
  return data.data || [];
}
```

**renderFieldInput avec Alert helper** :
```tsx
// frontend/src/components/catalog/renderFieldInput.tsx
import { Select, Spin, Alert } from 'antd';
import { InfoCircleOutlined } from '@ant-design/icons';

interface RenderFieldInputProps {
  field: ParameterField & { renderType?: string; inventorySource?: string };
  environment: string;
  value: any;
  onChange: (value: any) => void;
  inventoryData: Record<string, InventoryItem[]>;
  inventoryWarnings: Record<string, boolean>;
  loadingInventory: boolean;
  // Story 23.6 - Filter instances/databases by selected servers
  selectedServerNames?: string[];
}

export const renderFieldInput = ({
  field,
  environment,
  value,
  onChange,
  inventoryData,
  inventoryWarnings,
  loadingInventory,
  selectedServerNames = [],
}: RenderFieldInputProps) => {
  // Story 23.5 - Rendu Select inventaire
  if (field.renderType === 'inventory-select' && field.inventorySource) {
    const items = inventoryData[field.inventorySource] || [];
    const isLoading = loadingInventory;

    // Story 23.6 - Show help message when no server selected for instance/database fields
    const needsServerSelection = (field.inventorySource === 'instances' || field.inventorySource === 'databases')
      && selectedServerNames.length === 0;

    if (needsServerSelection) {
      const entityLabel = field.inventorySource === 'instances' ? 'instances' : 'bases de données';
      return (
        <>
          <Alert
            type="info"
            showIcon
            icon={<InfoCircleOutlined />}
            closable={false}
            message={`Veuillez d'abord sélectionner un serveur à l'étape 1 pour afficher les ${entityLabel} disponibles.`}
            style={{ marginBottom: 8 }}
          />
          <Select
            value={value}
            onChange={onChange}
            placeholder={`Sélectionnez ${field.label.toLocaleLowerCase('fr-FR')}`}
            disabled
            notFoundContent="Sélectionnez d'abord un serveur"
          />
        </>
      );
    }

    const entityLabel = field.inventorySource === 'instances' ? 'instance'
      : field.inventorySource === 'databases' ? 'base de données'
      : 'serveur';

    const notFoundMessage = items.length === 0 && selectedServerNames.length > 0
      ? `Aucune ${entityLabel} disponible pour les serveurs sélectionnés`
      : `Aucune ${entityLabel} disponible`;

    return (
      <Select
        value={value}
        onChange={onChange}
        placeholder={`Sélectionnez ${field.label.toLocaleLowerCase('fr-FR')}`}
        loading={isLoading}
        notFoundContent={isLoading ? <Spin size="small" /> : notFoundMessage}
        showSearch
        filterOption={(input, option) =>
          (option?.label ?? '').toLowerCase().includes(input.toLowerCase())
        }
      >
        {items.map((item) => (
          <Select.Option key={item.name} value={item.name} label={item.name}>
            {item.name}
          </Select.Option>
        ))}
      </Select>
    );
  }

  // Fallback : Input standard
  return <Input value={value} onChange={(e) => onChange(e.target.value)} />;
};
```

### Standards de tests

**Référence** : Stories 23.1-23.5 (69+43+57+53+94 tests), Story 17.2 (ExecutionWizard refactoring), Story 20.4 (useTargetInventory refactoring)

**Couverture requise** :
- Tests unitaires useTargetInventory : selectedServerNames passé, cache invalidé, rechargement (5 tests)
- Tests unitaires execution_service : query string server_names, rétrocompatibilité (4 tests)
- Tests unitaires renderFieldInput : Alert affiché, Select filtré, notFoundContent (5 tests)
- Tests intégration ExecutionWizard : étapes 1→2 avec filtrage serveur (4 tests)
- Coverage ≥ 85% pour composants modifiés

**Assertions clés** :
- Vérifier `selectedServerNames` calculé correctement depuis `effectiveTargetNames`
- Vérifier appel `fetchInventoryItems` avec `options.server_names` pour instances/databases
- Vérifier query string `?server_names=srv01,srv02` construit correctement
- Vérifier cache invalidé si `selectedServerNames` change (useEffect re-triggered)
- Vérifier Alert affiché si `selectedServerNames = []` et `inventorySource !== 'servers'`
- Vérifier rétrocompatibilité : actions sans inventaire inchangées

**Pattern tests hook** :
```typescript
// frontend/src/hooks/__tests__/useTargetInventory.test.ts
import { renderHook, waitFor } from '@testing-library/react';
import { useTargetInventory } from '../useTargetInventory';
import * as executionService from '../../services/execution_service';

vi.mock('../../services/execution_service');

describe('useTargetInventory - Story 23.6', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('passe selectedServerNames à fetchInventoryItems pour instances', async () => {
    vi.spyOn(executionService, 'fetchInventoryItems').mockResolvedValue([
      { id: 'inst01', name: 'inst01', environment: 'dev' },
    ]);

    const { result } = renderHook(() =>
      useTargetInventory({
        open: true,
        currentStep: 1,
        parameterFields: [{ inventorySource: 'instances' }],
        environment: 'dev',
        selectedServerNames: ['srv01', 'srv02'],
      })
    );

    await waitFor(() => {
      expect(executionService.fetchInventoryItems).toHaveBeenCalledWith(
        'instances',
        'dev',
        { server_names: ['srv01', 'srv02'] }
      );
    });
  });

  it('recharge inventaire quand selectedServerNames change', async () => {
    vi.spyOn(executionService, 'fetchInventoryItems').mockResolvedValue([]);

    const { rerender } = renderHook(
      ({ selectedServerNames }) =>
        useTargetInventory({
          open: true,
          currentStep: 1,
          parameterFields: [{ inventorySource: 'instances' }],
          environment: 'dev',
          selectedServerNames,
        }),
      { initialProps: { selectedServerNames: ['srv01'] } }
    );

    await waitFor(() => {
      expect(executionService.fetchInventoryItems).toHaveBeenCalledTimes(1);
    });

    // Changer selectedServerNames
    rerender({ selectedServerNames: ['srv02', 'srv03'] });

    await waitFor(() => {
      expect(executionService.fetchInventoryItems).toHaveBeenCalledTimes(2);
      expect(executionService.fetchInventoryItems).toHaveBeenLastCalledWith(
        'instances',
        'dev',
        { server_names: ['srv02', 'srv03'] }
      );
    });
  });

  it('ne passe pas server_names pour inventorySource servers', async () => {
    vi.spyOn(executionService, 'fetchInventoryItems').mockResolvedValue([]);

    renderHook(() =>
      useTargetInventory({
        open: true,
        currentStep: 1,
        parameterFields: [{ inventorySource: 'servers' }],
        environment: 'dev',
        selectedServerNames: ['srv01'],
      })
    );

    await waitFor(() => {
      expect(executionService.fetchInventoryItems).toHaveBeenCalledWith('servers', 'dev', undefined);
    });
  });
});
```

**Pattern tests renderFieldInput** :
```typescript
// frontend/src/components/catalog/__tests__/renderFieldInput.test.tsx
import { render, screen } from '@testing-library/react';
import { renderFieldInput } from '../renderFieldInput';

describe('renderFieldInput - Story 23.6', () => {
  it('affiche Alert si selectedServerNames vide et inventorySource instances', () => {
    const field = {
      name: 'instance_name',
      label: 'Instance',
      type: 'string' as const,
      renderType: 'inventory-select',
      inventorySource: 'instances',
    };

    render(
      renderFieldInput({
        field,
        environment: 'dev',
        value: null,
        onChange: vi.fn(),
        inventoryData: { instances: [] },
        inventoryWarnings: {},
        loadingInventory: false,
        selectedServerNames: [],
      })
    );

    expect(screen.getByText(/Veuillez d'abord sélectionner un serveur/i)).toBeInTheDocument();
    expect(screen.getByRole('combobox')).toBeDisabled();
  });

  it('affiche Select avec items si selectedServerNames fourni', () => {
    const field = {
      name: 'instance_name',
      label: 'Instance',
      type: 'string' as const,
      renderType: 'inventory-select',
      inventorySource: 'instances',
    };

    render(
      renderFieldInput({
        field,
        environment: 'dev',
        value: null,
        onChange: vi.fn(),
        inventoryData: { instances: [{ id: 'inst01', name: 'inst01', environment: 'dev' }] },
        inventoryWarnings: {},
        loadingInventory: false,
        selectedServerNames: ['srv01'],
      })
    );

    expect(screen.queryByText(/Veuillez d'abord sélectionner/i)).not.toBeInTheDocument();
    expect(screen.getByRole('combobox')).not.toBeDisabled();
    expect(screen.getByText('inst01')).toBeInTheDocument();
  });

  it('pas d\'Alert pour inventorySource servers même si selectedServerNames vide', () => {
    const field = {
      name: 'server_name',
      label: 'Serveur',
      type: 'string' as const,
      renderType: 'inventory-select',
      inventorySource: 'servers',
    };

    render(
      renderFieldInput({
        field,
        environment: 'dev',
        value: null,
        onChange: vi.fn(),
        inventoryData: { servers: [{ id: 'srv01', name: 'srv01', environment: 'dev' }] },
        inventoryWarnings: {},
        loadingInventory: false,
        selectedServerNames: [],
      })
    );

    expect(screen.queryByText(/Veuillez d'abord sélectionner/i)).not.toBeInTheDocument();
  });
});
```

### Dépendances et ordre

**Dépend de** :
- Story 23.1 (done) : InventoryMapper avec config mapping
- Story 23.2 (done) : InventoryService.list_instances, list_databases avec `server_name` param
- Story 23.3 (done) : API endpoints /api/v1/inventory/{instances|databases} avec `server_names` query param
- Story 23.5 (done) : Admin source inventaire + inventory_type dans schéma paramètres, renderFieldInput Select inventaire
- Story 17.2 (done) : ExecutionWizard refactoring (TargetSelectionStep, ParametersFormStep, hooks)
- Story 20.4 (done) : useTargetInventory hook extraction, usePatternResolver

**Bloque** :
- Story 23.7 (next) : ProfileForm options Tous / Oracle / SQL (besoin inventaire filtré fonctionnel)

**N'affecte PAS** :
- Actions avec paramètres `source: 'manual'` : comportement inchangé
- Actions avec `inventory_type: 'servers'` : comportement inchangé (pas de filtrage serveur)
- API backend inventaire : déjà implémenté Story 23.3 (aucune modification backend requise)

### Risques et mitigations

**Risque** : selectedServerNames vide cause liste vide instances/databases au lieu de montrer toutes (UX dégradée)
**Mitigation** : Afficher Alert info explicite AC4 + Select disabled + message aide "Sélectionnez d'abord un serveur"

**Risque** : Cache inventaire invalide si utilisateur change serveur à l'étape 1 puis retourne étape 2
**Mitigation** : Ajouter `selectedServerNames` aux dépendances useEffect AC5, invalider cache avec `lastServerNamesRef` comparaison JSON.stringify

**Risque** : Multi-sélection serveurs (srv01, srv02) génère URL trop longue si 20+ serveurs
**Mitigation** : Backend Story 23.3 a déjà limite ROWNUM ≤ 10000 (DoS prevention), frontend peut limiter selectedServerNames à 10 premiers si nécessaire (ou laisser backend gérer)

**Risque** : Mode manual target input (pas de selectedTargets) cause selectedServerNames = [] → Alert affiché même si valide
**Mitigation** : C'est intentionnel AC6 — mode manual ne permet pas filtrage par serveur (utilisateur doit saisir manuellement instance/DB), Alert aide utilisateur comprendre qu'il doit passer en mode liste

**Risque** : Rétrocompatibilité cassée si action existante sans `source: 'inventory'`
**Mitigation** : Tests AC7 extensifs, `inventorySource` undefined → pas d'appel fetchInventoryItems, pas d'impact selectedServerNames

### Intelligence des Stories 23.1-23.5

**Story 23.1 (done)** :
- InventoryMapper.get_entity_data('instances', filters={'server_name': 'srv01'})
- Query SQL avec WHERE sur colonnes mappées (relations serveur→instance)
- 69 tests passent, validation sécurité SAFE_TABLE_NAME_PATTERN

**Story 23.2 (done)** :
- InventoryService.list_instances(environment='dev', server_name='srv01') → liste filtrée
- Support `server_name` (single) ou `server_names` (array) pour multi-sélection
- 43 tests passent, gestion empty list si serveur sans instances

**Story 23.3 (done)** :
- API GET /api/v1/inventory/instances?environment=dev&server_names=srv01,srv02
- Backend parse `server_names` query param, split par virgule, filtre instances
- 57 tests passent, validation RBAC (serveurs autorisés)

**Story 23.4 (done)** :
- RBAC filtres par attribut : `filter_by_attribute_json: {"engine_type": ["oracle"]}`
- Appliqué dans list_targets_for_user après LIST/PATTERN/ALL
- 53 tests passent, validation concepts disponibles

**Story 23.5 (done)** :
- Admin paramètres : `source: 'inventory', inventory_type: 'instances'`
- useDynamicForm mappe `inventory_type` → `inventorySource` pour renderFieldInput
- renderFieldInput rendu Select peuplé par `inventoryData[inventorySource]`
- 94 tests passent (79 frontend + 15 backend)
- **Known Limitation (Story 23.5 AI-Review HIGH-2)** : "renderFieldInput selectedServerNames absent — structure prête pour Story 23.6 devra modifier signature pour filtrer instances/databases par serveur"

**Patterns à réutiliser** :
- useMemo pour valeurs dérivées (ExecutionWizard ligne 184, 191)
- useRef pour comparaison valeurs précédentes (lastInventoryEnvRef ligne 176)
- useEffect avec dépendances strictes (useTargetInventory ligne 62)
- Query string construction avec URLSearchParams (execution_service.ts pattern)
- Alert Ant Design avec InfoCircleOutlined (Story 23.5, 2-17, 2-18)
- Tests React Testing Library avec waitFor + vi.spyOn (Story 5-5, 22-8)

### Commits récents pertinents

**Référence** : `git log --oneline -5`

- `4420133 feat(23-5): code review fixes - French accents, type consolidation, validation docs` — Story 23.5, 94 tests
- `bd33797 feat(23-4): implement RBAC profile filtering by inventory attributes` — Story 23.4, 53 tests
- `a840414 feat(23-3): implement multi-table inventory API endpoints` — Story 23.3, 57 tests
- `6f61d93 feat(23-2): add multi-table inventory service methods` — Story 23.2, 43 tests
- `3d39053 feat(23-1): implement config-driven multi-table inventory mapping` — Story 23.1, 69 tests

**Code patterns récents Epic 23** :
- Backend API avec query params : `request.query_params.get('server_names', '').split(',')` (Story 23.3)
- Frontend query string : `const params = new URLSearchParams(); params.append('server_names', names.join(','))` (pattern)
- useEffect cache invalidation : `const changed = JSON.stringify(prev) !== JSON.stringify(current)` (Story 20.4)
- Alert Ant Design : `<Alert type="info" showIcon closable={false} message="..." />` (Story 23.5)
- Tests hook avec renderHook + waitFor : `const { result } = renderHook(() => useHook()); await waitFor(() => expect(...))` (Story 5-5)

### Architecture Frontend (référence)

**Fichier** : docs/architecture.md §Frontend (pas dans contexte mais pattern connu)

**ExecutionWizard flow (Story 17.2 refactoring)** :
```
ExecutionWizard.tsx (controller)
├── Step 0: TargetSelectionStep
│   ├── selectedTargets state (Target[])
│   ├── targetInputMode: 'list' | 'pattern' | 'manual'
│   └── effectiveTargetNames (calculated)
├── Step 1: ParametersFormStep
│   ├── useDynamicForm → parameterFields avec inventorySource
│   ├── useTargetInventory → inventoryData par source
│   └── renderFieldInput → Select ou Input selon field
└── Step 2: ConfirmationStep
    └── Révision + soumission
```

**useTargetInventory hook (Story 20.4)** :
```
useTargetInventory
├── Input: open, currentStep, parameterFields, environment, selectedServerNames (NEW)
├── State: inventoryData, loadingInventory, environmentsCache, inventoryWarnings
├── useEffect 1: Load environments (once)
├── useEffect 2: Load inventory data (per source + environment + selectedServerNames)
│   ├── Detect sourcesToLoad depuis parameterFields
│   ├── Cache check : envChanged || serverNamesChanged (NEW)
│   ├── fetchInventoryItems(source, env, options) (MODIFIED)
│   └── setInventoryData
└── Return: inventoryData, loadingInventory, inventoryWarnings, environmentsCache
```

### Exemples d'utilisation

**Exemple 1 : Action "Patching instance Oracle" avec serveur sélectionné**

Schéma de l'action (Admin) :
```json
{
  "parameters": [
    {
      "name": "instance_name",
      "label": "Nom de l'instance",
      "type": "string",
      "required": true,
      "source": "inventory",
      "inventory_type": "instances"
    },
    {
      "name": "patch_version",
      "label": "Version du patch",
      "type": "string",
      "required": true,
      "source": "manual"
    }
  ]
}
```

**Flow utilisateur** :
1. **Étape 1 (Cibles)** : Utilisateur sélectionne `srv-oracle-01` (mode liste)
   - `selectedTargets = [{ name: 'srv-oracle-01', environment: 'dev' }]`
   - `effectiveTargetNames = ['srv-oracle-01']`
   - `selectedServerNames = ['srv-oracle-01']`

2. **Étape 2 (Paramètres)** :
   - `useTargetInventory` reçoit `selectedServerNames = ['srv-oracle-01']`
   - Appel API : `GET /api/v1/inventory/instances?environment=dev&server_names=srv-oracle-01`
   - Backend retourne : `{ data: [{ name: 'ORCL01', environment: 'dev' }, { name: 'ORCL02', environment: 'dev' }] }`
   - Champ "Nom de l'instance" : Select avec options ORCL01, ORCL02 (seulement instances liées à srv-oracle-01)
   - Champ "Version du patch" : Input text manuel

**Exemple 2 : Multi-sélection serveurs**

**Flow utilisateur** :
1. **Étape 1** : Utilisateur sélectionne `srv-oracle-01`, `srv-oracle-02` (mode liste)
   - `selectedServerNames = ['srv-oracle-01', 'srv-oracle-02']`

2. **Étape 2** :
   - Appel API : `GET /api/v1/inventory/instances?environment=prod&server_names=srv-oracle-01,srv-oracle-02`
   - Backend retourne : `{ data: [{ name: 'ORCL01' }, { name: 'ORCL02' }, { name: 'ORCL03' }, { name: 'ORCL04' }] }`
   - Select affiche les 4 instances (agrégation des instances des 2 serveurs)

**Exemple 3 : Mode manual (pas de liste serveurs)**

**Flow utilisateur** :
1. **Étape 1** : Utilisateur passe en mode `manual`, saisit `srv-custom-01`
   - `targetInputMode = 'manual'`
   - `manualTargetInput = 'srv-custom-01'`
   - `selectedTargets = []` (vide car mode manual)
   - `effectiveTargetNames = ['srv-custom-01']` (parsed depuis manualTargetInput)
   - `selectedServerNames = ['srv-custom-01']` (calculé depuis effectiveTargetNames)

2. **Étape 2** :
   - Appel API : `GET /api/v1/inventory/instances?environment=dev&server_names=srv-custom-01`
   - Si srv-custom-01 existe en inventaire, instances retournées
   - Si srv-custom-01 n'existe pas, backend retourne liste vide → `notFoundContent` affiché

**Exemple 4 : Action sans serveur sélectionné (edge case)**

**Flow utilisateur** :
1. **Étape 1** : Utilisateur ne sélectionne aucun serveur (liste vide)
   - `selectedTargets = []`
   - `effectiveTargetNames = []`
   - `selectedServerNames = []`

2. **Étape 2** :
   - Champ "Nom de l'instance" (inventory_type: instances)
   - `renderFieldInput` détecte `selectedServerNames.length === 0` et `inventorySource === 'instances'`
   - Alert info affiché : "Veuillez d'abord sélectionner un serveur à l'étape 1 pour afficher les instances disponibles."
   - Select disabled avec placeholder "Sélectionnez d'abord un serveur"

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (workflow dev-story)

### Debug Log References

N/A

### Completion Notes List

- Story 23.6 créée automatiquement depuis Epic 23 description + docs/inventaire-multi-tables-ux-cibles.md
- 10 Acceptance Criteria détaillés couvrant flow complet selectedServerNames → API → renderFieldInput
- 13 Tasks avec 60+ subtasks couvrant types, hook, service, composants, tests, docs
- Référence complète Stories 23.1-23.5 (done) + Story 17.2, 20.4 (ExecutionWizard refactoring)
- Patterns de code complets avec exemples TypeScript/React
- Aucune modification backend requise (Story 23.3 déjà implémenté `server_names` query param)
- Rétrocompatibilité complète : actions existantes inchangées, params manual inchangés

#### Implémentation (2026-02-09)
- **useTargetInventory.ts** : `selectedServerNames` param ajouté à UseTargetInventoryOptions, cache invalidation via lastServerNamesRef, passage server_names à fetchInventoryItems pour instances/databases uniquement
- **execution_service.ts** : paramètre `options?: { server_names?: string[] }` ajouté à fetchInventoryItems, construction query string avec URLSearchParams
- **ExecutionWizard.tsx** : `selectedServerNames` calculé via useMemo depuis effectiveTargetNames, propagé à useTargetInventory et ParametersFormStep
- **ParametersFormStep.tsx** : prop `selectedServerNames` acceptée et propagée à renderFieldInput
- **renderFieldInput.tsx** : Alert info Ant Design si selectedServerNames vide pour instances/databases, Select disabled, notFoundContent dynamique pour liste vide après filtrage
- **ExecutionWizard.test.tsx** : 2 tests 503 cache adaptés (databases → servers) car Story 23.6 modifie le rendu des champs databases sans serveur sélectionné
- **Tests** : 101 tests passent (10 useTargetInventory + 4 execution_service + 23 renderFieldInput + 4 integration + 53 ExecutionWizard + 7 WorkflowStepsRenderer), 0 régression

### File List

**Frontend — Modifiés :**
- `frontend/src/hooks/useTargetInventory.ts` — selectedServerNames param, cache invalidation via lastServerNamesRef, passage server_names à fetchInventoryItems
- `frontend/src/services/execution_service.ts` — options param avec server_names ajouté à fetchInventoryItems, construction query string URLSearchParams
- `frontend/src/components/catalog/ExecutionWizard.tsx` — selectedServerNames calculé via useMemo depuis effectiveTargetNames, propagé au hook et ParametersFormStep
- `frontend/src/components/catalog/ParametersFormStep.tsx` — prop selectedServerNames acceptée et propagée à renderFieldInput
- `frontend/src/components/catalog/renderFieldInput.tsx` — selectedServerNames param, Alert info si vide pour instances/databases, notFoundContent dynamique
- `frontend/src/components/catalog/WorkflowStepsRenderer.tsx` — propagation selectedServerNames à renderFieldInput pour workflow steps (LOW-2 fix)
- `frontend/src/components/catalog/ExecutionWizard.test.tsx` — 2 tests 503 adaptés (databases → servers) pour compatibilité Story 23.6

**Frontend — Tests créés :**
- `frontend/src/hooks/useTargetInventory.test.ts` — +5 tests Story 23.6 (selectedServerNames passé, cache invalidé, rechargement, servers inchangé, empty)
- `frontend/src/services/__tests__/execution_service.test.ts` — 4 tests Story 23.6 (query string, rétrocompat, empty array, sans options)
- `frontend/src/components/catalog/renderFieldInput.test.tsx` — +5 tests Story 23.6 (Alert instances, Alert databases, pas Alert servers, Select avec items, notFoundContent)
- `frontend/src/components/catalog/ExecutionWizard.story23_6.test.tsx` — 4 tests intégration Story 23.6 (server_names vide, pas d'appel instances, Alert affiché, champ manual non impacté)

## Change Log

- **2026-02-09** : Implémentation complète Story 23.6 — selectedServerNames propagé de ExecutionWizard → useTargetInventory → fetchInventoryItems → API backend. Alert info pour instances/databases sans serveur sélectionné. 101 tests passent (41 Story 23.6 + 53 ExecutionWizard + 7 WorkflowStepsRenderer), 0 régression. 2 tests existants 503 cache adaptés (databases → servers).
- **2026-02-09 (Code Review)** : 10 issues fixées (4 HIGH + 4 MEDIUM + 2 LOW) — Alert title→message (Ant Design v6 API), cache key avec server_names (BUG critical fix), validation selectedServerNames, logging cache invalidation DEV mode, File List WorkflowStepsRenderer ajouté, commentaires français.

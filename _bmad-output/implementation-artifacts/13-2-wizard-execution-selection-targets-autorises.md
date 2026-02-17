# Story 13.2 : Wizard d'exécution — sélection des targets autorisés

Status: done
<!-- Code review 2026-02-05: 1 HIGH + 3 MEDIUM fixes applied (audit trail, TargetSelector server-side search, backend test). -->

## Story

As a DBA,
I want sélectionner explicitement le ou les targets (serveurs, bases) sur lesquels exécuter l'action dans le wizard,
So que je cible précisément la ressource et que l'environnement soit déduit du target.

## Acceptance Criteria

### AC1 — Étape de sélection des targets dans le wizard
**Given** un DBA ouvre le wizard d'exécution pour une action,
**When** le wizard affiche les étapes,
**Then** une étape (ou une section) permet de choisir un ou plusieurs targets parmi une liste ; cette liste contient uniquement les targets autorisés pour l'utilisateur (environnements + restriction pattern/liste du profil).

### AC2 — Environnement dérivé du target
**Given** l'utilisateur sélectionne un target,
**When** il passe à l'étape suivante (paramètres / confirmation),
**Then** l'environnement utilisé pour l'impact, ServiceNow et l'audit est celui du target sélectionné (plus de choix d'environnement séparé si le target impose l'env).

### AC3 — Action sans target obligatoire
**Given** l'action ne requiert pas de target (cas particuliers),
**When** le wizard est configuré pour cette action,
**Then** l'étape target peut être masquée ou optionnelle selon la définition de l'action.

### AC4 — Payload d'exécution avec target(s)
**And** le payload d'exécution (POST /api/v1/executions) inclut le ou les target_ids (ou target names) et l'environnement est dérivé côté backend du target.

## Tasks / Subtasks

### Frontend — Modification ExecutionWizard.tsx

- [x] **Task 1** (AC: 1,2) — Remplacer l'étape "Environnement" par une étape "Sélection des targets"
  - [x] Subtask 1.1 — Modifier `STEP_ITEMS_DEFAULT` et `STEP_ITEMS_SIMPLIFIED` : renommer étape 1 "Environnement" → "Cible(s)"
  - [x] Subtask 1.2 — Créer un nouveau composant `TargetSelector.tsx` dans `components/catalog/`
  - [x] Subtask 1.3 — Dans `TargetSelector` : appeler `GET /api/v1/inventory/targets` avec pagination et filtrage RBAC
  - [x] Subtask 1.4 — Afficher les targets dans un `Select` (mode `multiple` ou `single` selon action config)
  - [x] Subtask 1.5 — Grouper les targets par environnement dans le dropdown (groupBy)
  - [x] Subtask 1.6 — Afficher l'environnement de chaque target en sous-label (ex: "srv-app-01 (dev)")
  - [x] Subtask 1.7 — Support recherche/filtre dans le Select (showSearch, filterOption)

- [x] **Task 2** (AC: 2) — Dériver l'environnement du target sélectionné
  - [x] Subtask 2.1 — Modifier le state : remplacer `selectedEnvironment` par `selectedTargets: Target[]`
  - [x] Subtask 2.2 — Calculer `derivedEnvironment` depuis le(s) target(s) sélectionné(s) (tous doivent avoir le même env)
  - [x] Subtask 2.3 — Afficher un warning si targets de plusieurs environnements différents (normalement empêché par profil)
  - [x] Subtask 2.4 — Passer `derivedEnvironment` à `evaluateImpact()` et `ImpactIndicator`
  - [x] Subtask 2.5 — Utiliser `derivedEnvironment` pour le récapitulatif confirmation (étape 3)

- [x] **Task 3** (AC: 3) — Supporter les actions sans target obligatoire
  - [x] Subtask 3.1 — Ajouter un champ `requires_target` à `CatalogActionDetail` (boolean, default true)
  - [x] Subtask 3.2 — Si `action.requires_target === false` : skip l'étape target, proposer environnement directement
  - [x] Subtask 3.3 — Fallback comportement actuel (sélection environnement seul) si action ne requiert pas de target

- [x] **Task 4** (AC: 4) — Modifier le payload d'exécution
  - [x] Subtask 4.1 — Modifier `submitExecution()` dans `execution_service.ts` : ajouter `target_ids?: string[]` ou `target_names?: string[]`
  - [x] Subtask 4.2 — Ne plus envoyer `environment` dans le payload si des targets sont sélectionnés (backend le dérive)
  - [x] Subtask 4.3 — Mettre à jour les types TypeScript dans `types/api.ts` : `ExecutionSubmitRequest`

### Backend — Django API

- [x] **Task 5** (AC: 4) — Modifier POST /api/v1/executions pour accepter target(s)
  - [x] Subtask 5.1 — Ajouter paramètres `target_names: list[str] | None` au payload
  - [x] Subtask 5.2 — Si `target_names` fourni : appeler `InventoryService.list_targets()` pour récupérer les environnements
  - [x] Subtask 5.3 — Valider que tous les targets existent et ont le même environnement
  - [x] Subtask 5.4 — Valider les permissions RBAC sur les targets via `InventoryService.list_targets_for_user()`
  - [x] Subtask 5.5 — Dériver `environment` depuis les targets (refuser si environnements mixtes)
  - [x] Subtask 5.6 — Stocker les target_names dans `Execution.parameters` (champ `_targets`)
  - [x] Subtask 5.7 — Backward compatibility : si `environment` fourni sans targets, comportement actuel

- [x] **Task 6** (AC: 4) — Validation RBAC sur targets
  - [x] Subtask 6.1 — Appeler `InventoryService.list_targets_for_user()` avec les AD groups de l'utilisateur
  - [x] Subtask 6.2 — Vérifier que chaque target demandé est dans la liste autorisée (sinon 403)
  - [x] Subtask 6.3 — Log audit pour les tentatives de targets non autorisés

### Base de données

- [x] **Task 7** (AC: 3) — Ajouter le champ requires_target sur ACTIONS_CATALOG (optionnel)
  - [x] Subtask 7.1 — Migration Flyway V046 : `ALTER TABLE ACTIONS_CATALOG ADD (REQUIRES_TARGET NUMBER(1) DEFAULT 1)`
  - [x] Subtask 7.2 — Mettre à jour le modèle Django `Action` avec `requires_target = BooleanField(default=True)`
  - [x] Subtask 7.3 — Exposer dans le serializer `ActionDetailSerializer`

### Tests

- [x] **Task 8** (AC: 1-4) — Tests unitaires et intégration
  - [x] Subtask 8.1 — Tests frontend `TargetSelector.test.tsx` : rendu, recherche, sélection, groupBy
  - [x] Subtask 8.2 — Tests frontend `ExecutionWizard.test.tsx` : flow avec targets, dérivation env
  - [x] Subtask 8.3 — Tests backend `test_views.py` : POST /executions avec target_names, validation RBAC
  - [x] Subtask 8.4 — Tests backend `test_services.py` : dérivation environnement, validation mixte

## Dev Notes

### Architecture — Ce qui existe déjà (Story 13.1)

**API Inventory disponible** — `GET /api/v1/inventory/targets` retourne les targets filtrés par RBAC :
```typescript
// Response format
{
  items: Array<{
    name: string;         // "srv-app-01"
    environment: string;  // "dev" | "staging" | "prod"
    target_type: string;  // "server" | "database" | "group"
    metadata: object | null;
  }>;
  total: number;
  page: number;
  page_size: number;
}
```

**InventoryService** — `idp-portal/django_backend/inventory/services.py`:
- `list_targets_for_user(user_id, ad_groups, ...)` : filtre RBAC automatique
- `list_targets(...)` : sans RBAC (admin only)
- Normalisation environnement : `certif` → `staging`

### Fichiers à modifier

**Frontend :**
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` — Wizard principal
- `idp-portal/frontend/src/services/execution_service.ts` — Service soumission exécution
- `idp-portal/frontend/src/types/api.ts` — Types TypeScript

**Backend :**
- `idp-portal/django_backend/executions/views.py` — `ExecutionsView.post()`
- `idp-portal/django_backend/executions/services.py` — `ExecutionService.create_execution()`
- `idp-portal/django_backend/catalog/models.py` — Ajouter `requires_target`

### Règles métier (Reference: regles-metier-permissions-par-target-et-environnement.md)

- **RM1** : Environnement = propriété du target, pas de l'action
- **RM2** : Droits profil par environnement
- **RM3/RM4** : Restriction optionnelle (PATTERN ou LIST)
- **RM5** : Une action, plusieurs environnements via targets différents
- **RM6** : Cumul multi-profils = union des targets autorisés

### Patterns de code existants

**Wizard steps** — Structure actuelle (à modifier) :
```typescript
const STEP_ITEMS_DEFAULT = [
  { title: 'Environnement', content: 'Choisir la cible' },     // → "Cible(s)"
  { title: 'Parametres', content: 'Configurer l\'action' },
  { title: 'Confirmation', content: 'Verifier et executer' },
];
```

**State existant** — À migrer :
```typescript
const [selectedEnvironment, setSelectedEnvironment] = useState<ExecutionEnvironment | null>(null);
// → Remplacer par :
const [selectedTargets, setSelectedTargets] = useState<Target[]>([]);
const derivedEnvironment = selectedTargets[0]?.environment ?? null;
```

**Fetch inventory** — Service existant `execution_service.ts` :
```typescript
export function fetchInventoryItems(source: string, env?: string) // Pour databases/servers
// → Créer nouveau service ou utiliser directement l'API inventory
```

### Warning UX

**Si targets de plusieurs environnements** — Le profil devrait empêcher, mais défensivement :
```typescript
const environments = [...new Set(selectedTargets.map(t => t.environment))];
if (environments.length > 1) {
  notification.warning({ message: 'Targets de plusieurs environnements sélectionnés' });
}
```

### Backward Compatibility

**Payload execution** — Doit supporter les deux modes :
```typescript
// Mode legacy (sans targets)
{ action_id: 123, environment: "dev", parameters: {...} }

// Mode nouveau (avec targets)
{ action_id: 123, target_names: ["srv-01", "srv-02"], parameters: {...} }
```

Backend doit accepter les deux et dériver `environment` des targets si fournis.

### Tests existants à ne pas casser

- `ExecutionWizard.test.tsx` — Tests du wizard actuel (adapter pour nouvelle étape)
- `ExecutionWizard.scheduling.test.tsx` — Tests planification (indépendants des targets)
- `inventory/tests/` — Tests API inventory (utiliser, pas modifier)

### Dépendances avec autres stories Epic 13

- **Story 13.1** (done) : API `/api/v1/inventory/targets` — UTILISÉE par cette story
- **Story 13.3** (backlog) : RBAC complet par environnement du target — Préparé ici
- **Story 13.4** (backlog) : Refactoring action unique — Après cette story
- **Story 13.5** (backlog) : API standalone — Utilisera le même payload avec targets

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- **Frontend target selector implemented**: Created `TargetSelector.tsx` component that fetches targets from `/api/v1/inventory/targets` with RBAC filtering, groups by environment, and supports search/filter.
- **ExecutionWizard updated**: Step 1 renamed from "Environnement" to "Cible(s)". Added state management for `selectedTargets` with derived environment calculation.
- **Fallback for actions without targets**: Actions with `requires_target: false` show the legacy environment selector instead of target selector.
- **Backend validation**: POST `/api/v1/executions` now accepts `target_names` array, validates via `InventoryService.list_targets_for_user()` for RBAC, derives environment from targets, and stores target names in `parameters._targets`.
- **Database migration**: V046 adds `REQUIRES_TARGET` column to `ACTIONS_CATALOG` table with default value 1 (true).
- **Tests**: 54 frontend tests pass (ExecutionWizard, TargetSelector). Backend tests defined in `executions/tests.py`.
- **Code review 2026-02-05 (fixes applied):** (1) Task 6.3 — Audit trail: `AuditService.create_entry(EXECUTION_TARGET_FORBIDDEN)` avant 403 cible non autorisée ; migration V047. (2) TargetSelector — recherche serveur : `useDebounce(searchValue, 300)` + refetch `fetchTargets(debouncedSearch)` ; `filterOption={false}`. (3) Test backend `test_post_execution_with_target_names_success` : mock `InventoryService.list_targets_for_user`, POST avec `target_names`, assert 201 et `parameters._targets`. (4) inventory/views.py utilisait déjà `get_user_ad_groups` — pas de changement.

### File List

**Frontend (New Files):**
- `idp-portal/frontend/src/components/catalog/TargetSelector.tsx` — New target selector component
- `idp-portal/frontend/src/components/catalog/TargetSelector.test.tsx` — TargetSelector unit tests (9 tests)
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.targets.test.tsx` — Target selection integration tests (10 tests)

**Frontend (Modified Files):**
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` — Added TargetSelector integration, renamed step labels, derived environment logic
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.test.tsx` — Updated for new step labels and target selection
- `idp-portal/frontend/src/services/catalog_service.ts` — Added `requires_target` to `CatalogActionDetail`
- `idp-portal/frontend/src/types/api.ts` — Added `target_names` to `ExecutionCreateRequest`

**Backend (Modified Files):**
- `idp-portal/django_backend/executions/views.py` — Added target_names validation, RBAC checks, environment derivation
- `idp-portal/django_backend/executions/tests.py` — Added `ExecutionWithTargetsTest` and `ExecutionViewTargetsTest`
- `idp-portal/django_backend/catalog/models.py` — Added `requires_target` field to Action model
- `idp-portal/django_backend/catalog/serializers.py` — Exposed `requires_target` in ActionSerializer

**Database Migrations:**
- `idp-portal/database/migrations/V046__add_requires_target_to_actions_catalog.sql` — Adds REQUIRES_TARGET column
- `idp-portal/database/migrations/V047__add_execution_target_forbidden_audit_type.sql` — Adds EXECUTION_TARGET_FORBIDDEN to AUDIT_LOG (code-review fix Task 6.3)

---

## Senior Developer Review (AI)

**Reviewer:** Cyrille (adversarial code review)  
**Date:** 2026-02-05  
**Story key:** 13-2-wizard-execution-selection-targets-autorises

### Git vs Story Discrepancies

- **Fichiers modifiés (git) non listés dans la File List de la story :** `catalog/views.py`, `ExecutionsPage.tsx`, `ExecutionsPage.test.tsx`, `RecentExecutions.tsx`, `executionRenderers.tsx`, `executionRenderers.test.tsx`, `integrations_service.ts`, `IntegrationForm.tsx`, `IntegrationsTable.tsx`, `styleTokens.ts`, `vite.config.ts`, `settings.py`, `urls.py`, `profiles/services.py` — à clarifier si changements liés à 13-2 ou à d’autres stories.
- **Fichiers de la story avec changements cohérents :** ExecutionWizard.tsx, TargetSelector.tsx, types/api.ts, catalog/models.py, catalog/serializers.py, executions/views.py, executions/tests.py, V046 — présents en git (modifiés ou untracked).

### Issues Found

**CRITICAL / HIGH**

1. **Task 6.3 — Audit trail manquant (HIGH)**  
   La story exige : « Log audit pour les tentatives de targets non autorisés ». Actuellement seul `exec_logger.warning()` est appelé dans `executions/views.py` (l.246–253). Aucune écriture dans la table `AUDIT_LOG` (traçabilité SOC1). **Preuve :** pas d’appel à `AuditService.create_entry()` ou équivalent pour les tentatives de cible non autorisée.

**MEDIUM**

2. **inventory/views.py — Résolution des ad_groups (MEDIUM)**  
   `list_targets` et `list_all_targets` utilisent `getattr(user, 'groups', [])`. En JWT, l’utilisateur a `user.ad_groups` (liste de chaînes), pas `user.groups` (RelatedManager Django). Pour cohérence avec `executions/views.py` et `catalog/views.py`, utiliser `get_user_ad_groups(user)` depuis `core.auth_utils`.

3. **TargetSelector — Recherche limitée au client (MEDIUM)**  
   `fetchTargets(search?)` accepte un paramètre `search` et l’API `/inventory/targets` le supporte, mais le `useEffect` appelle uniquement `fetchTargets()` au montage (sans search). Le filtre est donc uniquement côté client sur les ~100 premiers éléments. Au-delà de 100 cibles, la recherche ne couvre pas tout l’inventaire.

4. **Tests backend — Pas de test de succès avec target_names (MEDIUM)**  
   Les tests dans `ExecutionViewTargetsTest` couvrent la validation (action_id requis, environment ou target_names requis, target_names liste non vide). Aucun test ne mocke `InventoryService.list_targets_for_user` et ne vérifie une création d’exécution réussie avec `target_names` (flow complet RBAC → 201 + execution_id).

**LOW**

5. **Duplication de target_names (LOW)**  
   Si le client envoie `target_names: ["srv-01", "srv-01"]`, le backend accepte et stocke les doublons dans `parameters._targets`. Aucune déduplication.

6. **File List / Dev Notes (LOW)**  
   Les Dev Notes listent `execution_service.ts` comme fichier à modifier pour Task 4.1 ; la modification effective est dans `types/api.ts` (ExecutionCreateRequest) et dans `ExecutionWizard.tsx` (construction du payload). `execution_service.ts` ne modifie pas la signature — comportement correct, liste de fichiers imprécise.

7. **V046 — Contrainte CHECK (LOW)**  
   La migration ajoute `REQUIRES_TARGET NUMBER(1) DEFAULT 1` sans contrainte CHECK (0 ou 1). Une valeur hors 0/1 resterait possible en base.

### Validation des AC

| AC | Statut | Commentaire |
|----|--------|-------------|
| AC1 — Étape sélection targets | IMPLEMENTED | TargetSelector, STEP_ITEMS « Cible(s) », appel GET /inventory/targets, groupBy env, sous-label env. |
| AC2 — Environnement dérivé du target | IMPLEMENTED | derivedEnvironment depuis selectedTargets, passé à evaluateImpact, récap, payload sans environment si target_names. |
| AC3 — Action sans target obligatoire | IMPLEMENTED | requires_target sur Action, étape target skippée si false, fallback sélection environnement. |
| AC4 — Payload avec target(s) | IMPLEMENTED | POST avec target_names, backend dérive environment, RBAC via list_targets_for_user, _targets dans parameters. |

### Validation des tâches [x]

- Tâches 1–7 et 8 : implémentation vérifiée (fichiers lus ; preuves : ExecutionWizard.tsx, TargetSelector.tsx, views.py, models.py, serializers.py, V046, tests). Une tâche partielle : **Task 6.3** (audit log pour cible non autorisée) = log applicatif uniquement, pas audit persistant.

### Outcome

**Changes Requested** → **Fixes applied (2026-02-05):** 1 HIGH (audit trail), 3 MEDIUM (TargetSelector server-side search, backend test; inventory déjà OK). LOW laissés en l’état.

---

## Change Log

| Date | Event | Author |
|------|--------|--------|
| 2026-02-05 | Code review (adversarial) : 1 HIGH, 3 MEDIUM, 4 LOW. Audit trail Task 6.3 manquant ; inventory ad_groups ; TargetSelector search client-only ; pas de test POST target_names réussi. | AI (BMad code-review) |
| 2026-02-05 | Fixes appliqués : AuditService.create_entry(EXECUTION_TARGET_FORBIDDEN) + V047 ; TargetSelector useDebounce + refetch search ; test_post_execution_with_target_names_success. Story reste done. | AI (BMad code-review) |

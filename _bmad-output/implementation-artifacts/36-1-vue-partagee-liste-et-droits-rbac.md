# Story 36.1 : Vue partagée — Liste et droits RBAC

Status: done

## Story

En tant qu'utilisateur du portail (DBA, DBOPS ou autre profil),
je veux que l'onglet « Toutes les exécutions » affiche toutes les exécutions auxquelles j'ai accès selon mes droits RBAC (y compris celles lancées par d'autres utilisateurs),
afin de suivre l'activité collective sur les actions et environnements que je suis autorisé à consulter.

## Acceptance Criteria

1. **Given** je suis connecté avec n'importe quel profil
   **When** j'ouvre la page Exécutions
   **Then** l'onglet « Toutes les exécutions » est visible pour tous les utilisateurs (pas seulement DBA/DBOPS)

2. **Given** je suis connecté et j'ai accès à certaines actions via mon profil RBAC
   **When** j'ouvre l'onglet « Toutes les exécutions »
   **Then** je vois toutes les exécutions pour les actions auxquelles mon profil me donne accès, y compris celles lancées par d'autres utilisateurs
   **And** je ne vois pas les exécutions sur des actions auxquelles je n'ai pas accès

3. **Given** je suis DBA ou DBOPS
   **When** j'ouvre l'onglet « Toutes les exécutions »
   **Then** je vois toutes les exécutions sans restriction (comportement actuel inchangé)

4. **Given** la liste des exécutions en scope=all
   **When** j'affiche le tableau
   **Then** la colonne « Utilisateur » est visible et indique qui a lancé chaque exécution
   **And** la valeur de fallback est « Utilisateur inconnu » si `user_display_name` est null

5. **Given** je consulte l'onglet « Mes exécutions »
   **When** j'affiche le tableau
   **Then** je vois uniquement mes propres exécutions (comportement actuel inchangé)

6. **Given** l'API backend reçoit `scope=all` d'un utilisateur non-DBA/DBOPS
   **When** l'utilisateur a des permissions sur des actions spécifiques (via ses profils RBAC)
   **Then** le backend retourne les exécutions filtrées par `action_id__in=<action_ids_autorisés>`
   **And** le `effective_scope` retourné est `"all"` (pas de fallback silencieux vers `"mine"`)

7. **Given** l'API backend reçoit `scope=all` d'un utilisateur avec aucune permission d'action
   **When** `get_allowed_action_ids_for_user()` retourne un `set` vide
   **Then** le backend retourne une liste vide (0 exécutions)

## Tasks / Subtasks

- [x] **Task 1 — Backend : modifier `apply_scope_filter()`** (AC: #2, #3, #6, #7)
  - [x] 1.1 Modifier `executions/utils/filters.py` : pour `scope=all` sur utilisateur non-DBA/DBOPS, appeler `get_allowed_action_ids_for_user(user)` et filtrer `qs.filter(action_id__in=allowed_ids)` si résultat est un `set`
  - [x] 1.2 Si `get_allowed_action_ids_for_user()` retourne `None` → pas de filtre (accès complet)
  - [x] 1.3 Ne plus faire de fallback silencieux vers `"mine"` : retourner `("all", qs_filtered)` dans tous les cas `scope=all`
  - [x] 1.4 Supprimer la logique `can_view_all = profile_str in IsDBAOrDBOPS.ADMIN_PROFILES` pour le scope (garder pour d'autres usages éventuels)

- [x] **Task 2 — Backend : tests `apply_scope_filter()`** (AC: #2, #3, #6, #7)
  - [x] 2.1 Modifier `test_all_scope_for_non_dba_falls_back_to_mine` → doit maintenant refléter le filtrage par action IDs (non fallback 'mine')
  - [x] 2.2 Ajouter `test_all_scope_for_non_dba_with_specific_action_permissions` : mock `get_allowed_action_ids_for_user` retourne `{1, 2, 3}` → `qs.filter(action_id__in={1,2,3})` appelé
  - [x] 2.3 Ajouter `test_all_scope_for_non_dba_with_all_access_permission` : mock retourne `None` → aucun filtre appliqué
  - [x] 2.4 Ajouter `test_all_scope_for_non_dba_with_empty_permissions` : mock retourne `set()` → `qs.filter(action_id__in=set())` appelé (résultat vide)
  - [x] 2.5 Ajouter `test_all_scope_returns_all_as_effective_scope_for_any_user` : vérifier que `effective_scope == "all"` même pour non-DBA

- [x] **Task 3 — Frontend : rendre « Toutes les exécutions » accessible à tous** (AC: #1, #4)
  - [x] 3.1 `ExecutionsPage.tsx` : séparer `canViewAll` de `canApprove`. `canApprove` reste inchangé (DBA/DBOPS uniquement). `canViewAll = true` pour tous les utilisateurs authentifiés
  - [x] 3.2 Mettre à jour la logique de sync du scope (useEffect ligne 72-77) : supprimer la condition qui force les non-DBA vers `scope=mine`, le scope par défaut devient `all` pour tous
  - [x] 3.3 `ExecutionsTabs.tsx` : passer `canViewAll={true}` systématiquement, ou modifier le composant pour ne plus conditionner l'affichage des deux onglets sur `canViewAll`

- [x] **Task 4 — Frontend : tests** (AC: #1, #4, #5)
  - [x] 4.1 `ExecutionsTabs.test.tsx` : vérifier que les deux onglets s'affichent même avec `canViewAll=false` (comportement mis à jour)
  - [x] 4.2 `ExecutionsPage.test.tsx` : vérifier que la page initialise le scope à `all` pour un utilisateur non-DBA
  - [x] 4.3 Vérifier que la colonne « Utilisateur » apparaît dans le tableau quand scope=all

## Dev Notes

### Analyse de l'état actuel

**Le problème :** `apply_scope_filter()` fait un fallback silencieux `scope=all → scope=mine` pour les utilisateurs non-DBA/DBOPS. L'onglet « Toutes les exécutions » est masqué pour ces mêmes utilisateurs.

**Ce qui doit changer :** La visibilité des exécutions doit suivre le même modèle RBAC que le catalogue — pas un contrôle admin-only, mais un filtre par les actions auxquelles l'utilisateur a accès.

### Fichier critique — `apply_scope_filter()` actuel

**Chemin :** `idp-portal/django_backend/executions/utils/filters.py` lignes 102–119

```python
def apply_scope_filter(qs, *, user, scope):
    scope = (scope or "mine").lower()
    # ACTUEL (à modifier) :
    profile_str = (getattr(user, 'profile', '') or '').lower()
    can_view_all = profile_str in IsDBAOrDBOPS.ADMIN_PROFILES
    effective_scope = scope if (scope == "mine" or can_view_all) else "mine"
    if effective_scope == "mine":
        qs = qs.filter(user_id=user.id)
    return qs, effective_scope
```

**Implémentation cible :**

```python
def apply_scope_filter(qs, *, user, scope):
    scope = (scope or "mine").lower()
    if scope not in ("mine", "all"):
        raise BadRequestError(code="BAD_REQUEST", message="scope invalide", details={"scope": scope})

    if scope == "mine":
        qs = qs.filter(user_id=user.id)
        return qs, "mine"

    # scope == "all" : vérifier si admin ou filtrer par RBAC
    profile_str = (getattr(user, 'profile', '') or '').lower()
    is_admin = profile_str in IsDBAOrDBOPS.ADMIN_PROFILES
    if is_admin:
        # Admins voient tout
        return qs, "all"

    # Utilisateurs non-admin : filtrer par leurs action IDs autorisés
    allowed_ids = get_allowed_action_ids_for_user(user)
    if allowed_ids is None:
        # Cas 'all' access (actions_type='all' dans permissions)
        return qs, "all"
    # Set vide → aucune exécution visible
    qs = qs.filter(action_id__in=allowed_ids)
    return qs, "all"
```

**Import à ajouter** dans `filters.py` :
```python
from executions.utils.rbac_helpers import get_allowed_action_ids_for_user
```

> ⚠️ **Attention import circulaire** : `get_allowed_action_ids_for_user` est dans `executions/utils/rbac_helpers.py`. Le module `executions/utils/__init__.py` exporte déjà cette fonction. Utiliser l'import direct depuis `executions.utils.rbac_helpers` pour éviter tout cycle.

### Fichier `get_allowed_action_ids_for_user` (déjà implémenté)

**Chemin :** `idp-portal/django_backend/executions/utils/rbac_helpers.py` lignes 20–76

Comportement déjà implémenté :
- Retourne `None` → l'utilisateur a `actions_type='all'` dans ses permissions profil
- Retourne `set[int]` → IDs des actions autorisées (union de tous les profils)
- Retourne `set()` vide → aucune permission → aucune exécution visible
- En cas d'erreur ProfileService → retourne `set()` (fail secure)

Ce pattern est déjà utilisé dans `executions/views/scheduled_views.py` lignes 84–86 :
```python
allowed_action_ids = get_allowed_action_ids_for_user(request.user)
if allowed_action_ids is not None:
    qs = qs.filter(action_id__in=allowed_action_ids)
```

### Tests backend à modifier

**Chemin :** `idp-portal/django_backend/executions/tests/test_utils.py` — classe `TestApplyScopeFilter` (ligne 247+)

- `test_all_scope_for_non_dba_falls_back_to_mine` (ligne 268) : ce test **doit être mis à jour** — le comportement change. Le nouveau comportement est le filtrage par action IDs, pas le fallback vers 'mine'. Ce test doit mocker `get_allowed_action_ids_for_user` et vérifier le nouveau comportement.

### Fichiers frontend à modifier

**`ExecutionsPage.tsx`** — `idp-portal/frontend/src/pages/ExecutionsPage.tsx`

Lignes concernées :
```typescript
// Ligne 52–56 (ACTUEL) :
const canApprove = useMemo(() =>
  user?.profile?.toLowerCase() === 'dba' || user?.profile?.toLowerCase() === 'dbops',
  [user?.profile]
);
const canViewAll = canApprove;  // ← À changer

// NOUVEAU :
const canViewAll = true; // Tous les utilisateurs authentifiés voient l'onglet "Toutes"
// Le backend gère le filtrage RBAC
```

Lignes 72–77 (sync scope) — **à modifier** :
```typescript
// ACTUEL :
useEffect(() => {
  if (userHasChosenScope.current) return;
  if (authLoading) { if (activeScope !== 'mine') setActiveScope('mine'); return; }
  if (canViewAll && activeScope === 'mine') { setActiveScope('all'); return; }
  if (!canViewAll && activeScope === 'all') { setActiveScope('mine'); }
}, [...]);

// NOUVEAU : scope par défaut = 'all' pour tous (le backend filtre)
useEffect(() => {
  if (userHasChosenScope.current) return;
  if (authLoading) { if (activeScope !== 'all') setActiveScope('all'); return; }
  if (activeScope === 'mine') setActiveScope('all');
}, [authLoading, activeScope, setActiveScope, userHasChosenScope]);
```

**`ExecutionsTabs.tsx`** — `idp-portal/frontend/src/components/executions/ExecutionsTabs.tsx`

Lignes 38–43 : supprimer la condition `canViewAll` ou passer `true` systématiquement depuis `ExecutionsPage`.

```typescript
// NOUVEAU : montrer les deux onglets à tous (le backend filtre)
const items = [
  { key: 'all', label: 'Toutes les exécutions' },
  { key: 'mine', label: 'Mes exécutions' },
];
// Supprimer la prop canViewAll ou la garder pour d'autres usages
```

### Colonne « Utilisateur » — déjà implémentée conditionnellement

**Chemin :** `idp-portal/frontend/src/pages/executions/executionsColumns.tsx` lignes 135–144

La colonne `user_display_name` s'affiche déjà quand `activeScope === 'all'`. Avec les changements ci-dessus (scope par défaut = 'all'), elle sera visible par défaut pour tous. **Aucun changement nécessaire dans ce fichier.**

### Tests frontend à modifier

**`ExecutionsTabs.test.tsx`** — `idp-portal/frontend/src/components/executions/ExecutionsTabs.test.tsx`

Mettre à jour les tests qui vérifient que le tab "Toutes les exécutions" est caché pour `canViewAll=false`.

**`ExecutionsPage.test.tsx`** — `idp-portal/frontend/src/pages/ExecutionsPage.test.tsx`

Vérifier que le scope initial est `all` pour tous les profils utilisateurs.

### Pattern de mock pour les tests `apply_scope_filter` (backend)

```python
from unittest.mock import patch, MagicMock

class TestApplyScopeFilter(TestCase):
    def test_all_scope_for_non_dba_with_specific_action_permissions(self):
        user = MagicMock()
        user.id = 42
        user.profile = "business"
        qs = MagicMock()

        with patch(
            'executions.utils.filters.get_allowed_action_ids_for_user',
            return_value={1, 2, 3}
        ):
            result_qs, effective = apply_scope_filter(qs, user=user, scope="all")

        assert effective == "all"
        qs.filter.assert_called_once_with(action_id__in={1, 2, 3})
```

### Project Structure Notes

- Pas de nouvelle migration Django nécessaire (pas de changement de modèle)
- Pas de nouveau endpoint API nécessaire
- `apply_scope_filter` est utilisée dans 3 vues : `ExecutionsListView`, `ExecutionStatsView`, `ExecutionTimeSeriesView` → la modification s'applique à toutes

**Fichiers back-end à modifier :**
- `idp-portal/django_backend/executions/utils/filters.py`
- `idp-portal/django_backend/executions/tests/test_utils.py`

**Fichiers front-end à modifier :**
- `idp-portal/frontend/src/pages/ExecutionsPage.tsx`
- `idp-portal/frontend/src/components/executions/ExecutionsTabs.tsx`
- `idp-portal/frontend/src/components/executions/ExecutionsTabs.test.tsx`
- `idp-portal/frontend/src/pages/ExecutionsPage.test.tsx`

### References

- Epic 36 : `_bmad-output/planning-artifacts/epic-36-vue-executions-partagee-mise-a-jour-statut.md`
- Spec détaillée : `_bmad-output/planning-artifacts/spec-vue-executions-partagee-mise-a-jour-statut.md`
- `apply_scope_filter()` : `idp-portal/django_backend/executions/utils/filters.py#apply_scope_filter`
- `get_allowed_action_ids_for_user()` : `idp-portal/django_backend/executions/utils/rbac_helpers.py#L20`
- Tests existants scope : `idp-portal/django_backend/executions/tests/test_utils.py#L247`
- `ExecutionsTabs` : `idp-portal/frontend/src/components/executions/ExecutionsTabs.tsx`
- `executionsColumns` colonne Utilisateur : `idp-portal/frontend/src/pages/executions/executionsColumns.tsx#L135`
- Pattern scheduled_views (même usage `get_allowed_action_ids_for_user`) : `idp-portal/django_backend/executions/views/scheduled_views.py#L84`
- [Source: `_bmad-output/planning-artifacts/epic-36-vue-executions-partagee-mise-a-jour-statut.md` — Stories 36.1]
- [Source: `idp-portal/django_backend/executions/utils/filters.py#L102`]
- [Source: `idp-portal/frontend/src/pages/ExecutionsPage.tsx#L52-77`]

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

### Completion Notes List

### File List

### Completion Notes

Story 36.1 implémentée le 2026-02-23 par claude-sonnet-4-6.

**Backend (`filters.py`):** `apply_scope_filter()` révisée — plus de fallback silencieux `scope=all → scope=mine` pour les non-DBA/DBOPS. La logique RBAC utilise `get_allowed_action_ids_for_user()` : `None` → accès complet, `set` vide → liste vide, `set` d'IDs → `filter(action_id__in=...)`. `effective_scope` vaut toujours `"all"` pour `scope=all`.

**Backend (tests):** 8 tests `TestApplyScopeFilter` passent (51/51 `test_utils.py`). Test `test_all_scope_for_non_dba_falls_back_to_mine` remplacé par 4 nouveaux tests couvrant les cas RBAC.

**Frontend (`ExecutionsPage.tsx`):** `canViewAll = true` pour tous les utilisateurs authentifiés. useEffect de sync scope : default `all` pour tous (plus de condition `canViewAll`).

**Frontend (`ExecutionsTabs.tsx`):** Les deux onglets toujours affichés (suppression de la condition `canViewAll` sur les items). La prop `canViewAll` est conservée pour rétrocompatibilité.

**Tests frontend:** 78/78 tests passent (8 `ExecutionsTabs.test.tsx` + 70 `ExecutionsPage.test.tsx`). 4 tests mis à jour (ordre colonnes avec Utilisateur, scope=all par défaut).

### File List

- idp-portal/django_backend/executions/utils/filters.py
- idp-portal/django_backend/executions/tests/test_utils.py
- idp-portal/frontend/src/pages/ExecutionsPage.tsx
- idp-portal/frontend/src/components/executions/ExecutionsTabs.tsx
- idp-portal/frontend/src/components/executions/ExecutionsTabs.test.tsx
- idp-portal/frontend/src/pages/ExecutionsPage.test.tsx
- idp-portal/frontend/src/hooks/useExecutionsData.ts
- _bmad-output/implementation-artifacts/36-1-vue-partagee-liste-et-droits-rbac.md
- _bmad-output/implementation-artifacts/sprint-status.yaml

### Change Log

- 2026-02-23: Story 36.1 implémentée — RBAC-based scope filtering pour tous les utilisateurs. `apply_scope_filter()` utilise `get_allowed_action_ids_for_user()` pour les non-admins. Frontend: `canViewAll=true` + scope=all par défaut pour tous. 51 backend + 78 frontend tests passent.
- 2026-02-23: Code review (AI) — 3 corrections appliquées : (1) `useExecutionsData.ts` ajouté à la File List (changement critique non documenté : `activeScope` initialisé à `'all'`) ; (2) JSDoc `canViewAll` dans `ExecutionsTabs.tsx` marqué `@deprecated` (dead code rétrocompat) ; (3) test `test_all_scope_for_dbops` ajouté dans `TestApplyScopeFilter` pour couvrir AC3 côté backend. Statut → done.

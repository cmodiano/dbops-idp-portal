# Story 8.9: Tabs "Toutes les exécutions" et "Mes exécutions" sur la page Executions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBA,
I want voir toutes les exécutions auxquelles j'ai accès ou uniquement mes propres exécutions via des tabs,
So that je peux choisir entre une vue globale (pour supervision) ou une vue personnelle (pour mes actions).

## Acceptance Criteria

1. **AC1 - Tabs affichés au chargement**
   - **Given** un DBA accède à la page Executions
   - **When** la page se charge
   - **Then** deux tabs s'affichent : "Toutes les exécutions" et "Mes exécutions"

2. **AC2 - Tab "Toutes les exécutions"**
   - **Given** le DBA sélectionne le tab "Toutes les exécutions"
   - **When** la page se charge
   - **Then** la table affiche toutes les exécutions auxquelles l'utilisateur a accès selon les règles RBAC (même comportement que le Dashboard pour les exécutions récentes)

3. **AC3 - Tab "Mes exécutions"**
   - **Given** le DBA sélectionne le tab "Mes exécutions"
   - **When** la page se charge
   - **Then** la table affiche uniquement les exécutions de l'utilisateur connecté (comportement actuel de Story 4.8)

4. **AC4 - Changement de tab**
   - **Given** le DBA change de tab
   - **When** il passe de "Mes exécutions" à "Toutes les exécutions" (ou inversement)
   - **Then** la table se recharge avec les données correspondantes et la pagination se remet à la page 1

5. **AC5 - Conservation des filtres**
   - **Given** le DBA applique des filtres (tri, pagination)
   - **When** il change de tab
   - **Then** les filtres sont conservés (tri et pagination restent actifs)

6. **AC6 - RBAC pour utilisateurs non-DBA/DBOPS**
   - **Given** un utilisateur non-DBA/DBOPS accède à la page Executions
   - **When** la page se charge
   - **Then** seul le tab "Mes exécutions" est visible (pas de tab "Toutes les exécutions")

7. **AC7 - API backend avec paramètre scope**
   - **Given** l'API GET /api/v1/executions retourne les exécutions de l'utilisateur courant (comportement existant)
   - **When** le paramètre ?scope=all est utilisé
   - **Then** l'API retourne toutes les exécutions auxquelles l'utilisateur a accès selon RBAC (nouveau paramètre)

8. **AC8 - Filtrage RBAC backend**
   - **Given** le backend filtre les exécutions selon les permissions RBAC de l'utilisateur
   - **When** l'utilisateur n'est pas DBA ou DBOPS
   - **Then** le paramètre ?scope=all retourne uniquement les exécutions de l'utilisateur (même comportement que scope=mine)

9. **AC9 - Colonne "Utilisateur" dans le tab "Toutes les exécutions"**
   - **Given** le DBA consulte le tab "Toutes les exécutions"
   - **When** la table s'affiche
   - **Then** une colonne "Utilisateur" (user_display_name) est visible pour distinguer qui a lancé chaque exécution

## Tasks / Subtasks

### Backend

- [x] Task 1: Créer repository methods pour "Toutes les exécutions" (AC: #2, #7)
  - [x] 1.1 Créer `list_all_executions(limit, offset)` dans execution_repository.py
  - [x] 1.2 Query SQL qui retourne toutes les exécutions avec JOIN sur USERS pour user_display_name
  - [x] 1.3 Créer `count_all_executions()` pour pagination
  - [x] 1.4 Trier par CREATED_AT DESC (cohérent avec list_by_user)

- [x] Task 2: Modifier endpoint GET /executions pour supporter scope (AC: #7, #8)
  - [x] 2.1 Ajouter paramètre `scope: str = Query("mine", regex="^(mine|all)$")` dans executions.py
  - [x] 2.2 Si scope == "all" ET user est DBA/DBOPS → appeler list_all_executions() et count_all_executions()
  - [x] 2.3 Si scope == "all" ET user n'est PAS DBA/DBOPS → appeler list_by_user() (fallback sécurisé)
  - [x] 2.4 Si scope == "mine" → comportement actuel (list_by_user)
  - [x] 2.5 Documenter le paramètre scope dans la docstring de l'endpoint

- [x] Task 3: Tests backend pour scope (AC: #7, #8)
  - [x] 3.1 Test GET /executions?scope=mine retourne uniquement les exécutions de l'utilisateur
  - [x] 3.2 Test GET /executions?scope=all retourne toutes les exécutions pour DBA
  - [x] 3.3 Test GET /executions?scope=all retourne uniquement les exécutions de l'utilisateur pour client business (fallback RBAC)
  - [x] 3.4 Test count correct avec scope=all vs scope=mine
  - [x] 3.5 Test user_display_name présent dans les résultats pour scope=all

### Frontend

- [x] Task 4: Créer composant ExecutionsTabs (AC: #1, #6)
  - [x] 4.1 Créer `components/executions/ExecutionsTabs.tsx` inspiré de CategoryTabs
  - [x] 4.2 Définir type `ExecutionScope = 'all' | 'mine'`
  - [x] 4.3 Tabs: [{ key: 'all', label: 'Toutes les exécutions' }, { key: 'mine', label: 'Mes exécutions' }]
  - [x] 4.4 Props: `activeScope: ExecutionScope`, `onScopeChange: (scope) => void`, `canViewAll: boolean` (RBAC)
  - [x] 4.5 Condition d'affichage: si `canViewAll === false`, n'afficher que le tab "Mes exécutions"
  - [x] 4.6 Style cohérent avec CategoryTabs (theme, indicator, tabBarStyle)

- [x] Task 5: Intégrer ExecutionsTabs dans ExecutionsPage (AC: #1, #4)
  - [x] 5.1 Modifier `pages/ExecutionsPage.tsx`
  - [x] 5.2 Importer ExecutionsTabs
  - [x] 5.3 Ajouter state `activeScope: ExecutionScope` (défaut: 'mine')
  - [x] 5.4 Calculer `canViewAll` avec pattern RBAC existant (DBA/DBOPS)
  - [x] 5.5 Afficher ExecutionsTabs après la section PendingApprovals
  - [x] 5.6 Wrapper ExecutionsTabs dans un espace dédié (marginBottom: 16px)

- [x] Task 6: Gérer le changement de tab (AC: #4, #5)
  - [x] 6.1 Créer handler `handleScopeChange(scope: ExecutionScope)`
  - [x] 6.2 Mettre à jour `activeScope` state
  - [x] 6.3 Réinitialiser pagination (currentPage = 1)
  - [x] 6.4 Appeler `fetchExecutions()` avec le nouveau scope
  - [x] 6.5 Conserver le tri actuel (sortField, sortOrder)

- [x] Task 7: Modifier fetchExecutions pour utiliser scope (AC: #2, #3)
  - [x] 7.1 Ajouter paramètre `scope` dans l'appel à `listExecutions(limit, offset, scope)`
  - [x] 7.2 Modifier service `execution_service.ts` : ajouter paramètre optionnel `scope?: ExecutionScope`
  - [x] 7.3 Construire query string avec scope : `/executions?limit=${limit}&offset=${offset}&scope=${scope}`
  - [x] 7.4 Si scope non fourni, utiliser 'mine' par défaut (backward compatible)

- [x] Task 8: Ajouter colonne "Utilisateur" pour scope=all (AC: #9)
  - [x] 8.1 Modifier colonnes de la Table dans ExecutionsPage
  - [x] 8.2 Ajouter colonne "Utilisateur" conditionnelle : `if (activeScope === 'all') { ... }`
  - [x] 8.3 Afficher `record.user_display_name` (déjà présent dans ExecutionResponse)
  - [x] 8.4 Positionner la colonne après "Action" et avant "Environnement"
  - [x] 8.5 Gérer cas où user_display_name est null/undefined (fallback: "Utilisateur inconnu")

- [x] Task 9: Tests frontend pour ExecutionsTabs (AC: #1, #6)
  - [x] 9.1 Créer `components/executions/ExecutionsTabs.test.tsx`
  - [x] 9.2 Test affiche les deux tabs quand canViewAll=true
  - [x] 9.3 Test affiche uniquement "Mes exécutions" quand canViewAll=false
  - [x] 9.4 Test tab "mine" actif par défaut
  - [x] 9.5 Test onChange appelé avec le bon scope au clic
  - [x] 9.6 Test style cohérent avec dark/light theme

- [x] Task 10: Tests frontend pour ExecutionsPage avec tabs (AC: #1-#9)
  - [x] 10.1 Test ExecutionsTabs affiché pour DBA (canViewAll=true)
  - [x] 10.2 Test ExecutionsTabs affiche uniquement "Mes exécutions" pour client business
  - [x] 10.3 Test changement de tab appelle listExecutions avec scope correct
  - [x] 10.4 Test changement de tab réinitialise pagination (page 1)
  - [x] 10.5 Test changement de tab conserve le tri
  - [x] 10.6 Test colonne "Utilisateur" visible uniquement pour scope=all
  - [x] 10.7 Test colonne "Utilisateur" affiche user_display_name correct
  - [x] 10.8 Test API appelée avec scope=mine par défaut au mount
  - [x] 10.9 Test API appelée avec scope=all quand tab "Toutes les exécutions" actif

## Dev Notes

### Architecture et patterns à suivre

**Backend - Repository methods pour "Toutes les exécutions":**
```python
# Fichier: idp-portal/backend/app/repositories/execution_repository.py

async def list_all_executions(
    self,
    limit: int = 50,
    offset: int = 0,
) -> list[ExecutionResponse]:
    """List all executions (Story 8.9, DBA/DBOPS only).

    Args:
        limit: Maximum number of results
        offset: Offset for pagination

    Returns:
        List of ExecutionResponse ordered by created_at DESC
    """
    start_time = time.perf_counter()
    query = """
        SELECT E.ID, E.ACTION_ID, E.USER_ID, E.ENVIRONMENT, E.PARAMETERS,
               E.STATUS, E.SERVICENOW_CHANGE_ID, E.STARTED_AT, E.COMPLETED_AT, E.CREATED_AT,
               A.NAME AS ACTION_NAME, U.DISPLAY_NAME AS USER_DISPLAY_NAME,
               E.APPROVED_BY, E.APPROVED_AT, E.APPROVAL_COMMENT
        FROM EXECUTIONS E
        LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
        LEFT JOIN USERS U ON U.ID = E.USER_ID
        ORDER BY E.CREATED_AT DESC
        OFFSET :offset ROWS FETCH NEXT :limit ROWS ONLY
    """

    async with self.pool.acquire() as conn:
        cursor = await conn.cursor()
        await cursor.execute(query, {"offset": offset, "limit": limit})
        rows = await cursor.fetchall()
        await cursor.close()

    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info(
        "execution_repository.list_all_executions",
        extra={
            "limit": limit,
            "offset": offset,
            "rows_returned": len(rows),
            "elapsed_ms": round(elapsed, 2),
        },
    )

    return [_map_execution_row_to_response(r) for r in rows]

async def count_all_executions(self) -> int:
    """Return total number of all executions (Story 8.9, pagination support)."""
    start_time = time.perf_counter()
    query = "SELECT COUNT(*) FROM EXECUTIONS"

    async with self.pool.acquire() as conn:
        cursor = await conn.cursor()
        await cursor.execute(query)
        row = await cursor.fetchone()
        await cursor.close()

    count = row[0] if row else 0
    elapsed = (time.perf_counter() - start_time) * 1000
    logger.info(
        "execution_repository.count_all_executions",
        extra={"count": count, "elapsed_ms": round(elapsed, 2)},
    )

    return count
```

**Backend - Endpoint avec paramètre scope:**
```python
# Fichier: idp-portal/backend/app/api/v1/executions.py

@router.get("", response_model=None)
async def list_executions(
    user: UserProfile = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    scope: str = Query("mine", regex="^(mine|all)$"),  # Story 8.9: scope filter
) -> dict:
    """GET /api/v1/executions - List executions with scope filter (Story 4.1, 4.8, 8.9).

    Args:
        scope: "mine" for user's executions (default), "all" for all executions (DBA/DBOPS only)

    Returns:
        { "data": list[ExecutionResponse], "pagination": { page, page_size, total_count, total_pages } }
    """
    limit = min(max(1, limit), 100)
    offset = max(offset, 0)

    # Story 8.9: Determine if user can view all executions
    can_view_all = (user.profile or "").lower() in _EXECUTION_VIEW_ANY_PROFILES

    # Story 8.9: If scope=all and user is DBA/DBOPS, return all executions
    if scope == "all" and can_view_all:
        total_count = await execution_repository.count_all_executions()
        executions = await execution_repository.list_all_executions(
            limit=limit,
            offset=offset,
        )
    else:
        # Default behavior: return user's executions only
        total_count = await execution_repository.count_by_user(user_id=user.id)
        executions = await execution_repository.list_by_user(
            user_id=user.id,
            limit=limit,
            offset=offset,
        )

    page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    return {
        "data": [e.model_dump(mode="json") for e in executions],
        "pagination": {
            "page": page,
            "page_size": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        },
    }
```

**Frontend - Composant ExecutionsTabs:**
```typescript
// components/executions/ExecutionsTabs.tsx
import { Tabs } from 'antd';
import { useTheme } from '@/contexts/ThemeContext';

export type ExecutionScope = 'all' | 'mine';

export interface ExecutionsTabsProps {
  activeScope: ExecutionScope;
  onScopeChange: (scope: ExecutionScope) => void;
  canViewAll: boolean; // RBAC: true for DBA/DBOPS
}

export function ExecutionsTabs({
  activeScope,
  onScopeChange,
  canViewAll,
}: ExecutionsTabsProps) {
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';

  // Si l'utilisateur ne peut pas voir toutes les exécutions, afficher uniquement "Mes exécutions"
  const items = canViewAll
    ? [
        { key: 'all', label: 'Toutes les exécutions' },
        { key: 'mine', label: 'Mes exécutions' },
      ]
    : [{ key: 'mine', label: 'Mes exécutions' }];

  return (
    <Tabs
      activeKey={activeScope}
      onChange={(key) => onScopeChange(key as ExecutionScope)}
      items={items}
      style={{ marginBottom: 16 }}
      tabBarStyle={{
        borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid #e8e8e8',
      }}
      indicator={{
        size: (origin) => origin - 16,
        align: 'center',
      }}
    />
  );
}
```

**Frontend - Intégration dans ExecutionsPage:**
```typescript
// pages/ExecutionsPage.tsx - Modifications pour Story 8.9

import { ExecutionsTabs, ExecutionScope } from '@/components/executions/ExecutionsTabs';

export function ExecutionsPage() {
  const { user } = useAuth();
  const [activeScope, setActiveScope] = useState<ExecutionScope>('mine'); // Story 8.9

  // Story 8.9: Determine if user can view all executions
  const canViewAll =
    user?.profile?.toLowerCase() === 'dba' ||
    user?.profile?.toLowerCase() === 'dbops';

  // Story 8.9: Handler pour changement de scope
  const handleScopeChange = useCallback(
    (scope: ExecutionScope) => {
      setActiveScope(scope);
      setCurrentPage(1); // Reset pagination
      // fetchExecutions sera rappelé par useEffect avec le nouveau scope
    },
    []
  );

  // Modifier fetchExecutions pour utiliser scope
  const fetchExecutions = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const offset = (currentPage - 1) * PAGE_SIZE;

      // Story 8.9: Passer scope à l'API
      const result = await listExecutions(PAGE_SIZE, offset, activeScope);

      setExecutions(result.data);
      setTotalCount(result.pagination.total_count);
    } catch (err) {
      console.error('Failed to fetch executions:', err);
      setError('Impossible de charger les exécutions. Veuillez réessayer.');
      setExecutions([]);
    } finally {
      setLoading(false);
    }
  }, [currentPage, activeScope]); // Ajouter activeScope dans les dépendances

  // Story 8.9: Colonne "Utilisateur" conditionnelle
  const columns = useMemo(() => {
    const baseColumns = [
      {
        title: 'Action',
        dataIndex: 'action_name',
        key: 'action_name',
        sorter: true,
        render: (text: string) => text || 'Action inconnue',
      },
    ];

    // Story 8.9: Ajouter colonne "Utilisateur" uniquement pour scope=all
    if (activeScope === 'all') {
      baseColumns.push({
        title: 'Utilisateur',
        dataIndex: 'user_display_name',
        key: 'user_display_name',
        render: (text: string) => text || 'Utilisateur inconnu',
      });
    }

    baseColumns.push(
      {
        title: 'Environnement',
        dataIndex: 'environment',
        key: 'environment',
        render: (env: string) => <Tag color={getEnvColor(env)}>{env}</Tag>,
      },
      {
        title: 'Statut',
        dataIndex: 'status',
        key: 'status',
        render: (status: ExecutionStatus, record: ExecutionResponse) => (
          <ExecutionStatusTag status={status} record={record} />
        ),
      },
      // ... autres colonnes
    );

    return baseColumns;
  }, [activeScope]);

  return (
    <div className="executions-page">
      <Typography.Title level={2}>Exécutions</Typography.Title>

      {/* Pending Approvals Section - Story 8.8 */}
      {canApprove && pendingApprovals.length > 0 && (
        <Card
          id="pending-approvals"
          title={...}
          style={{ marginBottom: 24, borderColor: token.colorWarning }}
        >
          <PendingApprovalsList
            executions={pendingApprovals}
            loading={pendingApprovalsLoading}
            onActionComplete={handleApprovalComplete}
          />
        </Card>
      )}

      {/* Story 8.9: Tabs pour Toutes/Mes exécutions */}
      <ExecutionsTabs
        activeScope={activeScope}
        onScopeChange={handleScopeChange}
        canViewAll={canViewAll}
      />

      {/* Table des exécutions */}
      <Table
        columns={columns}
        dataSource={executions}
        loading={loading}
        pagination={{
          current: currentPage,
          pageSize: PAGE_SIZE,
          total: totalCount,
          onChange: setCurrentPage,
        }}
        // ... reste de la configuration
      />

      {/* Drawer with ExecutionTimeline */}
    </div>
  );
}
```

**Frontend - Service execution_service.ts:**
```typescript
// services/execution_service.ts - Modifications pour Story 8.9

export async function listExecutions(
  limit = 50,
  offset = 0,
  scope: 'all' | 'mine' = 'mine' // Story 8.9: nouveau paramètre
): Promise<ListExecutionsResponse> {
  return apiFetchRaw<ListExecutionsResponse>(
    `/executions?limit=${limit}&offset=${offset}&scope=${scope}`
  );
}
```

### Project Structure Notes

**Backend - Fichiers à modifier:**
- `idp-portal/backend/app/api/v1/executions.py` - Ajouter paramètre `scope` à GET /executions
- `idp-portal/backend/app/repositories/execution_repository.py` - Ajouter méthodes `list_all_executions()` et `count_all_executions()`
- `idp-portal/backend/tests/unit/test_executions_api.py` - Tests pour scope=all vs scope=mine

**Frontend - Fichiers à créer:**
- `idp-portal/frontend/src/components/executions/ExecutionsTabs.tsx` - Composant tabs scope
- `idp-portal/frontend/src/components/executions/ExecutionsTabs.test.tsx` - Tests du composant

**Frontend - Fichiers à modifier:**
- `idp-portal/frontend/src/pages/ExecutionsPage.tsx` - Intégrer ExecutionsTabs, gérer activeScope, colonne utilisateur conditionnelle
- `idp-portal/frontend/src/pages/ExecutionsPage.test.tsx` - Tests pour tabs et colonne utilisateur
- `idp-portal/frontend/src/services/execution_service.ts` - Ajouter paramètre `scope` à `listExecutions()`

**Types à mettre à jour:**
- `idp-portal/frontend/src/types/common.ts` - Ajouter type `ExecutionScope = 'all' | 'mine'` si nécessaire

### Intelligence de la story précédente (8.8)

**Patterns établis dans story 8-8:**
- PendingApprovalsList déplacé de Dashboard vers ExecutionsPage
- Icône BellOutlined dans TopNav avec Badge et polling 60s
- RBAC strict: DBA/DBOPS uniquement pour approvals
- Pattern de vérification profile: `user?.profile?.toLowerCase() === 'dba'`

**Learnings de code-review 8-8:**
- Design tokens au lieu de hardcoded colors (token.colorWarning, token.colorPrimary)
- Aria-label dynamique pour accessibilité
- Tests de polling avec setInterval mock
- Error handling avec tooltip pour fetch failures
- Scroll behavior avec getElementById et scrollIntoView
- Comprehensive test coverage (66/66 tests pass)

**Pattern de commit:** `feat(executions): move approvals to executions page and add notification bell to top bar (story 8-8)`

### Git Intelligence (commits récents)

```
e0ed14d feat(executions): move approvals to executions page and add notification bell to top bar (story 8-8)
e9f4845 feat(catalog): add category navigation with tabs and integrated horizontal filters (story 8-7)
38c5724 feat(analytics): add advanced comparison and analysis features for reporting dashboard (story 8-6)
4a38a97 feat(analytics): add CSV and PDF export for reporting dashboard (story 8-5)
15dd16c feat(analytics): add advanced filters for reporting dashboard (story 8-4)
```

**Observation:** Epic 8 suit un pattern cohérent de features UX incrémentales. Story 8.9 améliore la navigation et la supervision des exécutions avec un système de tabs.

### Décisions techniques

1. **Backend avec paramètre scope** - Approche retenue pour pagination correcte et performance optimale. Alternative filtrage côté client écartée (problème de pagination).

2. **RBAC centralisé backend** - Si utilisateur non-DBA/DBOPS demande scope=all, le backend retourne automatiquement scope=mine (fallback sécurisé). Pas d'erreur HTTP.

3. **Repository methods dédiés** - `list_all_executions()` et `count_all_executions()` séparés de `list_by_user()` pour clarté et maintenabilité.

4. **Colonne "Utilisateur" conditionnelle** - Ajoutée dynamiquement uniquement pour scope=all. Utilise `user_display_name` déjà disponible dans ExecutionResponse (JOIN avec table USERS).

5. **Réinitialisation pagination au changement de tab** - currentPage = 1 lors du changement de scope pour éviter confusion (page 5 de "Mes exécutions" pourrait être vide dans "Toutes les exécutions").

6. **Conservation du tri au changement de tab** - sortField et sortOrder maintenus pour cohérence UX. L'utilisateur garde son tri préféré entre les vues.

7. **Composant ExecutionsTabs inspiré de CategoryTabs** - Réutilisation du pattern Ant Design Tabs avec style cohérent (theme, indicator, tabBarStyle).

8. **Visibilité des tabs basée sur RBAC** - Si canViewAll=false, le composant ExecutionsTabs affiche uniquement "Mes exécutions". Pas de logique de masquage côté parent.

9. **Scope par défaut: "mine"** - Backward compatible. Si le paramètre scope n'est pas fourni à l'API, comportement actuel maintenu (mes exécutions).

10. **Query SQL avec JOIN USERS** - Pour obtenir user_display_name dans scope=all. Utilise LEFT JOIN pour gérer les exécutions orphelines (user supprimé).

### Architecture compliance

**API Patterns (architecture.md):**
- Endpoint sous /api/v1/executions
- Query param snake_case: `scope`
- Response wrapper: `{ "data": [...], "pagination": {...} }` (existant)
- RBAC via middleware (DBA/DBOPS pour scope=all)

**Frontend Patterns (architecture.md):**
- Composant dans components/executions/ExecutionsTabs.tsx
- Service dans services/execution_service.ts
- Page dans pages/ExecutionsPage.tsx
- Tests co-localisés (*.test.tsx)
- State management avec useState et useCallback

**UX Design Compliance (ux-design-specification.md):**
- Tabs Ant Design avec style cohérent (borderBottom, indicator)
- Thème dark/light supporté (useTheme hook)
- Skeleton loading pendant chargement
- Messages d'erreur clairs ("Impossible de charger les exécutions")
- ARIA: accessibilité native des Tabs Ant Design

**Ant Design 6.2 Patterns:**
- Tabs component pour navigation scope
- Table avec colonnes conditionnelles
- Tag pour environnement (cohérent avec existant)
- Typography.Title pour en-têtes
- Card pour section approvals (existant)

### Pattern RBAC détaillé

**Backend - Profils autorisés à voir toutes les exécutions:**
```python
# executions.py (lignes 46-62)
_EXECUTION_VIEW_ANY_PROFILES = frozenset({"dba", "dbops"})

def _can_view_execution(execution_user_id: int, user: UserProfile) -> bool:
    """True if user may view this execution (owner or DBA/DBOPS)."""
    if user.id == execution_user_id:
        return True
    return (user.profile or "").lower() in _EXECUTION_VIEW_ANY_PROFILES
```

**Frontend - Vérification profile:**
```typescript
// ExecutionsPage.tsx
const canViewAll =
  user?.profile?.toLowerCase() === 'dba' ||
  user?.profile?.toLowerCase() === 'dbops';
```

**Pattern de fallback sécurisé:**
- Si scope=all demandé par utilisateur non autorisé → backend retourne scope=mine automatiquement
- Pas d'erreur HTTP 403, pas de message d'erreur UI
- Comportement transparent pour l'utilisateur final
- Logs backend pour tracer les tentatives d'accès non autorisées

### Gestion des cas limites

- **Utilisateur non-DBA/DBOPS:** Voit uniquement le tab "Mes exécutions", scope=all ignoré par backend (fallback scope=mine)
- **Aucune exécution:** Empty state existant s'affiche, message "Aucune exécution trouvée"
- **user_display_name null:** Colonne "Utilisateur" affiche "Utilisateur inconnu" (cas edge: utilisateur supprimé de la table USERS)
- **Changement de tab avec page > 1:** Pagination réinitialisée à page 1 pour éviter confusion
- **Erreur API:** Message d'erreur existant affiché ("Impossible de charger les exécutions")
- **Tri actif lors changement de tab:** Tri conservé (sortField, sortOrder maintenus)
- **Scope invalide (ex: ?scope=invalid):** Backend regex validation rejette avec HTTP 422 (Ant Design Query validation)

### Performance considerations

**Query SQL optimization:**
```sql
-- scope=mine (comportement existant):
SELECT E.*, A.NAME AS ACTION_NAME FROM EXECUTIONS E
LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
WHERE E.USER_ID = :user_id
ORDER BY E.CREATED_AT DESC
-- Index existant sur USER_ID

-- scope=all (nouveau):
SELECT E.*, A.NAME AS ACTION_NAME, U.DISPLAY_NAME AS USER_DISPLAY_NAME
FROM EXECUTIONS E
LEFT JOIN ACTIONS_CATALOG A ON A.ID = E.ACTION_ID
LEFT JOIN USERS U ON U.ID = E.USER_ID
ORDER BY E.CREATED_AT DESC
-- Index sur CREATED_AT recommandé pour performance
```

**Cache consideration:**
- Pas de cache pour les exécutions (données temps réel)
- Pagination côté serveur (limit/offset) pour éviter chargement complet
- Table virtuelle Ant Design si > 1000 lignes (config existante)

**Impact backend:**
- scope=all pour DBA/DBOPS: 1 query supplémentaire avec JOIN USERS
- Charge additionnelle négligeable (< 10 DBA/DBOPS simultanés typiquement)
- Pagination limite à 50-100 résultats par requête

### Tests critiques

**Backend:**
- GET /executions?scope=mine retourne uniquement les exécutions de l'utilisateur
- GET /executions?scope=all retourne toutes les exécutions pour DBA/DBOPS
- GET /executions?scope=all retourne uniquement les exécutions de l'utilisateur pour client business (fallback RBAC)
- Count correct avec scope=all vs scope=mine
- user_display_name présent dans les résultats pour scope=all
- Validation regex: scope doit être "mine" ou "all" (HTTP 422 sinon)

**Frontend:**
- ExecutionsTabs affiche les deux tabs pour DBA/DBOPS
- ExecutionsTabs affiche uniquement "Mes exécutions" pour client business
- Changement de tab appelle listExecutions avec scope correct
- Changement de tab réinitialise pagination (page 1)
- Changement de tab conserve le tri
- Colonne "Utilisateur" visible uniquement pour scope=all
- Colonne "Utilisateur" affiche user_display_name correct
- Fallback "Utilisateur inconnu" si user_display_name null
- API appelée avec scope=mine par défaut au mount

### Compatibilité ascendante

**Backward compatibility garantie:**
- Si paramètre `scope` non fourni → comportement actuel (scope=mine implicite)
- Endpoint GET /executions existant fonctionne sans modification des clients
- Types TypeScript ExecutionResponse inchangés (user_display_name déjà présent)
- Tests existants passent sans modification (scope=mine par défaut)

### Alternatives considérées et rejetées

**Alternative 1: Filtrage côté client (comme CatalogPage)**
- Avantages: Pas de modification backend, simple
- Inconvénients: Pagination incorrecte, performance dégradée, UX confuse
- Rejetée: Pagination côté serveur obligatoire pour grande volumétrie

**Alternative 2: Endpoint séparé GET /executions/all**
- Avantages: Séparation claire des responsabilités
- Inconvénients: Duplication de code, plus de routes à maintenir
- Rejetée: Paramètre scope plus élégant et RESTful

**Alternative 3: WebSocket temps réel pour les exécutions**
- Avantages: Mise à jour instantanée
- Inconvénients: Complexité, pas nécessaire pour liste historique
- Rejetée: WebSocket réservé à ExecutionTimeline (timeline temps réel)

### Opportunités d'amélioration futures (post-MVP)

- **Filtrage avancé:** Date range, statut, environnement (Epic 8 Story 8.4 pattern)
- **Export CSV/PDF:** Exporter liste des exécutions avec filtres (Epic 8 Story 8.5 pattern)
- **Colonne "Utilisateur" triable:** Permettre tri par user_display_name
- **Recherche full-text:** Filtrer par nom d'action, utilisateur, paramètres
- **Badge count sur tabs:** Afficher nombre d'exécutions par tab (ex: "Mes exécutions (42)")
- **Refresh automatique:** Polling ou WebSocket pour mise à jour en temps réel de la liste

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Epic 8 Story 8.9 (lignes 2082-2119)]
- [Source: _bmad-output/planning-artifacts/architecture.md#API-Patterns]
- [Source: _bmad-output/planning-artifacts/architecture.md#Repository-Pattern]
- [Source: idp-portal/frontend/src/pages/ExecutionsPage.tsx - Page executions existante]
- [Source: idp-portal/frontend/src/components/catalog/CategoryTabs.tsx - Pattern tabs Story 8.7]
- [Source: idp-portal/backend/app/api/v1/executions.py - Endpoints executions]
- [Source: idp-portal/backend/app/repositories/execution_repository.py - Repository executions]
- [Source: _bmad-output/implementation-artifacts/8-8-deplacement-approbations-vers-page-executions-et-notification-top-bar.md - Intelligence story précédente]
- [Source: _bmad-output/implementation-artifacts/8-7-navigation-par-categories-avec-tabs-et-filtres-integres.md - Pattern CategoryTabs]
- [Source: _bmad-output/implementation-artifacts/4-8-historique-des-executions.md - Story executions originale]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

- Story created with comprehensive context from Epic 8 Story 8.9 in epics.md
- Analyzed ExecutionsPage current implementation (structure, state, RBAC, API calls)
- Reviewed CategoryTabs pattern from Story 8.7 for tabs implementation
- Analyzed backend executions.py router and execution_repository.py
- Determined backend approach: scope parameter with list_all_executions() method
- Reviewed RBAC patterns (backend _EXECUTION_VIEW_ANY_PROFILES, frontend canViewAll)
- Analyzed PendingApprovalsList integration from Story 8.8
- Created ExecutionsTabs component design inspired by CategoryTabs
- Defined conditional column "Utilisateur" for scope=all
- Mapped all 9 acceptance criteria to detailed tasks with subtasks
- Comprehensive Dev Notes with code examples for backend (repository, router) and frontend (tabs, page)
- Applied learnings from Story 8.8 (design tokens, RBAC patterns, polling, accessibility)
- Leveraged architecture patterns for API query params and repository methods
- Defined fallback sécurisé RBAC: scope=all pour non-DBA/DBOPS → retourne scope=mine
- Backward compatibility guaranteed: scope parameter optional (default "mine")
- Performance considerations: SQL JOIN optimization, pagination, no cache
- Tests critiques identifiés: backend RBAC fallback, frontend tabs visibility, colonne conditionnelle

**Implementation completed 2026-02-01:**
- Task 1: Added `list_all_executions()` and `count_all_executions()` methods to execution_repository.py with LEFT JOIN on USERS for user_display_name
- Task 2: Added `scope` Query parameter with regex validation to GET /executions endpoint; implements RBAC fallback (non-DBA/DBOPS requests scope=all → returns scope=mine silently)
- Task 3: Added 7 backend tests in TestListExecutionsScope class covering scope=mine, scope=all for DBA, RBAC fallback, count validation, and user_display_name presence
- Task 4: Created ExecutionsTabs.tsx component with RBAC-aware tab rendering (canViewAll prop)
- Tasks 5-8: Integrated ExecutionsTabs into ExecutionsPage, added activeScope state, handleScopeChange handler, conditional "Utilisateur" column for scope=all
- Task 9: Created ExecutionsTabs.test.tsx with 8 tests covering RBAC, tab switching, accessibility, and theme support
- Task 10: Added 9 tests to ExecutionsPage.test.tsx for Story 8.9 functionality; fixed ThemeProvider requirement by creating renderWithTheme helper
- All 41 frontend tests pass (8 ExecutionsTabs + 33 ExecutionsPage)
- All 7 new backend tests pass (32 total in test_execution_api.py, 2 pre-existing failures unrelated to this story)

### File List

**Files modified:**

Backend:
- `idp-portal/backend/app/api/v1/executions.py` - Added scope parameter to GET /executions endpoint with RBAC logic
- `idp-portal/backend/app/repositories/execution_repository.py` - Added list_all_executions() and count_all_executions() methods
- `idp-portal/backend/tests/unit/test_execution_api.py` - Added TestListExecutionsScope class with 7 tests

Frontend:
- `idp-portal/frontend/src/pages/ExecutionsPage.tsx` - Integrated ExecutionsTabs, added activeScope state, conditional "Utilisateur" column
- `idp-portal/frontend/src/pages/ExecutionsPage.test.tsx` - Added 9 tests for Story 8.9 + ThemeProvider wrapper fix
- `idp-portal/frontend/src/services/execution_service.ts` - Added scope parameter to listExecutions()

**Files created:**

Frontend:
- `idp-portal/frontend/src/components/executions/ExecutionsTabs.tsx` - Tabs component for scope selection with RBAC
- `idp-portal/frontend/src/components/executions/ExecutionsTabs.test.tsx` - 8 tests for ExecutionsTabs component

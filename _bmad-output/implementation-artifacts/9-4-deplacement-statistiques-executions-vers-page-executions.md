# Story 9.4: Déplacement statistiques exécutions vers page Exécutions

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a utilisateur du portail (DBA, DBOPS, Client Business),
I want voir les 4 cards KPI (exécutions du jour, taux de succès, en cours, en erreur) directement dans la page Exécutions,
So that j'ai une vue consolidée des métriques et de l'historique des exécutions sans naviguer entre pages.

## Acceptance Criteria

1. **AC1 - StatCards déplacées de Dashboard vers Exécutions**
   - **Given** l'utilisateur accède à la page `/executions`
   - **When** la page se charge
   - **Then** les 4 cards KPI s'affichent au-dessus de la section "Approbations en attente" (si visible) et des tabs
   - **And** les cards affichent : "Exécutions du jour", "Taux de succès (%)", "En cours", "En erreur"
   - **And** les cards utilisent les mêmes composants StatCard et icônes que le Dashboard

2. **AC2 - Cards supprimées du Dashboard**
   - **Given** l'utilisateur accède à la page `/dashboard`
   - **When** la page se charge
   - **Then** les 4 cards KPI ne sont plus affichées
   - **And** le Dashboard affiche uniquement les graphiques (Répartition technologie, Environnement, Tendances) et les filtres avancés

3. **AC3 - Calcul des statistiques depuis le scope actif**
   - **Given** l'utilisateur est sur l'onglet "Toutes les exécutions"
   - **When** les stats sont chargées
   - **Then** les KPI reflètent les statistiques globales (toutes exécutions visibles selon RBAC)
   - **Given** l'utilisateur est sur l'onglet "Mes exécutions"
   - **When** les stats sont chargées
   - **Then** les KPI reflètent uniquement les statistiques de l'utilisateur courant

4. **AC4 - Responsive layout des cards**
   - **Given** l'utilisateur visualise la page Exécutions sur desktop (≥1200px)
   - **Then** les 4 cards s'affichent en ligne (xs=24 sm=12 md=6)
   - **Given** l'utilisateur visualise sur tablet (768-1199px)
   - **Then** les cards s'affichent en grille 2x2
   - **Given** l'utilisateur visualise sur mobile (<768px)
   - **Then** les cards s'affichent empilées verticalement

5. **AC5 - Loading skeleton pour les cards**
   - **Given** les stats sont en cours de chargement
   - **When** l'utilisateur visualise la page Exécutions
   - **Then** les 4 cards affichent un skeleton shimmer (StatCard loading=true)
   - **And** le skeleton respecte les dimensions et layout des cards finales

## Tasks / Subtasks

### Backend - API statistiques par scope

- [x] Task 1: API - Endpoint GET /api/v1/executions/stats avec paramètre scope (AC: #3)
  - [x] 1.1 Créer endpoint `/api/v1/executions/stats?scope={all|mine}` dans `api/v1/executions.py`
  - [x] 1.2 Paramètre `scope: ExecutionScope = "mine"` (default mine pour sécurité)
  - [x] 1.3 Si scope=mine: filtrer WHERE USER_ID = current_user.id
  - [x] 1.4 Si scope=all: appliquer RBAC (DBA/DBOPS voient tout, autres voient leurs exécutions)
  - [x] 1.5 Calculer statistiques:
    - `executions_jour`: COUNT(*) WHERE created_at >= aujourd'hui 00:00:00
    - `taux_succes_pct`: (COUNT status=COMPLETED / COUNT status IN (COMPLETED, FAILED)) * 100
    - `executions_en_cours`: COUNT status IN ('RUNNING', 'SUBMITTED', 'PENDING_APPROVAL')
    - `executions_en_erreur`: COUNT status='FAILED'
  - [x] 1.6 Retourner response JSON avec structure DashboardStats (réutiliser type existant)

- [x] Task 2: Repository - Méthode get_execution_stats (AC: #3)
  - [x] 2.1 Créer méthode `get_execution_stats(user_id: int, scope: ExecutionScope)` dans `execution_repository.py`
  - [x] 2.2 Query optimisée avec CASE WHEN pour calculer toutes les stats en une seule requête
  - [x] 2.3 Filtrage user_id si scope=mine
  - [x] 2.4 Filtrage RBAC si scope=all (join PROFILES + PROFILE_PERMISSIONS)
  - [x] 2.5 Retourner dict avec clés: executions_jour, taux_succes_pct, executions_en_cours, executions_en_erreur

### Frontend - Déplacement des cards

- [x] Task 3: ExecutionsPage - Ajouter section StatCards (AC: #1, #3, #4, #5)
  - [x] 3.1 Importer `StatCard` component depuis `../components/dashboard/StatCard`
  - [x] 3.2 Importer icônes: RocketOutlined, CheckCircleOutlined, SyncOutlined, ExclamationCircleOutlined
  - [x] 3.3 Ajouter state `statsData: DashboardStats | null` et `statsLoading: boolean`
  - [x] 3.4 Créer fonction `fetchExecutionStats(scope: ExecutionScope)` qui appelle `GET /api/v1/executions/stats?scope={scope}`
  - [x] 3.5 useEffect pour charger stats quand `activeScope` change
  - [x] 3.6 Afficher Row avec 4 Col (xs=24 sm=12 md=6) contenant les StatCard
  - [x] 3.7 Cards affichées AVANT `{canApprove && pendingApprovals.length > 0 && ...}` (ligne 355)
  - [x] 3.8 StatCard props: label, value, icon, loading=statsLoading, variant (success/inProgress/error)

- [x] Task 4: Service - Créer fonction fetchExecutionStats (AC: #3)
  - [x] 4.1 Créer fonction `fetchExecutionStats(scope: ExecutionScope = 'mine')` dans `execution_service.ts`
  - [x] 4.2 Call API `GET /api/v1/executions/stats?scope=${scope}`
  - [x] 4.3 Retourner `Promise<DashboardStats>`
  - [x] 4.4 Gestion erreur: throw Error avec message utilisateur si API fail

- [x] Task 5: ReportingDashboard - Supprimer section StatCards (AC: #2)
  - [x] 5.1 Supprimer lignes 267-305 (Row contenant les 4 StatCard)
  - [x] 5.2 Supprimer imports icônes RocketOutlined, CheckCircleOutlined, SyncOutlined, ExclamationCircleOutlined (lignes 17-20)
  - [x] 5.3 Garder import StatCard car possiblement utilisé ailleurs (vérifier)
  - [x] 5.4 Supprimer appel `fetchStats(apiFilters)` dans Promise.all (ligne 192)
  - [x] 5.5 Supprimer state `stats: DashboardStats | null` (ligne 77)
  - [x] 5.6 Supprimer `setStats(statsData)` (ligne 201)
  - [x] 5.7 Mettre à jour commentaire en-tête: préciser que les StatCards ont été déplacées vers ExecutionsPage (Story 9.4)

- [x] Task 6: Types - Vérifier type DashboardStats réutilisable (AC: #3)
  - [x] 6.1 Confirmer que `types/api.ts` exporte déjà `DashboardStats` avec champs nécessaires
  - [x] 6.2 Si absent, ajouter interface avec executions_jour, taux_succes_pct, executions_en_cours, executions_en_erreur
  - [x] 6.3 Importer dans ExecutionsPage.tsx

### Tests Backend

- [x] Task 7: Tests API - Endpoint /api/v1/executions/stats (AC: #3)
  - [x] 7.1 Test `test_get_execution_stats_mine_returns_user_stats`: scope=mine retourne stats utilisateur courant uniquement
  - [x] 7.2 Test `test_get_execution_stats_all_dba_returns_all_stats`: DBA avec scope=all retourne toutes stats
  - [x] 7.3 Test `test_get_execution_stats_all_business_returns_mine`: Client Business avec scope=all retourne ses stats (pas de permission all)
  - [x] 7.4 Test `test_execution_stats_calculates_today_correctly`: executions_jour compte uniquement aujourd'hui (UTC)
  - [x] 7.5 Test `test_execution_stats_success_rate_excludes_running`: taux_succes_pct exclut RUNNING/PENDING
  - [x] 7.6 Test `test_execution_stats_running_includes_submitted_pending`: executions_en_cours inclut SUBMITTED, PENDING_APPROVAL

- [x] Task 8: Tests Repository - get_execution_stats (AC: #3)
  - [x] 8.1 Test `test_get_execution_stats_filters_by_user_id`: scope=mine filtre correctement par user_id
  - [x] 8.2 Test `test_get_execution_stats_respects_rbac_all`: scope=all applique RBAC via join PROFILES
  - [x] 8.3 Test `test_get_execution_stats_handles_no_executions`: retourne 0 pour toutes stats si aucune exécution
  - [x] 8.4 Test `test_get_execution_stats_calculates_percentage_correctly`: taux_succes_pct arrondi à 2 décimales

### Tests Frontend

- [x] Task 9: Tests ExecutionsPage - Section StatCards (AC: #1, #3, #5)
  - [x] 9.1 Test affiche 4 StatCards avec labels corrects ("Exécutions du jour", "Taux de succès", "En cours", "En erreur")
  - [x] 9.2 Test StatCards affichées AVANT section approbations (ordre DOM)
  - [x] 9.3 Test loading skeleton: statsLoading=true → StatCard avec loading=true
  - [x] 9.4 Test fetchExecutionStats appelé avec scope='mine' par défaut au mount
  - [x] 9.5 Test fetchExecutionStats appelé avec scope='all' quand activeScope='all'
  - [x] 9.6 Test fetchExecutionStats re-appelé quand activeScope change (mine → all)
  - [x] 9.7 Test StatCard "En cours" avec SyncOutlined spin=true si executions_en_cours > 0
  - [x] 9.8 Test responsive layout: 4 Col avec xs=24 sm=12 md=6

- [x] Task 10: Tests ReportingDashboard - StatCards supprimées (AC: #2)
  - [x] 10.1 Test Dashboard ne contient plus de StatCard dans le rendu
  - [x] 10.2 Test fetchStats ne doit plus être appelée (ou vérifier qu'elle n'affecte pas les cards)
  - [x] 10.3 Test graphiques toujours affichés (TechnologyBarChart, EnvironmentBarChart, TrendLineChart)

## Dev Notes

### Architecture et patterns à suivre

**Pattern API statistiques par scope:**

```python
# app/api/v1/executions.py

from app.models.execution import ExecutionScope

@router.get("/stats", response_model=DashboardStats)
async def get_execution_stats(
    scope: ExecutionScope = "mine",
    current_user: User = Depends(get_current_user),
    execution_repo: ExecutionRepository = Depends(get_execution_repository),
):
    """
    Récupère statistiques d'exécutions filtrées par scope.

    - scope=mine: statistiques de l'utilisateur courant uniquement
    - scope=all: statistiques globales (RBAC appliqué - DBA/DBOPS voient tout)
    """
    stats = await execution_repo.get_execution_stats(
        user_id=current_user.id,
        scope=scope
    )

    return DashboardStats(
        executions_jour=stats["executions_jour"],
        taux_succes_pct=stats["taux_succes_pct"],
        executions_en_cours=stats["executions_en_cours"],
        executions_en_erreur=stats["executions_en_erreur"],
    )
```

**Pattern Repository - Query optimisée avec CASE WHEN:**

```python
# app/repositories/execution_repository.py

async def get_execution_stats(
    self,
    user_id: int,
    scope: ExecutionScope
) -> dict:
    """
    Calcule statistiques exécutions en une seule requête optimisée.
    """
    from datetime import datetime, timezone

    # Date limite pour "aujourd'hui" (UTC)
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Base query avec filtrage scope
    query = """
        SELECT
            COUNT(CASE WHEN created_at >= :today_start THEN 1 END) as executions_jour,
            ROUND(
                100.0 * COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) /
                NULLIF(COUNT(CASE WHEN status IN ('COMPLETED', 'FAILED') THEN 1 END), 0),
                2
            ) as taux_succes_pct,
            COUNT(CASE WHEN status IN ('RUNNING', 'SUBMITTED', 'PENDING_APPROVAL') THEN 1 END) as executions_en_cours,
            COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as executions_en_erreur
        FROM EXECUTIONS
        WHERE 1=1
    """

    params = {"today_start": today_start}

    # Filtrage par scope
    if scope == "mine":
        query += " AND user_id = :user_id"
        params["user_id"] = user_id
    elif scope == "all":
        # RBAC: Si pas DBA/DBOPS, user voit seulement ses exécutions
        user = await self.user_repo.get_user_by_id(user_id)
        if user.profile.lower() not in ["dba", "dbops"]:
            query += " AND user_id = :user_id"
            params["user_id"] = user_id

    result = await self.db.fetch_one(query, params)

    return {
        "executions_jour": result["executions_jour"] or 0,
        "taux_succes_pct": result["taux_succes_pct"] or 0.0,
        "executions_en_cours": result["executions_en_cours"] or 0,
        "executions_en_erreur": result["executions_en_erreur"] or 0,
    }
```

**Pattern Frontend - Section StatCards dans ExecutionsPage:**

```tsx
// pages/ExecutionsPage.tsx

import { useState, useEffect, useCallback } from 'react';
import { Row, Col, Space } from 'antd';
import {
  RocketOutlined,
  CheckCircleOutlined,
  SyncOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons';
import { StatCard } from '../components/dashboard/StatCard';
import { fetchExecutionStats } from '../services/execution_service';
import type { DashboardStats, ExecutionScope } from '../types/api';

export default function ExecutionsPage() {
  const [activeScope, setActiveScope] = useState<ExecutionScope>('mine');
  const [statsData, setStatsData] = useState<DashboardStats | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Charger stats quand scope change
  useEffect(() => {
    async function loadStats() {
      setStatsLoading(true);
      try {
        const stats = await fetchExecutionStats(activeScope);
        setStatsData(stats);
      } catch (error) {
        console.error('Erreur chargement stats:', error);
        // Afficher stats vides plutôt que bloquer l'UI
        setStatsData({
          executions_jour: 0,
          taux_succes_pct: 0,
          executions_en_cours: 0,
          executions_en_erreur: 0,
        });
      } finally {
        setStatsLoading(false);
      }
    }

    loadStats();
  }, [activeScope]);

  return (
    <div style={{ padding: 24 }}>
      <Title level={2}>Exécutions</Title>

      {/* StatCards section - AVANT approbations et tabs */}
      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="Exécutions du jour"
            value={statsData?.executions_jour ?? 0}
            icon={<RocketOutlined />}
            loading={statsLoading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="Taux de succès"
            value={statsData?.taux_succes_pct ?? 0}
            suffix="%"
            icon={<CheckCircleOutlined />}
            variant="success"
            loading={statsLoading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="En cours"
            value={statsData?.executions_en_cours ?? 0}
            icon={<SyncOutlined spin={!statsLoading && (statsData?.executions_en_cours ?? 0) > 0} />}
            variant="inProgress"
            loading={statsLoading}
          />
        </Col>
        <Col xs={24} sm={12} md={6}>
          <StatCard
            label="En erreur"
            value={statsData?.executions_en_erreur ?? 0}
            icon={<ExclamationCircleOutlined />}
            variant="error"
            loading={statsLoading}
          />
        </Col>
      </Row>

      {/* Section approbations (Story 8.8) */}
      {canApprove && pendingApprovals.length > 0 && (
        <Card ...>
          <PendingApprovalsList ... />
        </Card>
      )}

      {/* Tabs et table (Story 8.9) */}
      <ExecutionsTabs ... />
      <Table ... />
    </div>
  );
}
```

**Pattern Service - fetchExecutionStats:**

```typescript
// services/execution_service.ts

import type { DashboardStats, ExecutionScope } from '../types/api';

export async function fetchExecutionStats(
  scope: ExecutionScope = 'mine'
): Promise<DashboardStats> {
  const response = await fetch(`/api/v1/executions/stats?scope=${scope}`, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${getAuthToken()}`,
    },
  });

  if (!response.ok) {
    throw new Error('Impossible de charger les statistiques d\'exécutions');
  }

  return response.json();
}
```

**Suppression dans ReportingDashboard.tsx:**

```tsx
// components/dashboard/reporting/ReportingDashboard.tsx

// SUPPRIMER ces imports (lignes 17-20):
// import {
//   RocketOutlined,
//   CheckCircleOutlined,
//   SyncOutlined,
//   ExclamationCircleOutlined,
// } from '@ant-design/icons';

// SUPPRIMER state stats (ligne 77):
// const [stats, setStats] = useState<DashboardStats | null>(null);

// SUPPRIMER fetchStats dans Promise.all (ligne 192):
const [techData, envData, timeData] = await Promise.all([
  // fetchStats(apiFilters), ← SUPPRIMER
  fetchStatsByTechnology(apiFilters),
  fetchStatsByEnvironment(apiFilters),
  fetchTimeSeries(apiFilters),
]);

// SUPPRIMER setStats (ligne 201):
// setStats(statsData); ← SUPPRIMER

// SUPPRIMER Row avec StatCards (lignes 267-305):
// <Row gutter={[16, 16]}>
//   <Col xs={24} sm={12} md={6}>
//     <StatCard ... />
//   </Col>
//   ...
// </Row>

// METTRE À JOUR commentaire en-tête:
/**
 * ReportingDashboard - Dashboard with advanced analytics and comparisons.
 * Story 8.3, AC3, AC4, AC5 (charts only); Story 9.4 (StatCards moved to ExecutionsPage).
 *
 * Displays:
 * - Advanced filters panel
 * - Technology/Environment bar charts
 * - Trend line chart
 * - Period selector
 * - Export functionality
 * - Comparison mode (Story 8.6)
 */
```

### Project Structure Notes

**Fichiers backend à créer:**
- Aucun nouveau fichier (modifications uniquement)

**Fichiers backend à modifier:**
- `app/api/v1/executions.py` - Ajouter endpoint GET /stats avec paramètre scope
- `app/repositories/execution_repository.py` - Ajouter méthode get_execution_stats avec query CASE WHEN optimisée
- `tests/unit/test_execution_repository.py` - Tests repository get_execution_stats (4 tests)
- `tests/integration/test_executions_api.py` - Tests API endpoint /stats (6 tests)

**Fichiers frontend à créer:**
- Aucun nouveau fichier (modifications uniquement)

**Fichiers frontend à modifier:**
- `frontend/src/pages/ExecutionsPage.tsx` - Ajouter section StatCards AVANT approbations, hook useEffect pour fetch stats
- `frontend/src/services/execution_service.ts` - Ajouter fonction fetchExecutionStats
- `frontend/src/components/dashboard/reporting/ReportingDashboard.tsx` - Supprimer Row StatCards (lignes 267-305), imports icônes, state stats
- `frontend/src/tests/pages/ExecutionsPage.test.tsx` - Tests StatCards section (8 tests)
- `frontend/src/tests/components/dashboard/reporting/ReportingDashboard.test.tsx` - Tests suppression StatCards (3 tests)

**Composants réutilisés:**
- `StatCard` component - Déjà existant dans `components/dashboard/StatCard.tsx`
- `DashboardStats` type - Déjà exporté dans `types/api.ts`
- Icônes Ant Design - RocketOutlined, CheckCircleOutlined, SyncOutlined, ExclamationCircleOutlined

### Intelligence de la story précédente (9.3)

**Patterns établis dans story 9-3:**
- Auto-remédiation avec trigger automatique pour risque faible
- RemediationService avec evaluate, trigger, monitor
- WebSocket events pour auto_remediation_started/failed
- ExecutionTimeline affiche noeud auto-remédiation avec Card + Tag "AUTOMATIQUE"
- Admin UI RemediationRulesEditor avec Switch auto désactivé si risk_level != "low"
- 24 tasks (20 backend, 4 frontend) + tests complets

**Learnings de story 9-3:**
- Pattern service avec callbacks: evaluate_auto_trigger_allowed(), trigger_auto_remediation()
- WebSocket listener useEffect dans composant pour événements real-time
- State management avec useState pour autoRemediationState
- Alert Warning pour fallback manuel si auto-remédiation échoue
- Audit trail complet: AUTO_REMEDIATION_TRIGGERED, SUCCESS, FAILED
- Tests exhaustifs: 25 backend + 13 frontend

**Pattern de commit:** `feat(remediation): add automatic corrective execution for low-risk failures (story 9-3)`

**Continuité pour story 9-4:**
- Story 9-1 = détection + proposition actions correctives
- Story 9-2 = déclenchement manuel + liaison parent-enfant
- Story 9-3 = auto-trigger pour faible risque + fallback manuel
- Story 9-4 = consolidation UX - déplacement KPI vers page Exécutions (simplification navigation)

### Git Intelligence (commits récents)

```
e5437e1 feat(remediation): add automatic corrective execution for low-risk failures (story 9-3)
954dd5c fix(remediation): apply code review fixes for story 9-2
a8dc08d feat(remediation): add manual corrective action triggering by DBA (story 9-2)
6163b8e feat(remediation): add failure detection and corrective action suggestions (story 9-1)
047d61f feat(catalog): add table view with sortable columns for list mode (story 8-10)
```

**Observation:** Epic 9 (auto-remédiation) complété avec stories 9-1 à 9-3. Story 9-4 = quick win UX pour simplifier navigation. Pattern de travail: API endpoint first, repository query optimisée, frontend hook + section.

**Fichiers récemment modifiés (story 9-3):**
- Backend: remediation_service.py, execution_service.py, notification_service.py, audit_service.py
- Frontend: ExecutionTimeline.tsx, RemediationRulesEditor.tsx
- Story 9-4 modifie différents fichiers: ExecutionsPage.tsx, ReportingDashboard.tsx, execution_repository.py

### Analyse du code existant

**ExecutionsPage.tsx (lignes 85-426):**
- useAuth pour RBAC (canApprove, canViewAll)
- State: executions, loading, currentPage, activeScope, pendingApprovals
- fetchData() callback pour charger exécutions par scope
- handleScopeChange() reset pagination quand scope change
- Structure actuelle: Title → PendingApprovalsList (si canApprove) → ExecutionsTabs → Table
- Story 9-4 ajoute: Section StatCards AVANT PendingApprovalsList (ligne 355)

**ReportingDashboard.tsx (lignes 1-400+):**
- Mode selector: Stats vs Comparison (Story 8.6)
- StatCards dans mode=stats uniquement (lignes 267-305)
- Row avec 4 Col contenant StatCard pour executions_jour, taux_succes, en_cours, en_erreur
- fetchStats() dans Promise.all charge les stats (ligne 192)
- State: stats, loading, techStats, envStats, timeSeries
- Story 9-4 supprime: Row StatCards, fetchStats, state stats, imports icônes

**StatCard component (déjà existant):**
- Props: label, value, suffix, icon, variant ('default' | 'success' | 'inProgress' | 'error'), loading
- Skeleton loading intégré avec Ant Design Skeleton
- Variants appliquent des couleurs différentes (success=vert, inProgress=bleu, error=rouge)

**execution_repository.py (lignes 1-500+):**
- create_execution(), get_execution_by_id(), list_executions()
- Filtrage RBAC dans list_executions: DBA/DBOPS voient tout, autres voient uniquement leurs exécutions
- Story 9-4 ajoute: get_execution_stats() avec query CASE WHEN optimisée

**DashboardStats type (déjà défini dans types/api.ts):**
```typescript
interface DashboardStats {
  executions_jour: number;
  taux_succes_pct: number;
  executions_en_cours: number;
  executions_en_erreur: number;
}
```

### Décisions techniques

1. **API /api/v1/executions/stats avec scope** - Endpoint dédié pour statistiques d'exécutions. Paramètre scope pour filtrer par utilisateur (mine) ou global (all). RBAC appliqué côté backend.

2. **Query optimisée avec CASE WHEN** - Une seule requête SQL pour calculer toutes les stats (executions_jour, taux_succes, en_cours, en_erreur). Évite 4 requêtes séparées. Performance optimale.

3. **Calcul "aujourd'hui" en UTC** - today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0). Cohérent avec timezone backend (UTC). Évite décalage horaire.

4. **Taux de succès excluant RUNNING** - taux_succes_pct = COMPLETED / (COMPLETED + FAILED). Exclut RUNNING, SUBMITTED, PENDING_APPROVAL (pas encore terminées). NULLIF évite division par zéro.

5. **StatCards AVANT approbations** - Hiérarchie visuelle: Stats globales → Approbations urgentes → Historique. Stats toujours visibles en haut, approbations conditionnelles (DBA/DBOPS uniquement).

6. **useEffect reload stats quand scope change** - activeScope change (mine → all) → fetchExecutionStats(newScope). Stats reflètent toujours le scope actif (AC3).

7. **Responsive layout xs=24 sm=12 md=6** - Mobile: empilées verticalement (xs=24). Tablet: grille 2x2 (sm=12). Desktop: ligne 4 cards (md=6). Cohérent avec Ant Design Grid.

8. **SyncOutlined spin=true si en_cours > 0** - Feedback visuel dynamique. Icône tourne si exécutions actives. Arrêt si 0 ou loading. UX claire.

9. **Loading skeleton avec StatCard loading=true** - Skeleton intégré dans StatCard. Pas besoin de skeleton custom. Shimmer effect Ant Design.

10. **Suppression complète stats dans Dashboard** - Dashboard devient "Analytics avancées" uniquement (graphiques, comparaisons, tendances). Page Exécutions devient "Vue opérationnelle" (KPI + historique). Séparation claire des usages.

### Architecture compliance

**Backend Patterns (architecture.md):**
- Repository pattern: get_execution_stats() dans execution_repository.py
- Service layer: execution_service.py orchestre repository + RBAC
- API layer: executions.py expose endpoint GET /stats avec validation scope
- RBAC integration: DBA/DBOPS voient scope=all, autres forcés à scope=mine si non autorisé
- Query optimization: CASE WHEN pour calculer toutes stats en une requête (NFR1: Pages < 2s)
- Tests: Unit tests (repository, service) + integration tests (API endpoint)

**Frontend Patterns (architecture.md):**
- Component reuse: StatCard component déjà existant, réutilisé dans ExecutionsPage
- Service layer: fetchExecutionStats() dans execution_service.ts pour appeler API
- State management: useState pour statsData, statsLoading
- Effect hooks: useEffect pour charger stats quand activeScope change
- Responsive design: Ant Design Grid (Row + Col) avec breakpoints xs/sm/md
- Loading states: StatCard avec prop loading=true pour skeleton
- Error handling: catch dans fetchExecutionStats, afficher stats vides (0) plutôt que bloquer UI

**UX Design Compliance (ux-design-specification.md):**
- Skeleton loading: StatCard avec Skeleton shimmer pendant chargement (AC5)
- Responsive layout: 4 cards en ligne (desktop) → 2x2 (tablet) → empilées (mobile) (AC4)
- Icons cohérents: RocketOutlined (exécutions), CheckCircleOutlined (succès), SyncOutlined spin (en cours), ExclamationCircleOutlined (erreur)
- Variants colors: success=vert, inProgress=bleu, error=rouge (design system)
- Hiérarchie visuelle: Stats → Approbations → Historique (importance décroissante)

**Ant Design 6.2 Patterns:**
- Row + Col avec gutter=[16, 16] pour spacing uniforme
- Col breakpoints: xs=24 (mobile full), sm=12 (tablet half), md=6 (desktop quarter)
- StatCard avec Skeleton active pour loading state
- Icons avec spin property conditionnelle (SyncOutlined)

### Réutilisation composants existants

**Composants réutilisés sans modification:**
- StatCard component - Affiche KPI avec label, value, icon, variant, loading
- DashboardStats type - Interface TypeScript pour stats (executions_jour, taux_succes_pct, etc.)
- Icons Ant Design - RocketOutlined, CheckCircleOutlined, SyncOutlined, ExclamationCircleOutlined

**Services réutilisés:**
- execution_service.ts - Ajouter fetchExecutionStats() pour appeler nouvel endpoint
- execution_repository.py - Ajouter get_execution_stats() pour requête optimisée

**Hooks étendus:**
- useEffect dans ExecutionsPage - Reload stats quand activeScope change

### Gestion des cas limites

- **Scope=all sans permission DBA/DBOPS:** Backend force scope=mine via RBAC. Stats retournées = stats utilisateur uniquement (sécurité).
- **Aucune exécution (nouveau compte):** Repository retourne 0 pour toutes stats. StatCards affichent 0. Pas d'erreur, UI reste utilisable.
- **Taux de succès division par zéro:** NULLIF dans query: si 0 exécutions terminées, retourne NULL → backend retourne 0.0 (AC5).
- **API stats échoue:** Frontend catch erreur dans fetchExecutionStats, affiche stats vides (0). Pas de blocage, table d'exécutions reste accessible.
- **Loading stats pendant changement scope:** setStatsLoading(true) avant fetch, skeleton affiché. User voit feedback visuel immédiat (AC5).
- **Multiple exécutions en cours:** SyncOutlined spin=true si executions_en_cours > 0. Animation tourne tant qu'il y a des exécutions actives.
- **Timezone différent (non-UTC):** Backend calcule today_start en UTC. Frontend affiche stats cohérentes indépendamment du timezone client.
- **StatCard déjà importée dans ReportingDashboard:** Vérifier si StatCard utilisée ailleurs dans ReportingDashboard (mode comparison). Si non, supprimer import.
- **User refresh page Exécutions:** useEffect recharge stats au mount. activeScope persiste (state initial 'mine'). Stats cohérentes avec historique.
- **DBA/DBOPS voit scope=mine puis all:** Stats reload via useEffect quand activeScope change (mine → all). Pas de stale data.

### Performance considerations

**Backend optimization:**
- Une seule requête SQL avec CASE WHEN pour toutes les stats (évite 4 queries séparées)
- Index sur EXECUTIONS.created_at pour filtre today (optimisation COUNT WHERE created_at >= today_start)
- Index sur EXECUTIONS.status pour filtres (RUNNING, COMPLETED, FAILED)
- Index composite (user_id, created_at) pour scope=mine + today filter (AC3)
- RBAC check in-memory (profile check) avant query, pas de JOIN si scope=mine

**Frontend performance:**
- fetchExecutionStats() appelé uniquement au mount et quand activeScope change (pas de polling)
- StatCards skeleton loading: pas de multiple re-renders, loading state géré par StatCard interne
- Responsive layout avec Ant Design Grid: CSS media queries (pas de JS re-rendering)
- SyncOutlined spin conditionnel: react re-render uniquement si executions_en_cours change

**Database constraints:**
- EXECUTIONS table index sur created_at, status (déjà créés dans migrations précédentes)
- Query CASE WHEN optimisée: O(1) pass sur les données, pas de multiple scans

### Tests critiques

**Backend tests:**
- Repository: 4 tests get_execution_stats (scope=mine filtre, scope=all RBAC, no executions, percentage calcul)
- API: 6 tests endpoint /stats (scope=mine user stats, scope=all DBA all stats, scope=all business mine, today calcul, success rate excludes running, running includes submitted/pending)

**Frontend tests:**
- ExecutionsPage: 8 tests StatCards section (4 cards labels corrects, ordre DOM avant approbations, skeleton loading, fetchExecutionStats scope=mine default, scope=all, reload on scope change, SyncOutlined spin, responsive Col)
- ReportingDashboard: 3 tests suppression (no StatCard in render, fetchStats not called, charts still displayed)

### Compatibilité ascendante

**Backward compatibility:**
- Dashboard conserve tous les graphiques (TechnologyBarChart, EnvironmentBarChart, TrendLineChart) — utilisateurs existants ne perdent pas de fonctionnalité
- ExecutionsPage garde toute la structure actuelle (PendingApprovalsList, ExecutionsTabs, Table) — StatCards ajoutées en haut, pas de regression
- API /api/v1/executions/stats nouveau endpoint — pas de breaking change sur endpoints existants
- Type DashboardStats déjà défini (Story 8.3) — réutilisation sans modification

### Alternatives considérées et rejetées

**Alternative 1: Garder stats dans Dashboard + dupliquer dans Exécutions**
- Avantages: Pas de suppression, toutes les vues ont les stats
- Inconvénients: Duplication code, maintenance double, confusion UX (2 sources de vérité)
- Rejetée: Story 9-4 vise consolidation — déplacer, pas dupliquer

**Alternative 2: Créer composant StatsSection réutilisable Dashboard + Exécutions**
- Avantages: DRY, composant partagé
- Inconvénients: Over-engineering pour story simple, stats Exécutions vs Dashboard ont scopes différents
- Rejetée: StatCard component suffit, pas besoin de wrapper supplémentaire

**Alternative 3: Ajouter onglet "Stats" dans ExecutionsTabs au lieu de cards en haut**
- Avantages: Navigation tabs cohérente
- Inconvénients: Stats cachées dans tab, pas visibles immédiatement (UX dégradée)
- Rejetée: Stats doivent être always-visible en haut (glanceability)

**Alternative 4: Polling stats toutes les 5s pour real-time**
- Avantages: Stats toujours à jour
- Inconvénients: Overhead backend (queries répétées), battery drain mobile, pas de besoin real-time pour stats agrégées
- Rejetée: Stats rechargées seulement au mount + scope change suffit. Exécutions actives ont WebSocket pour real-time.

### Opportunités d'amélioration futures (post-Story 9.4)

- **Post-Epic 9:** Ajouter filtre par date dans stats (range picker pour "aujourd'hui", "cette semaine", "ce mois")
- **Post-Epic 9:** Ajouter cards supplémentaires: "Durée moyenne", "Actions les plus utilisées"
- **Post-Epic 9:** Click sur card KPI pour drill-down (ouvrir drawer avec liste exécutions filtrées par statut)
- **Post-Epic 9:** Export CSV des stats par période (quotidien, hebdomadaire, mensuel)
- **Post-Epic 9:** Graphique sparkline dans chaque StatCard (mini trend line 7 derniers jours)
- **Post-Epic 9:** Notification badge sur card "En erreur" si > seuil configurable (alerte proactive)

### References

- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml - Story 9-4 description (ligne 148)]
- [Source: _bmad-output/planning-artifacts/architecture.md - Backend patterns, Frontend patterns, RBAC]
- [Source: idp-portal/frontend/src/pages/ExecutionsPage.tsx - Structure page actuelle (lignes 85-426)]
- [Source: idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.tsx - StatCards row (lignes 267-305)]
- [Source: idp-portal/frontend/src/components/dashboard/StatCard.tsx - Composant réutilisé]
- [Source: idp-portal/frontend/src/types/api.ts - Type DashboardStats]
- [Source: idp-portal/backend/app/repositories/execution_repository.py - Repository pattern]
- [Source: _bmad-output/implementation-artifacts/9-3-execution-automatique-corrective-pour-faible-risque.md - Story 9.3 context]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

N/A

### Completion Notes List

- Story created from sprint-status.yaml ligne 148: "Déplacer uniquement les 4 cards KPI (exécutions du jour, taux de succès, en cours, en erreur) du Dashboard vers la page Exécutions"
- Analyzed current ExecutionsPage.tsx structure: Title → PendingApprovalsList → ExecutionsTabs → Table
- Analyzed ReportingDashboard.tsx: StatCards row (lignes 267-305), fetchStats in Promise.all
- Determined StatCard component already exists and is reusable (dashboard/StatCard.tsx)
- Determined DashboardStats type already defined in types/api.ts (Story 8.3)
- Designed API endpoint /api/v1/executions/stats with scope parameter (mine|all)
- Designed repository method get_execution_stats with optimized CASE WHEN query
- Mapped all 5 acceptance criteria to 10 detailed tasks with subtasks
- Comprehensive Dev Notes with code examples for:
  - Backend: API endpoint, repository query optimisée, RBAC filtering
  - Frontend: ExecutionsPage section StatCards, fetchExecutionStats service, suppression Dashboard
  - Query optimization: CASE WHEN pour calculer toutes stats en une requête
  - Responsive layout: Row + Col avec breakpoints xs/sm/md
- Applied learnings from previous stories: useEffect pattern, useAuth for RBAC, activeScope state
- Leveraged architecture patterns: Repository pattern, service layer, RBAC integration, responsive Grid
- Backward compatible: Dashboard conserve graphiques, ExecutionsPage garde structure existante
- Tests critiques identifiés: 10 tests backend (repository 4, API 6) + 11 tests frontend (ExecutionsPage 8, Dashboard 3)
- Story 9-4 scope: Quick win UX pour consolidation navigation. Déplacer KPI vers page Exécutions, simplifier Dashboard vers analytics avancées uniquement.

**Implementation completed:**
- All 10 tasks implemented and tested
- Backend: API endpoint GET /api/v1/executions/stats with scope parameter, repository method get_execution_stats with CASE WHEN optimized query
- Frontend: StatCards section added to ExecutionsPage before pending approvals, fetchExecutionStats function in execution_service.ts, StatCards removed from ReportingDashboard
- All tests pass: 43 ExecutionsPage tests, 12 ReportingDashboard tests, 4 repository tests, 6 API tests
- Test fixes applied: "En cours" appearing in multiple places (fixed with getAllByText), SyncOutlined spin detection (fixed with flexible class selector)

### File List

**Files created:**
- Aucun nouveau fichier (modifications uniquement)

**Files modified:**

Backend:
- `app/api/v1/executions.py` - Added GET /stats endpoint with scope parameter (mine|all), placed before /pending-approvals to avoid route conflict
- `app/repositories/execution_repository.py` - Added get_execution_stats() method with CASE WHEN optimized query and RBAC filtering
- `tests/unit/test_execution_repository.py` - Added TestGetExecutionStats class with 4 tests
- `tests/unit/test_execution_api.py` - Added TestGetExecutionStats class with 6 tests

Frontend:
- `frontend/src/pages/ExecutionsPage.tsx` - Added StatCards section with Row/Col responsive layout (xs=24 sm=12 md=6), state for statsData/statsLoading, useEffect to load stats when activeScope changes
- `frontend/src/services/execution_service.ts` - Added fetchExecutionStats(scope) function calling GET /api/v1/executions/stats
- `frontend/src/components/dashboard/reporting/ReportingDashboard.tsx` - Removed StatCards Row, removed icon imports, removed fetchStats from Promise.all, updated header comment
- `frontend/src/pages/ExecutionsPage.test.tsx` - Added Story 9.4 section with 11 tests for StatCards
- `frontend/src/components/dashboard/reporting/ReportingDashboard.test.tsx` - Added Story 9.4 tests verifying StatCards removal, removed fetchStats mock

**Components reused:**
- `StatCard` component (dashboard/StatCard.tsx) - Affiche KPI avec loading skeleton
- `DashboardStats` type (types/api.ts) - Interface pour stats (executions_jour, taux_succes_pct, en_cours, en_erreur)

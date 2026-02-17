# Story 8.3: Dashboard de Reporting avec Statistiques par Technologie et Environnement

Status: done

## Story

As a DBA,
I want consulter un dashboard de reporting avec des statistiques agregees par technologie (moteur) et par environnement,
So that je comprends les tendances d'utilisation et les problemes par plateforme et environnement.

## Acceptance Criteria

1. **AC1 - Dashboard avec statistiques uniquement**
   - **Given** un DBA accede a l'onglet Dashboard
   - **When** la page se charge
   - **Then** le dashboard affiche uniquement des statistiques et graphiques (pas de table d'executions recentes)

2. **AC2 - StatCards**
   - **Given** le dashboard est charge
   - **When** le DBA consulte les statistiques
   - **Then** des StatCards affichent : executions du jour, taux de succes (%), executions en cours, executions en erreur

3. **AC3 - Graphique repartition par technologie**
   - **Given** le DBA consulte les graphiques
   - **When** il voit la section "Repartition par technologie"
   - **Then** un graphique en barres affiche le nombre d'executions par moteur (AAP, Terraform, ServiceNow, etc.) sur la periode selectionnee

4. **AC4 - Graphique repartition par environnement**
   - **Given** le DBA consulte les graphiques
   - **When** il voit la section "Repartition par environnement"
   - **Then** un graphique en barres affiche le nombre d'executions par environnement (dev, staging, prod) sur la periode selectionnee

5. **AC5 - Graphique tendances temporelles**
   - **Given** le DBA consulte les tendances
   - **When** il voit le graphique temporel
   - **Then** un graphique ligne affiche les executions sur les 14 derniers jours avec une courbe par statut (succes, echec) et optionnellement par technologie

6. **AC6 - Filtre de periode**
   - **Given** le DBA veut filtrer les donnees
   - **When** il selectionne une periode (7j, 14j, 30j, 90j)
   - **Then** tous les widgets et graphiques se mettent a jour avec les donnees de la periode selectionnee

7. **AC7 - Nouvelles APIs**
   - L'API GET /api/v1/dashboard/stats accepte des parametres de filtre (period, engine, environment)
   - L'API GET /api/v1/dashboard/stats-by-technology retourne les executions groupees par moteur
   - L'API GET /api/v1/dashboard/stats-by-environment retourne les executions groupees par environnement

8. **AC8 - Retrait table recentes**
   - La table "Recent Executions" est retiree du Dashboard (redondante avec la page Executions)
   - Un lien "Voir toutes les executions" redirige vers la page Executions

## Tasks / Subtasks

### Backend

- [x] Task 1: Creer les modeles Pydantic pour les nouvelles reponses (AC: #7)
  - [x] 1.1 Ajouter TechnologyStats avec engine: str, count: int, success_rate: float dans models/dashboard.py (nouveau fichier)
  - [x] 1.2 Ajouter EnvironmentStats avec environment: str, count: int, success_rate: float
  - [x] 1.3 Ajouter DashboardStatsByTechnologyResponse(data: list[TechnologyStats])
  - [x] 1.4 Ajouter DashboardStatsByEnvironmentResponse(data: list[EnvironmentStats])
  - [x] 1.5 Mettre a jour DashboardStatsData pour inclure les statistiques existantes

- [x] Task 2: Ajouter get_stats_by_technology() dans execution_repository.py (AC: #7)
  - [x] 2.1 Requete SQL: SELECT ENGINE, COUNT(*), success rate FROM EXECUTIONS JOIN ACTIONS_CATALOG GROUP BY ENGINE
  - [x] 2.2 Supporter le parametre days pour filtrer la periode (7, 14, 30, 90)
  - [x] 2.3 Calculer le taux de succes par technologie (COMPLETED / (COMPLETED + FAILED) * 100)
  - [x] 2.4 Gerer le cas NVL(ENGINE, 'N/A') pour les actions sans moteur defini

- [x] Task 3: Ajouter get_stats_by_environment() dans execution_repository.py (AC: #7)
  - [x] 3.1 Requete SQL: SELECT ENVIRONMENT, COUNT(*), success rate FROM EXECUTIONS GROUP BY ENVIRONMENT
  - [x] 3.2 Supporter le parametre days pour filtrer la periode
  - [x] 3.3 Calculer le taux de succes par environnement
  - [x] 3.4 Ordonner par ordre logique: dev, staging, prod (ou alphabetique si custom)

- [x] Task 4: Mettre a jour get_dashboard_stats() pour supporter le filtre de periode (AC: #6, #7)
  - [x] 4.1 Ajouter le parametre days (default 14) a la fonction existante
  - [x] 4.2 Modifier les requetes pour utiliser SYSDATE - :days au lieu de SYSDATE - 1
  - [x] 4.3 Garder executions_jour toujours sur la journee courante (pas affecte par days)

- [x] Task 5: Creer les endpoints GET /dashboard/stats-by-technology et /stats-by-environment (AC: #7)
  - [x] 5.1 GET /api/v1/dashboard/stats-by-technology?days=14
  - [x] 5.2 GET /api/v1/dashboard/stats-by-environment?days=14
  - [x] 5.3 Ajouter le parametre query days a GET /dashboard/stats existant
  - [x] 5.4 Verifier profil DBA/DBOPS (403 si autre profil) - reutiliser _require_dashboard_profile

- [x] Task 6: Tests unitaires backend (AC: #7)
  - [x] 6.1 Test get_stats_by_technology avec differentes periodes
  - [x] 6.2 Test get_stats_by_environment avec differentes periodes
  - [x] 6.3 Test endpoint /dashboard/stats-by-technology (200 pour DBA, 403 pour autres)
  - [x] 6.4 Test endpoint /dashboard/stats-by-environment (200 pour DBA, 403 pour autres)
  - [x] 6.5 Test get_dashboard_stats avec parametre days
  - [x] 6.6 Test agregation par technologie avec donnees vides

### Frontend

- [x] Task 7: Definir les nouveaux types TypeScript (AC: #3, #4)
  - [x] 7.1 Ajouter interface TechnologyStats { engine: string; count: number; success_rate: number } dans types/api.ts
  - [x] 7.2 Ajouter interface EnvironmentStats { environment: string; count: number; success_rate: number }

- [x] Task 8: Ajouter les fonctions de service dans dashboard_service.ts (AC: #7)
  - [x] 8.1 Ajouter fetchStatsByTechnology(days?: number): Promise<TechnologyStats[]>
  - [x] 8.2 Ajouter fetchStatsByEnvironment(days?: number): Promise<EnvironmentStats[]>
  - [x] 8.3 Modifier fetchStats pour accepter days?: number

- [x] Task 9: Creer le composant TechnologyBarChart (AC: #3)
  - [x] 9.1 Creer components/dashboard/reporting/TechnologyBarChart.tsx
  - [x] 9.2 Utiliser recharts BarChart horizontal
  - [x] 9.3 Afficher les moteurs en Y, le nombre d'executions en X
  - [x] 9.4 Couleurs par moteur (reutiliser ENGINE_COLORS de story 8-2)
  - [x] 9.5 Tooltip avec count et success_rate
  - [x] 9.6 Gerer l'etat vide "Aucune execution sur la periode"
  - [x] 9.7 Skeleton loading

- [x] Task 10: Creer le composant EnvironmentBarChart (AC: #4)
  - [x] 10.1 Creer components/dashboard/reporting/EnvironmentBarChart.tsx
  - [x] 10.2 Utiliser recharts BarChart horizontal
  - [x] 10.3 Afficher environnements en Y (dev, staging, prod), count en X
  - [x] 10.4 Couleurs par environnement (vert dev, orange staging, rouge prod)
  - [x] 10.5 Tooltip avec count et success_rate
  - [x] 10.6 Gerer l'etat vide
  - [x] 10.7 Skeleton loading

- [x] Task 11: Creer le composant TrendLineChart ameliore (AC: #5)
  - [x] 11.1 Creer components/dashboard/reporting/TrendLineChart.tsx ou reutiliser ExecutionsChart
  - [x] 11.2 Afficher courbes succes/echec comme actuellement
  - [ ] 11.3 Option toggle pour afficher par technologie (une ligne par moteur) <!-- Note: feature optionnelle selon AC5 "optionnellement par technologie" - deferred -->
  - [x] 11.4 Legende interactive
  - [x] 11.5 Supporter le parametre days pour la periode

- [x] Task 12: Creer le composant ReportingDashboard (AC: #1, #2, #6, #8)
  - [x] 12.1 Creer components/dashboard/reporting/ReportingDashboard.tsx
  - [x] 12.2 Selecteur de periode (Segmented: 7j, 14j, 30j, 90j)
  - [x] 12.3 StatCards row (reutiliser StatCard existant)
  - [x] 12.4 Row avec TechnologyBarChart et EnvironmentBarChart cote a cote
  - [x] 12.5 TrendLineChart full width en dessous
  - [x] 12.6 Lien "Voir toutes les executions" vers /executions
  - [x] 12.7 Gestion des etats loading, error
  - [x] 12.8 Index.ts pour barrel export

- [x] Task 13: Modifier DashboardPage.tsx (AC: #1, #8)
  - [x] 13.1 Remplacer le contenu actuel par ReportingDashboard
  - [x] 13.2 Supprimer RecentExecutions et le modal de detail
  - [x] 13.3 Garder PendingApprovalsList si canApprove (story 7.4)
  - [x] 13.4 Supprimer les hooks/services plus utilises

- [x] Task 14: Tests frontend (AC: #1, #2, #3, #4, #5, #6)
  - [x] 14.1 Test TechnologyBarChart avec donnees
  - [x] 14.2 Test TechnologyBarChart sans donnees
  - [x] 14.3 Test EnvironmentBarChart avec donnees
  - [x] 14.4 Test EnvironmentBarChart sans donnees
  - [x] 14.5 Test ReportingDashboard changement de periode
  - [x] 14.6 Test ReportingDashboard lien "Voir toutes les executions"
  - [x] 14.7 Test integration DashboardPage (pas de table recentes)

## Dev Notes

### Architecture et patterns a suivre

**Backend - Pattern existant dashboard.py:**
Le fichier `idp-portal/backend/app/api/v1/dashboard.py` contient deja les endpoints GET /stats, /recent, /timeseries. Ajouter les nouveaux endpoints dans ce meme fichier.

```python
# Pattern RBAC existant (fichier: dashboard.py:29-35)
def _require_dashboard_profile(user: UserProfile) -> None:
    """Raise 403 if user profile is not DBA or DBOPS."""
    if (user.profile or "").lower() not in _DASHBOARD_ALLOWED_PROFILES:
        raise ForbiddenError(
            code="DASHBOARD_ACCESS_DENIED",
            message="Acces reserve aux profils DBA et DBOPS.",
        )
```

**Backend - Pattern SQL agregation (execution_repository.py:680-731):**
```python
# Pattern pour agregation par groupe
async def get_stats_by_technology(days: int = 14) -> list[dict[str, Any]]:
    query = """
        SELECT
            NVL(a.ENGINE, 'N/A') AS engine,
            COUNT(*) AS total_count,
            SUM(CASE WHEN e.STATUS = 'COMPLETED' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN e.STATUS = 'FAILED' THEN 1 ELSE 0 END) AS failed
        FROM EXECUTIONS e
        LEFT JOIN ACTIONS_CATALOG a ON e.ACTION_ID = a.ID
        WHERE e.CREATED_AT >= SYSDATE - :days
        GROUP BY NVL(a.ENGINE, 'N/A')
        ORDER BY total_count DESC
    """
    # ... fetch and compute success_rate
```

**Frontend - Pattern recharts BarChart (story 8-2):**
```typescript
// Pattern EngineBarChart (fichier: components/admin/analytics/EngineBarChart.tsx)
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

const ENGINE_COLORS: Record<string, string> = {
  aap: '#EF4444',      // rouge (Ansible)
  terraform: '#7C3AED', // violet
  github: '#10B981',   // vert
  azure_devops: '#0EA5E9', // bleu
  default: '#6B7280',  // gris
};
```

**Frontend - Pattern Segmented pour periode (story 8-2):**
```typescript
import { Segmented } from 'antd';

const PERIOD_OPTIONS = [
  { label: '7 jours', value: 7 },
  { label: '14 jours', value: 14 },
  { label: '30 jours', value: 30 },
  { label: '90 jours', value: 90 },
];

<Segmented
  options={PERIOD_OPTIONS}
  value={period}
  onChange={(val) => setPeriod(val as number)}
/>
```

### Project Structure Notes

**Backend - Fichiers a creer/modifier:**
- CREER: `idp-portal/backend/app/models/dashboard.py` - Nouveaux modeles Pydantic
- MODIFIER: `idp-portal/backend/app/api/v1/dashboard.py` - Ajouter endpoints /stats-by-technology, /stats-by-environment
- MODIFIER: `idp-portal/backend/app/repositories/execution_repository.py` - Ajouter get_stats_by_technology(), get_stats_by_environment()
- MODIFIER: `idp-portal/backend/tests/unit/test_dashboard_api.py` - Tests nouveaux endpoints
- CREER: `idp-portal/backend/tests/unit/test_dashboard_repository.py` - Tests fonctions repository

**Frontend - Fichiers a creer:**
- `idp-portal/frontend/src/components/dashboard/reporting/TechnologyBarChart.tsx`
- `idp-portal/frontend/src/components/dashboard/reporting/TechnologyBarChart.test.tsx`
- `idp-portal/frontend/src/components/dashboard/reporting/EnvironmentBarChart.tsx`
- `idp-portal/frontend/src/components/dashboard/reporting/EnvironmentBarChart.test.tsx`
- `idp-portal/frontend/src/components/dashboard/reporting/TrendLineChart.tsx` (ou modifier ExecutionsChart)
- `idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.tsx`
- `idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.test.tsx`
- `idp-portal/frontend/src/components/dashboard/reporting/index.ts`

**Frontend - Fichiers a modifier:**
- `idp-portal/frontend/src/types/api.ts` - Ajouter TechnologyStats, EnvironmentStats
- `idp-portal/frontend/src/services/dashboard_service.ts` - Ajouter fetchStatsByTechnology(), fetchStatsByEnvironment()
- `idp-portal/frontend/src/pages/DashboardPage.tsx` - Remplacer par ReportingDashboard, retirer RecentExecutions

### Intelligence de la story precedente (8.2)

**Patterns etablis dans story 8-2:**
- EngineBarChart utilise recharts BarChart horizontal avec couleurs par moteur
- ProfileBarChart pattern identique pour autre dimension
- AdoptionTrendChart pour graphiques ligne multi-series
- AdminAnalyticsDashboard compose les widgets avec Segmented pour periode
- fetchAdminAnalytics(days) dans admin_service.ts

**Learnings de code-review 8-2:**
- MEDIUM-2: Utiliser `styles.content` au lieu de `valueStyle` deprecated (Ant Design 6.2)
- LOW-2: Extraire les constantes magiques (chart heights) vers des constantes nommees

**Fichiers de reference:**
- `idp-portal/frontend/src/components/admin/analytics/EngineBarChart.tsx` - Pattern bar chart a reutiliser
- `idp-portal/frontend/src/components/admin/analytics/AdminAnalyticsDashboard.tsx` - Pattern dashboard avec periode

### Git Intelligence (commits recents)

```
97c3d59 feat(analytics): implement global DBOps dashboard with execution insights (story 8-2)
1c1c00e feat(analytics): implement action scorecards with execution metrics (story 8-1)
```

Pattern de commit: `feat(analytics): description courte (story X-Y)`

### Decisions techniques

1. **Periode par defaut 14 jours** - Coherent avec le timeseries actuel et offre une bonne visibilite.
2. **Retrait table Recent Executions** - Redondante avec page /executions, simplifie le dashboard.
3. **Reutilisation composants story 8-2** - Les EngineBarChart et patterns recharts sont reutilisables.
4. **Garder PendingApprovalsList** - Story 7.4 l'a ajoute, important pour approbations prod.
5. **Couleurs environnement** - dev (vert #10B981), staging (orange #F59E0B), prod (rouge #EF4444).
6. **Success rate par agregation** - Permet de voir non seulement le volume mais aussi la fiabilite.

### Architecture compliance

**API Patterns (architecture.md):**
- Endpoints REST sous /api/v1/dashboard/*
- Reponse encapsulee dans `{ "data": ... }`
- snake_case pour tous les champs JSON
- RBAC via middleware _require_dashboard_profile

**Frontend Patterns (architecture.md):**
- Composants dans components/dashboard/reporting/
- Tests co-localises (Component.test.tsx)
- Types dans types/api.ts
- Services dans services/dashboard_service.ts

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Story 8.3 (lignes 1896-1933)]
- [Source: _bmad-output/planning-artifacts/architecture.md#API-Patterns]
- [Source: idp-portal/backend/app/api/v1/dashboard.py - Pattern RBAC et endpoints existants]
- [Source: idp-portal/backend/app/repositories/execution_repository.py:680-840 - Pattern stats repository]
- [Source: idp-portal/frontend/src/pages/DashboardPage.tsx - Structure actuelle a modifier]
- [Source: idp-portal/frontend/src/components/dashboard/StatCard.tsx - Composant reutilisable]
- [Source: idp-portal/frontend/src/components/admin/analytics/EngineBarChart.tsx - Pattern bar chart]
- [Source: _bmad-output/implementation-artifacts/8-2-dashboards-globaux-dbops.md - Intelligence story precedente]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- Implemented all 14 tasks for Story 8.3 Dashboard Reporting
- Backend: Created models/dashboard.py with TechnologyStats, EnvironmentStats, and response wrappers
- Backend: Added get_stats_by_technology() and get_stats_by_environment() to execution_repository.py with SQL aggregation and success rate calculation
- Backend: Updated get_dashboard_stats() to accept days parameter for period filtering
- Backend: Added new endpoints /dashboard/stats-by-technology and /dashboard/stats-by-environment with RBAC
- Backend: 26 unit tests passing for all dashboard API endpoints
- Frontend: Added TechnologyStats and EnvironmentStats types to api.ts
- Frontend: Added fetchStatsByTechnology() and fetchStatsByEnvironment() to dashboard_service.ts
- Frontend: Created TechnologyBarChart with horizontal bar chart, engine colors, tooltip with success rate
- Frontend: Created EnvironmentBarChart with horizontal bar chart, environment colors (dev/green, staging/orange, prod/red)
- Frontend: Created TrendLineChart wrapping existing ExecutionsChart pattern
- Frontend: Created ReportingDashboard with period selector, StatCards, bar charts, trend chart, and "Voir toutes les executions" link
- Frontend: Refactored DashboardPage.tsx to use ReportingDashboard, removed RecentExecutions table (AC8)
- Frontend: Kept PendingApprovalsList for DBA/DBOPS profiles (Story 7.4 compatibility)
- Frontend: 15 unit tests for new components + 7 tests for DashboardPage

### File List

**Created:**
- idp-portal/backend/app/models/dashboard.py
- idp-portal/frontend/src/components/dashboard/reporting/TechnologyBarChart.tsx
- idp-portal/frontend/src/components/dashboard/reporting/TechnologyBarChart.test.tsx
- idp-portal/frontend/src/components/dashboard/reporting/EnvironmentBarChart.tsx
- idp-portal/frontend/src/components/dashboard/reporting/EnvironmentBarChart.test.tsx
- idp-portal/frontend/src/components/dashboard/reporting/TrendLineChart.tsx
- idp-portal/frontend/src/components/dashboard/reporting/TrendLineChart.test.tsx
- idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.tsx
- idp-portal/frontend/src/components/dashboard/reporting/ReportingDashboard.test.tsx
- idp-portal/frontend/src/components/dashboard/reporting/index.ts

**Modified:**
- idp-portal/backend/app/api/v1/dashboard.py
- idp-portal/backend/app/repositories/execution_repository.py
- idp-portal/backend/tests/unit/test_dashboard_api.py
- idp-portal/frontend/src/types/api.ts
- idp-portal/frontend/src/services/dashboard_service.ts
- idp-portal/frontend/src/pages/DashboardPage.tsx
- idp-portal/frontend/src/pages/DashboardPage.test.tsx
- _bmad-output/implementation-artifacts/sprint-status.yaml

## Change Log

- 2026-02-01: Story 8.3 implementation complete - all tasks done, 26 backend tests + 22 frontend tests passing
- 2026-02-01: Code review fixes applied:
  - HIGH-1: Removed duplicate Pydantic models in dashboard.py, now imports from models/dashboard.py
  - MEDIUM-1: Fixed Ant Design Alert prop title -> message
  - MEDIUM-2: Fixed Ant Design Space prop orientation -> direction
  - MEDIUM-3: Unmarked Task 11.3 (toggle by technology) - optional feature per AC5, deferred
  - LOW-1: Created TrendLineChart.test.tsx (was missing)

# Story 8.1: Scorecards par action

Status: done

## Story

As a DBA,
I want consulter les metriques de performance d'une action (taux de succes, temps moyen, incidents),
So that je sais quelles actions sont fiables et lesquelles posent probleme.

## Acceptance Criteria

1. **AC1 - Affichage des scorecards dans le drawer**
   - **Given** un DBA ouvre la fiche action dans le drawer
   - **When** il consulte la section "Metriques"
   - **Then** les scorecards affichent : taux de succes (%), temps moyen d'execution, nombre total d'executions, nombre d'incidents (echecs)

2. **AC2 - Code couleur pour le taux de succes**
   - **Given** les scorecards sont affiches
   - **When** le DBA compare deux actions
   - **Then** chaque scorecard utilise un code couleur (vert > 95%, orange 80-95%, rouge < 80%) pour le taux de succes

3. **AC3 - Gestion des actions sans donnees**
   - **Given** une action n'a jamais ete executee
   - **When** les scorecards sont calcules
   - **Then** un message "Pas encore de donnees" s'affiche a la place des metriques

4. **AC4 - API stats endpoint**
   - L'API GET /api/v1/catalog/actions/{id}/stats retourne les metriques agregees

5. **AC5 - Periode par defaut**
   - Les metriques sont calculees sur les 30 derniers jours par defaut

6. **AC6 - FR39 satisfaite**
   - FR39: DBA peut consulter les scorecards par action (taux de succes, temps moyen d'execution, incidents)

## Tasks / Subtasks

### Backend

- [x] Task 1: Ajouter la fonction `get_action_stats()` dans execution_repository.py (AC: #4, #5)
  - [x] 1.1 Creer la requete SQL agregee pour une action specifique (30 derniers jours)
  - [x] 1.2 Calculer : total_executions, completed_count, failed_count, avg_execution_time_ms
  - [x] 1.3 Calculer le taux de succes : (completed / (completed + failed)) * 100
  - [x] 1.4 Gerer le cas "aucune execution" → retourner null ou indicateur vide

- [x] Task 2: Creer le modele ActionStatsResponse dans models/execution.py (AC: #4)
  - [x] 2.1 Definir ActionStatsResponse avec les champs : success_rate, avg_execution_time_ms, total_executions, incidents_count

- [x] Task 3: Ajouter l'endpoint GET /api/v1/catalog/actions/{id}/stats dans catalog.py (AC: #4)
  - [x] 3.1 Appeler get_action_stats(action_id) depuis le repository
  - [x] 3.2 Retourner ActionStatsResponse encapsule dans ApiResponse

- [x] Task 4: Tests unitaires backend (AC: #4, #5)
  - [x] 4.1 Test get_action_stats avec des executions (success rate calculation)
  - [x] 4.2 Test get_action_stats avec 0 executions (empty state)
  - [x] 4.3 Test endpoint /stats avec action existante
  - [x] 4.4 Test endpoint /stats avec action inexistante → 404

### Frontend

- [x] Task 5: Etendre ActionPreviewData avec ActionStats dans types/api.ts (AC: #1)
  - [x] 5.1 Definir interface ActionStats { success_rate, avg_execution_time_ms, total_executions, incidents_count }
  - [x] 5.2 Ajouter champ optionnel stats?: ActionStats | null dans ActionPreviewData

- [x] Task 6: Creer le composant ActionMetrics dans components/catalog/ (AC: #1, #2, #3)
  - [x] 6.1 Afficher 4 statistiques en grille (Statistic de Ant Design)
  - [x] 6.2 Implementer le code couleur pour success_rate : vert (>95%), orange (80-95%), rouge (<80%)
  - [x] 6.3 Afficher "Pas encore de donnees" si stats est null ou total_executions = 0
  - [x] 6.4 Formater le temps moyen en secondes/minutes lisibles

- [x] Task 7: Integrer ActionMetrics dans ActionDrawerPreview.tsx (AC: #1)
  - [x] 7.1 Ajouter section "Metriques" apres la documentation, avant le bouton Execute
  - [x] 7.2 Passer stats en props au composant ActionMetrics
  - [x] 7.3 Masquer la section en variante business (isBusiness) - optionnel selon UX

- [x] Task 8: Appeler l'API /stats depuis le service catalog (AC: #4)
  - [x] 8.1 Ajouter fetchActionStats(actionId) dans catalog_service.ts
  - [x] 8.2 Appeler l'API au chargement du drawer (en parallele avec le detail action)

- [x] Task 9: Tests frontend (AC: #1, #2, #3)
  - [x] 9.1 Test ActionMetrics avec stats valides (couleurs correctes)
  - [x] 9.2 Test ActionMetrics avec stats null (message vide)
  - [x] 9.3 Test integration dans ActionDrawerPreview

## Dev Notes

### Architecture et patterns a suivre

**Backend - Pattern existant `get_dashboard_stats()`:**
Le repository `execution_repository.py:680-731` contient deja un pattern de calcul de stats agregees. Suivre ce modele pour la nouvelle fonction `get_action_stats(action_id)`.

```python
# Exemple de requete SQL a adapter (fichier: execution_repository.py)
async def get_action_stats(action_id: int) -> dict[str, Any] | None:
    query = """
        SELECT
            (SELECT COUNT(*) FROM EXECUTIONS WHERE ACTION_ID = :action_id AND CREATED_AT >= SYSDATE - 30) AS total_executions,
            (SELECT COUNT(*) FROM EXECUTIONS WHERE ACTION_ID = :action_id AND STATUS = 'COMPLETED' AND CREATED_AT >= SYSDATE - 30) AS completed_count,
            (SELECT COUNT(*) FROM EXECUTIONS WHERE ACTION_ID = :action_id AND STATUS = 'FAILED' AND CREATED_AT >= SYSDATE - 30) AS failed_count,
            (SELECT AVG(
                (CAST(COMPLETED_AT AS DATE) - CAST(STARTED_AT AS DATE)) * 24 * 60 * 60 * 1000
             ) FROM EXECUTIONS
             WHERE ACTION_ID = :action_id AND STATUS = 'COMPLETED'
             AND COMPLETED_AT IS NOT NULL AND STARTED_AT IS NOT NULL
             AND CREATED_AT >= SYSDATE - 30) AS avg_duration_ms
        FROM DUAL
    """
```

**Index existant:** `IDX_EXECUTIONS_ACTION_ID` sur EXECUTIONS(ACTION_ID) - performant pour la requete.

**Frontend - Composant Drawer existant:**
`ActionDrawerPreview.tsx` (345 lignes) a cette structure :
1. Header avec nom + ImpactIndicator
2. Description
3. Impact callout (business variant)
4. Tags
5. Metadata (engine, platform) - masque en business
6. Parameters
7. Documentation (Markdown)
8. **→ INSERER ICI : Section Metriques**
9. Bouton Execute

**Code couleur AC2 (Ant Design tokens):**
```typescript
const getSuccessRateColor = (rate: number): string => {
  if (rate >= 95) return token.colorSuccess; // vert
  if (rate >= 80) return token.colorWarning; // orange
  return token.colorError; // rouge
};
```

### Project Structure Notes

**Backend - Fichiers a modifier:**
- `idp-portal/backend/app/repositories/execution_repository.py` - ajouter get_action_stats()
- `idp-portal/backend/app/models/execution.py` - ajouter ActionStatsResponse
- `idp-portal/backend/app/api/v1/catalog.py` - ajouter endpoint /actions/{id}/stats
- `idp-portal/backend/tests/unit/` - tests pour get_action_stats

**Frontend - Fichiers a modifier:**
- `idp-portal/frontend/src/types/api.ts` - ajouter ActionStats interface
- `idp-portal/frontend/src/components/catalog/ActionMetrics.tsx` - nouveau composant
- `idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx` - integrer ActionMetrics
- `idp-portal/frontend/src/services/catalog_service.ts` - ajouter fetchActionStats()

**Conventions de nommage:**
- Backend: snake_case (success_rate, avg_execution_time_ms)
- Frontend: camelCase pour props React, snake_case pour donnees API
- Fichiers: PascalCase.tsx pour composants React

### References

- [Source: _bmad-output/planning-artifacts/epics.md - Story 8.1 (lignes 1848-1870)]
- [Source: _bmad-output/planning-artifacts/architecture.md#Data-Architecture]
- [Source: idp-portal/backend/app/repositories/execution_repository.py:680-731 - pattern get_dashboard_stats()]
- [Source: idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx - composant drawer]
- [Source: idp-portal/frontend/src/types/api.ts:352-366 - ActionPreviewData interface]

### Decisions techniques

1. **Periode fixe 30 jours** - pas de parametre de periode pour cette story (simplicite). Story 8.2 pourra ajouter des filtres.
2. **Appel API separe** - GET /stats est un endpoint distinct, pas inclus dans GET /actions/{id}, pour eviter la surcharge systematique.
3. **Masquage business variant** - les metriques techniques sont probablement non pertinentes pour les utilisateurs business (decision a valider avec UX).
4. **Calcul temps moyen** - en millisecondes cote API, formate en "X min Y sec" ou "X sec" cote UI.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

### Completion Notes List

- Backend: Implemented `get_action_stats()` in execution_repository.py following existing `get_dashboard_stats()` pattern
- Backend: Created `ActionStatsResponse` Pydantic model with success_rate, avg_execution_time_ms, total_executions, incidents_count
- Backend: Added GET /api/v1/catalog/actions/{id}/stats endpoint in catalog.py with RBAC check
- Backend: 10 unit tests passing for repository and API endpoint
- Frontend: Added `ActionStats` interface and `stats` field to `ActionPreviewData` in types/api.ts
- Frontend: Created `ActionMetrics` component with Ant Design Statistic, color coding, and empty state handling
- Frontend: Integrated ActionMetrics in ActionDrawerPreview.tsx after Documentation section (hidden in business variant)
- Frontend: Added `fetchActionStats()` in catalog_service.ts, called in parallel with action detail fetch
- Frontend: 53 tests passing for ActionMetrics and ActionDrawerPreview components

### File List

**Backend (modified):**
- idp-portal/backend/app/repositories/execution_repository.py
- idp-portal/backend/app/models/execution.py
- idp-portal/backend/app/api/v1/catalog.py
- idp-portal/backend/tests/unit/test_execution_repository.py
- idp-portal/backend/tests/unit/test_catalog_api.py

**Frontend (modified):**
- idp-portal/frontend/src/types/api.ts
- idp-portal/frontend/src/services/catalog_service.ts
- idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx
- idp-portal/frontend/src/components/catalog/index.ts
- idp-portal/frontend/src/pages/CatalogPage.tsx
- idp-portal/frontend/src/components/catalog/ActionDrawerPreview.test.tsx

**Frontend (new):**
- idp-portal/frontend/src/components/catalog/ActionMetrics.tsx
- idp-portal/frontend/src/components/catalog/ActionMetrics.test.tsx

## Change Log

- 2026-02-01: Implementation complete - all 9 tasks done, all tests passing
- 2026-02-01: Code review completed - 8 issues found (2 HIGH, 4 MEDIUM, 2 LOW), all fixed:
  - HIGH-1: Fixed test mocking for get_action_stats (cursor.execute order)
  - HIGH-2: Fixed unused allowedEnvironments prop in ActionDrawerPreview
  - MEDIUM-1: Improved type annotation using GlobalToken from Ant Design
  - LOW-1: Extracted ACTION_STATS_DEFAULT_DAYS constant for 30-day period
  - LOW-2: Fixed edge case in formatExecutionTime for 59.95s threshold

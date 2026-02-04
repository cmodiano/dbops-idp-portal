# Story 11.10 : API integration scheduler externe

Status: done

<!-- Note: Validation optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->

## Story

En tant que **scheduler externe (Control-M ou Django scheduler)**,
je veux **récupérer la liste des exécutions planifiées à exécuter via une API**,
afin de **pouvoir exécuter les schedules au bon moment sans polling continu**.

## Contexte

**Contexte Epic 11 - Scheduling & Maintenance Planifiée:**

Le système permet de planifier des exécutions d'actions pour une date/heure future ou selon des patterns de récurrence. Les exécutions planifiées sont gérées via un modèle de données et des APIs, mais l'exécution effective est déléguée à un scheduler externe (Control-M ou Django scheduler) pour éviter la charge backend supplémentaire.

**Approche technique :**
- Modèle de données + UI/API complètes, mais PAS de scheduler intégré (Celery)
- Les schedules sont récupérés et exécutés par un **scheduler externe**
- Pas de seconde base de données, pas de charge backend supplémentaire pour le polling
- Le scheduler externe interroge l'API pour obtenir les exécutions à lancer via `NEXT_EXECUTION_DATE`

**État actuel:**

Stories précédentes complétées dans Epic 11 :
- **Story 11.1** (done) : Modèle de données SCHEDULED_EXECUTIONS et RECURRING_PATTERNS créé (migration V038)
  - Table SCHEDULED_EXECUTIONS avec colonnes: id, action_id, user_id, environment, parameters, scheduled_at, status, correlation_id, execution_id, created_at, updated_at
  - Table RECURRING_PATTERNS avec colonnes: scheduled_execution_id, pattern_type (daily, weekly, cron), pattern_config (CLOB JSON), next_execution_date, is_active
  - Index composite optimisé sur (IS_ACTIVE, NEXT_EXECUTION_DATE) pour requêtes du scheduler externe
  - scheduled_at NULL pour récurrences (utiliser RECURRING_PATTERNS.next_execution_date)
- **Story 11.3** (done) : API `POST /api/v1/scheduled-executions` pour créer une exécution planifiée one-time
  - Validation timezone, paramètres, permissions RBAC
  - Correlation ID pour tracing distribué
  - Audit logging avec SCHEDULED_EXECUTION_CREATED
- **Story 11.5** (done) : UI scheduler dans le wizard d'exécution
  - Option "Exécuter maintenant" vs "Planifier"
  - DatePicker avec validation date future
- **Story 11.6** (done) : Liste des exécutions planifiées et annulation
  - GET /api/v1/scheduled-executions avec filtres et pagination
  - PATCH /api/v1/scheduled-executions/{id} pour annuler (status → cancelled)
  - RBAC filtering: DBOPS voit toutes, DBA voit seulement ses propres
  - Modal détails avec correlation_id et execution_id (HIGH-2 fix)
- **Story 11.7** (done) : Patterns de récurrence simples (daily et weekly)
  - API étendue avec recurring_pattern pour daily/weekly
  - Calcul automatique de next_execution_date via `recurrence.py`
  - PATCH /api/v1/scheduled-executions/{id}/recurring-pattern pour toggle is_active
  - Recalcul next_execution_date lors de la réactivation
- **Story 11.8** (done) : Expressions cron pour récurrence avancée
  - Support expressions cron complètes avec bibliothèque croniter
  - Endpoints GET /validate-cron et /cron-next-executions
  - Calcul next_execution_date pour cron patterns avec croniter
  - UI avec presets, validation temps réel, preview

**Objectif de cette story (11.10):**

Créer une API dédiée pour un **scheduler externe** (Control-M, Django scheduler, etc.) qui lui permet de :
1. **Récupérer la liste des exécutions pending** à exécuter (one-time et recurring) en fonction d'un timestamp
2. **Créer l'exécution effective** en appelant POST /api/v1/executions (endpoint existant)
3. **Mettre à jour le statut** de l'exécution planifiée après exécution (status → executed, execution_id renseigné)
4. **Recalculer automatiquement** le next_execution_date pour les patterns récurrents après exécution

Cette story est le **point d'intégration critique** entre le portail IDP et les systèmes d'orchestration externes. Elle permet au scheduler externe d'interroger l'API pour obtenir les schedules à exécuter sans avoir à accéder directement à la base de données Oracle.

## Acceptance Criteria

### AC1 - Endpoint GET /api/v1/scheduled-executions/pending

**Given** un scheduler externe est configuré et authentifié
**When** il appelle GET /api/v1/scheduled-executions/pending?before={timestamp}
**Then** l'API retourne la liste des exécutions avec status="pending" et (scheduled_at <= before OU recurring_pattern.next_execution_date <= before)

**Given** le timestamp before est "2026-02-03T06:00:00Z"
**When** la requête est envoyée
**Then** l'API retourne :
- Toutes les exécutions one-time avec scheduled_at <= "2026-02-03T06:00:00Z" et status="pending"
- Toutes les exécutions récurrentes (daily, weekly, cron) avec recurring_pattern.next_execution_date <= "2026-02-03T06:00:00Z" et recurring_pattern.is_active=true

**And** la réponse inclut pour chaque exécution :
- scheduled_execution_id
- action_id, action_name (JOIN avec ACTIONS_CATALOG)
- user_id, user_name (JOIN avec USERS)
- environment
- parameters (CLOB JSON)
- scheduled_at (NULL pour récurrences)
- recurring_pattern (si applicable) : pattern_type, pattern_config, next_execution_date
- correlation_id
- created_at

### AC2 - Pagination et tri des exécutions pending

**Given** le scheduler appelle GET /api/v1/scheduled-executions/pending?before={timestamp}
**When** il y a plus de 100 exécutions à retourner
**Then** l'API supporte la pagination avec paramètres `limit` (défaut: 100, max: 100) et `offset` (défaut: 0)

**And** la réponse inclut :
```json
{
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 100,
    "total_count": 250,
    "total_pages": 3
  }
}
```

**Given** plusieurs exécutions sont pending
**When** la liste est retournée
**Then** les exécutions sont triées par date d'exécution prévue (most urgent first) :
- ORDER BY COALESCE(scheduled_at, next_execution_date) ASC

### AC3 - Exécuter une scheduled execution via POST /api/v1/executions

**Given** le scheduler externe a récupéré une exécution planifiée via GET /pending
**When** il veut l'exécuter
**Then** il appelle POST /api/v1/executions (endpoint existant de Story 4-3) avec les paramètres :
```json
{
  "action_id": 123,
  "environment": "prod",
  "parameters": {...},
  "correlation_id": "uuid-from-scheduled-execution"
}
```

**And** l'API POST /api/v1/executions retourne :
```json
{
  "data": {
    "execution_id": 456,
    "status": "SUBMITTED",
    "correlation_id": "uuid-from-scheduled-execution",
    "created_at": "2026-02-03T02:00:05Z"
  }
}
```

### AC4 - Mettre à jour le statut après exécution

**Given** le scheduler externe a créé une exécution via POST /api/v1/executions
**When** il reçoit l'execution_id de retour (ex: 456)
**Then** il appelle PATCH /api/v1/scheduled-executions/{scheduled_execution_id} avec :
```json
{
  "status": "executed",
  "execution_id": 456
}
```

**And** la table SCHEDULED_EXECUTIONS est mise à jour :
- status → "executed"
- execution_id → 456
- updated_at → timestamp actuel

**And** un log audit est créé avec action_type : "SCHEDULED_EXECUTION_EXECUTED"

### AC5 - Recalcul automatique du next_execution_date pour récurrences

**Given** une exécution récurrente (daily, weekly ou cron) est mise à jour avec status="executed"
**When** l'API PATCH est appelée
**Then** le backend recalcule automatiquement next_execution_date selon le pattern de récurrence :
- Daily : +1 jour
- Weekly : +7 jours
- Cron : Utilise croniter pour calculer la prochaine occurrence depuis current_next_execution_date

**And** RECURRING_PATTERNS.next_execution_date est mis à jour avec la nouvelle valeur
**And** RECURRING_PATTERNS.is_active reste à true (la récurrence continue)
**And** SCHEDULED_EXECUTIONS.status revient à "pending" pour la prochaine occurrence

**Given** l'exécution est one-time (pas de recurring_pattern)
**When** elle est mise à jour avec status="executed"
**Then** next_execution_date n'est PAS recalculé (pas applicable)
**And** status reste "executed" (terminée définitivement)

### AC6 - Gestion des erreurs et cas limites

**Given** le scheduler appelle GET /pending?before={timestamp}
**When** aucune exécution n'est à exécuter
**Then** l'API retourne une liste vide :
```json
{
  "data": [],
  "pagination": {
    "page": 1,
    "page_size": 100,
    "total_count": 0,
    "total_pages": 1
  }
}
```

**Given** le scheduler appelle PATCH avec scheduled_execution_id inexistant
**When** la requête est envoyée
**Then** l'API retourne une erreur 404 avec :
```json
{
  "error": {
    "code": "SCHEDULED_EXECUTION_NOT_FOUND",
    "message": "Exécution planifiée introuvable avec ID {id}"
  }
}
```

**Given** le scheduler appelle PATCH avec status="executed" mais execution_id manquant
**When** la requête est envoyée
**Then** l'API retourne une erreur 400 avec :
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "execution_id est requis lors de la transition vers status 'executed'"
  }
}
```

**Given** le scheduler appelle PATCH pour une exécution déjà executed
**When** la requête est envoyée
**Then** l'API retourne une erreur 400 avec :
```json
{
  "error": {
    "code": "INVALID_STATE",
    "message": "Impossible de mettre à jour une exécution déjà executed"
  }
}
```

### AC7 - Sécurité et authentification du scheduler externe

**Given** le scheduler externe appelle l'API
**When** il s'authentifie
**Then** il utilise un compte de service avec profil "dbops" et JWT token

**And** tous les appels API incluent le header Authorization avec Bearer token
**And** tous les appels sont tracés dans les logs avec scheduler_identity
**And** le rate limiting est appliqué : maximum 100 requêtes/minute

**Given** un utilisateur non-dbops tente d'appeler GET /pending
**When** la requête est envoyée
**Then** l'API retourne une erreur 403 Forbidden

### AC8 - Audit logging et traceability

**Given** le scheduler récupère des exécutions pending
**When** GET /pending est appelé
**Then** un log est créé avec :
- event: "scheduled_executions_pending_requested"
- before: timestamp
- count: nombre d'exécutions retournées
- correlation_id: UUID généré pour la requête

**Given** le scheduler met à jour une exécution avec status="executed"
**When** PATCH est appelé
**Then** un log audit est créé dans AUDIT_LOG avec :
- action_type: "SCHEDULED_EXECUTION_EXECUTED"
- resource_type: "scheduled_execution"
- resource_id: scheduled_execution_id
- details: {"execution_id": 456, "next_execution_date": "2026-02-04T02:00:00Z" (si recurring)}
- user_id: scheduler service account user_id
- correlation_id: UUID de la scheduled execution

## Tasks / Subtasks

- [x] Task 1: Créer l'endpoint GET /api/v1/scheduled-executions/pending (AC1, AC2)
  - [ ] Subtask 1.1: Ajouter route GET /pending dans `backend/app/api/v1/scheduled_executions.py`
  - [ ] Subtask 1.2: Ajouter paramètre Query `before: datetime` (obligatoire)
  - [ ] Subtask 1.3: Ajouter paramètres pagination `limit: int = 100` (max 100), `offset: int = 0`
  - [ ] Subtask 1.4: Vérifier RBAC : utilisateur doit avoir profil "dbops" (require_profile("dbops"))
  - [ ] Subtask 1.5: Appeler repository.list_pending_executions(before, limit, offset)
  - [ ] Subtask 1.6: Appeler repository.count_pending_executions(before) pour total_count
  - [ ] Subtask 1.7: Calculer pagination (page, page_size, total_count, total_pages)
  - [ ] Subtask 1.8: Retourner réponse avec {"data": [...], "pagination": {...}}
  - [ ] Subtask 1.9: Logger l'événement "scheduled_executions_pending_requested" avec correlation_id

- [x] Task 2: Implémenter repository.list_pending_executions() (AC1)
  - [ ] Subtask 2.1: Créer méthode `list_pending_executions(before, limit, offset)` dans `scheduled_execution_repository.py`
  - [ ] Subtask 2.2: Construire requête SQL avec :
    - JOIN ACTIONS_CATALOG pour action_name
    - JOIN USERS pour user_name (username)
    - LEFT JOIN RECURRING_PATTERNS pour recurring info
  - [ ] Subtask 2.3: Filtrer WHERE (SE.STATUS = 'pending' AND ((SE.SCHEDULED_AT IS NOT NULL AND SE.SCHEDULED_AT <= :before) OR (RP.NEXT_EXECUTION_DATE IS NOT NULL AND RP.NEXT_EXECUTION_DATE <= :before AND RP.IS_ACTIVE = 1)))
  - [ ] Subtask 2.4: Trier ORDER BY COALESCE(SE.SCHEDULED_AT, RP.NEXT_EXECUTION_DATE) ASC
  - [ ] Subtask 2.5: Appliquer pagination avec OFFSET et FETCH NEXT
  - [ ] Subtask 2.6: Parser les résultats et créer objets ScheduledExecutionPendingItem
  - [ ] Subtask 2.7: Parser recurring_pattern JSON si présent

- [x] Task 3: Implémenter repository.count_pending_executions() (AC2)
  - [ ] Subtask 3.1: Créer méthode `count_pending_executions(before)` dans repository
  - [ ] Subtask 3.2: Construire requête SQL COUNT avec même filtre WHERE que list_pending_executions
  - [ ] Subtask 3.3: Retourner int (total count)

- [x] Task 4: Créer modèles Pydantic pour pending endpoint (AC1)
  - [ ] Subtask 4.1: Créer `ScheduledExecutionPendingItem` dans `backend/app/models/scheduled_execution.py`
  - [ ] Subtask 4.2: Fields : scheduled_execution_id, action_id, action_name, user_id, user_name, environment, parameters, scheduled_at, recurring_pattern, correlation_id, created_at
  - [ ] Subtask 4.3: Utiliser RecurringPatternResponse existant pour recurring_pattern

- [x] Task 5: Étendre l'endpoint PATCH pour accepter status="executed" et execution_id (AC4)
  - [ ] Subtask 5.1: Modifier endpoint PATCH /api/v1/scheduled-executions/{id} existant (Story 11.6)
  - [ ] Subtask 5.2: Créer modèle Pydantic `ScheduledExecutionUpdateRequest` avec fields: status (Literal["cancelled", "executed"]), execution_id (Optional[int])
  - [ ] Subtask 5.3: Valider : si status="executed" → execution_id est requis (sinon erreur 400)
  - [ ] Subtask 5.4: Appeler repository.get_scheduled_execution(id) pour vérifier existence
  - [ ] Subtask 5.5: Vérifier que status actuel est "pending" (sinon erreur 400 "INVALID_STATE")
  - [ ] Subtask 5.6: Si status="executed" et recurring_pattern existe → appeler service pour recalculer next_execution_date
  - [ ] Subtask 5.7: Appeler repository.update_scheduled_execution_status(id, new_status, execution_id)
  - [ ] Subtask 5.8: Tracer dans audit_log : SCHEDULED_EXECUTION_EXECUTED avec execution_id et next_execution_date (si recurring)

- [x] Task 6: Implémenter la logique de recalcul next_execution_date (AC5)
  - [ ] Subtask 6.1: Créer service method `handle_scheduled_execution_executed(scheduled_execution_id, execution_id)` dans service layer
  - [ ] Subtask 6.2: Charger la scheduled execution avec repository.get_by_id()
  - [ ] Subtask 6.3: Vérifier si recurring_pattern existe (si non → one-time, pas de recalcul)
  - [ ] Subtask 6.4: Si recurring → charger recurring_pattern avec repository.get_recurring_pattern()
  - [ ] Subtask 6.5: Calculer new_next_execution_date avec recurrence.increment_next_execution_date(pattern_type, pattern_config, current_next_execution_date)
  - [ ] Subtask 6.6: Appeler repository.update_recurring_pattern_next_execution(scheduled_execution_id, new_next_execution_date)
  - [ ] Subtask 6.7: Mettre à jour SCHEDULED_EXECUTIONS status → "pending" pour la prochaine occurrence (si recurring)
  - [ ] Subtask 6.8: Logger l'événement "recurring_pattern_next_execution_recalculated"

- [x] Task 7: Implémenter repository.update_scheduled_execution_status() (AC4)
  - [ ] Subtask 7.1: Créer méthode `update_scheduled_execution_status(id, new_status, execution_id)` dans repository
  - [ ] Subtask 7.2: Construire UPDATE SQL : SET STATUS = :new_status, EXECUTION_ID = :execution_id, UPDATED_AT = CURRENT_TIMESTAMP WHERE ID = :id
  - [ ] Subtask 7.3: Exécuter query avec bind variables
  - [ ] Subtask 7.4: Commit transaction
  - [ ] Subtask 7.5: Retourner bool (updated or not)

- [x] Task 8: Implémenter repository.update_recurring_pattern_next_execution() (AC5)
  - [ ] Subtask 8.1: Créer méthode `update_recurring_pattern_next_execution(scheduled_execution_id, new_next_execution_date)` dans repository
  - [ ] Subtask 8.2: Construire UPDATE SQL : SET NEXT_EXECUTION_DATE = :new_date, UPDATED_AT = CURRENT_TIMESTAMP WHERE SCHEDULED_EXECUTION_ID = :id
  - [ ] Subtask 8.3: Exécuter query avec bind variables
  - [ ] Subtask 8.4: Commit transaction

- [x] Task 9: Gestion des erreurs et validations (AC6)
  - [ ] Subtask 9.1: Valider before timestamp : doit être datetime ISO 8601
  - [ ] Subtask 9.2: Si scheduled_execution_id not found → lever NotFoundError avec code "SCHEDULED_EXECUTION_NOT_FOUND"
  - [ ] Subtask 9.3: Si status="executed" sans execution_id → lever InvalidStateError avec code "VALIDATION_ERROR"
  - [ ] Subtask 9.4: Si tentative de mettre à jour une exécution déjà executed → lever InvalidStateError avec code "INVALID_STATE"
  - [ ] Subtask 9.5: Gérer erreurs DB et lever exceptions appropriées

- [x] Task 10: Sécurité et RBAC (AC7)
  - [ ] Subtask 10.1: Ajouter Depends(require_profile("dbops")) sur GET /pending
  - [ ] Subtask 10.2: Documenter dans architecture : compte de service scheduler avec profil "dbops"
  - [ ] Subtask 10.3: Vérifier que le token JWT inclut le user_id du scheduler service account
  - [ ] Subtask 10.4: Logger tous les appels avec scheduler_identity (user_id ou username)
  - [ ] Subtask 10.5: Considérer rate limiting (100 req/min) - documenter dans README

- [x] Task 11: Audit logging (AC8)
  - [ ] Subtask 11.1: Logger GET /pending avec structlog : "scheduled_executions_pending_requested", before, count, correlation_id
  - [ ] Subtask 11.2: Créer audit log pour PATCH executed : action_type="SCHEDULED_EXECUTION_EXECUTED", details avec execution_id et next_execution_date
  - [ ] Subtask 11.3: Bind correlation_id dans structlog contextvars pour tous les logs de la requête

- [x] Task 12: Tests backend pour GET /pending (AC1, AC2)
  - [ ] Subtask 12.1: Test integration `test_get_pending_executions_one_time` - Exécution one-time avec scheduled_at <= before
  - [ ] Subtask 12.2: Test integration `test_get_pending_executions_recurring_daily` - Exécution daily avec next_execution_date <= before
  - [ ] Subtask 12.3: Test integration `test_get_pending_executions_recurring_cron` - Exécution cron avec next_execution_date <= before
  - [ ] Subtask 12.4: Test integration `test_get_pending_executions_excludes_future` - Exécutions avec scheduled_at > before sont exclues
  - [ ] Subtask 12.5: Test integration `test_get_pending_executions_excludes_cancelled` - Exécutions cancelled sont exclues
  - [ ] Subtask 12.6: Test integration `test_get_pending_executions_excludes_executed` - Exécutions executed sont exclues
  - [ ] Subtask 12.7: Test integration `test_get_pending_executions_excludes_inactive_recurring` - Récurrences is_active=false exclues
  - [ ] Subtask 12.8: Test integration `test_get_pending_executions_sorted_by_date` - Tri par date ASC (most urgent first)
  - [ ] Subtask 12.9: Test integration `test_get_pending_executions_pagination` - Pagination avec limit et offset
  - [ ] Subtask 12.10: Test integration `test_get_pending_executions_empty_list` - Aucune exécution pending → []
  - [ ] Subtask 12.11: Test integration `test_get_pending_executions_includes_action_name` - JOIN avec ACTIONS_CATALOG
  - [ ] Subtask 12.12: Test integration `test_get_pending_executions_includes_user_name` - JOIN avec USERS

- [x] Task 13: Tests backend pour PATCH status="executed" (AC4, AC5, AC6)
  - [ ] Subtask 13.1: Test integration `test_update_scheduled_execution_to_executed_one_time` - One-time → executed, pas de recalcul
  - [ ] Subtask 13.2: Test integration `test_update_scheduled_execution_to_executed_recurring_daily` - Daily → executed, next_execution_date +1 jour
  - [ ] Subtask 13.3: Test integration `test_update_scheduled_execution_to_executed_recurring_weekly` - Weekly → executed, next_execution_date +7 jours
  - [ ] Subtask 13.4: Test integration `test_update_scheduled_execution_to_executed_recurring_cron` - Cron → executed, next_execution_date recalculé avec croniter
  - [ ] Subtask 13.5: Test integration `test_update_scheduled_execution_missing_execution_id` - status="executed" sans execution_id → 400
  - [ ] Subtask 13.6: Test integration `test_update_scheduled_execution_not_found` - ID inexistant → 404
  - [ ] Subtask 13.7: Test integration `test_update_scheduled_execution_already_executed` - Déjà executed → 400 INVALID_STATE
  - [ ] Subtask 13.8: Test integration `test_update_scheduled_execution_audit_log` - Vérifie SCHEDULED_EXECUTION_EXECUTED dans audit_log
  - [ ] Subtask 13.9: Test integration `test_update_scheduled_execution_execution_id_populated` - EXECUTION_ID renseigné dans DB

- [x] Task 14: Tests backend pour RBAC et sécurité (AC7)
  - [ ] Subtask 14.1: Test integration `test_get_pending_requires_dbops_profile` - Non-DBOPS → 403
  - [ ] Subtask 14.2: Test integration `test_get_pending_with_dbops_profile` - DBOPS → 200
  - [ ] Subtask 14.3: Test integration `test_patch_executed_requires_dbops_profile` - Non-DBOPS → 403 (si applicable)

- [x] Task 15: Documentation et validation manuelle (AC7, AC8)
  - [ ] Subtask 15.1: Documenter dans README : endpoint GET /pending pour scheduler externe
  - [ ] Subtask 15.2: Documenter format de réponse avec exemple complet
  - [ ] Subtask 15.3: Documenter workflow : GET /pending → POST /executions → PATCH /scheduled-executions
  - [ ] Subtask 15.4: Documenter authentification : JWT token avec profil "dbops"
  - [ ] Subtask 15.5: Documenter rate limiting : 100 req/min recommandé
  - [ ] Subtask 15.6: Tester manuellement GET /pending avec before dans le futur → liste non-vide
  - [ ] Subtask 15.7: Tester manuellement POST /executions avec paramètres d'une scheduled execution
  - [ ] Subtask 15.8: Tester manuellement PATCH avec status="executed" et execution_id → next_execution_date recalculé
  - [ ] Subtask 15.9: Vérifier audit logs pour tous les événements
  - [ ] Subtask 15.10: Story file mis à jour avec status=done

## Dev Notes

### Architecture et contraintes techniques

**Stack technique backend :**
- Backend : FastAPI + python-oracledb (async)
- Base de données : Oracle 19c
- Migration : Flyway (V038 déjà appliquée en Story 11.1, **aucune nouvelle migration requise**)
- Pattern : SQL brut via repositories
- Authentification : JWT via `Depends(get_current_user)`
- RBAC : Vérification profil "dbops" avec `require_profile("dbops")`
- Date/time : datetime.timezone.utc pour tous les calculs
- Logging : structlog avec correlation_id

**Tables utilisées :**
- `SCHEDULED_EXECUTIONS` : Exécutions planifiées (one-time et recurring)
  - Colonnes clés : id, action_id, user_id, environment, parameters (CLOB JSON), scheduled_at (NULL pour recurring), status ('pending', 'executed', 'cancelled'), correlation_id, execution_id (FK vers EXECUTIONS), created_at, updated_at
- `RECURRING_PATTERNS` : Patterns de récurrence (daily, weekly, cron)
  - Colonnes clés : scheduled_execution_id (PK, FK), pattern_type ('daily', 'weekly', 'cron'), pattern_config (CLOB JSON), next_execution_date (TIMESTAMP), is_active (NUMBER(1)), updated_at
  - Index : (IS_ACTIVE, NEXT_EXECUTION_DATE) pour performance GET /pending
- `ACTIONS_CATALOG` : Détails des actions (JOIN pour action_name)
- `USERS` : Utilisateurs (JOIN pour user_name/username)
- `EXECUTIONS` : Exécutions effectives (référencées par execution_id)
- `AUDIT_LOG` : Traçabilité des opérations

**Endpoint existant à réutiliser :**
- `POST /api/v1/executions` (Story 4-3) : Créer et lancer une exécution
  - Input : action_id, environment, parameters, correlation_id (optional)
  - Output : execution_id, status ("SUBMITTED"), correlation_id, created_at

**Endpoint existant à étendre :**
- `PATCH /api/v1/scheduled-executions/{id}` (Story 11.6) : Actuellement pour annulation (status → cancelled)
  - Étendre pour supporter : status → "executed" avec execution_id requis
  - Déclencher recalcul next_execution_date si recurring

**Bibliothèques existantes :**
- `app/utils/recurrence.py` (Stories 11.7, 11.8) : Fonctions calculate_next_execution_date() et increment_next_execution_date()
- `croniter` (Story 11.8) : Pour calcul cron patterns

### Patterns de code à suivre

**Pattern 1 : Endpoint GET /pending avec pagination**

Source : Extension de `/idp-portal/backend/app/api/v1/scheduled_executions.py`

```python
# backend/app/api/v1/scheduled_executions.py

from fastapi import APIRouter, Depends, Query, status
from datetime import datetime, timezone
import uuid
import structlog
from app.api.deps import get_current_user
from app.core.security import require_profile
from app.models.auth import UserProfile
from app.models.scheduled_execution import ScheduledExecutionPendingItem
from app.repositories import scheduled_execution_repository
from app.core.exceptions import NotFoundError, InvalidStateError

router = APIRouter()
logger = structlog.get_logger(__name__)

@router.get("/scheduled-executions/pending", response_model=None)
async def get_pending_executions(
    before: datetime = Query(
        ...,
        description="Timestamp limite pour récupérer les exécutions à lancer (ISO 8601 UTC)",
        example="2026-02-03T06:00:00Z",
    ),
    limit: int = Query(100, ge=1, le=100, description="Nombre max d'exécutions à retourner"),
    offset: int = Query(0, ge=0, description="Offset pour pagination"),
    user: UserProfile = Depends(require_profile("dbops")),
) -> dict:
    """
    Récupérer la liste des exécutions planifiées pending à exécuter (Story 11.10).

    Endpoint dédié pour scheduler externe (Control-M, Django scheduler).
    Retourne les exécutions one-time et recurring à exécuter avant le timestamp 'before'.

    Requires: DBOPS profile (compte de service scheduler)
    """
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    # Validate before timestamp (ensure UTC)
    if before.tzinfo is None:
        before = before.replace(tzinfo=timezone.utc)

    logger.info(
        "scheduled_executions_pending_requested",
        before=before.isoformat(),
        limit=limit,
        offset=offset,
        user_id=user.id,
    )

    # Get pending executions
    items = await scheduled_execution_repository.list_pending_executions(
        before=before,
        limit=limit,
        offset=offset,
    )

    # Get total count for pagination
    total_count = await scheduled_execution_repository.count_pending_executions(
        before=before,
    )

    # Calculate pagination
    page = (offset // limit) + 1
    total_pages = (total_count + limit - 1) // limit if total_count > 0 else 1

    logger.info(
        "scheduled_executions_pending_retrieved",
        count=len(items),
        total_count=total_count,
    )

    return {
        "data": [item.model_dump(mode="json") for item in items],
        "pagination": {
            "page": page,
            "page_size": limit,
            "total_count": total_count,
            "total_pages": total_pages,
        },
        "correlation_id": correlation_id,
    }
```

**Pattern 2 : Repository list_pending_executions avec JOIN**

Source : Extension de `/idp-portal/backend/app/repositories/scheduled_execution_repository.py`

```python
# backend/app/repositories/scheduled_execution_repository.py

import json
import structlog
from datetime import datetime, timezone
from typing import Optional
from app.models.scheduled_execution import (
    ScheduledExecutionPendingItem,
    RecurringPatternResponse,
)
from app.db.connection import get_db_connection

logger = structlog.get_logger(__name__)

async def list_pending_executions(
    before: datetime,
    limit: int = 100,
    offset: int = 0,
) -> list[ScheduledExecutionPendingItem]:
    """
    Récupérer la liste des exécutions pending à exécuter avant 'before'.

    Inclut :
    - Exécutions one-time avec scheduled_at <= before
    - Exécutions recurring avec next_execution_date <= before et is_active=true

    Tri par date d'exécution prévue (ASC, most urgent first).
    """
    connection = await get_db_connection()
    cursor = connection.cursor()

    # Query SQL avec JOINs pour enrichissement
    query = """
        SELECT
            SE.ID AS scheduled_execution_id,
            SE.ACTION_ID,
            AC.NAME AS action_name,
            SE.USER_ID,
            U.USERNAME AS user_name,
            SE.ENVIRONMENT,
            SE.PARAMETERS,
            SE.SCHEDULED_AT,
            SE.CORRELATION_ID,
            SE.CREATED_AT,
            RP.PATTERN_TYPE,
            RP.PATTERN_CONFIG,
            RP.NEXT_EXECUTION_DATE,
            RP.IS_ACTIVE
        FROM SCHEDULED_EXECUTIONS SE
        INNER JOIN ACTIONS_CATALOG AC ON SE.ACTION_ID = AC.ID
        INNER JOIN USERS U ON SE.USER_ID = U.ID
        LEFT JOIN RECURRING_PATTERNS RP ON SE.ID = RP.SCHEDULED_EXECUTION_ID
        WHERE SE.STATUS = 'pending'
          AND (
              (SE.SCHEDULED_AT IS NOT NULL AND SE.SCHEDULED_AT <= :before)
              OR (RP.NEXT_EXECUTION_DATE IS NOT NULL AND RP.NEXT_EXECUTION_DATE <= :before AND RP.IS_ACTIVE = 1)
          )
        ORDER BY COALESCE(SE.SCHEDULED_AT, RP.NEXT_EXECUTION_DATE) ASC
        OFFSET :offset ROWS
        FETCH NEXT :limit ROWS ONLY
    """

    try:
        cursor.execute(
            query,
            before=before,
            offset=offset,
            limit=limit,
        )

        rows = cursor.fetchall()
        items = []

        for row in rows:
            # Parse recurring_pattern if present
            recurring_pattern = None
            if row[10] is not None:  # PATTERN_TYPE
                pattern_config = json.loads(row[11]) if row[11] else {}
                recurring_pattern = RecurringPatternResponse(
                    pattern_type=row[10],
                    pattern_config=pattern_config,
                    next_execution_date=row[12],
                    is_active=bool(row[13]),
                )

            # Parse parameters CLOB
            parameters = json.loads(row[6]) if row[6] else {}

            item = ScheduledExecutionPendingItem(
                scheduled_execution_id=row[0],
                action_id=row[1],
                action_name=row[2],
                user_id=row[3],
                user_name=row[4],
                environment=row[5],
                parameters=parameters,
                scheduled_at=row[7],
                recurring_pattern=recurring_pattern,
                correlation_id=row[8],
                created_at=row[9],
            )
            items.append(item)

        logger.info(
            "pending_executions_retrieved",
            count=len(items),
            before=before.isoformat(),
        )

        return items

    finally:
        cursor.close()

async def count_pending_executions(before: datetime) -> int:
    """
    Compter le nombre total d'exécutions pending avant 'before'.
    """
    connection = await get_db_connection()
    cursor = connection.cursor()

    query = """
        SELECT COUNT(*)
        FROM SCHEDULED_EXECUTIONS SE
        LEFT JOIN RECURRING_PATTERNS RP ON SE.ID = RP.SCHEDULED_EXECUTION_ID
        WHERE SE.STATUS = 'pending'
          AND (
              (SE.SCHEDULED_AT IS NOT NULL AND SE.SCHEDULED_AT <= :before)
              OR (RP.NEXT_EXECUTION_DATE IS NOT NULL AND RP.NEXT_EXECUTION_DATE <= :before AND RP.IS_ACTIVE = 1)
          )
    """

    try:
        cursor.execute(query, before=before)
        result = cursor.fetchone()
        return result[0] if result else 0
    finally:
        cursor.close()
```

**Pattern 3 : Modèle Pydantic ScheduledExecutionPendingItem**

Source : Extension de `/idp-portal/backend/app/models/scheduled_execution.py`

```python
# backend/app/models/scheduled_execution.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ScheduledExecutionPendingItem(BaseModel):
    """
    Exécution planifiée pending pour scheduler externe (Story 11.10).
    """
    scheduled_execution_id: int = Field(..., description="ID de l'exécution planifiée")
    action_id: int = Field(..., description="ID de l'action à exécuter")
    action_name: str = Field(..., description="Nom de l'action")
    user_id: int = Field(..., description="ID de l'utilisateur ayant créé l'exécution")
    user_name: str = Field(..., description="Nom d'utilisateur")
    environment: str = Field(..., description="Environnement (dev, staging, prod)")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Paramètres de l'action")
    scheduled_at: Optional[datetime] = Field(None, description="Date/heure planifiée (NULL pour recurring)")
    recurring_pattern: Optional[RecurringPatternResponse] = Field(None, description="Pattern de récurrence si applicable")
    correlation_id: str = Field(..., description="Correlation ID pour tracing")
    created_at: datetime = Field(..., description="Date de création")

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }
```

**Pattern 4 : Extension PATCH pour status="executed"**

Source : Extension de `/idp-portal/backend/app/api/v1/scheduled_executions.py`

```python
# backend/app/api/v1/scheduled_executions.py

class ScheduledExecutionUpdateRequest(BaseModel):
    """Request pour mise à jour d'une scheduled execution (Story 11.10)."""
    status: Literal["cancelled", "executed"] = Field(..., description="Nouveau statut")
    execution_id: Optional[int] = Field(None, description="ID de l'exécution créée (requis si status=executed)")

    @model_validator(mode="after")
    def validate_execution_id_required_for_executed(self):
        """Valider que execution_id est présent si status=executed."""
        if self.status == "executed" and self.execution_id is None:
            raise ValueError(
                "execution_id est requis lors de la transition vers status 'executed'"
            )
        return self

@router.patch("/scheduled-executions/{scheduled_execution_id}", response_model=None)
async def update_scheduled_execution(
    scheduled_execution_id: int,
    request: ScheduledExecutionUpdateRequest,
    user: UserProfile = Depends(get_current_user),
) -> dict:
    """
    Mettre à jour le statut d'une exécution planifiée (Stories 11.6, 11.10).

    - status="cancelled" : Annuler l'exécution (Story 11.6)
    - status="executed" : Marquer comme exécutée après lancement par scheduler externe (Story 11.10)
    """
    correlation_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    logger.info(
        "scheduled_execution_update_requested",
        scheduled_execution_id=scheduled_execution_id,
        new_status=request.status,
        execution_id=request.execution_id,
    )

    # Get scheduled execution
    scheduled_execution = await scheduled_execution_repository.get_by_id(scheduled_execution_id)
    if not scheduled_execution:
        raise NotFoundError(
            message=f"Exécution planifiée introuvable avec ID {scheduled_execution_id}",
            code="SCHEDULED_EXECUTION_NOT_FOUND",
        )

    # Verify current status is "pending"
    if scheduled_execution.status != "pending":
        raise InvalidStateError(
            message=f"Impossible de mettre à jour une exécution avec status '{scheduled_execution.status}'",
            code="INVALID_STATE",
        )

    # Handle status="executed" with recalculation for recurring
    if request.status == "executed":
        # Check if recurring pattern exists
        recurring_pattern = await scheduled_execution_repository.get_recurring_pattern(scheduled_execution_id)

        if recurring_pattern:
            # Recalculate next_execution_date for recurring patterns
            from app.utils.recurrence import increment_next_execution_date

            new_next_execution_date = increment_next_execution_date(
                pattern_type=recurring_pattern.pattern_type,
                pattern_config=recurring_pattern.pattern_config,
                current_next_execution=recurring_pattern.next_execution_date,
            )

            # Update recurring pattern
            await scheduled_execution_repository.update_recurring_pattern_next_execution(
                scheduled_execution_id=scheduled_execution_id,
                new_next_execution_date=new_next_execution_date,
            )

            # Update status back to "pending" for next occurrence (recurring continues)
            await scheduled_execution_repository.update_scheduled_execution_status(
                scheduled_execution_id=scheduled_execution_id,
                new_status="pending",
                execution_id=request.execution_id,
            )

            logger.info(
                "recurring_pattern_next_execution_recalculated",
                scheduled_execution_id=scheduled_execution_id,
                pattern_type=recurring_pattern.pattern_type,
                old_next_execution=recurring_pattern.next_execution_date.isoformat(),
                new_next_execution=new_next_execution_date.isoformat(),
            )

            # Audit log
            await audit_repository.create_audit_log(
                action_type="SCHEDULED_EXECUTION_EXECUTED",
                resource_type="scheduled_execution",
                resource_id=scheduled_execution_id,
                user_id=user.id,
                details={
                    "execution_id": request.execution_id,
                    "recurring": True,
                    "next_execution_date": new_next_execution_date.isoformat(),
                },
                correlation_id=correlation_id,
            )
        else:
            # One-time execution: status stays "executed"
            await scheduled_execution_repository.update_scheduled_execution_status(
                scheduled_execution_id=scheduled_execution_id,
                new_status="executed",
                execution_id=request.execution_id,
            )

            # Audit log
            await audit_repository.create_audit_log(
                action_type="SCHEDULED_EXECUTION_EXECUTED",
                resource_type="scheduled_execution",
                resource_id=scheduled_execution_id,
                user_id=user.id,
                details={
                    "execution_id": request.execution_id,
                    "recurring": False,
                },
                correlation_id=correlation_id,
            )

    elif request.status == "cancelled":
        # Existing cancellation logic from Story 11.6
        await scheduled_execution_repository.update_scheduled_execution_status(
            scheduled_execution_id=scheduled_execution_id,
            new_status="cancelled",
            execution_id=None,
        )

        # Audit log (existing)
        await audit_repository.create_audit_log(
            action_type="SCHEDULED_EXECUTION_CANCELLED",
            resource_type="scheduled_execution",
            resource_id=scheduled_execution_id,
            user_id=user.id,
            details={},
            correlation_id=correlation_id,
        )

    logger.info(
        "scheduled_execution_updated",
        scheduled_execution_id=scheduled_execution_id,
        new_status=request.status,
    )

    return {"message": "Exécution planifiée mise à jour avec succès"}
```

**Pattern 5 : Repository update methods**

Source : Extension de `/idp-portal/backend/app/repositories/scheduled_execution_repository.py`

```python
# backend/app/repositories/scheduled_execution_repository.py

async def update_scheduled_execution_status(
    scheduled_execution_id: int,
    new_status: str,
    execution_id: Optional[int] = None,
) -> bool:
    """
    Mettre à jour le statut d'une scheduled execution (Stories 11.6, 11.10).
    """
    connection = await get_db_connection()
    cursor = connection.cursor()

    query = """
        UPDATE SCHEDULED_EXECUTIONS
        SET STATUS = :new_status,
            EXECUTION_ID = :execution_id,
            UPDATED_AT = CURRENT_TIMESTAMP
        WHERE ID = :scheduled_execution_id
    """

    try:
        cursor.execute(
            query,
            new_status=new_status,
            execution_id=execution_id,
            scheduled_execution_id=scheduled_execution_id,
        )

        connection.commit()

        logger.info(
            "scheduled_execution_status_updated",
            scheduled_execution_id=scheduled_execution_id,
            new_status=new_status,
            execution_id=execution_id,
        )

        return cursor.rowcount > 0

    finally:
        cursor.close()

async def update_recurring_pattern_next_execution(
    scheduled_execution_id: int,
    new_next_execution_date: datetime,
) -> None:
    """
    Mettre à jour next_execution_date pour un pattern récurrent (Story 11.10).
    """
    connection = await get_db_connection()
    cursor = connection.cursor()

    query = """
        UPDATE RECURRING_PATTERNS
        SET NEXT_EXECUTION_DATE = :new_next_execution_date,
            UPDATED_AT = CURRENT_TIMESTAMP
        WHERE SCHEDULED_EXECUTION_ID = :scheduled_execution_id
    """

    try:
        cursor.execute(
            query,
            new_next_execution_date=new_next_execution_date,
            scheduled_execution_id=scheduled_execution_id,
        )

        connection.commit()

        logger.info(
            "recurring_pattern_next_execution_updated",
            scheduled_execution_id=scheduled_execution_id,
            new_next_execution_date=new_next_execution_date.isoformat(),
        )

    finally:
        cursor.close()
```

### Source tree components to touch

**Fichiers à modifier :**
```
idp-portal/backend/app/api/v1/scheduled_executions.py                   # Ajouter GET /pending, étendre PATCH
idp-portal/backend/app/repositories/scheduled_execution_repository.py   # Ajouter list_pending_executions, count_pending_executions, update methods
idp-portal/backend/app/models/scheduled_execution.py                    # Ajouter ScheduledExecutionPendingItem, ScheduledExecutionUpdateRequest
```

**Fichiers à créer :**
```
idp-portal/backend/tests/integration/test_scheduled_executions_pending_api.py  # Tests GET /pending (12 tests)
idp-portal/backend/tests/integration/test_scheduled_executions_executed_api.py # Tests PATCH executed (9 tests)
```

**Fichiers de référence (patterns) :**
```
idp-portal/backend/app/api/v1/scheduled_executions.py                   # Pattern endpoint GET avec pagination (Story 11.6)
idp-portal/backend/app/api/v1/executions.py                             # Pattern POST executions (Story 4-3)
idp-portal/backend/app/api/v1/audit.py                                  # Pattern pagination (Story 6-3)
idp-portal/backend/app/repositories/scheduled_execution_repository.py   # Pattern repository (Stories 11.3, 11.6, 11.7)
idp-portal/backend/app/utils/recurrence.py                              # Pattern increment_next_execution_date (Stories 11.7, 11.8)
```

**Aucune modification frontend requise pour cette story** - API backend uniquement pour scheduler externe

### Testing standards summary

**Tests backend (pytest) :**

1. **Tests intégration GET /pending (test_scheduled_executions_pending_api.py) :**
   - `test_get_pending_executions_one_time` - Exécution one-time avec scheduled_at <= before
   - `test_get_pending_executions_recurring_daily` - Exécution daily avec next_execution_date <= before
   - `test_get_pending_executions_recurring_weekly` - Exécution weekly avec next_execution_date <= before
   - `test_get_pending_executions_recurring_cron` - Exécution cron avec next_execution_date <= before
   - `test_get_pending_executions_excludes_future` - Exécutions avec scheduled_at > before exclues
   - `test_get_pending_executions_excludes_cancelled` - Exécutions cancelled exclues
   - `test_get_pending_executions_excludes_executed` - Exécutions executed exclues
   - `test_get_pending_executions_excludes_inactive_recurring` - Récurrences is_active=false exclues
   - `test_get_pending_executions_sorted_by_date` - Tri par date ASC (most urgent first)
   - `test_get_pending_executions_pagination` - Pagination avec limit et offset
   - `test_get_pending_executions_empty_list` - Aucune exécution pending → []
   - `test_get_pending_executions_includes_action_name` - JOIN avec ACTIONS_CATALOG vérifié
   - `test_get_pending_executions_includes_user_name` - JOIN avec USERS vérifié
   - `test_get_pending_executions_requires_dbops_profile` - Non-DBOPS → 403

2. **Tests intégration PATCH executed (test_scheduled_executions_executed_api.py) :**
   - `test_update_scheduled_execution_to_executed_one_time` - One-time → executed, pas de recalcul
   - `test_update_scheduled_execution_to_executed_recurring_daily` - Daily → executed, next_execution_date +1 jour
   - `test_update_scheduled_execution_to_executed_recurring_weekly` - Weekly → executed, next_execution_date +7 jours
   - `test_update_scheduled_execution_to_executed_recurring_cron` - Cron → executed, next_execution_date recalculé avec croniter
   - `test_update_scheduled_execution_missing_execution_id` - status="executed" sans execution_id → 400
   - `test_update_scheduled_execution_not_found` - ID inexistant → 404
   - `test_update_scheduled_execution_already_executed` - Déjà executed → 400 INVALID_STATE
   - `test_update_scheduled_execution_audit_log` - Vérifie SCHEDULED_EXECUTION_EXECUTED dans audit_log
   - `test_update_scheduled_execution_execution_id_populated` - EXECUTION_ID renseigné dans DB

**Validation manuelle :**
1. Créer une exécution one-time avec scheduled_at dans le futur proche
2. Créer une exécution recurring daily avec next_execution_date dans le futur proche
3. Appeler GET /pending?before={futur} avec timestamp incluant ces exécutions → liste non-vide
4. Vérifier que les exécutions sont triées par date (ASC)
5. Appeler POST /api/v1/executions avec paramètres d'une exécution pending → récupérer execution_id
6. Appeler PATCH /api/v1/scheduled-executions/{id} avec status="executed" et execution_id → succès
7. Vérifier dans DB : SCHEDULED_EXECUTIONS.EXECUTION_ID renseigné
8. Si recurring : Vérifier que RECURRING_PATTERNS.NEXT_EXECUTION_DATE a été recalculé
9. Si recurring : Vérifier que SCHEDULED_EXECUTIONS.STATUS est revenu à "pending"
10. Vérifier audit logs : SCHEDULED_EXECUTION_EXECUTED avec execution_id et next_execution_date (si recurring)

### Learnings from previous stories (11-1, 11-3, 11-6, 11-7, 11-8)

**Story 11.1 (Modèle de données) :**
- Table RECURRING_PATTERNS avec IS_ACTIVE pour activer/désactiver sans supprimer
- Index composite `(IS_ACTIVE, NEXT_EXECUTION_DATE)` optimisé pour GET /pending
- scheduled_at NULL pour récurrences (utiliser RECURRING_PATTERNS.next_execution_date)
- Relation 1-to-0..1 : SCHEDULED_EXECUTIONS ↔ RECURRING_PATTERNS (UNIQUE constraint)

**Story 11.3 (API création one-time) :**
- Correlation ID systématique pour tracing distribué
- Validation timezone obligatoire avec Pydantic
- Audit logging pour toutes les opérations
- Deep copy de schema JSON pour éviter mutations

**Story 11.6 (Liste et annulation) :**
- Pattern pagination : limit (1-100), offset, page, total_count, total_pages
- RBAC filtering : DBA voit ses propres, DBOPS voit toutes
- JOIN avec ACTIONS_CATALOG et USERS pour enrichissement
- Modal détails avec correlation_id et execution_id (HIGH-2 fix)
- Pattern PATCH pour mise à jour statut (à étendre pour status="executed")

**Story 11.7 (Patterns daily/weekly) :**
- Calcul next_execution_date en backend avec datetime.timezone.utc
- Fonction increment_next_execution_date() pour recalcul après exécution
- PATCH toggle is_active avec recalcul automatique next_execution_date
- Audit logging pour RECURRING_* actions

**Story 11.8 (Expressions cron) :**
- Bibliothèque croniter pour parsing et calcul cron
- increment_next_execution_date() supporte cron avec croniter.get_next()
- Validation syntaxique ET sémantique avec croniter.is_valid()

**Patterns à éviter :**
- ❌ Ne pas calculer next_execution_date côté frontend (toujours backend)
- ❌ Ne pas oublier de recalculer next_execution_date après exécution (recurring)
- ❌ Ne pas oublier validation execution_id requis si status="executed"
- ❌ Ne pas permettre mise à jour si status n'est pas "pending" (état invalide)
- ❌ Ne pas oublier audit logging pour SCHEDULED_EXECUTION_EXECUTED

**Patterns à suivre :**
- ✅ Utiliser COALESCE(scheduled_at, next_execution_date) pour tri unifié
- ✅ Filter WHERE avec (one-time OR recurring) logique séparée
- ✅ JOIN avec ACTIONS_CATALOG et USERS pour enrichir la réponse
- ✅ Pagination avec OFFSET/FETCH NEXT pour Oracle
- ✅ Recalcul next_execution_date via increment_next_execution_date() (réutilisable)
- ✅ Validation Pydantic avec model_validator pour dépendances entre fields
- ✅ Correlation ID dans contextvars structlog pour tous les logs de la requête
- ✅ Audit logging avec details JSON pour next_execution_date et execution_id

**Learnings spécifiques scheduler externe :**
- Scheduler externe = compte de service avec profil "dbops"
- GET /pending interrogé régulièrement (ex: toutes les minutes) par scheduler
- Scheduler crée exécutions via POST /api/v1/executions (endpoint existant)
- Scheduler met à jour statut via PATCH avec execution_id
- Recalcul next_execution_date automatique pour récurrences → exécution continue
- Index (IS_ACTIVE, NEXT_EXECUTION_DATE) critique pour performance GET /pending

### Project Structure Notes

**Alignement avec unified project structure :**
- Backend FastAPI : `/idp-portal/backend/app/` (api/v1, repositories, models)
- Tests backend : `/idp-portal/backend/tests/` (integration/test_scheduled_executions_pending_api.py, integration/test_scheduled_executions_executed_api.py)
- Migrations Oracle : `/idp-portal/database/migrations/` (V038 déjà créée en Story 11.1, **aucune nouvelle migration requise**)

**Conventions de nommage :**
- API JSON fields : snake_case (`scheduled_execution_id`, `execution_id`, `next_execution_date`)
- Python : snake_case pour tout (fonctions, variables, modules)
- Endpoints : kebab-case (`/scheduled-executions/pending`)
- Fichiers tests : test_*_api.py (`test_scheduled_executions_pending_api.py`)

**Detected conflicts or variances :**
- ✅ Aucun conflit - Cette story étend Story 11.6 sans modifier les fonctionnalités existantes
- ✅ Réutilise endpoint POST /api/v1/executions de Story 4-3 (pas de modification nécessaire)
- ✅ Réutilise fonction increment_next_execution_date() de Stories 11.7 et 11.8
- ✅ Index (IS_ACTIVE, NEXT_EXECUTION_DATE) déjà optimisé en Story 11.1 pour cette requête
- ⚠️ **Attention** : GET /pending doit filtrer is_active=true pour récurrences (exclure désactivées)
- ⚠️ **Attention** : PATCH executed pour recurring doit remettre status à "pending" (pas "executed")
- ⚠️ **Attention** : Validation execution_id requis si status="executed" (erreur 400 sinon)
- ⚠️ **Attention** : Tri par COALESCE(scheduled_at, next_execution_date) pour unifier one-time et recurring

### References

**Epic et stories connexes :**
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 11] - Contexte complet Epic 11 Scheduling
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.10] - API integration scheduler externe (cette story)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.1] - Modèle de données SCHEDULED_EXECUTIONS et RECURRING_PATTERNS
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.3] - API créer exécution planifiée one-time
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.6] - Liste des exécutions planifiées et annulation
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.7] - Patterns de récurrence simples (daily/weekly)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.8] - Cron expressions pour récurrence avancée
- [Source: _bmad-output/planning-artifacts/epics.md#Story 4.3] - Moteur d'exécution et facade API (POST /executions)

**Architecture et patterns :**
- [Source: _bmad-output/planning-artifacts/architecture.md#API Patterns] - Conventions endpoint, réponse format, pagination
- [Source: _bmad-output/planning-artifacts/architecture.md#Security] - RBAC, JWT, profils (dbops)
- [Source: idp-portal/backend/app/utils/recurrence.py:1-640] - Pattern increment_next_execution_date (Stories 11.7, 11.8)
- [Source: idp-portal/backend/app/api/v1/scheduled_executions.py:1-903] - Pattern API avec pagination et RBAC
- [Source: idp-portal/backend/app/repositories/scheduled_execution_repository.py:1-842] - Pattern repository avec CLOB JSON
- [Source: idp-portal/backend/app/api/v1/executions.py:1-250] - POST /executions endpoint (Story 4-3)
- [Source: idp-portal/backend/app/api/v1/audit.py:1-420] - Pattern pagination (Story 6-3)

**Stories récentes (context et patterns) :**
- [Source: _bmad-output/implementation-artifacts/11-8-cron-expressions-pour-recurrence-avancee.md] - Story précédente (cron patterns)
- [Source: _bmad-output/implementation-artifacts/11-7-patterns-recurrence-simples-daily-weekly.md] - Patterns daily/weekly
- [Source: _bmad-output/implementation-artifacts/11-6-liste-executions-planifiees-et-annulation.md] - Liste et annulation
- [Source: _bmad-output/implementation-artifacts/11-3-api-creer-execution-planifiee-one-time.md] - API création scheduled execution
- [Source: _bmad-output/implementation-artifacts/11-1-modele-donnees-scheduled-executions-et-recurrence.md] - Modèle de données

**Commits récents (Git intelligence) :**
- Commit `eb14d29` : feat(scheduling): add cron expressions for advanced recurrence (story 11-8)
  - Fichiers : recurrence.py (_calculate_cron_next_execution), scheduled_executions.py (validate-cron, cron-next-executions)
  - Learnings : croniter pour parsing cron, increment_next_execution_date supporte cron
- Commit `bda6f78` : feat(scheduling): add daily and weekly recurring patterns (story 11-7)
  - Fichiers : recurrence.py (increment_next_execution_date), API PATCH toggle is_active
  - Learnings : Recalcul next_execution_date automatique, audit logging
- Commit `e286f13` : feat(scheduling): add scheduled executions list and cancellation (story 11-6)
  - Fichiers : scheduled_executions.py (GET, PATCH cancel), repository list/count
  - Learnings : Pattern pagination, RBAC filtering, enriched JOINs
- Commit `316cdd2` : feat(scheduling): add one-time scheduled execution API (story 11-3)
  - Learnings : Correlation ID, validation timezone, audit logging

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5-20250929

### Debug Log References

N/A

### Completion Notes List

Story créée avec contexte complet via :
1. Analyse exhaustive du codebase (agent Explore pour architecture + scheduled execution implementation)
2. Lecture des stories précédentes Epic 11 (11-1, 11-3, 11-5, 11-6, 11-7, 11-8)
3. Analyse des commits récents (git log)
4. Patterns API existants (executions.py, audit.py, scheduled_executions.py)

**Contexte analysé :**
- Modèle de données V038 (SCHEDULED_EXECUTIONS, RECURRING_PATTERNS avec index optimisé)
- API existante POST /api/v1/executions (Story 4-3) pour créer exécutions
- API existante GET/PATCH /api/v1/scheduled-executions (Stories 11.6, 11.7, 11.8)
- Fonction increment_next_execution_date() (Stories 11.7, 11.8) pour recalcul
- Patterns pagination, RBAC, audit logging, error handling

**Approche recommandée :**
1. Créer GET /api/v1/scheduled-executions/pending avec pagination et tri
2. Implémenter repository.list_pending_executions() avec JOINs et COALESCE
3. Implémenter repository.count_pending_executions() pour pagination
4. Étendre PATCH /api/v1/scheduled-executions/{id} pour status="executed"
5. Implémenter logique recalcul next_execution_date pour récurrences
6. Implémenter repository.update_scheduled_execution_status() et update_recurring_pattern_next_execution()
7. Tests complets : 12+ GET /pending + 9+ PATCH executed

**Points critiques :**
- Tri par COALESCE(scheduled_at, next_execution_date) ASC (most urgent first) (AC2)
- Filter WHERE avec logique (one-time OR recurring) pour inclure tous les types (AC1)
- Recalcul next_execution_date automatique pour recurring après exécution (AC5)
- Status revient à "pending" pour recurring (exécution continue) vs "executed" pour one-time (AC5)
- Validation execution_id requis si status="executed" (AC6)
- RBAC : require_profile("dbops") pour GET /pending (AC7)
- Audit logging avec SCHEDULED_EXECUTION_EXECUTED (AC8)

**Dépendances techniques :**
- Réutilise endpoint POST /api/v1/executions (Story 4-3) - aucune modification
- Réutilise fonction increment_next_execution_date() (Stories 11.7, 11.8) - aucune modification
- Réutilise croniter (Story 11.8) pour cron patterns
- Index (IS_ACTIVE, NEXT_EXECUTION_DATE) déjà créé en Story 11.1

**Compatibilité :**
- ✅ Compatible avec toutes les stories Epic 11 précédentes
- ✅ Réutilise modèle de données existant (pas de migration)
- ✅ Étend API existante PATCH (backward compatible)
- ✅ Suit patterns architecture : pagination, RBAC, audit

### File List

**Fichiers modifiés :**
- `idp-portal/backend/app/api/v1/scheduled_executions.py` - Ajout GET /pending, extension PATCH pour status="executed"
- `idp-portal/backend/app/repositories/scheduled_execution_repository.py` - Ajout list_pending_executions, count_pending_executions, update_scheduled_execution_status, update_recurring_pattern_next_execution
- `idp-portal/backend/app/models/scheduled_execution.py` - Ajout ScheduledExecutionPendingItem, ScheduledExecutionUpdateRequest

**Fichiers créés :**
- `idp-portal/backend/tests/integration/test_scheduled_executions_pending_api.py` - Tests GET /pending (14 tests)
- `idp-portal/backend/tests/integration/test_scheduled_executions_executed_api.py` - Tests PATCH executed (9 tests)

**Aucune migration de base de données requise** - Réutilise migration V038 de Story 11.1

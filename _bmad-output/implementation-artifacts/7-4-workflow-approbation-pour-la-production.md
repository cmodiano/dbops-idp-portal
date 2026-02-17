# Story 7.4: Workflow d'approbation pour la production

Status: complete

## Story

As a DBA,
I want approuver ou refuser les demandes d'execution en production qui le requierent,
So that les actions a fort impact sont validees par un expert avant execution.

## Acceptance Criteria

### AC1: Soumission en attente d'approbation
**Given** une action requiert approbation DBA pour la production (definie par DBOPS a l'Epic 2 via impact_level=CRITICAL ou HIGH en prod)
**When** un utilisateur soumet l'execution en environnement Production
**Then** l'execution passe en statut "PENDING_APPROVAL" (au lieu de SUBMITTED) et le DBA approbateur est notifie

### AC2: Consultation de la demande par le DBA
**Given** un DBA voit une execution en attente
**When** il consulte la demande (action, parametres, environnement, demandeur)
**Then** il peut "Approuver" ou "Refuser" avec un commentaire optionnel

### AC3: Approbation et reprise du workflow
**Given** le DBA approuve
**When** l'execution reprend
**Then** le workflow d'execution continue normalement et l'approbation est enregistree dans AUDIT_LOG (qui, quand, commentaire)

### AC4: Refus et notification
**Given** le DBA refuse
**When** le demandeur consulte son execution
**Then** le statut est "REJECTED" avec le commentaire du DBA visible

### AC5: API endpoints d'approbation
**And** l'API POST /api/v1/executions/{id}/approve et POST /api/v1/executions/{id}/reject gerent les decisions

### AC6: Notifications visibles sur le dashboard
**And** les notifications d'approbation en attente sont visibles dans le dashboard (badge compteur)
**And** FR27 et FR28 sont satisfaites

## Tasks / Subtasks

### Task 1: Configuration du critere d'approbation par action (AC: #1)
- [x] 1.1 Ajouter champ `requires_approval` (boolean) ou utiliser `impact_level` CRITICAL/HIGH en prod dans `catalog_repository.py`
- [x] 1.2 Ajouter fonction `get_requires_approval(action_id: int, environment: str) -> bool` dans `catalog_repository.py`
  - Retourne True si impact_rules[environment].level == "critical" ou "high"
- [x] 1.3 Verifier que les actions existantes ont leurs impact_rules configures (Story 2.18)

### Task 2: Modification du flux de soumission d'execution (AC: #1)
- [x] 2.1 Modifier `executions.py:create_execution()` pour verifier `requires_approval` avant creation
- [x] 2.2 Si approbation requise ET environnement == PROD:
  - Creer execution avec status = `PENDING_APPROVAL` (pas SUBMITTED)
  - Ne PAS lancer `background_tasks.add_task(execution_service.start_execution)`
- [x] 2.3 Ajouter entree AUDIT_LOG avec action_type = `EXECUTION_PENDING_APPROVAL`
- [x] 2.4 Retourner `{ status: "PENDING_APPROVAL", requires_approval: true }` dans la reponse

### Task 3: Endpoints d'approbation et de refus (AC: #2, #3, #4, #5)
- [x] 3.1 Ajouter endpoint `POST /api/v1/executions/{id}/approve` dans `executions.py`:
  - Verifier que l'execution existe et status == PENDING_APPROVAL
  - Verifier que l'utilisateur a le profil DBA ou DBOPS
  - Accepter body optionnel `{ "comment": "..." }`
  - Mettre a jour status = SUBMITTED
  - Lancer `execution_service.start_execution()` en background
  - Creer entree AUDIT_LOG avec action_type = `EXECUTION_APPROVED`
- [x] 3.2 Ajouter endpoint `POST /api/v1/executions/{id}/reject` dans `executions.py`:
  - Verifier que l'execution existe et status == PENDING_APPROVAL
  - Verifier que l'utilisateur a le profil DBA ou DBOPS
  - Accepter body optionnel `{ "comment": "..." }`
  - Mettre a jour status = `REJECTED` (nouveau statut a ajouter)
  - Creer entree AUDIT_LOG avec action_type = `EXECUTION_REJECTED`
- [x] 3.3 Ajouter `REJECTED` a l'enum `ExecutionStatus` dans `models/execution.py`

### Task 4: Repository execution pour approbation (AC: #1, #3, #4)
- [x] 4.1 Ajouter colonnes dans table EXECUTIONS (si pas deja presentes):
  - `APPROVED_BY` (int, nullable, FK vers USERS)
  - `APPROVED_AT` (timestamp, nullable)
  - `APPROVAL_COMMENT` (varchar2(1000), nullable)
- [x] 4.2 Ajouter fonction `execution_repository.approve(execution_id, user_id, comment) -> bool`
- [x] 4.3 Ajouter fonction `execution_repository.reject(execution_id, user_id, comment) -> bool`
- [x] 4.4 Ajouter fonction `execution_repository.list_pending_approvals(limit, offset) -> list[ExecutionResponse]`

### Task 5: Liste des executions en attente pour DBA (AC: #2, #6)
- [x] 5.1 Ajouter endpoint `GET /api/v1/executions/pending-approvals` (DBA/DBOPS only)
  - Retourne toutes les executions avec status = PENDING_APPROVAL
  - Include action_name, demandeur (user), environment, parameters, created_at
- [x] 5.2 Modifier `GET /api/v1/executions` pour inclure celles en PENDING_APPROVAL pour les DBA/DBOPS

### Task 6: Modification du modele ExecutionResponse (AC: #3, #4)
- [x] 6.1 Ajouter champs dans `ExecutionResponse`:
  - `approved_by: int | None`
  - `approved_at: datetime | None`
  - `approval_comment: str | None`
  - `rejection_reason: str | None` (alias approval_comment si REJECTED)
- [x] 6.2 Mettre a jour `execution_repository.get_by_id()` pour mapper ces champs

### Task 7: Frontend - Liste des approbations en attente (AC: #2, #6)
- [x] 7.1 Ajouter composant `PendingApprovalsList.tsx` dans `components/dashboard/`
  - Affiche les executions PENDING_APPROVAL sous forme de liste
  - Boutons "Approuver" (vert) et "Refuser" (rouge) avec modal de commentaire
- [x] 7.2 Ajouter badge compteur dans le header/navigation pour les DBA/DBOPS
  - Utiliser `GET /api/v1/executions/pending-approvals?count_only=true` ou websocket
- [x] 7.3 Ajouter section "Approbations en attente" dans DashboardPage (visible DBA/DBOPS seulement)

### Task 8: Frontend - Timeline et statut PENDING_APPROVAL (AC: #1, #4)
- [x] 8.1 Modifier `ExecutionTimeline.tsx` pour afficher le statut PENDING_APPROVAL:
  - Icone hourglass/clock jaune
  - Message "En attente d'approbation DBA"
- [x] 8.2 Afficher le statut REJECTED avec icone X rouge et le commentaire de refus
- [x] 8.3 Afficher le statut approuve avec icone check vert et info approbateur

### Task 9: Notifications temps reel via WebSocket (AC: #6)
- [x] 9.1 Modifier `dashboard_ws.py` pour pusher les nouvelles demandes d'approbation:
  - Event type: `APPROVAL_REQUIRED`
  - Payload: execution_id, action_name, demandeur, environment
- [x] 9.2 Modifier le frontend pour ecouter ces events et mettre a jour le badge

### Task 10: Tests unitaires et integration (AC: tous)
- [x] 10.1 Test backend `test_approval_workflow.py`:
  - Soumission action HIGH impact en prod -> status PENDING_APPROVAL
  - Soumission action LOW impact en prod -> status SUBMITTED (pas d'approbation)
  - POST /approve par DBA -> status SUBMITTED, execution demarre
  - POST /reject par DBA -> status REJECTED
  - POST /approve par non-DBA -> 403 Forbidden
- [x] 10.2 Test frontend `PendingApprovalsList.test.tsx`:
  - Affiche les executions en attente
  - Clic Approuver ouvre modal, confirme -> appel API
  - Clic Refuser ouvre modal avec champ commentaire obligatoire
- [x] 10.3 Test integration: workflow complet soumission -> approbation -> execution

## Dev Notes

### Architecture d'approbation basee sur impact_rules

Le systeme utilise les `impact_rules` deja configures (Story 2.18) pour determiner si une approbation est requise:

```python
# Logique de determination d'approbation requise
async def requires_approval(action_id: int, environment: str) -> bool:
    """Check if action requires DBA approval for given environment."""
    action = await catalog_repository.get_by_id(action_id)
    if not action or not action.impact_rules:
        return False

    env_rules = action.impact_rules.get(environment.lower(), {})
    impact_level = env_rules.get("level", action.default_impact_level or "low")

    # CRITICAL or HIGH impact in PROD requires approval
    return environment.lower() == "prod" and impact_level in ("critical", "high")
```

### Statuts d'execution etendus

Le cycle de vie d'une execution avec approbation:

```
SUBMITTED -> RUNNING -> COMPLETED/FAILED  (sans approbation)

PENDING_APPROVAL -> APPROVED -> RUNNING -> COMPLETED/FAILED
                 -> REJECTED (terminal)
```

**Note**: Le statut `PENDING_APPROVAL` existe deja dans `models/execution.py:19`. Il faut ajouter `REJECTED`.

### Fichiers cles a modifier

**Backend - API:**
- `idp-portal/backend/app/api/v1/executions.py` — Endpoints approve/reject + modification create_execution
- `idp-portal/backend/app/models/execution.py` — Ajouter REJECTED, champs approbation

**Backend - Repository:**
- `idp-portal/backend/app/repositories/execution_repository.py` — Fonctions approve/reject
- `idp-portal/backend/app/repositories/catalog_repository.py` — Fonction requires_approval

**Backend - Services:**
- `idp-portal/backend/app/services/execution_service.py` — Pas de modification (lance apres approbation)

**Backend - WebSocket:**
- `idp-portal/backend/app/websocket/dashboard_ws.py` — Event APPROVAL_REQUIRED

**Frontend - Components:**
- `idp-portal/frontend/src/components/dashboard/PendingApprovalsList.tsx` — Nouveau
- `idp-portal/frontend/src/components/catalog/ExecutionTimeline.tsx` — Statuts PENDING_APPROVAL/REJECTED
- `idp-portal/frontend/src/pages/DashboardPage.tsx` — Section approbations

**Frontend - Services:**
- `idp-portal/frontend/src/services/execution_service.ts` — API approve/reject

### Modele de donnees - Colonnes a ajouter

```sql
-- Migration Flyway: V14__add_approval_columns.sql
ALTER TABLE EXECUTIONS ADD (
    APPROVED_BY NUMBER(10) REFERENCES USERS(ID),
    APPROVED_AT TIMESTAMP,
    APPROVAL_COMMENT VARCHAR2(1000)
);

COMMENT ON COLUMN EXECUTIONS.APPROVED_BY IS 'DBA who approved/rejected the execution';
COMMENT ON COLUMN EXECUTIONS.APPROVED_AT IS 'Timestamp of approval/rejection';
COMMENT ON COLUMN EXECUTIONS.APPROVAL_COMMENT IS 'Optional comment from approver';
```

### Audit Trail pour FR27

Chaque action d'approbation genere une entree dans AUDIT_LOG:

```python
# Nouveaux AuditActionType a ajouter dans audit_repository.py
class AuditActionType(str, Enum):
    # ... existants ...
    EXECUTION_PENDING_APPROVAL = "execution_pending_approval"  # Soumission avec approbation requise
    EXECUTION_APPROVED = "execution_approved"                  # DBA approuve
    EXECUTION_REJECTED = "execution_rejected"                  # DBA refuse
```

### RBAC pour endpoints approbation

Seuls les profils DBA et DBOPS peuvent approuver/refuser:

```python
_APPROVAL_PROFILES = frozenset({"dba", "dbops"})

def _can_approve(user: UserProfile) -> bool:
    """True if user can approve/reject executions."""
    return (user.profile or "").lower() in _APPROVAL_PROFILES
```

### Project Structure Notes

- Backend structure monorepo: `idp-portal/backend/app/`
- Frontend structure: `idp-portal/frontend/src/`
- Migrations Flyway: `idp-portal/backend/migrations/`
- Tests co-localises avec le code source

### References

- [Source: planning-artifacts/epics.md#Story 7.4] — Definition de la story et AC
- [Source: planning-artifacts/epics.md#FR27-FR28] — Workflow d'approbation et configuration
- [Source: planning-artifacts/architecture.md#FR24-FR29] — Controle d'acces et approbation
- [Source: 7-3-rbac-granulaire-par-action-profil-et-environnement.md] — RBAC granulaire existant
- [Source: backend/app/models/execution.py:16-23] — ExecutionStatus enum avec PENDING_APPROVAL
- [Source: backend/app/models/catalog.py:55-60] — ImpactLevel enum (LOW, MEDIUM, HIGH, CRITICAL)
- [Source: backend/app/api/v1/executions.py] — Endpoint create_execution existant
- [Source: backend/app/repositories/audit_repository.py] — AuditActionType pour audit trail

### Risques et points d'attention

1. **Race condition approbation** — S'assurer que deux DBA ne peuvent pas approuver/refuser simultanement (verrouillage optimiste via status check)
2. **Timeout approbation** — Considerer un delai maximum pour les approbations en attente (future story)
3. **Notification DBA** — Pour MVP, badge sur dashboard; email/SMS en phase future
4. **Execution bloquee** — Si aucun DBA n'approuve, l'execution reste en PENDING_APPROVAL indefiniment (alerting future)
5. **Coherence RBAC** — Le demandeur ne peut pas s'auto-approuver meme s'il est DBA

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A

### Completion Notes List

**Implementation completed on 2026-02-01:**

1. **Backend Changes:**
   - Added `get_requires_approval()` and `get_action_impact_level()` functions to `catalog_repository.py`
   - Modified `create_execution()` in `executions.py` to check for approval requirement
   - Added endpoints: `POST /approve`, `POST /reject`, `GET /pending-approvals`
   - Added repository functions: `create_execution_pending_approval()`, `approve()`, `reject()`, `list_pending_approvals()`, `count_pending_approvals()`, `get_by_id_with_approval()`
   - Added `REJECTED` status to `ExecutionStatus` enum
   - Added `EXECUTION_PENDING_APPROVAL`, `EXECUTION_APPROVED`, `EXECUTION_REJECTED` to `AuditActionType`
   - Added `broadcast_approval_required()` to `DashboardWebSocketManager`

2. **Database Migration:**
   - Created `V030__add_approval_workflow.sql` adding columns: `APPROVED_BY`, `APPROVED_AT`, `APPROVAL_COMMENT`
   - Updated `CHK_EXECUTION_STATUS` constraint to include `REJECTED`

3. **Frontend Changes:**
   - Created `PendingApprovalsList.tsx` component with Approve/Reject buttons and confirmation modals
   - Updated `DashboardPage.tsx` to show pending approvals section for DBA/DBOPS
   - Updated `ExecutionTimeline.tsx` to display PENDING_APPROVAL and REJECTED status banners
   - Updated `api.ts` types with REJECTED and approval fields
   - Added `listPendingApprovals()`, `getPendingApprovalsCount()`, `approveExecution()`, `rejectExecution()` to execution_service.ts

4. **Tests:**
   - Created `test_approval_workflow.py` (13 tests) - all passing
   - Created `test_approval_api.py` (13 tests) - all passing
   - Created `PendingApprovalsList.test.tsx` (16 tests) - all passing
   - Updated `ExecutionTimeline.test.tsx` with Story 7.4 status tests (19 tests) - all passing

5. **Route Fix:**
   - Moved `/pending-approvals` route BEFORE routes with `{execution_id}` parameter to avoid FastAPI interpreting "pending-approvals" as an integer

### Code Review Issues Fixed (2026-02-01)

**Issue 1 (HIGH):** Paramètre `comment` passé en query string au lieu du body JSON
- **Fichiers:** `executions.py:507,637`
- **Fix:** Ajout de modèle Pydantic `ApprovalRequest` et modification des endpoints pour accepter le body JSON

**Issue 2 (MEDIUM):** PendingApprovalsList affiche user_id brut au lieu du nom
- **Fichiers:** `PendingApprovalsList.tsx`, `execution_repository.py`, `execution.py`, `api.ts`
- **Fix:** Ajout de champ `user_display_name` et jointure avec table USERS dans `list_pending_approvals`

**Issue 3 (MEDIUM):** Syntaxe Oracle invalide pour index partiel
- **Fichier:** `V030__add_approval_workflow.sql`
- **Fix:** Utilisation d'un function-based index avec CASE expression

### File List

**Created:**
- `idp-portal/database/migrations/V030__add_approval_workflow.sql`
- `idp-portal/frontend/src/components/dashboard/PendingApprovalsList.tsx`
- `idp-portal/backend/tests/unit/test_approval_workflow.py`
- `idp-portal/backend/tests/unit/test_approval_api.py`
- `idp-portal/frontend/src/components/dashboard/PendingApprovalsList.test.tsx`

**Modified:**
- `idp-portal/backend/app/models/execution.py` - Added REJECTED status, approval fields, user_display_name to ExecutionResponse
- `idp-portal/backend/app/repositories/audit_repository.py` - Added approval-related AuditActionType enums
- `idp-portal/backend/app/repositories/catalog_repository.py` - Added get_requires_approval, get_action_impact_level
- `idp-portal/backend/app/api/v1/executions.py` - Added approval workflow endpoints with ApprovalRequest body model
- `idp-portal/backend/app/repositories/execution_repository.py` - Added approval repository functions with user_display_name
- `idp-portal/backend/app/websocket/dashboard_ws.py` - Added broadcast_approval_required
- `idp-portal/frontend/src/types/api.ts` - Updated types for REJECTED, approval fields, and user_display_name
- `idp-portal/frontend/src/services/execution_service.ts` - Added approval API functions
- `idp-portal/frontend/src/pages/DashboardPage.tsx` - Added pending approvals section
- `idp-portal/frontend/src/components/execution/ExecutionTimeline.tsx` - Added PENDING_APPROVAL and REJECTED status display
- `idp-portal/frontend/src/components/execution/ExecutionTimeline.test.tsx` - Added Story 7.4 tests

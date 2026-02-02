# Story 11.7 : Patterns recurrence simples daily weekly

Status: done

<!-- Note: Validation optionnelle. Exécuter validate-create-story pour contrôle qualité avant dev-story. -->

## Story

En tant que **DBA**,
je veux **planifier des exécutions répétitives avec des patterns simples (tous les jours, toutes les semaines)**,
afin de **automatiser des tâches de maintenance régulières sans configuration complexe**.

## Contexte

**Contexte Epic 11 - Scheduling & Maintenance Planifiée:**

Le système permet de planifier des exécutions d'actions pour une date/heure future ou selon des patterns de récurrence. Les exécutions planifiées sont gérées via un modèle de données et des APIs, mais l'exécution effective est déléguée à un scheduler externe (Control-M ou Django scheduler) pour éviter la charge backend supplémentaire.

**Approche technique :**
- Modèle de données + UI/API complètes, mais PAS de scheduler intégré (Celery)
- Les schedules sont récupérés et exécutés par un scheduler externe
- Pas de seconde base de données, pas de charge backend supplémentaire pour le polling
- Le scheduler externe interroge l'API pour obtenir les exécutions à lancer via `NEXT_EXECUTION_DATE`

**État actuel:**

Stories précédentes complétées dans Epic 11 :
- **Story 11.1** (done) : Modèle de données SCHEDULED_EXECUTIONS et RECURRING_PATTERNS créé (migration V038)
  - Table RECURRING_PATTERNS avec pattern_type (one_time, daily, weekly, cron)
  - Colonne NEXT_EXECUTION_DATE pour scheduler externe
  - Index composite optimisé sur (IS_ACTIVE, NEXT_EXECUTION_DATE)
- **Story 11.3** (done) : API `POST /api/v1/scheduled-executions` pour créer une exécution planifiée one-time
  - Validation timezone avec Pydantic
  - Validation paramètres avec jsonschema
  - Traçabilité audit avec correlation_id
- **Story 11.5** (done) : UI scheduler dans le wizard d'exécution avec option "Exécuter maintenant" vs "Planifier"
  - DatePicker avec showTime et validation date future
  - Display timezone UTC avec tooltip
  - Tests complets (45 tests passent)
- **Story 11.6** (done) : Liste des exécutions planifiées et annulation
  - Page Admin avec liste filtrée par RBAC
  - Annulation des exécutions pending avec PATCH endpoint
  - Modal détails avec correlation_id et execution_id

**Objectif de cette story:**

Permettre aux DBAs de créer des exécutions récurrentes avec des patterns **simples** (Daily et Weekly) :
1. **Daily pattern** : Exécution tous les jours à une heure spécifique (ex: 2h30 tous les matins)
2. **Weekly pattern** : Exécution chaque semaine à un jour et heure spécifiques (ex: tous les lundis à 14h00)
3. **Calcul automatique** du `NEXT_EXECUTION_DATE` pour le scheduler externe
4. **Désactivation** des récurrences sans supprimer l'historique (is_active=false)

Cette story étend l'API et l'UI du wizard d'exécution pour supporter la récurrence basique. Les patterns cron avancés seront traités en Story 11.8.

## Acceptance Criteria

### AC1 - Option de récurrence dans le wizard d'exécution

**Given** le DBA ouvre le wizard d'exécution
**When** il clique sur "Planifier"
**Then** il voit trois options : "One-time" (défaut), "Daily", "Weekly"

**Given** le DBA sélectionne "One-time"
**When** il configure la planification
**Then** il voit uniquement le DatePicker date/heure (comportement actuel de Story 11.5)

### AC2 - Configuration pattern Daily

**Given** le DBA sélectionne "Daily"
**When** l'interface s'ajuste
**Then** il voit deux Select : "Heure" (00-23) et "Minute" (00, 15, 30, 45)

**Given** le DBA choisit "02" pour l'heure et "30" pour les minutes
**When** il confirme la création
**Then** l'API `POST /api/v1/scheduled-executions` est appelée avec :
```json
{
  "action_id": 123,
  "environment": "prod",
  "parameters": {...},
  "recurring_pattern": {
    "pattern_type": "daily",
    "pattern_config": {
      "hour": 2,
      "minute": 30
    }
  }
}
```

**And** une entrée SCHEDULED_EXECUTIONS est créée avec scheduled_at=NULL (récurrent, pas de date unique)
**And** une entrée RECURRING_PATTERNS est créée avec :
- pattern_type="daily"
- pattern_config={"hour": 2, "minute": 30}
- next_execution_date = prochaine occurrence (demain à 2h30 UTC)
- is_active=true

### AC3 - Configuration pattern Weekly

**Given** le DBA sélectionne "Weekly"
**When** l'interface s'ajuste
**Then** il voit trois Select : "Jour de la semaine" (Lundi-Dimanche), "Heure" (00-23), "Minute" (00, 15, 30, 45)

**Given** le DBA choisit "Lundi", "14", "00"
**When** il confirme la création
**Then** l'API `POST /api/v1/scheduled-executions` est appelée avec :
```json
{
  "action_id": 123,
  "environment": "prod",
  "parameters": {...},
  "recurring_pattern": {
    "pattern_type": "weekly",
    "pattern_config": {
      "day_of_week": 1,
      "hour": 14,
      "minute": 0
    }
  }
}
```

**And** une entrée SCHEDULED_EXECUTIONS est créée avec scheduled_at=NULL
**And** une entrée RECURRING_PATTERNS est créée avec :
- pattern_type="weekly"
- pattern_config={"day_of_week": 1, "hour": 14, "minute": 0}
- next_execution_date = prochain lundi à 14h00 UTC
- is_active=true

**And** day_of_week suit la convention : 1=Lundi, 2=Mardi, ..., 7=Dimanche

### AC4 - Calcul de next_execution_date pour Daily

**Given** une récurrence Daily avec hour=2, minute=30
**When** la récurrence est créée le 2026-02-02 à 15:00 UTC
**Then** next_execution_date est calculé pour 2026-02-03 à 02:30 UTC

**Given** une récurrence Daily est créée le 2026-02-02 à 01:00 UTC (avant 02:30)
**When** elle est créée
**Then** next_execution_date est calculé pour 2026-02-02 à 02:30 UTC (aujourd'hui si pas encore passée)

**Given** une exécution daily est exécutée par le scheduler externe
**When** elle se termine et le scheduler appelle l'API de mise à jour
**Then** next_execution_date est incrémenté de 1 jour (même heure)

### AC5 - Calcul de next_execution_date pour Weekly

**Given** une récurrence Weekly avec day_of_week=1 (lundi), hour=14, minute=0
**When** la récurrence est créée le mardi 2026-02-03 à 10:00 UTC
**Then** next_execution_date est calculé pour le prochain lundi 2026-02-09 à 14:00 UTC

**Given** une récurrence Weekly est créée le lundi 2026-02-02 à 10:00 UTC (avant 14h)
**When** elle est créée
**Then** next_execution_date est calculé pour 2026-02-02 à 14:00 UTC (aujourd'hui si pas encore passée)

**Given** une exécution weekly est exécutée par le scheduler externe
**When** elle se termine et le scheduler appelle l'API de mise à jour
**Then** next_execution_date est incrémenté de 7 jours

### AC6 - Validation des patterns de récurrence

**Given** le DBA tente de créer une récurrence Daily sans spécifier hour ou minute
**When** la requête est envoyée
**Then** l'API retourne une erreur 400 avec message "Pattern config incomplet : hour et minute requis pour pattern daily"

**Given** le DBA tente de créer une récurrence Weekly sans day_of_week
**When** la requête est envoyée
**Then** l'API retourne une erreur 400 avec message "Pattern config incomplet : day_of_week, hour et minute requis pour pattern weekly"

**Given** le DBA spécifie hour=25 (invalide)
**When** la requête est envoyée
**Then** l'API retourne une erreur 400 avec message "Valeur invalide pour hour : doit être entre 0 et 23"

**Given** le DBA spécifie day_of_week=8 (invalide)
**When** la requête est envoyée
**Then** l'API retourne une erreur 400 avec message "Valeur invalide pour day_of_week : doit être entre 1 (lundi) et 7 (dimanche)"

### AC7 - Affichage des récurrences dans la liste des exécutions planifiées

**Given** un DBA consulte la page "Exécutions planifiées" (Story 11.6)
**When** une exécution récurrente (daily ou weekly) est affichée
**Then** la colonne "Date/heure planifiée" affiche :
- "Tous les jours à 02:30 (UTC)" pour Daily
- "Tous les lundis à 14:00 (UTC)" pour Weekly
- Avec en dessous : "Prochaine : 09/02/2026 à 14:00"

**And** la colonne "Type" affiche un badge "Récurrent" en bleu
**And** le statut peut être "pending" (active, next_execution_date dans le futur)

### AC8 - Modal de détails pour exécutions récurrentes

**Given** le DBA clique sur "Voir détails" pour une exécution récurrente
**When** la modal s'ouvre
**Then** elle affiche :
- ID de l'exécution planifiée
- Action (nom + ID)
- Type : "Récurrent - Daily" ou "Récurrent - Weekly"
- Configuration : "Tous les jours à 02:30 (UTC)" ou "Tous les lundis à 14:00 (UTC)"
- Prochaine exécution : "09/02/2026 à 14:00 (UTC)"
- Statut : "Actif" (si is_active=true) ou "Désactivé" (si is_active=false)
- Date de création
- Correlation ID

**And** si l'exécution est active (is_active=true), un bouton "Désactiver" est affiché
**And** si l'exécution est désactivée (is_active=false), un bouton "Réactiver" est affiché

### AC9 - Désactivation d'une récurrence

**Given** une exécution récurrente active (is_active=true)
**When** le DBA clique sur "Désactiver" dans la modal de détails
**Then** une confirmation s'affiche : "Êtes-vous sûr de vouloir désactiver cette récurrence ? Elle ne sera plus exécutée automatiquement."

**Given** le DBA confirme la désactivation
**When** la confirmation est soumise
**Then** l'API `PATCH /api/v1/scheduled-executions/{id}/recurring-pattern` est appelée avec `{ "is_active": false }`
**And** is_active est mis à false dans RECURRING_PATTERNS
**And** next_execution_date reste inchangé (pour historique)
**And** le scheduler externe ne récupère plus cette récurrence (WHERE is_active=1)
**And** une notification success s'affiche : "Récurrence désactivée avec succès"

### AC10 - Réactivation d'une récurrence

**Given** une exécution récurrente désactivée (is_active=false)
**When** le DBA clique sur "Réactiver"
**Then** l'API `PATCH /api/v1/scheduled-executions/{id}/recurring-pattern` est appelée avec `{ "is_active": true }`
**And** is_active est mis à true
**And** next_execution_date est recalculé selon le pattern (prochaine occurrence)
**And** une notification success s'affiche : "Récurrence réactivée avec succès"

### AC11 - Audit des opérations sur récurrences

**Given** une récurrence est créée, désactivée ou réactivée
**When** l'opération est effectuée
**Then** un log est créé dans audit_log avec :
- action_type : "SCHEDULED_EXECUTION_RECURRING_CREATED", "SCHEDULED_EXECUTION_RECURRING_DISABLED", "SCHEDULED_EXECUTION_RECURRING_ENABLED"
- resource_type : "scheduled_execution"
- resource_id : ID de la scheduled execution
- details : pattern_type, pattern_config, next_execution_date
- correlation_id

## Tasks / Subtasks

- [x] Task 1: Étendre les modèles backend pour supporter recurring_pattern (AC2, AC3)
  - [x] Subtask 1.1: Créer modèle Pydantic `RecurringPatternConfig` dans `backend/app/models/scheduled_execution.py`
  - [x] Subtask 1.2: Créer unions `DailyConfig`, `WeeklyConfig` avec field_validator pour validation
  - [x] Subtask 1.3: Étendre `ScheduledExecutionCreate` avec champ optionnel `recurring_pattern: RecurringPatternConfig | None`
  - [x] Subtask 1.4: Créer `RecurringPatternResponse` pour les réponses API avec pattern_type, pattern_config, next_execution_date, is_active

- [x] Task 2: Implémenter le calcul de next_execution_date (AC4, AC5)
  - [x] Subtask 2.1: Créer helper `backend/app/utils/recurrence.py` avec fonction `calculate_next_execution_date(pattern_type, pattern_config, reference_datetime) -> datetime`
  - [x] Subtask 2.2: Implémenter logique Daily : si reference_datetime.time() < pattern_time → today, sinon tomorrow
  - [x] Subtask 2.3: Implémenter logique Weekly : trouver prochain jour de la semaine à partir de reference_datetime
  - [x] Subtask 2.4: Utiliser `datetime.timezone.utc` pour tous les calculs
  - [x] Subtask 2.5: Ajouter tests unitaires pour calculate_next_execution_date (22 tests créés)

- [x] Task 3: Étendre l'API POST /api/v1/scheduled-executions pour récurrences (AC2, AC3, AC6)
  - [x] Subtask 3.1: Modifier endpoint pour accepter `recurring_pattern` optionnel dans body
  - [x] Subtask 3.2: Si recurring_pattern présent → valider pattern_config selon pattern_type
  - [x] Subtask 3.3: Si Daily → valider hour (0-23), minute (0-59)
  - [x] Subtask 3.4: Si Weekly → valider day_of_week (1-7), hour, minute
  - [x] Subtask 3.5: Calculer next_execution_date avec calculate_next_execution_date()
  - [x] Subtask 3.6: Appeler repository pour créer SCHEDULED_EXECUTIONS avec scheduled_at=NULL ET RECURRING_PATTERNS
  - [x] Subtask 3.7: Retourner réponse enrichie avec recurring_pattern
  - [x] Subtask 3.8: Tracer dans audit_log : SCHEDULED_EXECUTION_RECURRING_CREATED

- [x] Task 4: Étendre le repository pour créer recurring patterns (AC2, AC3)
  - [x] Subtask 4.1: Modifier `create_scheduled_execution()` pour accepter `recurring_pattern: RecurringPatternConfig | None`
  - [x] Subtask 4.2: Si recurring_pattern présent → INSERT dans RECURRING_PATTERNS après INSERT dans SCHEDULED_EXECUTIONS
  - [x] Subtask 4.3: Utiliser RETURNING pour récupérer ID de RECURRING_PATTERNS
  - [x] Subtask 4.4: Sérialiser pattern_config en JSON avec `_json_to_str()`
  - [x] Subtask 4.5: Créer méthode `get_recurring_pattern(scheduled_execution_id) -> RecurringPattern | None`

- [x] Task 5: Créer l'API PATCH pour activer/désactiver récurrence (AC9, AC10)
  - [x] Subtask 5.1: Créer endpoint `PATCH /api/v1/scheduled-executions/{id}/recurring-pattern`
  - [x] Subtask 5.2: Accepter payload : `{ "is_active": true | false }`
  - [x] Subtask 5.3: Valider que scheduled_execution a une RECURRING_PATTERNS (erreur 404 si one-time)
  - [x] Subtask 5.4: Si is_active=true → recalculer next_execution_date avec calculate_next_execution_date()
  - [x] Subtask 5.5: Mettre à jour RECURRING_PATTERNS avec is_active et next_execution_date
  - [x] Subtask 5.6: Tracer dans audit_log : SCHEDULED_EXECUTION_RECURRING_ENABLED ou DISABLED
  - [x] Subtask 5.7: Retourner recurring pattern mis à jour

- [x] Task 6: Étendre le wizard d'exécution pour récurrences (AC1, AC2, AC3)
  - [x] Subtask 6.1: Modifier `ExecutionWizard.tsx` pour ajouter Radio.Group "Type de planification"
  - [x] Subtask 6.2: Options : "One-time" (défaut), "Daily", "Weekly"
  - [x] Subtask 6.3: Si "One-time" → afficher DatePicker existant (Story 11.5)
  - [x] Subtask 6.4: Si "Daily" → afficher deux Select (hour: 0-23, minute: 0/15/30/45)
  - [x] Subtask 6.5: Si "Weekly" → afficher trois Select (day_of_week: Lundi-Dimanche, hour, minute)
  - [x] Subtask 6.6: Mapper day_of_week labels : { 1: "Lundi", 2: "Mardi", ..., 7: "Dimanche" }
  - [x] Subtask 6.7: Construire payload selon le type sélectionné
  - [x] Subtask 6.8: Appeler service `createScheduledExecution()` avec recurring_pattern si Daily/Weekly

- [x] Task 7: Étendre le service frontend pour recurring patterns (AC2, AC3)
  - [x] Subtask 7.1: Modifier `createScheduledExecution()` dans `scheduled_execution_service.ts`
  - [x] Subtask 7.2: Accepter paramètre `recurringPattern?: RecurringPatternRequest`
  - [x] Subtask 7.3: Ajouter types TypeScript dans `types/api.ts` :
    - `RecurringPatternRequest = DailyPatternRequest | WeeklyPatternRequest`
    - `DailyPatternRequest = { pattern_type: "daily", pattern_config: { hour, minute } }`
    - `WeeklyPatternRequest = { pattern_type: "weekly", pattern_config: { day_of_week, hour, minute } }`

- [x] Task 8: Afficher récurrences dans la liste ScheduledExecutionsPage (AC7)
  - [x] Subtask 8.1: Étendre `ScheduledExecutionListItem` avec champ `recurring_pattern?: RecurringPatternResponse`
  - [x] Subtask 8.2: Modifier colonne "Date/heure planifiée" pour afficher pattern si recurring_pattern présent
  - [x] Subtask 8.3: Fonction helper `formatRecurrenceDisplay(recurring_pattern)` :
    - Daily : "Tous les jours à HH:MM (UTC)"
    - Weekly : "Tous les [jour] à HH:MM (UTC)"
  - [x] Subtask 8.4: Afficher "Prochaine : DD/MM/YYYY à HH:MM" en dessous
  - [x] Subtask 8.5: Ajouter colonne "Type" avec Badge "Récurrent" (bleu) ou "Unique" (default)

- [x] Task 9: Étendre la modal de détails pour récurrences (AC8)
  - [x] Subtask 9.1: Modifier modal détails dans `ScheduledExecutionsPage.tsx`
  - [x] Subtask 9.2: Si recurring_pattern présent → afficher section "Récurrence"
  - [x] Subtask 9.3: Afficher Type, Configuration, Prochaine exécution, Statut (Actif/Désactivé)
  - [x] Subtask 9.4: Ajouter boutons "Désactiver" (si is_active=true) et "Réactiver" (si is_active=false)

- [x] Task 10: Implémenter activation/désactivation dans l'UI (AC9, AC10)
  - [x] Subtask 10.1: Créer fonction `toggleRecurringPattern(id, is_active)` dans service
  - [x] Subtask 10.2: Créer handler `handleToggleRecurrence()` dans ScheduledExecutionsPage
  - [x] Subtask 10.3: Afficher modal de confirmation pour désactivation
  - [x] Subtask 10.4: Appeler API PATCH → notification success/error → reload liste
  - [x] Subtask 10.5: Gérer erreur 404 si récurrence inexistante (one-time execution)

- [x] Task 11: Étendre le repository pour liste avec recurring patterns (AC7)
  - [x] Subtask 11.1: Modifier `list_scheduled_executions()` pour LEFT JOIN avec RECURRING_PATTERNS
  - [x] Subtask 11.2: Inclure colonnes : RP.PATTERN_TYPE, RP.PATTERN_CONFIG, RP.NEXT_EXECUTION_DATE, RP.IS_ACTIVE
  - [x] Subtask 11.3: Retourner recurring_pattern dans ScheduledExecutionListItem si présent

- [x] Task 12: Tests backend pour recurring patterns (AC2-AC6)
  - [x] Subtask 12.1: Test `test_create_daily_recurring_execution` - Daily pattern créé avec next_execution_date correct
  - [x] Subtask 12.2: Test `test_create_weekly_recurring_execution` - Weekly pattern créé avec next_execution_date correct
  - [x] Subtask 12.3: Test `test_daily_pattern_validation_missing_hour` - Erreur 400 si hour manquant
  - [x] Subtask 12.4: Test `test_weekly_pattern_validation_invalid_day_of_week` - Erreur 400 si day_of_week=8
  - [x] Subtask 12.5: Test `test_next_execution_date_daily_before_time` - Si créé avant l'heure → today
  - [x] Subtask 12.6: Test `test_next_execution_date_daily_after_time` - Si créé après l'heure → tomorrow
  - [x] Subtask 12.7: Test `test_next_execution_date_weekly_same_day_before_time` - Lundi créé lundi 10h, exécution 14h → today 14h
  - [x] Subtask 12.8: Test `test_next_execution_date_weekly_same_day_after_time` - Lundi créé lundi 16h, exécution 14h → next monday
  - [x] Subtask 12.9: Test `test_disable_recurring_pattern` - PATCH is_active=false → recurring_pattern.is_active=false
  - [x] Subtask 12.10: Test `test_enable_recurring_pattern_recalculates_next_execution` - PATCH is_active=true → next_execution_date recalculé
  - [x] Subtask 12.11: Test `test_audit_log_recurring_created` - Audit log créé avec SCHEDULED_EXECUTION_RECURRING_CREATED
  - [x] Subtask 12.12: Test `test_list_includes_recurring_patterns` - GET /scheduled-executions inclut recurring_pattern dans réponse

- [x] Task 13: Tests frontend pour recurring patterns (AC1-AC3, AC7-AC10)
  - [x] Subtask 13.1: Tests service scheduled_execution_service.ts (9 tests créés)
  - [x] Subtask 13.2: Test createScheduledExecution with daily pattern
  - [x] Subtask 13.3: Test createScheduledExecution with weekly pattern
  - [x] Subtask 13.4: Test listScheduledExecutions includes recurring_pattern
  - [x] Subtask 13.5: Test toggleRecurringPattern enable/disable

- [x] Task 14: Documentation et validation (AC11)
  - [x] Subtask 14.1: Types audit déjà présents : SCHEDULED_EXECUTION_RECURRING_CREATED, DISABLED, ENABLED
  - [x] Subtask 14.2: Migration V038 avec support recurring patterns (déjà créé en Story 11.1)
  - [x] Subtask 14.3: Story file mis à jour avec status=done
  - [x] Subtask 14.4: Sprint status mis à jour

## Dev Notes

### Architecture et contraintes techniques

**Stack technique frontend :**
- Framework : React 19
- UI Library : Ant Design 6.2
- Date manipulation : Dayjs (inclus avec Ant Design)
- Routing : React Router 7
- TypeScript : 5.x
- Build tool : Vite 7

**Stack technique backend :**
- Backend : FastAPI + python-oracledb (async)
- Base de données : Oracle 19c
- Migration : Flyway (V038 déjà appliquée en Story 11.1 avec RECURRING_PATTERNS)
- Pattern : SQL brut via repositories
- Authentification : JWT via `Depends(get_current_user)`
- RBAC : Vérification des rôles DBA/DBOPS
- Date/time : datetime.timezone.utc pour tous les calculs

**Tables utilisées :**
- `SCHEDULED_EXECUTIONS` (créée en V038) : Stocke les exécutions planifiées
  - scheduled_at devient NULL pour exécutions récurrentes (pas de date unique)
- `RECURRING_PATTERNS` (créée en V038) : Stocke les patterns de récurrence
  - pattern_type : 'daily', 'weekly', 'cron' (cron en Story 11.8)
  - pattern_config : CLOB JSON avec configuration spécifique au type
  - next_execution_date : TIMESTAMP WITH TIME ZONE utilisé par scheduler externe
  - is_active : NUMBER(1) booléen pour activer/désactiver
- `ACTIONS_CATALOG` : Détails des actions (JOIN pour action_name)
- `AUDIT_LOG` : Traçabilité des opérations sur récurrences

**Composants UI à modifier :**
- `ExecutionWizard.tsx` (Story 11.5) - Ajouter Radio.Group et Select pour patterns
- `ScheduledExecutionsPage.tsx` (Story 11.6) - Afficher récurrences et boutons activer/désactiver
- `Select` (Ant Design) - Sélection hour, minute, day_of_week
- `Radio` (Ant Design) - Choix du type de planification
- `Badge` (Ant Design) - Badge "Récurrent" pour identifier les récurrences
- `Modal` (Ant Design) - Confirmation désactivation/réactivation

### Patterns de code à suivre

**Pattern 1 : Modèles Pydantic pour recurring patterns**

Source : `/idp-portal/backend/app/models/scheduled_execution.py`

```python
# backend/app/models/scheduled_execution.py

from pydantic import BaseModel, Field, field_validator
from typing import Literal, Union
from datetime import datetime

class DailyPatternConfig(BaseModel):
    """Configuration for daily recurring pattern."""
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Minute of hour (0-59)")

class WeeklyPatternConfig(BaseModel):
    """Configuration for weekly recurring pattern."""
    day_of_week: int = Field(..., ge=1, le=7, description="Day of week: 1=Monday, 7=Sunday")
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Minute of hour (0-59)")

class RecurringPatternRequest(BaseModel):
    """Recurring pattern in creation request."""
    pattern_type: Literal["daily", "weekly"]
    pattern_config: DailyPatternConfig | WeeklyPatternConfig

    @field_validator("pattern_config")
    def validate_pattern_config(cls, v, info):
        """Validate pattern_config matches pattern_type."""
        pattern_type = info.data.get("pattern_type")
        if pattern_type == "daily" and not isinstance(v, DailyPatternConfig):
            raise ValueError("pattern_config doit être DailyPatternConfig pour pattern_type='daily'")
        if pattern_type == "weekly" and not isinstance(v, WeeklyPatternConfig):
            raise ValueError("pattern_config doit être WeeklyPatternConfig pour pattern_type='weekly'")
        return v

class RecurringPatternResponse(BaseModel):
    """Recurring pattern in API responses."""
    pattern_type: str
    pattern_config: dict
    next_execution_date: datetime
    is_active: bool

class ScheduledExecutionCreate(BaseModel):
    """Request model for creating scheduled execution."""
    action_id: int
    environment: str
    parameters: dict | None = None
    scheduled_at: datetime | None = None  # NULL if recurring
    recurring_pattern: RecurringPatternRequest | None = None

    @field_validator("scheduled_at", "recurring_pattern")
    def validate_scheduling_type(cls, v, info):
        """Ensure either scheduled_at OR recurring_pattern is provided, not both."""
        scheduled_at = info.data.get("scheduled_at")
        recurring_pattern = info.data.get("recurring_pattern")

        if scheduled_at and recurring_pattern:
            raise ValueError("Impossible de spécifier à la fois scheduled_at et recurring_pattern")
        if not scheduled_at and not recurring_pattern:
            raise ValueError("Doit spécifier soit scheduled_at (one-time) soit recurring_pattern (récurrent)")

        return v
```

**Pattern 2 : Calcul de next_execution_date**

Source : Nouveau fichier `/idp-portal/backend/app/utils/recurrence.py`

```python
# backend/app/utils/recurrence.py

from datetime import datetime, timedelta, timezone
import structlog

logger = structlog.get_logger(__name__)

def calculate_next_execution_date(
    pattern_type: str,
    pattern_config: dict,
    reference_datetime: datetime | None = None,
) -> datetime:
    """
    Calculate next execution date for recurring pattern.

    Args:
        pattern_type: Type of pattern ("daily" or "weekly")
        pattern_config: Pattern configuration dict
        reference_datetime: Reference time (defaults to now in UTC)

    Returns:
        Next execution datetime in UTC

    Raises:
        ValueError: If pattern_type or pattern_config is invalid
    """
    if reference_datetime is None:
        reference_datetime = datetime.now(timezone.utc)

    # Ensure reference_datetime is in UTC
    if reference_datetime.tzinfo is None:
        reference_datetime = reference_datetime.replace(tzinfo=timezone.utc)

    if pattern_type == "daily":
        return _calculate_daily_next_execution(pattern_config, reference_datetime)
    elif pattern_type == "weekly":
        return _calculate_weekly_next_execution(pattern_config, reference_datetime)
    else:
        raise ValueError(f"Type de pattern non supporté : {pattern_type}")

def _calculate_daily_next_execution(
    pattern_config: dict,
    reference_datetime: datetime,
) -> datetime:
    """Calculate next execution for daily pattern."""
    hour = pattern_config.get("hour")
    minute = pattern_config.get("minute")

    if hour is None or minute is None:
        raise ValueError("Pattern config incomplet : hour et minute requis pour pattern daily")

    # Build target time for today
    target_time = reference_datetime.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    # If target time is in the future today, use today; otherwise tomorrow
    if target_time > reference_datetime:
        next_execution = target_time
    else:
        next_execution = target_time + timedelta(days=1)

    logger.info(
        "calculated_daily_next_execution",
        pattern_config=pattern_config,
        reference_datetime=reference_datetime.isoformat(),
        next_execution=next_execution.isoformat(),
    )

    return next_execution

def _calculate_weekly_next_execution(
    pattern_config: dict,
    reference_datetime: datetime,
) -> datetime:
    """Calculate next execution for weekly pattern."""
    day_of_week = pattern_config.get("day_of_week")  # 1=Monday, 7=Sunday
    hour = pattern_config.get("hour")
    minute = pattern_config.get("minute")

    if day_of_week is None or hour is None or minute is None:
        raise ValueError(
            "Pattern config incomplet : day_of_week, hour et minute requis pour pattern weekly"
        )

    # Python weekday: 0=Monday, 6=Sunday; convert from our convention (1=Monday, 7=Sunday)
    target_weekday = day_of_week - 1
    if target_weekday == 7:
        target_weekday = 6  # Map 7 (our Sunday) to 6 (Python Sunday)

    current_weekday = reference_datetime.weekday()

    # Calculate days until target weekday
    days_until_target = (target_weekday - current_weekday) % 7

    # Build target datetime
    target_datetime = reference_datetime + timedelta(days=days_until_target)
    target_datetime = target_datetime.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0,
    )

    # If target is in the past (same day but earlier time), move to next week
    if target_datetime <= reference_datetime:
        target_datetime += timedelta(weeks=1)

    logger.info(
        "calculated_weekly_next_execution",
        pattern_config=pattern_config,
        reference_datetime=reference_datetime.isoformat(),
        next_execution=target_datetime.isoformat(),
    )

    return target_datetime
```

**Pattern 3 : Extension de l'API POST pour récurrences**

Source : `/idp-portal/backend/app/api/v1/scheduled_executions.py` (à étendre)

```python
# backend/app/api/v1/scheduled_executions.py

from app.models.scheduled_execution import ScheduledExecutionCreate, RecurringPatternRequest
from app.utils.recurrence import calculate_next_execution_date
from app.repositories.audit_repository import AuditRepository
from app.models.audit import AuditActionType

@router.post("/scheduled-executions")
async def create_scheduled_execution(
    execution_data: ScheduledExecutionCreate,
    current_user: User = Depends(get_current_user),
):
    """
    Create a scheduled execution (one-time or recurring).
    """
    repo = ScheduledExecutionRepository()
    audit_repo = AuditRepository()

    # Validate action exists and is published
    if not await repo.action_exists(execution_data.action_id):
        raise NotFoundError(message="Action non trouvée ou non publiée")

    # Validate user has permission to execute action
    # ... (existing RBAC check from Story 11.3)

    # Validate parameters against action schema
    # ... (existing validation from Story 11.3)

    # Generate correlation_id
    correlation_id = str(uuid.uuid4())

    # Handle recurring pattern
    recurring_pattern_data = None
    if execution_data.recurring_pattern:
        pattern = execution_data.recurring_pattern

        # Calculate next_execution_date
        next_execution_date = calculate_next_execution_date(
            pattern_type=pattern.pattern_type,
            pattern_config=pattern.pattern_config.model_dump(),
            reference_datetime=None,  # Use now
        )

        recurring_pattern_data = {
            "pattern_type": pattern.pattern_type,
            "pattern_config": pattern.pattern_config.model_dump(),
            "next_execution_date": next_execution_date,
            "is_active": True,
        }

    # Create scheduled execution with optional recurring pattern
    scheduled_execution = await repo.create_scheduled_execution(
        action_id=execution_data.action_id,
        user_id=current_user.id,
        environment=execution_data.environment,
        parameters=execution_data.parameters,
        scheduled_at=execution_data.scheduled_at,  # NULL if recurring
        correlation_id=correlation_id,
        recurring_pattern=recurring_pattern_data,
    )

    # Audit log
    audit_action = (
        AuditActionType.SCHEDULED_EXECUTION_RECURRING_CREATED
        if recurring_pattern_data
        else AuditActionType.SCHEDULED_EXECUTION_CREATED
    )

    await audit_repo.log_action(
        user_id=current_user.id,
        action_type=audit_action,
        resource_type="scheduled_execution",
        resource_id=scheduled_execution.id,
        details={
            "action_id": execution_data.action_id,
            "environment": execution_data.environment,
            "scheduled_at": execution_data.scheduled_at.isoformat() if execution_data.scheduled_at else None,
            "recurring_pattern": recurring_pattern_data,
        },
        correlation_id=correlation_id,
    )

    return {"data": scheduled_execution}
```

**Pattern 4 : Extension du repository pour créer recurring patterns**

Source : `/idp-portal/backend/app/repositories/scheduled_execution_repository.py` (à étendre)

```python
# backend/app/repositories/scheduled_execution_repository.py

async def create_scheduled_execution(
    self,
    action_id: int,
    user_id: int,
    environment: str,
    parameters: dict | None,
    scheduled_at: datetime | None,
    correlation_id: str,
    recurring_pattern: dict | None = None,
) -> ScheduledExecutionResponse:
    """
    Create a scheduled execution with optional recurring pattern.

    Args:
        recurring_pattern: Dict with pattern_type, pattern_config, next_execution_date, is_active
    """
    async with get_connection() as connection:
        cursor = connection.cursor()

        # Insert SCHEDULED_EXECUTIONS
        query_se = """
            INSERT INTO SCHEDULED_EXECUTIONS
            (ACTION_ID, USER_ID, ENVIRONMENT, PARAMETERS, SCHEDULED_AT, STATUS, CORRELATION_ID)
            VALUES
            (:action_id, :user_id, :environment, :parameters, :scheduled_at, :status, :correlation_id)
            RETURNING ID, CREATED_AT INTO :out_id, :out_created_at
        """

        out_id = cursor.var(int)
        out_created_at = cursor.var(datetime)

        await cursor.execute(
            query_se,
            {
                "action_id": action_id,
                "user_id": user_id,
                "environment": environment,
                "parameters": _json_to_str(parameters),
                "scheduled_at": scheduled_at,  # NULL if recurring
                "status": "pending",
                "correlation_id": correlation_id,
                "out_id": out_id,
                "out_created_at": out_created_at,
            },
        )

        scheduled_execution_id = out_id.getvalue()[0]
        created_at = out_created_at.getvalue()[0]

        # Insert RECURRING_PATTERNS if provided
        recurring_pattern_response = None
        if recurring_pattern:
            query_rp = """
                INSERT INTO RECURRING_PATTERNS
                (SCHEDULED_EXECUTION_ID, PATTERN_TYPE, PATTERN_CONFIG, NEXT_EXECUTION_DATE, IS_ACTIVE)
                VALUES
                (:scheduled_execution_id, :pattern_type, :pattern_config, :next_execution_date, :is_active)
                RETURNING ID INTO :out_rp_id
            """

            out_rp_id = cursor.var(int)

            await cursor.execute(
                query_rp,
                {
                    "scheduled_execution_id": scheduled_execution_id,
                    "pattern_type": recurring_pattern["pattern_type"],
                    "pattern_config": _json_to_str(recurring_pattern["pattern_config"]),
                    "next_execution_date": recurring_pattern["next_execution_date"],
                    "is_active": 1 if recurring_pattern["is_active"] else 0,
                    "out_rp_id": out_rp_id,
                },
            )

            recurring_pattern_response = {
                "pattern_type": recurring_pattern["pattern_type"],
                "pattern_config": recurring_pattern["pattern_config"],
                "next_execution_date": recurring_pattern["next_execution_date"],
                "is_active": recurring_pattern["is_active"],
            }

        await connection.commit()

        return ScheduledExecutionResponse(
            scheduled_execution_id=scheduled_execution_id,
            action_id=action_id,
            user_id=user_id,
            environment=environment,
            scheduled_at=scheduled_at,
            status="pending",
            created_at=created_at,
            correlation_id=correlation_id,
            recurring_pattern=recurring_pattern_response,
        )

async def update_recurring_pattern_status(
    self,
    scheduled_execution_id: int,
    is_active: bool,
) -> RecurringPatternResponse:
    """
    Update is_active status of recurring pattern and recalculate next_execution_date if enabled.
    """
    async with get_connection() as connection:
        cursor = connection.cursor()

        # Get existing pattern
        query_get = """
            SELECT PATTERN_TYPE, PATTERN_CONFIG
            FROM RECURRING_PATTERNS
            WHERE SCHEDULED_EXECUTION_ID = :scheduled_execution_id
        """
        result = await cursor.execute(query_get, {"scheduled_execution_id": scheduled_execution_id})
        row = await result.fetchone()

        if not row:
            raise NotFoundError(message="Recurring pattern not found for this scheduled execution")

        pattern_type, pattern_config_str = row
        pattern_config = _str_to_json(pattern_config_str)

        # If enabling, recalculate next_execution_date
        next_execution_date = None
        if is_active:
            from app.utils.recurrence import calculate_next_execution_date
            next_execution_date = calculate_next_execution_date(
                pattern_type=pattern_type,
                pattern_config=pattern_config,
                reference_datetime=None,  # Use now
            )

        # Update pattern
        query_update = """
            UPDATE RECURRING_PATTERNS
            SET IS_ACTIVE = :is_active,
                NEXT_EXECUTION_DATE = :next_execution_date,
                UPDATED_AT = SYSTIMESTAMP
            WHERE SCHEDULED_EXECUTION_ID = :scheduled_execution_id
        """

        await cursor.execute(
            query_update,
            {
                "is_active": 1 if is_active else 0,
                "next_execution_date": next_execution_date,
                "scheduled_execution_id": scheduled_execution_id,
            },
        )

        await connection.commit()

        return RecurringPatternResponse(
            pattern_type=pattern_type,
            pattern_config=pattern_config,
            next_execution_date=next_execution_date,
            is_active=is_active,
        )
```

**Pattern 5 : API PATCH pour activer/désactiver récurrence**

Source : Nouveau endpoint dans `/idp-portal/backend/app/api/v1/scheduled_executions.py`

```python
# backend/app/api/v1/scheduled_executions.py

@router.patch("/scheduled-executions/{scheduled_execution_id}/recurring-pattern")
async def toggle_recurring_pattern(
    scheduled_execution_id: int,
    toggle_data: dict,  # {"is_active": true | false}
    current_user: User = Depends(get_current_user),
):
    """
    Toggle is_active status of recurring pattern.
    """
    repo = ScheduledExecutionRepository()
    audit_repo = AuditRepository()

    # Validate scheduled execution exists and user has permission
    scheduled_execution = await repo.get_by_id(scheduled_execution_id)
    if not scheduled_execution:
        raise NotFoundError(message="Scheduled execution not found")

    # RBAC: DBA can toggle own, DBOPS can toggle all
    if not has_dbops_role(current_user) and scheduled_execution.user_id != current_user.id:
        raise ForbiddenError(message="Permission denied")

    # Update recurring pattern
    is_active = toggle_data.get("is_active")
    if is_active is None:
        raise InvalidStateError(message="Field is_active required")

    recurring_pattern = await repo.update_recurring_pattern_status(
        scheduled_execution_id=scheduled_execution_id,
        is_active=is_active,
    )

    # Audit log
    audit_action = (
        AuditActionType.SCHEDULED_EXECUTION_RECURRING_ENABLED
        if is_active
        else AuditActionType.SCHEDULED_EXECUTION_RECURRING_DISABLED
    )

    await audit_repo.log_action(
        user_id=current_user.id,
        action_type=audit_action,
        resource_type="scheduled_execution",
        resource_id=scheduled_execution_id,
        details={
            "pattern_type": recurring_pattern.pattern_type,
            "is_active": is_active,
            "next_execution_date": recurring_pattern.next_execution_date.isoformat() if recurring_pattern.next_execution_date else None,
        },
        correlation_id=scheduled_execution.correlation_id,
    )

    return {"data": recurring_pattern}
```

**Pattern 6 : Extension du wizard pour recurring patterns**

Source : `/idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` (à étendre)

```tsx
// frontend/src/components/catalog/ExecutionWizard.tsx

import { Radio, Select } from 'antd';
import type { RecurringPatternRequest } from '../../types/api';

const ExecutionWizard: React.FC<ExecutionWizardProps> = ({ action, onClose }) => {
  // Existing state from Story 11.5
  const [isScheduling, setIsScheduling] = useState(false);
  const [scheduledDateTime, setScheduledDateTime] = useState<Dayjs | null>(null);

  // New state for recurring patterns
  const [schedulingType, setSchedulingType] = useState<'one-time' | 'daily' | 'weekly'>('one-time');
  const [dailyHour, setDailyHour] = useState<number>(2);
  const [dailyMinute, setDailyMinute] = useState<number>(0);
  const [weeklyDayOfWeek, setWeeklyDayOfWeek] = useState<number>(1); // 1=Monday
  const [weeklyHour, setWeeklyHour] = useState<number>(14);
  const [weeklyMinute, setWeeklyMinute] = useState<number>(0);

  const handleSchedule = async () => {
    if (!isScheduling) {
      // Immediate execution (existing logic from Story 11.5)
      await executeAction();
    } else {
      // Scheduled execution
      let recurringPattern: RecurringPatternRequest | undefined;

      if (schedulingType === 'daily') {
        recurringPattern = {
          pattern_type: 'daily',
          pattern_config: {
            hour: dailyHour,
            minute: dailyMinute,
          },
        };
      } else if (schedulingType === 'weekly') {
        recurringPattern = {
          pattern_type: 'weekly',
          pattern_config: {
            day_of_week: weeklyDayOfWeek,
            hour: weeklyHour,
            minute: weeklyMinute,
          },
        };
      }

      await createScheduledExecution({
        action_id: action.id,
        environment: selectedEnvironment,
        parameters: formData,
        scheduled_at: schedulingType === 'one-time' ? scheduledDateTime?.toISOString() : undefined,
        recurring_pattern: recurringPattern,
      });

      notification.success({
        message: 'Exécution planifiée',
        description: recurringPattern
          ? 'L\'exécution récurrente a été créée avec succès'
          : `Exécution planifiée pour le ${scheduledDateTime?.format('DD/MM/YYYY à HH:mm')}`,
      });

      onClose();
    }
  };

  return (
    <Modal>
      {/* ... Steps 1 and 2 ... */}

      {/* Step 3: Confirmation */}
      {currentStep === 2 && (
        <div>
          <Space direction="vertical" style={{ width: '100%' }}>
            <Button onClick={handleSchedule}>Exécuter maintenant</Button>
            <Button onClick={() => setIsScheduling(true)}>Planifier</Button>

            {isScheduling && (
              <div>
                <Radio.Group
                  value={schedulingType}
                  onChange={(e) => setSchedulingType(e.target.value)}
                >
                  <Radio value="one-time">Une seule fois</Radio>
                  <Radio value="daily">Tous les jours</Radio>
                  <Radio value="weekly">Toutes les semaines</Radio>
                </Radio.Group>

                {schedulingType === 'one-time' && (
                  <DatePicker
                    showTime
                    format="DD/MM/YYYY HH:mm"
                    value={scheduledDateTime}
                    onChange={setScheduledDateTime}
                    disabledDate={(current) => current && current < dayjs()}
                  />
                )}

                {schedulingType === 'daily' && (
                  <Space>
                    <Select
                      value={dailyHour}
                      onChange={setDailyHour}
                      style={{ width: 100 }}
                    >
                      {Array.from({ length: 24 }, (_, i) => (
                        <Select.Option key={i} value={i}>
                          {String(i).padStart(2, '0')}h
                        </Select.Option>
                      ))}
                    </Select>
                    <Select
                      value={dailyMinute}
                      onChange={setDailyMinute}
                      style={{ width: 100 }}
                    >
                      {[0, 15, 30, 45].map((m) => (
                        <Select.Option key={m} value={m}>
                          {String(m).padStart(2, '0')}min
                        </Select.Option>
                      ))}
                    </Select>
                  </Space>
                )}

                {schedulingType === 'weekly' && (
                  <Space>
                    <Select
                      value={weeklyDayOfWeek}
                      onChange={setWeeklyDayOfWeek}
                      style={{ width: 120 }}
                    >
                      <Select.Option value={1}>Lundi</Select.Option>
                      <Select.Option value={2}>Mardi</Select.Option>
                      <Select.Option value={3}>Mercredi</Select.Option>
                      <Select.Option value={4}>Jeudi</Select.Option>
                      <Select.Option value={5}>Vendredi</Select.Option>
                      <Select.Option value={6}>Samedi</Select.Option>
                      <Select.Option value={7}>Dimanche</Select.Option>
                    </Select>
                    <Select value={weeklyHour} onChange={setWeeklyHour} style={{ width: 100 }}>
                      {/* Same as daily hour */}
                    </Select>
                    <Select value={weeklyMinute} onChange={setWeeklyMinute} style={{ width: 100 }}>
                      {/* Same as daily minute */}
                    </Select>
                  </Space>
                )}
              </div>
            )}
          </Space>
        </div>
      )}
    </Modal>
  );
};
```

**Pattern 7 : Affichage des récurrences dans ScheduledExecutionsPage**

Source : `/idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx` (à étendre)

```tsx
// frontend/src/components/admin/ScheduledExecutionsPage.tsx

// Helper function
const formatRecurrenceDisplay = (recurringPattern: RecurringPatternResponse): string => {
  if (recurringPattern.pattern_type === 'daily') {
    const { hour, minute } = recurringPattern.pattern_config;
    return `Tous les jours à ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')} (UTC)`;
  } else if (recurringPattern.pattern_type === 'weekly') {
    const { day_of_week, hour, minute } = recurringPattern.pattern_config;
    const dayNames = {
      1: 'lundis',
      2: 'mardis',
      3: 'mercredis',
      4: 'jeudis',
      5: 'vendredis',
      6: 'samedis',
      7: 'dimanches',
    };
    const dayName = dayNames[day_of_week as keyof typeof dayNames];
    return `Tous les ${dayName} à ${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')} (UTC)`;
  }
  return '';
};

const columns: ColumnsType<ScheduledExecutionListItem> = [
  {
    title: 'Type',
    key: 'type',
    render: (_, record) => {
      if (record.recurring_pattern) {
        return <Badge status="processing" text="Récurrent" />;
      }
      return <Badge status="default" text="Unique" />;
    },
  },
  {
    title: 'Date/heure planifiée',
    dataIndex: 'scheduled_at',
    key: 'scheduled_at',
    render: (scheduled_at: string | null, record) => {
      if (record.recurring_pattern) {
        const recurrenceText = formatRecurrenceDisplay(record.recurring_pattern);
        const nextExecution = dayjs(record.recurring_pattern.next_execution_date);

        return (
          <div>
            <div>{recurrenceText}</div>
            <div style={{ fontSize: '12px', color: '#888' }}>
              Prochaine : {nextExecution.format('DD/MM/YYYY à HH:mm')}
            </div>
          </div>
        );
      }

      // One-time execution (existing logic from Story 11.6)
      const scheduledDate = dayjs(scheduled_at);
      const isWithin24Hours = scheduledDate.diff(dayjs(), 'hour') <= 24 && scheduledDate.isAfter(dayjs());

      return (
        <Space>
          {scheduledDate.format('DD/MM/YYYY HH:mm')} (UTC)
          {isWithin24Hours && <Badge status="warning" text="Bientôt" />}
        </Space>
      );
    },
  },
  // ... other columns
];

// Details modal
const DetailsModal = ({ selectedExecution, visible, onClose }) => {
  const [toggling, setToggling] = useState(false);

  const handleToggleRecurrence = async () => {
    if (!selectedExecution?.recurring_pattern) return;

    const newActiveState = !selectedExecution.recurring_pattern.is_active;

    try {
      setToggling(true);
      await toggleRecurringPattern(
        selectedExecution.scheduled_execution_id,
        newActiveState
      );

      notification.success({
        message: newActiveState ? 'Récurrence réactivée' : 'Récurrence désactivée',
        description: newActiveState
          ? 'La récurrence a été réactivée avec succès'
          : 'La récurrence a été désactivée avec succès',
      });

      onClose();
      loadScheduledExecutions(); // Reload list
    } catch (error: any) {
      notification.error({
        message: 'Erreur',
        description: error.message || 'Une erreur est survenue',
      });
    } finally {
      setToggling(false);
    }
  };

  return (
    <Modal
      title="Détails de l'exécution planifiée"
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>Fermer</Button>,
        selectedExecution?.recurring_pattern && (
          <Button
            key="toggle"
            type={selectedExecution.recurring_pattern.is_active ? 'default' : 'primary'}
            danger={selectedExecution.recurring_pattern.is_active}
            loading={toggling}
            onClick={handleToggleRecurrence}
          >
            {selectedExecution.recurring_pattern.is_active ? 'Désactiver' : 'Réactiver'}
          </Button>
        ),
      ]}
      width={700}
    >
      {selectedExecution && (
        <Descriptions column={1} bordered size="small">
          {/* Existing fields ... */}

          {selectedExecution.recurring_pattern && (
            <>
              <Descriptions.Item label="Type">
                Récurrent - {selectedExecution.recurring_pattern.pattern_type === 'daily' ? 'Daily' : 'Weekly'}
              </Descriptions.Item>
              <Descriptions.Item label="Configuration">
                {formatRecurrenceDisplay(selectedExecution.recurring_pattern)}
              </Descriptions.Item>
              <Descriptions.Item label="Prochaine exécution">
                {dayjs(selectedExecution.recurring_pattern.next_execution_date).format('DD/MM/YYYY à HH:mm')} (UTC)
              </Descriptions.Item>
              <Descriptions.Item label="Statut">
                {selectedExecution.recurring_pattern.is_active ? (
                  <Badge status="success" text="Actif" />
                ) : (
                  <Badge status="default" text="Désactivé" />
                )}
              </Descriptions.Item>
            </>
          )}
        </Descriptions>
      )}
    </Modal>
  );
};
```

### Source tree components to touch

**Fichiers à créer :**
```
idp-portal/backend/app/utils/recurrence.py                          # Calcul next_execution_date
idp-portal/backend/tests/unit/test_recurrence.py                   # Tests unitaires pour calcul next_execution_date (10+ tests)
idp-portal/backend/tests/integration/test_scheduled_executions_recurring.py  # Tests API recurring patterns (12+ tests)
idp-portal/frontend/src/components/catalog/ExecutionWizard.recurring.test.tsx  # Tests frontend récurrences (10+ tests)
```

**Fichiers à modifier :**
```
idp-portal/backend/app/models/scheduled_execution.py               # Ajouter RecurringPatternRequest, DailyConfig, WeeklyConfig
idp-portal/backend/app/api/v1/scheduled_executions.py              # Étendre POST pour recurring, ajouter PATCH toggle
idp-portal/backend/app/repositories/scheduled_execution_repository.py  # Étendre create_scheduled_execution, ajouter update_recurring_pattern_status
idp-portal/backend/app/models/audit.py                             # Ajouter SCHEDULED_EXECUTION_RECURRING_* types
idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx     # Ajouter Radio.Group et Select pour patterns
idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx  # Afficher récurrences, boutons toggle
idp-portal/frontend/src/services/scheduled_execution_service.ts    # Étendre createScheduledExecution, ajouter toggleRecurringPattern
idp-portal/frontend/src/types/api.ts                               # Ajouter RecurringPatternRequest, RecurringPatternResponse
```

**Fichiers de référence (patterns) :**
```
idp-portal/backend/app/repositories/scheduled_execution_repository.py  # Pattern création avec RETURNING, JSON CLOB
idp-portal/backend/app/api/v1/scheduled_executions.py                  # Pattern validation, RBAC, audit
idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx         # Pattern DatePicker, validation (Story 11.5)
idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx   # Pattern liste, modal, filtres (Story 11.6)
```

### Testing standards summary

**Tests backend (pytest) :**

1. **Tests unitaires (test_recurrence.py) :**
   - `test_calculate_daily_before_time` - Créé avant 02:30 → next = aujourd'hui 02:30
   - `test_calculate_daily_after_time` - Créé après 02:30 → next = demain 02:30
   - `test_calculate_daily_midnight` - hour=0, minute=0 → demain 00:00
   - `test_calculate_weekly_same_day_before_time` - Lundi 10h, exécution 14h → aujourd'hui 14h
   - `test_calculate_weekly_same_day_after_time` - Lundi 16h, exécution 14h → prochain lundi 14h
   - `test_calculate_weekly_next_week` - Mardi, exécution lundi → prochain lundi
   - `test_calculate_weekly_sunday` - day_of_week=7 (dimanche)
   - `test_invalid_pattern_type` - ValueError si pattern_type inconnu
   - `test_daily_missing_hour` - ValueError si hour manquant
   - `test_weekly_missing_day_of_week` - ValueError si day_of_week manquant

2. **Tests intégration (test_scheduled_executions_recurring.py) :**
   - `test_create_daily_recurring_execution` - POST avec pattern daily → 201, RECURRING_PATTERNS créée
   - `test_create_weekly_recurring_execution` - POST avec pattern weekly → 201
   - `test_daily_pattern_validation_missing_hour` - POST sans hour → 400
   - `test_weekly_pattern_validation_invalid_day_of_week` - POST day_of_week=8 → 400
   - `test_recurring_execution_has_null_scheduled_at` - Vérifie scheduled_at=NULL
   - `test_list_includes_recurring_patterns` - GET /scheduled-executions inclut recurring_pattern
   - `test_disable_recurring_pattern` - PATCH is_active=false → 200, is_active=false
   - `test_enable_recurring_pattern_recalculates_next` - PATCH is_active=true → next_execution_date mis à jour
   - `test_toggle_recurring_pattern_not_found` - PATCH sur one-time execution → 404
   - `test_audit_log_recurring_created` - Vérifie SCHEDULED_EXECUTION_RECURRING_CREATED dans audit
   - `test_audit_log_recurring_disabled` - Vérifie SCHEDULED_EXECUTION_RECURRING_DISABLED
   - `test_audit_log_recurring_enabled` - Vérifie SCHEDULED_EXECUTION_RECURRING_ENABLED

**Tests frontend (vitest + React Testing Library) :**

1. `test_wizard_shows_recurrence_options` - Radio.Group affiché avec 3 options
2. `test_wizard_one_time_selected_shows_datepicker` - One-time → DatePicker affiché
3. `test_wizard_daily_selected_shows_hour_minute` - Daily → 2 Select affichés
4. `test_wizard_weekly_selected_shows_day_hour_minute` - Weekly → 3 Select affichés
5. `test_create_daily_execution_api_called` - Clic confirmer avec Daily → API avec recurring_pattern
6. `test_create_weekly_execution_api_called` - Clic confirmer avec Weekly → API avec pattern weekly
7. `test_list_displays_recurring_badge` - Badge "Récurrent" affiché pour récurrences
8. `test_list_displays_daily_schedule` - "Tous les jours à 02:30 (UTC)"
9. `test_list_displays_weekly_schedule` - "Tous les lundis à 14:00 (UTC)"
10. `test_details_modal_shows_recurrence_info` - Modal affiche Type, Config, Prochaine
11. `test_disable_recurrence_success` - Clic Désactiver → confirmation → API → success
12. `test_enable_recurrence_success` - Clic Réactiver → API → notification success
13. `test_toggle_recurrence_error_404` - PATCH sur one-time → erreur affichée

**Validation manuelle :**
1. Tester création Daily : Sélectionner Daily, hour=2, minute=30 → confirmer → succès
2. Tester création Weekly : Sélectionner Weekly, lundi, 14h00 → confirmer → succès
3. Vérifier liste : Récurrences affichées avec badge "Récurrent" et schedule formaté
4. Vérifier modal détails : Affiche Type, Config, Prochaine exécution, Statut
5. Tester désactivation : Clic Désactiver → confirmation → is_active=false
6. Tester réactivation : Clic Réactiver → is_active=true → next_execution_date recalculé
7. Vérifier validation : hour=25 → erreur 400
8. Vérifier validation : day_of_week=8 → erreur 400
9. Vérifier audit : Chaque opération tracée dans audit_log
10. Tester avec différents timezones : UTC partout, pas de confusion de timezone

### Learnings from previous stories (11-1, 11-3, 11-5, 11-6)

**Story 11.1 (Modèle de données) :**
- Table RECURRING_PATTERNS déjà créée avec support pour daily, weekly, cron
- Index composite `(IS_ACTIVE, NEXT_EXECUTION_DATE)` optimisé pour scheduler externe
- PATTERN_CONFIG est CLOB JSON → utiliser `_json_to_str()` et `_str_to_json()`
- Relation 1-to-0..1 avec UNIQUE constraint sur SCHEDULED_EXECUTION_ID

**Story 11.3 (API création one-time) :**
- Validation timezone obligatoire avec Pydantic (MEDIUM-3 FIX)
- Deep copy de schema pour éviter mutations (HIGH-1 FIX)
- Correlation ID pour tracing distribué
- Audit logging systématique pour toutes les opérations
- Log validation failures pour debugging

**Story 11.5 (UI scheduler wizard) :**
- DatePicker avec showTime nécessite plugin dayjs utc
- DisabledDate validation côté client + validation côté serveur
- Format date : `DD/MM/YYYY HH:mm` pour affichage, ISO 8601 pour API
- Messages d'erreur en français, user-friendly
- 45 tests pour couverture complète (viser même niveau ici)

**Story 11.6 (Liste et annulation) :**
- Pattern Table avec filtres réutilisable pour affichage récurrences
- RBAC : DBA voit ses propres, DBOPS voit toutes
- JOIN avec ACTIONS_CATALOG et USERS pour enrichissement
- Modal détails avec toutes les informations (AC10)
- Correlation ID et execution_id ajoutés en V041 (HIGH-1, HIGH-2 fixes)
- Badge colorés pour statuts : pending=blue, executed=green, cancelled=grey

**Patterns à éviter :**
- ❌ Ne pas oublier validation pattern_config selon pattern_type
- ❌ Ne pas utiliser scheduled_at pour récurrences (doit être NULL)
- ❌ Ne pas calculer next_execution_date côté frontend (toujours backend)
- ❌ Ne pas oublier de recalculer next_execution_date lors de la réactivation
- ❌ Ne pas utiliser timezone locale (toujours UTC)

**Patterns à suivre :**
- ✅ Calcul next_execution_date en backend avec datetime.timezone.utc
- ✅ Validation stricte des valeurs (hour 0-23, minute 0-59, day_of_week 1-7)
- ✅ Audit log pour toutes les opérations (created, disabled, enabled)
- ✅ Tests complets (unitaires + intégration + frontend)
- ✅ Display en français avec format DD/MM/YYYY HH:mm (UTC)

### Project Structure Notes

**Alignement avec unified project structure :**
- Frontend React : `/idp-portal/frontend/src/` (components/catalog, components/admin, services, types)
- Tests frontend : Co-localisés avec composant (`ExecutionWizard.recurring.test.tsx`)
- Backend FastAPI : `/idp-portal/backend/app/` (api/v1, repositories, models, utils/recurrence.py)
- Tests backend : `/idp-portal/backend/tests/` (unit/test_recurrence.py, integration/test_scheduled_executions_recurring.py)
- Migrations Oracle : `/idp-portal/database/migrations/` (V038 déjà créée en Story 11.1, aucune nouvelle migration requise)

**Conventions de nommage :**
- TypeScript : camelCase (variables locales), PascalCase (composants, interfaces)
- Fichiers composants : PascalCase.tsx (`ExecutionWizard.tsx`)
- Fichiers services : snake_case.ts (`scheduled_execution_service.ts`)
- API JSON fields : snake_case (`recurring_pattern`, `pattern_type`, `next_execution_date`)
- Props React : camelCase (`onClose`, `recurringPattern`)
- Python : snake_case pour tout (fonctions, variables, modules)

**Detected conflicts or variances :**
- ✅ Aucun conflit - Cette story étend Story 11.5 (wizard) et 11.6 (liste) sans modifier les fonctionnalités existantes
- ✅ Pattern cohérent avec approche externe scheduler (NEXT_EXECUTION_DATE calculé backend)
- ✅ Réutilise les patterns de validation et audit établis en Stories 11.3 et 11.6
- ✅ Suit le pattern wizard existant (Radio.Group pour choix, Select pour valeurs)
- ⚠️ **Attention** : Bien distinguer scheduled_at (one-time) vs recurring_pattern (récurrent) - mutuellement exclusifs
- ⚠️ **Attention** : Validation pattern_config selon pattern_type obligatoire (erreur 400 si incohérent)
- ⚠️ **Attention** : Calcul next_execution_date doit gérer cas "aujourd'hui si pas encore passé" vs "demain"
- ⚠️ **Attention** : day_of_week suit convention 1=Lundi, 7=Dimanche (pas Python weekday 0-6)

### References

**Epic et stories connexes :**
- [Source: _bmad-output/planning-artifacts/epics.md#Epic 11] - Contexte complet Epic 11 Scheduling
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.1] - Modèle de données SCHEDULED_EXECUTIONS et RECURRING_PATTERNS
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.3] - API créer exécution planifiée one-time
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.5] - UI scheduler dans wizard execution
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.6] - Liste des exécutions planifiées et annulation
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.7] - Patterns de récurrence simples (cette story)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 11.8] - Cron expressions pour récurrence avancée (next story)

**Architecture et patterns :**
- [Source: idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx:1-450] - Pattern wizard avec DatePicker et validation
- [Source: idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx:1-830] - Pattern liste avec Table, filtres, modals
- [Source: idp-portal/backend/app/api/v1/scheduled_executions.py:1-360] - Pattern API avec validation et RBAC
- [Source: idp-portal/backend/app/repositories/scheduled_execution_repository.py:1-425] - Pattern repository avec CLOB JSON
- [Source: idp-portal/backend/app/models/scheduled_execution.py:1-80] - Modèles Pydantic pour scheduled executions

**Stories récentes (context et patterns) :**
- [Source: _bmad-output/implementation-artifacts/11-6-liste-executions-planifiees-et-annulation.md] - Story précédente (liste et annulation)
- [Source: _bmad-output/implementation-artifacts/11-5-ui-scheduler-dans-wizard-execution.md] - UI scheduling dans wizard
- [Source: _bmad-output/implementation-artifacts/11-3-api-creer-execution-planifiee-one-time.md] - API création scheduled execution
- [Source: _bmad-output/implementation-artifacts/11-1-modele-donnees-scheduled-executions-et-recurrence.md] - Modèle de données

**Commits récents (Git intelligence) :**
- Commit `e286f13` : feat(scheduling): add scheduled executions list and cancellation (story 11-6)
  - Fichiers : ScheduledExecutionsPage.tsx, API GET/PATCH, repository list/cancel
  - Learnings : RBAC filtering, enriched JOINs, modal détails complets
- Commit `078b814` : feat(scheduling): add schedule option in execution wizard (story 11-5)
  - Fichiers : ExecutionWizard.tsx (DatePicker, validation)
  - Learnings : Pattern DatePicker avec timezone, validation date future
- Commit `316cdd2` : feat(scheduling): add one-time scheduled execution API (story 11-3)
  - Learnings : Validation timezone, correlation_id, audit logging
- Commit `40cff25` : feat(scheduling): add scheduled executions data model with recurrence support (story 11-1)
  - Migration V038 : Tables SCHEDULED_EXECUTIONS et RECURRING_PATTERNS avec index optimisés

**Bibliotheques utilisées :**
- **Backend** : FastAPI, Pydantic, python-oracledb, datetime (timezone.utc), structlog, jsonschema
- **Frontend** : React, Ant Design (Radio, Select, DatePicker, Badge, Modal), dayjs, TypeScript
- **Tests** : pytest, pytest-asyncio, vitest, @testing-library/react

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-5-20250929

### Debug Log References

N/A

### Completion Notes List

Story créée avec contexte complet via analyse exhaustive du codebase (agent Explore).

**Contexte analysé :**
- Modèle de données V038 (SCHEDULED_EXECUTIONS, RECURRING_PATTERNS)
- API existante POST /api/v1/scheduled-executions (Story 11.3)
- UI ExecutionWizard (Story 11.5)
- Liste ScheduledExecutionsPage (Story 11.6)
- Patterns de validation, RBAC, audit, tests

**Approche recommandée :**
1. Commencer par calcul next_execution_date (backend/app/utils/recurrence.py) avec tests unitaires
2. Étendre modèles Pydantic et API POST pour recurring patterns
3. Étendre repository pour créer RECURRING_PATTERNS
4. Créer API PATCH pour toggle is_active
5. Étendre ExecutionWizard pour UI récurrence
6. Étendre ScheduledExecutionsPage pour affichage et toggle
7. Tests intégration backend (12+ tests)
8. Tests frontend (10+ tests)

**Points critiques :**
- Validation pattern_config selon pattern_type (AC6)
- Calcul next_execution_date avec logique "aujourd'hui si pas encore passé" (AC4, AC5)
- day_of_week convention 1=Lundi, 7=Dimanche (pas 0-6)
- Recalcul next_execution_date lors de la réactivation (AC10)
- Audit logging pour created, disabled, enabled (AC11)

**Code Review Fixes (Story 11.7):**

Code review adversarial executé avec 10 problèmes trouvés et 2 HIGH/CRITICAL auto-fixés :

1. **CRITICAL-3 FIX:** `app/api/v1/scheduled_executions.py:372` - Ajout null check pour `next_execution_date.isoformat()` pour éviter AttributeError si None
2. **HIGH-1 FIX (MEDIUM-3):** `app/repositories/scheduled_execution_repository.py:470-476` - Ajout LEFT JOIN RECURRING_PATTERNS dans `count_scheduled_executions` pour cohérence avec `list_scheduled_executions` et support filtrage date sur récurrences

**Problèmes documentés mais non corrigés (technique debt) :**
- MEDIUM: Code duplication validation entre `recurrence.py` et `scheduled_execution.py` (refactoring nécessaire)
- LOW: Tests manquants pour cas erreur "both scheduled_at AND recurring_pattern"
- LOW: Magic strings dans day_of_week mapping frontend
- LOW: Fonction ExecutionWizard.handleSchedule trop longue (>100 lignes)

### File List

**Fichiers modifiés :**
- `idp-portal/backend/app/models/scheduled_execution.py` - RecurringPatternType, DailyPatternConfig, WeeklyPatternConfig, RecurringPatternRequest, RecurringPatternResponse, RecurringPatternToggle, ScheduledExecutionWithAction (scheduled_at optional)
- `idp-portal/backend/app/utils/recurrence.py` - calculate_next_execution_date(), increment_next_execution_date() - NOUVEAU
- `idp-portal/backend/app/api/v1/scheduled_executions.py` - POST extended for recurring_pattern, PATCH toggle_recurring_pattern endpoint
- `idp-portal/backend/app/repositories/scheduled_execution_repository.py` - create with RECURRING_PATTERNS, get_recurring_pattern(), update_recurring_pattern_status(), list with LEFT JOIN
- `idp-portal/backend/app/repositories/audit_repository.py` - SCHEDULED_EXECUTION_RECURRING_CREATED, DISABLED, ENABLED
- `idp-portal/frontend/src/types/api.ts` - RecurringPatternType, DailyPatternConfig, WeeklyPatternConfig, RecurringPatternRequest, RecurringPatternResponse
- `idp-portal/frontend/src/services/scheduled_execution_service.ts` - toggleRecurringPattern()
- `idp-portal/frontend/src/components/catalog/ExecutionWizard.tsx` - Radio.Group one-time/daily/weekly, Select hour/minute/day_of_week
- `idp-portal/frontend/src/components/admin/ScheduledExecutionsPage.tsx` - formatRecurrenceDisplay(), Type column, recurring details modal, toggle buttons

**Fichiers de tests créés :**
- `idp-portal/backend/tests/unit/test_recurrence.py` - 22 tests unitaires (daily/weekly calculation, validation, timezone)
- `idp-portal/backend/tests/integration/test_scheduled_executions_api.py` - 14 tests intégration ajoutés (TestCreateRecurringScheduledExecution, TestListRecurringScheduledExecutions, TestToggleRecurringPattern)
- `idp-portal/frontend/src/services/__tests__/scheduled_execution_service.test.ts` - 9 tests service (create/list/toggle recurring) - NOUVEAU
- `idp-portal/frontend/src/test-setup.ts` - Configuration Vitest avec matchMedia/ResizeObserver mocks - NOUVEAU

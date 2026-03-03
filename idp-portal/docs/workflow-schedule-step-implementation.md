# Implémentation : Step de planification dans un Workflow

## 1. Contexte & Objectif

### Cas d'usage : Patch Oracle sur 100 machines

Un DBA doit patcher 100 bases Oracle. L'opération se fait en 2 temps :
1. **Préparation** (immédiate) : pré-checks, téléchargement des binaires, snapshot
2. **Application** (planifiée) : application du patch pendant la fenêtre de maintenance

Aujourd'hui, ces 2 phases sont des actions indépendantes sans lien. Le DBA doit manuellement planifier l'application après chaque préparation. Pour 100 machines, c'est 200 opérations manuelles.

### Solution

Introduire un nouveau type de step dans les workflows : `schedule_execution`. Ce step, au lieu d'exécuter une action sur une plateforme, **crée une `ScheduledExecution`** via le `SchedulingService` existant. Le `correlation_id` lie la préparation à l'application planifiée.

### Flux cible

```
┌───────────────────────────────┐
│  Utilisateur lance le         │
│  workflow "Patch Oracle"      │
│  pour 100 machines            │
└───────────┬───────────────────┘
            │
            ▼
┌───────────────────────────────┐         ┌──────────────────────────────────┐
│  Step 1 : Préparation         │─success─▶  Step 2 : Planifier application  │
│  step_type: "platform"        │         │  step_type: "schedule_execution" │
│  Ansible : pre-check, snap    │         │  Crée ScheduledExecution         │
│  Exécution immédiate          │         │  avec correlation_id             │
└───────────────────────────────┘         └──────────────────────┬───────────┘
                                                                 │
                                          Workflow COMPLETED ◀───┘
                                                                 │
                                                                 ▼
                                          ┌──────────────────────────────────┐
                                          │  SCHEDULED_EXECUTIONS (table)    │
                                          │  status: pending                 │
                                          │  scheduled_at: samedi 2h         │
                                          │  correlation_id: exec#1234       │
                                          └──────────────────────┬───────────┘
                                                                 │
                                                    Celery Beat (60s poll)
                                                    détecte scheduled_at atteint
                                                                 │
                                                                 ▼
                                          ┌──────────────────────────────────┐
                                          │  Nouvelle Execution créée        │
                                          │  correlation_id: exec#1234       │
                                          │  source: celery_beat             │
                                          │  Action: "Apply Patch"           │
                                          └──────────────────────────────────┘
```

### Ce que voit l'utilisateur (100 machines)

| Vue                    | Contenu                                                         |
|------------------------|-----------------------------------------------------------------|
| Exécutions récentes    | 100 workflows "Patch Oracle" → COMPLETED (vert)                |
| Planifiées             | 100 entrées "Apply Patch" avec date/heure prévue, annulables   |
| Fenêtre de maintenance | Les applications apparaissent au fur et à mesure dans Récentes |

Le dashboard n'est **jamais engorgé** de tâches en attente. Les planifications vivent dans leur onglet dédié.

---

## 2. Architecture & Points d'intégration

### Composants existants réutilisés (aucune modification)

| Composant                | Fichier                                          | Rôle                                  |
|--------------------------|--------------------------------------------------|---------------------------------------|
| `SchedulingService`      | `executions/scheduling_service.py`               | Crée les `ScheduledExecution`         |
| `ScheduledExecution`     | `executions/models.py`                           | Modèle ORM                           |
| `RecurringPattern`       | `executions/models.py`                           | Patterns récurrents (daily/weekly/cron) |
| `process_pending_*`      | `executions/tasks/scheduled.py`                  | Celery Beat : déclenche les SE        |
| `calculate_next_*`       | `executions/utils/scheduling.py`                 | Calcul de la prochaine date           |
| `WorkflowRuntime`        | `executions/workflow_runtime.py`                 | Boucle principale, `_resolve_next_step()` |
| Correlation ID middleware | `core/middleware.py`                             | Génération UUID, thread-local         |

### Composants modifiés

| Composant                | Fichier                                          | Nature du changement                  |
|--------------------------|--------------------------------------------------|---------------------------------------|
| `StepExecutor`           | `executions/workflow_step_executor.py`            | Nouveau code path `schedule_execution` |
| `WorkflowStep` (TS)      | `frontend/src/types/api/catalog.ts`              | Nouveau champ `schedule_config`        |
| `WorkflowStepNode`       | `frontend/src/components/admin/WorkflowStepNode.tsx` | Rendu visuel du step schedule      |
| `StepConfigPanel`        | `frontend/src/components/admin/StepConfigPanel.tsx`  | Config du schedule (action cible, date) |
| `workflowValidation`     | `frontend/src/utils/workflowValidation.ts`       | Validation du step schedule           |
| `validate_workflow_*`    | `executions/utils/workflow_parsing.py`            | Validation backend du nouveau step     |
| Validators backend       | `catalog/validators.py`                           | Validation `schedule_config`          |

---

## 3. Schéma du Workflow Step étendu

### 3.1 Définition JSON (stocké dans `action.execution_steps`)

Un step `schedule_execution` utilise le même schéma `WorkflowStep` avec deux ajouts :
- `step_type` : discriminant (valeur `"schedule_execution"`)
- `schedule_config` : configuration de la planification

```json
{
  "steps": [
    {
      "order": 1,
      "name": "Préparation du patch",
      "step_id": "prepare",
      "referenced_action_id": 42,
      "on_success_step_id": "schedule-apply",
      "on_error_step_id": null
    },
    {
      "order": 2,
      "name": "Planifier l'application",
      "step_id": "schedule-apply",
      "step_type": "schedule_execution",
      "referenced_action_id": 56,
      "schedule_config": {
        "schedule_source": "parameter",
        "schedule_parameter_name": "maintenance_scheduled_at",
        "inherit_parameters": true,
        "inherit_targets": true,
        "parameter_mapping": {
          "snapshot_id": "$.steps.prepare.output.snapshot_id"
        }
      },
      "on_success_step_id": null,
      "on_error_step_id": null
    }
  ]
}
```

### 3.2 Champ `schedule_config` — Spécification

| Champ                      | Type      | Requis | Description                                                    |
|----------------------------|-----------|--------|----------------------------------------------------------------|
| `schedule_source`          | string    | oui    | Source de la date. Valeurs : `"parameter"`, `"fixed_offset"`, `"recurring"` |
| `schedule_parameter_name`  | string    | si `parameter` | Nom du paramètre contenant la date ISO 8601 (rempli par l'utilisateur au lancement) |
| `fixed_offset`             | string    | si `fixed_offset` | Offset relatif à now(), ex: `"+3d"`, `"+6h"`, `"+1w"` |
| `recurring_pattern`        | object    | si `recurring` | `{ pattern_type, pattern_config }` identique au format existant |
| `inherit_parameters`       | boolean   | non    | Si true, copie les paramètres de l'exécution courante (défaut: `false`) |
| `inherit_targets`          | boolean   | non    | Si true, copie les targets de l'exécution courante (défaut: `false`) |
| `parameter_mapping`        | object    | non    | Mapping de paramètres additionnels. Clé = nom du param cible, Valeur = JSONPath ou valeur statique |

### 3.3 `schedule_source` : les 3 modes

#### Mode `parameter` — Date choisie par l'utilisateur

L'utilisateur saisit la date dans le formulaire de lancement du workflow. Le paramètre est défini dans le `parameters_schema` du workflow.

```json
{
  "schedule_source": "parameter",
  "schedule_parameter_name": "maintenance_scheduled_at"
}
```

Le `parameters_schema` du workflow inclut :
```json
{
  "properties": {
    "maintenance_scheduled_at": {
      "type": "string",
      "format": "date-time",
      "title": "Date d'application",
      "description": "Date prévue pour l'application du patch (fenêtre de maintenance)"
    }
  },
  "required": ["maintenance_scheduled_at"]
}
```

#### Mode `fixed_offset` — Offset relatif

La date est calculée automatiquement par le backend à l'exécution du step.

```json
{
  "schedule_source": "fixed_offset",
  "fixed_offset": "+3d"
}
```

Syntaxe supportée :
- `+Nd` : N jours
- `+Nh` : N heures
- `+Nw` : N semaines
- `+Nm` : N minutes

#### Mode `recurring` — Pattern récurrent

Crée une `ScheduledExecution` avec `RecurringPattern` (réutilise l'infra existante).

```json
{
  "schedule_source": "recurring",
  "recurring_pattern": {
    "pattern_type": "weekly",
    "pattern_config": { "day_of_week": 6, "hour": 2, "minute": 0 }
  }
}
```

---

## 4. Backend : Modifications

### 4.1 `StepExecutor.execute()` — Nouveau code path

**Fichier** : `executions/workflow_step_executor.py`

Le point d'entrée `execute()` (ligne 40) doit router sur le `step_type` :

```python
def execute(self, step, step_order, step_parameters):
    from executions.workflow_runtime import StepResult, StepOutcome

    step_type = step.get('step_type', 'platform')

    # Route par step_type
    if step_type == 'schedule_execution':
        return self._execute_schedule_step(step, step_order, step_parameters)

    # ... code existant (gate_conditions, platform dispatch) ...
```

### 4.2 Nouvelle méthode `_execute_schedule_step()`

```python
def _execute_schedule_step(
    self,
    step: Dict[str, Any],
    step_order: int,
    step_parameters: Dict[str, Any],
) -> "StepResult":
    """
    Exécute un step de type schedule_execution.

    Au lieu de dispatcher vers une plateforme, crée une ScheduledExecution
    via SchedulingService. Le workflow continue (step = SUCCESS).
    """
    from executions.workflow_runtime import StepResult, StepOutcome
    from executions.scheduling_service import SchedulingService
    from catalog.models import Action

    step_id = step.get('step_id')
    step_name = step.get('name', f"Step {step.get('order', 0)}")
    schedule_config = step.get('schedule_config', {})
    referenced_action_id = step.get('referenced_action_id')

    logger.info(
        "workflow_schedule_step_executing",
        execution_id=self.execution.id,
        step_id=step_id,
        referenced_action_id=referenced_action_id,
        schedule_source=schedule_config.get('schedule_source'),
        correlation_id=self.correlation_id,
    )

    # Créer l'ExecutionStep pour le suivi
    execution_step = ExecutionStep.objects.create(
        execution=self.execution,
        step_order=step_order,
        step_name=step_name,
        step_type='schedule_execution',
        status=ExecutionStepStatus.RUNNING,
        started_at=timezone.now(),
    )

    try:
        # 1. Charger l'action cible
        if not referenced_action_id:
            raise ValueError(f"Step {step_id}: referenced_action_id requis pour schedule_execution")

        target_action = Action.objects.get(id=referenced_action_id)

        # 2. Résoudre la date de planification
        scheduled_at = self._resolve_schedule_date(schedule_config, step_parameters)
        recurring_pattern_data = self._resolve_recurring_pattern(schedule_config)

        # 3. Construire les paramètres de l'exécution planifiée
        scheduled_params = self._build_scheduled_parameters(
            schedule_config, step_parameters, step
        )

        # 4. Créer la ScheduledExecution via le service existant
        scheduling_service = SchedulingService()
        scheduled_execution = scheduling_service.create_scheduled_execution(
            user=self.execution.user,
            action=target_action,
            environment=self.execution.environment,
            parameters=scheduled_params,
            scheduled_at=scheduled_at,
            recurring_pattern_data=recurring_pattern_data,
        )

        # 5. Stocker le correlation_id sur la SE pour traçabilité
        scheduled_execution.correlation_id = self.correlation_id or str(self.execution.id)
        scheduled_execution.save()

        # 6. Marquer le step comme COMPLETED
        execution_step.status = ExecutionStepStatus.COMPLETED
        execution_step.completed_at = timezone.now()
        execution_step.set_output({
            'scheduled_execution_id': scheduled_execution.id,
            'target_action_id': target_action.id,
            'target_action_name': target_action.name,
            'scheduled_at': str(scheduled_at) if scheduled_at else None,
            'recurring': recurring_pattern_data is not None,
            'correlation_id': scheduled_execution.correlation_id,
        })
        execution_step.save()

        # 7. Audit
        AuditService.create_entry(
            user_id=str(self.execution.user_id),
            action_type=AuditActionType.WORKFLOW_STEP_SCHEDULE_CREATED,
            entity_type=AuditEntityType.EXECUTION,
            entity_id=self.execution.id,
            details={
                'step_id': step_id,
                'step_name': step_name,
                'scheduled_execution_id': scheduled_execution.id,
                'target_action_id': target_action.id,
                'target_action_name': target_action.name,
                'scheduled_at': str(scheduled_at) if scheduled_at else None,
                'schedule_source': schedule_config.get('schedule_source'),
            },
            correlation_id=self.correlation_id,
        )

        logger.info(
            "workflow_schedule_step_completed",
            execution_id=self.execution.id,
            step_id=step_id,
            scheduled_execution_id=scheduled_execution.id,
            correlation_id=self.correlation_id,
        )

        return StepResult(
            outcome=StepOutcome.SUCCESS,
            output={
                'scheduled_execution_id': scheduled_execution.id,
                'target_action_id': target_action.id,
                'target_action_name': target_action.name,
            },
        )

    except Exception as e:
        execution_step.status = ExecutionStepStatus.FAILED
        execution_step.completed_at = timezone.now()
        execution_step.error_message = f"{type(e).__name__}: {str(e)}"
        execution_step.save()

        logger.error(
            "workflow_schedule_step_failed",
            execution_id=self.execution.id,
            step_id=step_id,
            error=str(e),
            correlation_id=self.correlation_id,
            exc_info=True,
        )

        return StepResult(
            outcome=StepOutcome.ERROR,
            error_message=str(e),
            error_details={'step_id': step_id, 'error_type': type(e).__name__},
        )
```

### 4.3 Méthodes utilitaires de résolution

```python
def _resolve_schedule_date(
    self, schedule_config: dict, step_parameters: dict
) -> datetime | None:
    """Résout la date de planification selon le schedule_source."""
    source = schedule_config.get('schedule_source', 'parameter')

    if source == 'parameter':
        param_name = schedule_config.get('schedule_parameter_name', 'scheduled_at')
        # Chercher dans les step_parameters d'abord, puis dans les params globaux
        date_str = step_parameters.get(param_name)
        if not date_str:
            global_params = self.execution.get_parameters() or {}
            date_str = global_params.get(param_name)
        if not date_str:
            raise ValueError(
                f"Paramètre '{param_name}' requis pour schedule_source='parameter'"
            )
        from django.utils.dateparse import parse_datetime
        parsed = parse_datetime(date_str)
        if not parsed:
            raise ValueError(f"Format de date invalide pour '{param_name}': {date_str}")
        return parsed

    elif source == 'fixed_offset':
        offset_str = schedule_config.get('fixed_offset', '+1d')
        return self._parse_fixed_offset(offset_str)

    elif source == 'recurring':
        return None  # Pas de scheduled_at pour les récurrents

    else:
        raise ValueError(f"schedule_source inconnu: {source}")


def _parse_fixed_offset(self, offset_str: str) -> datetime:
    """Parse '+3d', '+6h', '+1w', '+30m' en datetime absolue."""
    import re
    from datetime import timedelta

    match = re.match(r'^\+(\d+)([dhwm])$', offset_str)
    if not match:
        raise ValueError(f"Format d'offset invalide: {offset_str}. Attendu: +Nd, +Nh, +Nw, +Nm")

    value = int(match.group(1))
    unit = match.group(2)

    deltas = {'d': timedelta(days=value), 'h': timedelta(hours=value),
              'w': timedelta(weeks=value), 'm': timedelta(minutes=value)}

    return timezone.now() + deltas[unit]


def _resolve_recurring_pattern(self, schedule_config: dict) -> dict | None:
    """Construit recurring_pattern_data si schedule_source == 'recurring'."""
    if schedule_config.get('schedule_source') != 'recurring':
        return None

    pattern_data = schedule_config.get('recurring_pattern', {})
    pattern_type = pattern_data.get('pattern_type')
    pattern_config = pattern_data.get('pattern_config', {})

    if not pattern_type:
        raise ValueError("recurring_pattern.pattern_type requis pour schedule_source='recurring'")

    from executions.utils import calculate_next_execution_date
    next_date = calculate_next_execution_date(pattern_type, pattern_config, timezone.now())

    return {
        'pattern_type': pattern_type,
        'pattern_config': pattern_config,
        'next_execution_date': next_date,
    }


def _build_scheduled_parameters(
    self, schedule_config: dict, step_parameters: dict, step: dict
) -> dict | None:
    """Construit les paramètres pour la ScheduledExecution."""
    params = {}

    # Hériter des paramètres de l'exécution courante
    if schedule_config.get('inherit_parameters', False):
        global_params = self.execution.get_parameters() or {}
        # Copier les paramètres globaux (pas les workflow_step_parameters)
        for key, value in global_params.items():
            if key != 'workflow_step_parameters':
                params[key] = value

    # Ajouter/écraser avec le parameter_mapping
    mapping = schedule_config.get('parameter_mapping', {})
    for target_key, source_expr in mapping.items():
        if isinstance(source_expr, str) and source_expr.startswith('$.'):
            # Résolution JSONPath simplifiée (à étendre si besoin)
            # Format: $.steps.<step_id>.output.<field>
            params[target_key] = self._resolve_jsonpath(source_expr)
        else:
            # Valeur statique
            params[target_key] = source_expr

    # Ajouter les step_parameters explicites (priorité max)
    if step_parameters:
        schedule_param_name = schedule_config.get('schedule_parameter_name')
        for key, value in step_parameters.items():
            # Ne pas copier le paramètre de date dans les params de l'action cible
            if key != schedule_param_name:
                params[key] = value

    return params if params else None


def _resolve_jsonpath(self, expr: str) -> Any:
    """
    Résolution simplifiée pour $.steps.<step_id>.output.<field>.

    Récupère la valeur depuis les ExecutionStep existants de l'exécution en cours.
    """
    parts = expr.split('.')
    if len(parts) >= 5 and parts[1] == 'steps' and parts[3] == 'output':
        step_name = parts[2]
        field_name = '.'.join(parts[4:])
        # Chercher le step par step_name dans les ExecutionSteps précédents
        from executions.models import ExecutionStep as ES
        try:
            prev_step = ES.objects.filter(
                execution=self.execution, step_name=step_name
            ).order_by('-step_order').first()
            if prev_step:
                output = prev_step.get_output() or {}
                return output.get(field_name)
        except ES.DoesNotExist:
            pass
    return None
```

### 4.4 Nouveau type d'audit

**Fichier** : `core/models.py` — `AuditActionType`

Ajouter :
```python
WORKFLOW_STEP_SCHEDULE_CREATED = ('workflow_step_schedule_created', 'Workflow Step Schedule Created')
```

### 4.5 Migration : Nouveau type d'audit

**Fichier** : `database/migrations/V0XX__add_workflow_step_schedule_audit_type.sql`

```sql
-- Story XX: Add audit type for workflow schedule step
INSERT INTO REF_AUDIT_ACTION_TYPES (CODE, LABEL) VALUES
('workflow_step_schedule_created', 'Workflow Step Schedule Created');
```

### 4.6 Validation backend du `schedule_config`

**Fichier** : `catalog/validators.py`

```python
VALID_SCHEDULE_SOURCES = ('parameter', 'fixed_offset', 'recurring')
VALID_OFFSET_PATTERN = re.compile(r'^\+\d+[dhwm]$')


def validate_schedule_config(schedule_config: dict) -> None:
    """Valide la configuration schedule_config d'un step schedule_execution."""
    if not isinstance(schedule_config, dict):
        raise BadRequestError("schedule_config doit être un objet", code="INVALID_SCHEDULE_CONFIG")

    source = schedule_config.get('schedule_source')
    if source not in VALID_SCHEDULE_SOURCES:
        raise BadRequestError(
            f"schedule_source invalide: {source}. Valeurs attendues: {VALID_SCHEDULE_SOURCES}",
            code="INVALID_SCHEDULE_SOURCE",
        )

    if source == 'parameter':
        if not schedule_config.get('schedule_parameter_name'):
            raise BadRequestError(
                "schedule_parameter_name requis quand schedule_source='parameter'",
                code="MISSING_SCHEDULE_PARAMETER_NAME",
            )

    elif source == 'fixed_offset':
        offset = schedule_config.get('fixed_offset')
        if not offset or not VALID_OFFSET_PATTERN.match(offset):
            raise BadRequestError(
                f"fixed_offset invalide: {offset}. Format attendu: +Nd, +Nh, +Nw, +Nm",
                code="INVALID_FIXED_OFFSET",
            )

    elif source == 'recurring':
        pattern = schedule_config.get('recurring_pattern', {})
        if not pattern.get('pattern_type'):
            raise BadRequestError(
                "recurring_pattern.pattern_type requis quand schedule_source='recurring'",
                code="MISSING_PATTERN_TYPE",
            )
```

**Fichier** : `executions/utils/workflow_parsing.py` — `validate_workflow_referenced_actions()`

Ajouter la validation du `schedule_config` pour les steps de type `schedule_execution` :

```python
for step in steps:
    step_type = step.get('step_type', 'platform')
    if step_type == 'schedule_execution':
        schedule_config = step.get('schedule_config')
        if not schedule_config:
            raise BadRequestError(
                f"Step {step.get('step_id')}: schedule_config requis pour step_type='schedule_execution'"
            )
        validate_schedule_config(schedule_config)
```

### 4.7 Serializer — Exposer `step_type` et `schedule_config`

**Fichier** : `catalog/serializers.py` — `ActionSerializer.get_workflow_steps()`

Ajouter au dict retourné :
```python
{
    # ... champs existants ...
    'step_type': step.get('step_type', 'platform'),
    'schedule_config': step.get('schedule_config'),
}
```

---

## 5. Frontend : Modifications

### 5.1 Types TypeScript

**Fichier** : `frontend/src/types/api/catalog.ts`

```typescript
/** Schedule source for a schedule_execution step. */
export type ScheduleSource = 'parameter' | 'fixed_offset' | 'recurring';

/** Configuration for a schedule_execution workflow step. */
export interface ScheduleStepConfig {
  schedule_source: ScheduleSource;
  /** Parameter name containing the ISO 8601 date (when source='parameter'). */
  schedule_parameter_name?: string;
  /** Relative offset from now (when source='fixed_offset'). Format: +Nd, +Nh, +Nw, +Nm. */
  fixed_offset?: string;
  /** Recurring pattern definition (when source='recurring'). */
  recurring_pattern?: {
    pattern_type: 'daily' | 'weekly' | 'cron';
    pattern_config: Record<string, unknown>;
  };
  /** If true, inherit parameters from the parent execution. */
  inherit_parameters?: boolean;
  /** If true, inherit targets from the parent execution. */
  inherit_targets?: boolean;
  /** Mapping of parameters: key = target param name, value = JSONPath or static value. */
  parameter_mapping?: Record<string, string>;
}

export interface WorkflowStep {
  order: number;
  name: string | null;
  referenced_action_id: number;
  action_name?: string | null;
  step_id?: string | null;
  /** Step type: 'platform' (default) or 'schedule_execution'. */
  step_type?: 'platform' | 'schedule_execution';
  /** Configuration for schedule_execution steps. */
  schedule_config?: ScheduleStepConfig | null;
  on_success_step_id?: string | null;
  on_error_step_id?: string | null;
  retry_enabled?: boolean;
  retry_max_attempts?: number | null;
  retry_interval_seconds?: number | null;
  retry_backoff_multiplier?: number | null;
}
```

### 5.2 WorkflowBuilderCanvas — Nouvelle palette

**Fichier** : `frontend/src/components/admin/ActionPalette.tsx`

Ajouter une section "Steps spéciaux" dans la palette, avec une entrée "Planifier une exécution" qui crée un node de type `schedule_execution`.

```tsx
// Section "Steps spéciaux" dans la palette
<PaletteSection title="Steps spéciaux">
  <PaletteItem
    icon={<CalendarClockIcon />}
    label="Planifier une exécution"
    description="Crée une tâche planifiée au lieu d'exécuter immédiatement"
    onDrag={() => createScheduleNode()}
  />
</PaletteSection>
```

### 5.3 WorkflowStepNode — Rendu visuel

**Fichier** : `frontend/src/components/admin/WorkflowStepNode.tsx`

Le node d'un step `schedule_execution` se distingue visuellement :

```tsx
// Dans le rendu du node
const isScheduleStep = step.step_type === 'schedule_execution';

return (
  <div className={cn(
    'workflow-step-node',
    isScheduleStep && 'workflow-step-node--schedule'
  )}>
    {isScheduleStep ? <CalendarClockIcon /> : <PlayIcon />}
    <span className="step-name">{step.name}</span>
    <span className="step-action">{step.action_name}</span>
    {isScheduleStep && (
      <Badge variant="outline" className="text-xs">
        {formatScheduleSource(step.schedule_config?.schedule_source)}
      </Badge>
    )}
  </div>
);
```

Couleur différenciée : bordure bleue/violette au lieu de la bordure verte des steps platform.

### 5.4 StepConfigPanel — Configuration du schedule

**Fichier** : `frontend/src/components/admin/StepConfigPanel.tsx`

Quand un step `schedule_execution` est sélectionné dans le canvas, le panel de droite affiche :

```
┌─────────────────────────────────────┐
│  Configuration du step              │
│                                     │
│  Nom: [Planifier l'application    ] │
│                                     │
│  Action cible: [▼ Apply Patch     ] │
│  (sélecteur parmi les actions       │
│   publiées du même engine)          │
│                                     │
│  Source de la date:                  │
│  ○ Paramètre utilisateur            │
│    Nom du paramètre:                │
│    [maintenance_scheduled_at      ] │
│                                     │
│  ○ Offset fixe                      │
│    Délai: [+3d                    ] │
│                                     │
│  ○ Récurrent                        │
│    [Config daily/weekly/cron]       │
│                                     │
│  ☑ Hériter les paramètres           │
│  ☑ Hériter les targets              │
│                                     │
│  Mapping de paramètres:             │
│  ┌──────────────┬──────────────────┐│
│  │ Param cible  │ Source           ││
│  ├──────────────┼──────────────────┤│
│  │ snapshot_id  │ $.steps.prepare. ││
│  │              │   output.snap_id ││
│  └──────────────┴──────────────────┘│
│  [+ Ajouter un mapping]            │
│                                     │
│  ── Branchement ──                  │
│  En cas de succès: [▼ (Fin)       ] │
│  En cas d'erreur:  [▼ (Fin)       ] │
└─────────────────────────────────────┘
```

### 5.5 Validation frontend

**Fichier** : `frontend/src/utils/workflowValidation.ts`

Ajouter dans `validateWorkflowGraph()` :

```typescript
// Valider les steps schedule_execution
for (const step of steps) {
  if (step.step_type === 'schedule_execution') {
    if (!step.schedule_config) {
      errors.push(`Step "${step.name}": schedule_config requis`);
      continue;
    }
    const { schedule_source } = step.schedule_config;
    if (!['parameter', 'fixed_offset', 'recurring'].includes(schedule_source)) {
      errors.push(`Step "${step.name}": schedule_source invalide: ${schedule_source}`);
    }
    if (schedule_source === 'parameter' && !step.schedule_config.schedule_parameter_name) {
      errors.push(`Step "${step.name}": schedule_parameter_name requis`);
    }
    if (schedule_source === 'fixed_offset' && !step.schedule_config.fixed_offset) {
      errors.push(`Step "${step.name}": fixed_offset requis`);
    }
    if (schedule_source === 'recurring' && !step.schedule_config.recurring_pattern?.pattern_type) {
      errors.push(`Step "${step.name}": recurring_pattern.pattern_type requis`);
    }
  }
}
```

### 5.6 Conversion React Flow

**Fichier** : `frontend/src/utils/workflowConversion.ts`

`workflowStepsToReactFlow()` : les nodes `schedule_execution` reçoivent un `data.stepType` pour le rendu visuel différencié.

`reactFlowToWorkflowSteps()` : préserver `step_type` et `schedule_config` lors de la conversion inverse.

---

## 6. Frontend : Affichage des liens de traçabilité

### 6.1 Détail d'exécution — Lien vers la planification créée

Quand un workflow contient un step `schedule_execution` complété, afficher dans le détail de l'exécution :

```
Step 2 : Planifier l'application ✓ COMPLETED
  └─ Exécution planifiée #789 — Apply Patch — Samedi 2h00
     [Voir dans les planifications →]
```

Le `scheduled_execution_id` est dans le `step.output`.

### 6.2 Liste des planifications — Lien vers la préparation source

Dans l'onglet "Planifiées", ajouter une colonne "Origine" :

```
| Action         | Date prévue    | Statut  | Origine                  |
|----------------|----------------|---------|--------------------------|
| Apply Patch    | Sam. 07/03 2h  | pending | Workflow Prep #1234 →    |
| Apply Patch    | Sam. 07/03 2h  | pending | Workflow Prep #1235 →    |
```

Le lien est résolu via `scheduled_execution.correlation_id` → `execution.id`.

---

## 7. Traçabilité complète via `correlation_id`

### Flux du correlation_id

```
1. Utilisateur lance le workflow "Patch Oracle"
   → HTTP Request avec X-Correlation-ID (ou auto-généré)
   → correlation_id = "abc-123"

2. WorkflowRuntime.run() exécute Step 1 (Préparation)
   → ExecutionStep créé avec correlation_id dans les logs
   → Step COMPLETED

3. WorkflowRuntime.run() exécute Step 2 (Schedule)
   → StepExecutor._execute_schedule_step()
   → ScheduledExecution créée avec correlation_id = "abc-123"
   → Step COMPLETED, workflow COMPLETED

4. Samedi 2h: Celery Beat déclenche la ScheduledExecution
   → process_pending_scheduled_executions()
   → ExecutionService.create_execution() avec:
     - source = 'celery_beat'
     - correlation_id hérité de la ScheduledExecution = "abc-123"
   → Nouvelle Execution #999 avec correlation_id = "abc-123"

5. Recherche par correlation_id "abc-123" retourne:
   - Execution #1234 (workflow Patch Oracle) — COMPLETED
   - ScheduledExecution #789 (Apply Patch planifié) — EXECUTED
   - Execution #999 (Apply Patch déclenché) — COMPLETED
```

### Requête de traçabilité

```sql
-- Trouver toute la chaîne pour un workflow donné
SELECT 'execution' as type, id, status, correlation_id, created_at
FROM EXECUTIONS WHERE correlation_id = 'abc-123'
UNION ALL
SELECT 'scheduled' as type, id, status, correlation_id, created_at
FROM SCHEDULED_EXECUTIONS WHERE correlation_id = 'abc-123'
ORDER BY created_at;
```

---

## 8. Tests

### 8.1 Tests unitaires backend

**Fichier** : `tests/executions/test_schedule_step_executor.py`

| Test                                                    | Vérifie                                                    |
|---------------------------------------------------------|------------------------------------------------------------|
| `test_schedule_step_creates_scheduled_execution`        | Happy path : ScheduledExecution créée avec bons paramètres |
| `test_schedule_step_parameter_source`                   | Date extraite du paramètre utilisateur                     |
| `test_schedule_step_fixed_offset`                       | Date calculée depuis l'offset                              |
| `test_schedule_step_recurring`                          | RecurringPattern créé correctement                         |
| `test_schedule_step_inherit_parameters`                 | Paramètres hérités de l'exécution parent                   |
| `test_schedule_step_inherit_targets`                    | Targets hérités                                            |
| `test_schedule_step_parameter_mapping`                  | Mapping JSONPath résolu depuis output du step précédent    |
| `test_schedule_step_correlation_id_propagated`          | correlation_id correctement propagé                        |
| `test_schedule_step_missing_parameter_fails`            | Erreur si paramètre de date manquant                       |
| `test_schedule_step_invalid_offset_fails`               | Erreur si format d'offset invalide                         |
| `test_schedule_step_missing_action_fails`               | Erreur si referenced_action_id inexistant                  |
| `test_schedule_step_creates_audit_entry`                | Entrée d'audit WORKFLOW_STEP_SCHEDULE_CREATED créée        |
| `test_schedule_step_output_contains_scheduled_exec_id`  | step.output contient scheduled_execution_id                |

### 8.2 Tests d'intégration

**Fichier** : `tests/executions/test_workflow_with_schedule_step.py`

| Test                                                    | Vérifie                                                    |
|---------------------------------------------------------|------------------------------------------------------------|
| `test_workflow_prep_then_schedule_completes`            | Workflow à 2 steps (platform + schedule) → COMPLETED       |
| `test_workflow_schedule_step_on_prep_failure_skipped`   | Step schedule non exécuté si prep échoue (branche error)   |
| `test_celery_triggers_scheduled_from_workflow`          | process_pending_scheduled_executions déclenche l'action     |
| `test_full_chain_correlation_id`                        | correlation_id présent sur Execution + ScheduledExecution + Execution déclenchée |

### 8.3 Tests frontend

| Test                                                    | Vérifie                                                    |
|---------------------------------------------------------|------------------------------------------------------------|
| `test_schedule_step_node_renders`                       | WorkflowStepNode avec step_type=schedule_execution s'affiche |
| `test_step_config_panel_schedule`                       | StepConfigPanel affiche les options schedule_config         |
| `test_workflow_validation_schedule_step`                 | Validation rejette schedule_config incomplet               |
| `test_react_flow_conversion_preserves_schedule_config`  | Conversion aller-retour préserve step_type + schedule_config |

---

## 9. Séquence d'implémentation

### Phase 1 : Backend core (estimé : 1 sprint)

1. Migration : nouveau type d'audit `WORKFLOW_STEP_SCHEDULE_CREATED`
2. `StepExecutor._execute_schedule_step()` et méthodes utilitaires
3. Validation `validate_schedule_config()` dans `catalog/validators.py`
4. Validation dans `workflow_parsing.py`
5. Serializer : exposer `step_type` et `schedule_config`
6. Tests unitaires backend

### Phase 2 : Frontend workflow builder (estimé : 1 sprint)

1. Types TypeScript (`ScheduleStepConfig`, extension de `WorkflowStep`)
2. `ActionPalette` : entrée "Planifier une exécution"
3. `WorkflowStepNode` : rendu visuel schedule
4. `StepConfigPanel` : formulaire de configuration schedule
5. `workflowConversion.ts` : support du nouveau step type
6. `workflowValidation.ts` : validation frontend
7. Tests frontend

### Phase 3 : Traçabilité UI (estimé : 0.5 sprint)

1. Détail d'exécution : lien vers la planification créée
2. Liste des planifications : colonne "Origine" avec lien
3. Tests d'intégration end-to-end

---

## 10. Points d'attention

### 10.1 Pas de modification de la table `SCHEDULED_EXECUTIONS`

Le champ `correlation_id` existe déjà (V041). Aucune migration de schéma nécessaire.

### 10.2 Rétrocompatibilité

- `step_type` est optionnel, défaut `"platform"` → les workflows existants fonctionnent sans changement
- `schedule_config` est optionnel, ignoré pour les steps platform
- Le frontend doit gérer gracieusement l'absence de `step_type` (= platform)

### 10.3 Sécurité RBAC

Le step `schedule_execution` crée la ScheduledExecution au nom de l'utilisateur qui a lancé le workflow (`execution.user`). Les contrôles RBAC de `SchedulingService` s'appliquent normalement :
- L'utilisateur doit avoir accès à l'action cible
- L'utilisateur doit avoir accès à l'environnement

### 10.4 Annulation en cascade

Si l'utilisateur annule le workflow AVANT que le step schedule ne s'exécute, rien à faire (le step n'a pas encore créé de ScheduledExecution).

Si le workflow est COMPLETED et qu'une ScheduledExecution existe, l'utilisateur peut l'annuler indépendamment via l'onglet "Planifiées" (mécanisme existant).

### 10.5 Idempotence

Le retry du step `schedule_execution` pourrait créer des doublons. Protection recommandée :
- Le `StepExecutor` vérifie si un `ExecutionStep` avec le même `step_order` existe déjà en COMPLETED avant de re-créer
- Ou : utiliser le pattern "check-then-act" avec `select_for_update`

### 10.6 Limitations V1

- Le `parameter_mapping` avec JSONPath est simplifié (pas de bibliothèque JSONPath complète)
- Pas de support `maintenance_window` comme schedule_source en V1 (nécessiterait une intégration CMDB)
- Un step `schedule_execution` ne peut pas être en WAITING (pas de gate_conditions) — c'est volontaire, la planification est instantanée

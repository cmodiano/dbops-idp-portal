# Story 25.2 : Condition Gates — statut WAITING et gate_conditions dans execution_steps

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want pouvoir définir des préconditions (gates) sur une étape d'exécution (plage de maintenance, créneau horaire, approbation, état cible),
So que l'étape ne démarre qu'une fois les conditions remplies, sans exécution prématurée.

## Acceptance Criteria

**AC1: Nouveau statut WAITING dans ExecutionStepStatus**

**Given** le modèle ExecutionStep existe avec des statuts PENDING, RUNNING, COMPLETED, FAILED, SKIPPED
**When** j'ajoute le support des condition gates
**Then** un nouveau statut WAITING est ajouté à ExecutionStepStatus
**And** le statut WAITING signifie "l'étape attend que ses gate_conditions soient satisfaites"
**And** une migration Django ajoute WAITING aux choix du champ status
**And** une migration SQL V067 ajoute WAITING à la contrainte CHECK du champ STATUS dans EXECUTION_STEPS

**AC2: Support gate_conditions dans le JSON execution_steps des actions**

**Given** une action dont le champ execution_steps (JSON CLOB) définit des étapes
**When** une étape possède un attribut gate_conditions (tableau JSON de conditions)
**Then** le schéma JSON des gate_conditions est documenté avec au moins les types suivants :
  - `maintenance_window` : attendre la plage de maintenance des serveurs cibles
  - `time_window` : attendre un créneau horaire spécifique
  - `approval_granted` : attendre qu'une approbation soit accordée
  - `target_state` : attendre que les cibles soient dans un état donné
**And** chaque condition peut avoir un champ `timeout_hours` (optionnel) et `on_timeout` (FAIL | SKIP)

**AC3: Le WorkflowRuntime crée les ExecutionStep en statut WAITING si gate_conditions présent**

**Given** une action avec une étape possédant gate_conditions dans son JSON
**When** le workflow_runtime.py atteint cette étape lors de l'exécution
**Then** un ExecutionStep est créé avec status='WAITING' (au lieu de status='RUNNING')
**And** l'ExecutionStep n'est PAS exécuté immédiatement
**And** le champ output de l'ExecutionStep contient le contexte d'attente initial (raison, gate_conditions, created_at)
**And** le workflow_runtime marque cette étape comme "en attente de résolution" et NE passe PAS à l'étape suivante

**AC4: Contexte d'attente stocké dans ExecutionStep.output**

**Given** une ExecutionStep en statut WAITING
**When** les gate_conditions ne sont pas encore satisfaites
**Then** le champ output (JSON CLOB) de l'ExecutionStep contient :
  - `waiting_since` : timestamp de création de l'étape
  - `gate_conditions` : copie des conditions à satisfaire
  - `gate_status` : état de chaque condition (satisfied: false, reason: "...", next_possible_at: timestamp optionnel)
**And** ce contexte peut être mis à jour périodiquement par le service GateEvaluator

**AC5: Validation du schéma JSON gate_conditions dans le catalogue**

**Given** un administrateur crée ou modifie une action avec execution_steps
**When** une étape contient gate_conditions dans son JSON
**Then** le backend valide que gate_conditions est un tableau JSON
**And** chaque condition a au minimum un champ `type` (valeur : maintenance_window | time_window | approval_granted | target_state)
**And** si un timeout_hours est présent, il doit être un nombre > 0
**And** si on_timeout est présent, il doit être "FAIL" ou "SKIP"
**And** si la validation échoue, l'API retourne une erreur 400 avec un message explicite

**AC6: Documentation du pattern condition gates**

**Given** le pattern condition gates est implémenté
**When** un développeur ou un administrateur consulte la documentation
**Then** un document `docs/backend/condition-gates.md` existe et décrit :
  - Le concept de condition gate et son utilité
  - La structure JSON des gate_conditions
  - Les types de conditions supportés (maintenance_window, time_window, approval_granted, target_state)
  - Le cycle de vie d'une étape WAITING
  - Des exemples concrets de gate_conditions
  - Les limitations et cas d'usage recommandés

## Tasks / Subtasks

- [x] Task 1: Ajouter le statut WAITING à ExecutionStepStatus (AC: 1)
  - [x] 1.1: Modifier executions/models.py::ExecutionStepStatus et ajouter `WAITING = 'WAITING', 'Waiting'`
  - [x] 1.2: Créer migration Django pour ajouter WAITING aux choix du champ status
  - [x] 1.3: Créer migration SQL V067__add_waiting_status_to_execution_steps.sql
  - [x] 1.4: Ajouter WAITING à la contrainte CHECK STATUS IN ('PENDING', 'WAITING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED')
  - [x] 1.5: Vérifier que le statut WAITING s'affiche correctement dans l'admin Django (test manuel)

- [x] Task 2: Définir et documenter le schéma JSON gate_conditions (AC: 2, 6)
  - [x] 2.1: Créer docs/backend/condition-gates.md avec description complète du pattern
  - [x] 2.2: Documenter la structure JSON gate_conditions avec exemples pour chaque type
  - [x] 2.3: Documenter le cycle de vie PENDING → WAITING → RUNNING → COMPLETED/FAILED
  - [x] 2.4: Ajouter des exemples de gate_conditions dans la documentation (maintenance_window, time_window, approval_granted, target_state)
  - [x] 2.5: Documenter les champs optionnels timeout_hours et on_timeout (FAIL | SKIP)

- [x] Task 3: Implémenter la validation gate_conditions dans le catalogue (AC: 5)
  - [x] 3.1: Créer catalog/validators.py::validate_gate_conditions(gate_conditions: list) → ValidationResult
  - [x] 3.2: Vérifier que gate_conditions est une liste (tableau JSON)
  - [x] 3.3: Pour chaque condition, vérifier que le champ `type` est présent et valide (maintenance_window | time_window | approval_granted | target_state)
  - [x] 3.4: Si timeout_hours est présent, vérifier que c'est un nombre > 0
  - [x] 3.5: Si on_timeout est présent, vérifier que c'est "FAIL" ou "SKIP"
  - [x] 3.6: Intégrer validate_gate_conditions() dans catalog/services.py::CatalogService.update_execution_steps()
  - [x] 3.7: Tester la validation avec des gate_conditions valides et invalides

- [x] Task 4: Modifier WorkflowRuntime pour créer ExecutionStep en WAITING (AC: 3)
  - [x] 4.1: Dans executions/workflow_runtime.py::WorkflowRuntime._execute_step(), lire gate_conditions depuis step_def
  - [x] 4.2: Si gate_conditions est présent et non vide, créer ExecutionStep avec status='WAITING'
  - [x] 4.3: Peupler le champ output avec le contexte d'attente initial (waiting_since, gate_conditions, gate_status)
  - [x] 4.4: NE PAS appeler execute_step.delay() (pas d'exécution immédiate)
  - [x] 4.5: Retourner un indicateur "WAITING" au workflow_runtime pour qu'il n'avance pas automatiquement
  - [x] 4.6: Vérifier que l'exécution du workflow s'arrête à l'étape WAITING (pas de progression vers l'étape suivante)

- [x] Task 5: Implémenter le contexte d'attente dans ExecutionStep.output (AC: 4)
  - [x] 5.1: Créer executions/gate_context.py avec fonction build_waiting_context(step, gate_conditions) → dict
  - [x] 5.2: Retourner un dictionnaire contenant : waiting_since, gate_conditions, gate_status (par défaut : {type: condition.type, satisfied: false, reason: "En attente d'évaluation"})
  - [x] 5.3: Utiliser build_waiting_context() dans WorkflowRuntime lors de la création de l'ExecutionStep WAITING
  - [x] 5.4: Vérifier que le contexte JSON est correctement sérialisé dans ExecutionStep.output
  - [x] 5.5: Tester la récupération du contexte via ExecutionStep.get_output()

- [x] Task 6: Ajouter tests unitaires pour le statut WAITING (AC: 1, 3, 4)
  - [x] 6.1: Test modèle : ExecutionStep peut être créé avec status='WAITING'
  - [x] 6.2: Test validation : gate_conditions valide (maintenance_window avec timeout_hours=48) passe la validation
  - [x] 6.3: Test validation : gate_conditions invalide (type inconnu "unknown") échoue avec erreur 400
  - [x] 6.4: Test WorkflowRuntime : si gate_conditions présent, l'ExecutionStep est créé en WAITING (pas en RUNNING)
  - [x] 6.5: Test WorkflowRuntime : si gate_conditions absent, l'ExecutionStep est créé en RUNNING (comportement actuel)
  - [x] 6.6: Test contexte : vérifier que output contient waiting_since, gate_conditions, gate_status
  - [x] 6.7: Test workflow : vérifier que le workflow ne progresse pas automatiquement quand une étape est en WAITING

- [x] Task 7: Ajouter tests d'intégration pour le flow complet (AC: 2, 3, 4)
  - [x] 7.1: Test intégration : créer une action avec gate_conditions maintenance_window
  - [x] 7.2: Exécuter l'action et vérifier que l'ExecutionStep est créé en WAITING
  - [x] 7.3: Vérifier que le champ output contient le contexte d'attente
  - [x] 7.4: Vérifier que l'exécution reste en status RUNNING mais que l'étape reste en WAITING
  - [x] 7.5: Vérifier que l'API GET /api/v1/executions/{id}/ retourne le statut WAITING pour l'étape

## Dev Notes

### Architecture Context - Epic 25 Convergence DBOps

Cette story implémente le **cœur** de la convergence DBOps → IDP Portal (Réf: `_bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md#1-condition-gates-sur-les-etapes-dexecution`).

**Pourquoi cette story après 25.1 ?**
- Story 25.1 a créé le modèle `ExecutionTarget` qui lie une exécution à ses cibles (serveurs, bases)
- Les condition gates `maintenance_window` nécessitent de connaître les serveurs cibles pour interroger l'inventaire
- Cette story pose les **fondations** du statut WAITING et de la structure gate_conditions
- **Story 25.3** implémentera la tâche Celery Beat qui évaluera périodiquement les gates et débloquera les étapes WAITING

**Ordre d'implémentation de l'Epic 25 :**
```
1. ExecutionTarget (Story 25.1) ✅ DONE
2. Condition Gates + statut WAITING (CETTE STORY) ← Fondation (schéma + statut)
3. Tâche Celery Beat evaluate_waiting_gates (Story 25.3) ← Évaluation et déblocage
4. Overrides par environnement (Story 25.4)
5. Mutex inter-actions (Story 25.5) — dépend de ExecutionTarget
6. Deny explicite RBAC (Story 25.6)
```

**Scope de cette story :**
- ✅ Ajouter le statut WAITING à ExecutionStepStatus
- ✅ Définir le schéma JSON gate_conditions
- ✅ Valider gate_conditions dans le catalogue
- ✅ Modifier WorkflowRuntime pour créer ExecutionStep en WAITING
- ✅ Stocker le contexte d'attente dans ExecutionStep.output
- ❌ **HORS SCOPE** : L'évaluation périodique des gates (Story 25.3)
- ❌ **HORS SCOPE** : La transition WAITING → RUNNING (Story 25.3)
- ❌ **HORS SCOPE** : L'implémentation des evaluators (maintenance_window, time_window, etc.) — Story 25.3

### Existing Models and Patterns to Follow

**1. Current ExecutionStep Model** (`executions/models.py`):
```python
class ExecutionStepStatus(models.TextChoices):
    """Execution step status enum matching Oracle CHECK constraint."""
    PENDING = 'PENDING', 'Pending'
    RUNNING = 'RUNNING', 'Running'
    COMPLETED = 'COMPLETED', 'Completed'
    FAILED = 'FAILED', 'Failed'
    SKIPPED = 'SKIPPED', 'Skipped'
    # AJOUTER ICI :
    # WAITING = 'WAITING', 'Waiting'
```

**2. Pattern JSON Helper Methods** (déjà utilisé sur ExecutionStep) :
```python
class ExecutionStep(models.Model):
    output = models.TextField(null=True, blank=True, db_column='OUTPUT')

    def get_output(self) -> dict | None:
        """Deserialize JSON from CLOB."""
        if self.output:
            try:
                return json.loads(self.output)
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to deserialize output for ExecutionStep {self.id}: {e}")
                return None
        return None

    def set_output(self, value: dict | None):
        """Serialize JSON to CLOB."""
        if value is not None:
            self.output = json.dumps(value)
        else:
            self.output = None
```

**3. Migration Pattern** (depuis V066 et autres migrations récentes) :
```sql
-- V067__add_waiting_status_to_execution_steps.sql
ALTER TABLE EXECUTION_STEPS DROP CONSTRAINT CK_EXECUTION_STEPS_STATUS;

ALTER TABLE EXECUTION_STEPS ADD CONSTRAINT CK_EXECUTION_STEPS_STATUS
CHECK (STATUS IN ('PENDING', 'WAITING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED'));

COMMENT ON COLUMN EXECUTION_STEPS.STATUS IS
'Step status: PENDING (queued), WAITING (gate conditions not met), RUNNING (in progress), COMPLETED (success), FAILED (error), SKIPPED (skipped due to condition)';
```

**4. Action execution_steps JSON Schema** (depuis Story 16.2 et suivantes) :
- Le champ `execution_steps` d'une Action est un CLOB JSON contenant un tableau d'objets step
- Chaque step a déjà des attributs : `order`, `step_id`, `name`, `type`, `referenced_action_id`, `on_success_step_id`, `on_error_step_id`, etc.
- **À AJOUTER** : `gate_conditions` (tableau de conditions), optionnel

**5. WorkflowRuntime Context** (`executions/workflow_runtime.py`) :
- Depuis Story 16.3, le WorkflowRuntime lit execution_steps depuis Action et exécute séquentiellement
- Chaque étape est exécutée via `_execute_step(step_def)`
- Si gate_conditions est présent, on crée ExecutionStep en WAITING et on s'arrête (pas d'exécution immédiate)

### Gate Conditions JSON Schema

**Structure d'une condition gate :**
```json
{
  "type": "maintenance_window | time_window | approval_granted | target_state",
  "description": "Description lisible (optionnel)",
  "timeout_hours": 48,           // Optionnel : délai max avant timeout
  "on_timeout": "FAIL | SKIP"    // Optionnel : comportement si timeout
}
```

**Exemples de gate_conditions :**

**1. Maintenance Window Gate :**
```json
{
  "type": "maintenance_window",
  "description": "Attendre la plage de maintenance des serveurs cibles",
  "timeout_hours": 72,
  "on_timeout": "FAIL"
}
```
- **Évaluation (Story 25.3)** : Interroger l'inventaire via `InventoryService.get_next_maintenance_window(target_id)` pour chaque ExecutionTarget
- Si au moins un serveur cible n'est pas dans sa plage de maintenance, condition = NOT SATISFIED
- Le contexte retourné inclut `next_possible_at` (prochaine fenêtre commune)

**2. Time Window Gate :**
```json
{
  "type": "time_window",
  "after": "22:00",
  "before": "06:00",
  "timezone": "America/Toronto",
  "description": "Exécuter uniquement entre 22h et 6h (heure de Toronto)",
  "timeout_hours": 24,
  "on_timeout": "SKIP"
}
```
- **Évaluation (Story 25.3)** : Vérifier que l'heure actuelle (dans le timezone spécifié) est entre `after` et `before`

**3. Approval Granted Gate :**
```json
{
  "type": "approval_granted",
  "description": "Attendre l'approbation manuelle d'un DBA",
  "timeout_hours": 48,
  "on_timeout": "FAIL"
}
```
- **Évaluation (Story 25.3)** : Vérifier que Execution.status == 'RUNNING' (approuvé) et non 'PENDING_APPROVAL'
- Ou vérifier un champ dédié sur ExecutionStep (à définir dans Story 25.3)

**4. Target State Gate :**
```json
{
  "type": "target_state",
  "required_state": "MAINTENANCE",
  "description": "Attendre que le serveur cible soit en mode maintenance",
  "timeout_hours": 12,
  "on_timeout": "SKIP"
}
```
- **Évaluation (Story 25.3)** : Interroger l'inventaire pour vérifier l'état du serveur cible

**Exemple complet execution_steps avec gate_conditions :**
```json
{
  "execution_steps": [
    {
      "order": 1,
      "step_id": "prepare",
      "name": "Préparer le déploiement",
      "type": "platform",
      "referenced_action_id": 12
    },
    {
      "order": 2,
      "step_id": "deploy",
      "name": "Déployer le patch Oracle",
      "type": "platform",
      "referenced_action_id": 15,
      "gate_conditions": [
        {
          "type": "maintenance_window",
          "description": "Attendre la plage de maintenance",
          "timeout_hours": 72,
          "on_timeout": "FAIL"
        }
      ],
      "on_success_step_id": "verify"
    },
    {
      "order": 3,
      "step_id": "verify",
      "name": "Vérification post-déploiement",
      "type": "verification",
      "referenced_action_id": 18
    }
  ]
}
```

### Validation gate_conditions

**Location** : `catalog/validators.py::validate_gate_conditions(gate_conditions: list) → None`

**Règles de validation :**
1. `gate_conditions` doit être une liste (peut être vide → pas de gate)
2. Chaque condition DOIT avoir un champ `type` (str) avec valeur dans : `["maintenance_window", "time_window", "approval_granted", "target_state"]`
3. Si `timeout_hours` est présent, DOIT être un nombre > 0
4. Si `on_timeout` est présent, DOIT être "FAIL" ou "SKIP"
5. Les champs spécifiques par type (ex: `after`, `before` pour time_window) sont validés dans Story 25.3 (evaluators)

**Intégration dans ActionSerializer :**
```python
# catalog/serializers.py
class ActionSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        # Validation existante (parameters_schema, etc.)
        ...

        # Validation gate_conditions
        execution_steps = attrs.get('execution_steps')
        if execution_steps:
            steps_data = json.loads(execution_steps) if isinstance(execution_steps, str) else execution_steps
            for step in steps_data.get('execution_steps', []):
                if 'gate_conditions' in step:
                    validate_gate_conditions(step['gate_conditions'])

        return attrs
```

**Erreur retournée si validation échoue :**
```json
{
  "error": {
    "code": "INVALID_GATE_CONDITIONS",
    "message": "Invalid gate_conditions in execution_steps",
    "details": {
      "step_order": 2,
      "step_id": "deploy",
      "errors": [
        "Gate condition at index 0: 'type' field is required",
        "Gate condition at index 1: 'type' must be one of: maintenance_window, time_window, approval_granted, target_state",
        "Gate condition at index 2: 'timeout_hours' must be a positive number"
      ]
    }
  }
}
```

### WorkflowRuntime Modifications

**Fichier** : `executions/workflow_runtime.py::WorkflowRuntime._execute_step()`

**Logic actuelle (simplified) :**
```python
def _execute_step(self, step_def: dict):
    """Execute a single workflow step."""
    # Créer ExecutionStep en PENDING
    exec_step = ExecutionStep.objects.create(
        execution=self.execution,
        step_order=step_def['order'],
        step_name=step_def['name'],
        step_type=step_def.get('type', 'platform'),
        status='PENDING',
    )

    # Exécuter immédiatement
    execute_step.delay(exec_step.id)

    return exec_step
```

**Logic modifiée (avec gate_conditions) :**
```python
def _execute_step(self, step_def: dict):
    """Execute a single workflow step, or put it in WAITING if gate_conditions present."""
    gate_conditions = step_def.get('gate_conditions', [])

    if gate_conditions:
        # Créer ExecutionStep en WAITING (pas d'exécution immédiate)
        exec_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_def['order'],
            step_name=step_def['name'],
            step_type=step_def.get('type', 'platform'),
            status='WAITING',  # ← NOUVEAU STATUT
        )

        # Peupler le contexte d'attente
        waiting_context = build_waiting_context(exec_step, gate_conditions)
        exec_step.set_output(waiting_context)
        exec_step.save()

        # NE PAS exécuter immédiatement
        # La tâche Celery Beat (Story 25.3) évaluera les gates et débloquera l'étape
        logger.info(
            f"ExecutionStep {exec_step.id} created in WAITING status - gate_conditions present",
            extra={'correlation_id': self.execution.correlation_id, 'step_id': step_def.get('step_id')}
        )

        return 'WAITING'  # Signal au workflow_runtime de ne pas progresser
    else:
        # Comportement actuel (pas de gate_conditions)
        exec_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_def['order'],
            step_name=step_def['name'],
            step_type=step_def.get('type', 'platform'),
            status='PENDING',
        )
        execute_step.delay(exec_step.id)
        return exec_step
```

**Fonction build_waiting_context** (nouvelle) :
```python
# executions/gate_context.py
from datetime import datetime
from django.utils import timezone

def build_waiting_context(exec_step, gate_conditions: list) -> dict:
    """
    Build the initial waiting context for an ExecutionStep in WAITING status.

    Args:
        exec_step: ExecutionStep instance
        gate_conditions: List of gate conditions from step definition

    Returns:
        dict: Waiting context to be stored in ExecutionStep.output
    """
    gate_status = []
    for condition in gate_conditions:
        gate_status.append({
            'type': condition['type'],
            'satisfied': False,
            'reason': 'En attente d\'évaluation',
            'next_evaluation_at': None,  # Sera mis à jour par GateEvaluator (Story 25.3)
        })

    return {
        'waiting_since': exec_step.created_at.isoformat() if exec_step.created_at else timezone.now().isoformat(),
        'gate_conditions': gate_conditions,  # Copie des conditions pour référence
        'gate_status': gate_status,
    }
```

### Testing Strategy

**Nouveaux tests à créer :**

**1. Test modèle (`executions/tests/test_models.py`) :**
```python
def test_execution_step_waiting_status():
    """ExecutionStep can be created with WAITING status."""
    execution = ExecutionFactory()
    step = ExecutionStep.objects.create(
        execution=execution,
        step_order=1,
        step_name="Deploy patch",
        step_type='platform',
        status='WAITING',
    )
    assert step.status == 'WAITING'
```

**2. Test validation (`catalog/tests/test_validators.py`) :**
```python
def test_validate_gate_conditions_valid():
    """Valid gate_conditions pass validation."""
    gate_conditions = [
        {
            'type': 'maintenance_window',
            'timeout_hours': 48,
            'on_timeout': 'FAIL'
        }
    ]
    validate_gate_conditions(gate_conditions)  # Should not raise

def test_validate_gate_conditions_invalid_type():
    """Invalid gate type raises ValidationError."""
    gate_conditions = [
        {
            'type': 'unknown_type',
        }
    ]
    with pytest.raises(ValidationError, match="type must be one of"):
        validate_gate_conditions(gate_conditions)
```

**3. Test WorkflowRuntime (`executions/tests/test_workflow_runtime_gates.py`) :**
```python
def test_workflow_runtime_creates_step_in_waiting_if_gate_conditions():
    """If step has gate_conditions, ExecutionStep is created in WAITING (not RUNNING)."""
    action = ActionFactory(execution_steps={
        'execution_steps': [
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy patch',
                'type': 'platform',
                'referenced_action_id': 15,
                'gate_conditions': [
                    {'type': 'maintenance_window', 'timeout_hours': 48}
                ]
            }
        ]
    })
    execution = ExecutionFactory(action=action)

    runtime = WorkflowRuntime(execution)
    runtime._execute_step(action.get_execution_steps()['execution_steps'][0])

    step = ExecutionStep.objects.get(execution=execution, step_order=1)
    assert step.status == 'WAITING'
    assert step.get_output()['waiting_since'] is not None
    assert step.get_output()['gate_conditions'] is not None

def test_workflow_runtime_executes_step_immediately_if_no_gate_conditions():
    """If step has NO gate_conditions, ExecutionStep is created in PENDING (current behavior)."""
    action = ActionFactory(execution_steps={
        'execution_steps': [
            {
                'order': 1,
                'step_id': 'deploy',
                'name': 'Deploy patch',
                'type': 'platform',
                'referenced_action_id': 15,
                # NO gate_conditions
            }
        ]
    })
    execution = ExecutionFactory(action=action)

    runtime = WorkflowRuntime(execution)
    runtime._execute_step(action.get_execution_steps()['execution_steps'][0])

    step = ExecutionStep.objects.get(execution=execution, step_order=1)
    assert step.status == 'PENDING'  # Comportement actuel (ou RUNNING selon implémentation)
```

**4. Test API intégration (`executions/tests/test_execution_api_gates.py`) :**
```python
@pytest.mark.django_db
def test_create_execution_with_gate_conditions_creates_waiting_step(api_client, user):
    """
    Integration test: creating an execution for an action with gate_conditions
    creates an ExecutionStep in WAITING status.
    """
    action = ActionFactory(
        requires_target=True,
        execution_steps={
            'execution_steps': [
                {
                    'order': 1,
                    'step_id': 'deploy',
                    'name': 'Deploy patch',
                    'type': 'platform',
                    'referenced_action_id': 15,
                    'gate_conditions': [
                        {
                            'type': 'maintenance_window',
                            'description': 'Wait for maintenance window',
                            'timeout_hours': 72,
                            'on_timeout': 'FAIL'
                        }
                    ]
                }
            ]
        }
    )

    # Create execution
    response = api_client.post('/api/v1/executions/', {
        'action_id': action.id,
        'environment': 'dev',
        'parameters': {},
        'target_names': ['SERVER1']
    })
    assert response.status_code == 201

    execution_id = response.data['id']

    # Verify ExecutionStep is in WAITING
    step = ExecutionStep.objects.get(execution_id=execution_id, step_order=1)
    assert step.status == 'WAITING'

    # Verify output context
    output = step.get_output()
    assert output['waiting_since'] is not None
    assert output['gate_conditions'][0]['type'] == 'maintenance_window'
    assert output['gate_status'][0]['satisfied'] is False
```

### Database Schema Changes

**Migration SQL V067** :
```sql
-- V067__add_waiting_status_to_execution_steps.sql

-- Drop existing CHECK constraint on STATUS
ALTER TABLE EXECUTION_STEPS DROP CONSTRAINT CK_EXECUTION_STEPS_STATUS;

-- Add new CHECK constraint with WAITING status
ALTER TABLE EXECUTION_STEPS ADD CONSTRAINT CK_EXECUTION_STEPS_STATUS
CHECK (STATUS IN ('PENDING', 'WAITING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED'));

-- Update comment on STATUS column
COMMENT ON COLUMN EXECUTION_STEPS.STATUS IS
'Step status: PENDING (queued), WAITING (gate conditions not met), RUNNING (in progress), COMPLETED (success), FAILED (error), SKIPPED (skipped due to condition)';
```

**Migration Django** :
```python
# executions/migrations/0006_add_waiting_status.py
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('executions', '0005_add_execution_target'),
    ]

    operations = [
        migrations.AlterField(
            model_name='executionstep',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('WAITING', 'Waiting'),
                    ('RUNNING', 'Running'),
                    ('COMPLETED', 'Completed'),
                    ('FAILED', 'Failed'),
                    ('SKIPPED', 'Skipped')
                ],
                db_column='STATUS',
                default='PENDING',
                max_length=20
            ),
        ),
    ]
```

### Security & Performance Considerations

**Security :**
- Les gate_conditions sont stockées dans le JSON execution_steps de l'Action (CLOB)
- Validation côté backend OBLIGATOIRE pour éviter injection de types de conditions non supportés
- Le contexte d'attente (ExecutionStep.output) ne doit PAS contenir de secrets (uniquement des métadonnées publiques)

**Performance :**
- Le statut WAITING ne bloque PAS le backend — l'ExecutionStep est simplement en attente passive
- La tâche Celery Beat (Story 25.3) évaluera périodiquement les gates (ex: toutes les 60 secondes)
- L'impact performance est négligeable : quelques requêtes SQL périodiques pour sélectionner les ExecutionStep en WAITING

**Timeout et sécurité :**
- Chaque condition peut avoir un `timeout_hours` (optionnel)
- Si le timeout expire, l'étape passe en FAILED (ou SKIPPED selon `on_timeout`)
- Le timeout est géré par la tâche Celery Beat (Story 25.3) — PAS implémenté dans cette story

### References

**Architecture :**
- [Source: _bmad-output/implementation-artifacts/convergence-dbops-idp-portal.md#1-condition-gates-sur-les-etapes-dexecution]
- [Source: _bmad-output/planning-artifacts/architecture.md#api--communication-patterns]

**Code Patterns :**
- Modèle ExecutionStep : `executions/models.py::ExecutionStep`
- Pattern JSON helpers : `ExecutionStep.get_output()` / `ExecutionStep.set_output()`
- Migration SQL : `database/migrations/V066__create_execution_targets.sql` (pattern similar)
- WorkflowRuntime : `executions/workflow_runtime.py::WorkflowRuntime._execute_step()`

**Related Stories :**
- Story 25.1 : ExecutionTarget (fondation - cibles explicites) ✅ DONE
- Story 25.3 : Tâche Celery Beat evaluate_waiting_gates (évaluation et déblocage) ← À VENIR
- Story 16.3 : Moteur execution branches conditionnelles (branching workflow)
- Story 16.4 : Moteur retry backoff exponentiel (pattern similaire : étapes en attente)

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- 29/29 unit tests pass (test_condition_gates.py)
- 7/7 integration tests pass (test_condition_gates_integration.py)
- 19/19 existing workflow runtime tests pass (no regression)
- 131/134 broader execution tests pass (3 pre-existing failures unrelated to changes)

### Completion Notes List

- AC1: WAITING status added to ExecutionStepStatus enum, Django migration 0006, SQL migration V067
- AC2: gate_conditions JSON schema documented in docs/backend/condition-gates.md with all 4 types
- AC3: WorkflowRuntime._execute_step() creates WAITING step when gate_conditions present; workflow stays RUNNING
- AC4: build_waiting_context() stores waiting_since, gate_conditions, gate_status in ExecutionStep.output
- AC5: validate_gate_conditions() in catalog/validators.py validates type, timeout_hours, on_timeout; integrated in CatalogService.update_execution_steps()
- AC6: Full documentation in docs/backend/condition-gates.md (concept, JSON schema, types, lifecycle, examples, limitations)
- Added StepOutcome.WAITING and StepResult.is_waiting property for clean workflow control flow
- Note: 3.6 integrated in catalog/services.py instead of serializers.py (better architectural fit — service layer handles business validation)

### Change Log

- 2026-02-10: Story 25.2 implemented — condition gates with WAITING status, gate_conditions validation, WorkflowRuntime integration, documentation, 36 tests (29 unit + 7 integration)

### File List

- idp-portal/django_backend/executions/models.py (modified — WAITING status added to ExecutionStepStatus)
- idp-portal/django_backend/executions/migrations/0006_add_waiting_status.py (new — Django migration)
- idp-portal/database/migrations/V067__add_waiting_status_to_execution_steps.sql (new — SQL migration)
- idp-portal/django_backend/executions/gate_context.py (new — build_waiting_context function)
- idp-portal/django_backend/executions/workflow_runtime.py (modified — WAITING outcome, gate_conditions handling in _execute_step, workflow pause in run())
- idp-portal/django_backend/catalog/validators.py (new — validate_gate_conditions function)
- idp-portal/django_backend/catalog/services.py (modified — gate_conditions validation in update_execution_steps)
- idp-portal/docs/backend/condition-gates.md (new — documentation)
- idp-portal/django_backend/executions/tests/test_condition_gates.py (new — 29 unit tests)
- idp-portal/django_backend/executions/tests/test_condition_gates_integration.py (new — 7 integration tests)

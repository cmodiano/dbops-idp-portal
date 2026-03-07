# Condition Gates — Préconditions sur les étapes d'exécution

## Historique d'implémentation

### Story 25.2 — Fondation (statut WAITING + schéma gate_conditions)

✅ Statut WAITING ajouté à ExecutionStepStatus (modèle + migrations Django + SQL)
✅ Schéma JSON gate_conditions documenté et validé côté backend
✅ WorkflowRuntime crée ExecutionStep en WAITING si gate_conditions présent
✅ Contexte d'attente stocké dans ExecutionStep.output
✅ Tests unitaires (29) et d'intégration (7)

### Story 25.3 — Évaluation périodique et déblocage

✅ Tâche Celery Beat `evaluate_waiting_gates` (toutes les 60s, configurable)
✅ Service GateEvaluator avec dispatch par type de condition
✅ Évaluateur `maintenance_window` via InventoryService
✅ Gestion timeout_hours + on_timeout (FAIL/SKIP)
✅ Transition WAITING → RUNNING + déclenchement exécution réelle
✅ Audit trail (EXECUTION_STEP_GATE_SATISFIED, EXECUTION_STEP_GATE_TIMEOUT)
✅ Tests unitaires (13) et d'intégration (8)

### Hors scope (stories futures)

❌ Évaluateurs time_window, approval_granted, target_state (Story 25.3b ou 25.4)
❌ Notification WebSocket frontend WAITING → RUNNING
❌ UI contexte d'attente (next_possible_at, reason)

---

## Concept

Les **condition gates** (portes conditionnelles) permettent de définir des préconditions sur une étape d'exécution d'un workflow. Une étape avec des gate_conditions ne démarre pas immédiatement : elle est créée avec le statut **WAITING** et attend que toutes ses conditions soient satisfaites avant de passer en exécution.

### Cas d'usage

- **Plage de maintenance** : ne déployer que pendant la fenêtre de maintenance des serveurs cibles
- **Créneau horaire** : exécuter uniquement entre 22h et 6h (hors heures ouvrables)
- **Approbation** : attendre qu'un DBA approuve manuellement l'étape
- **État cible** : attendre que le serveur soit en mode maintenance

## Structure JSON des gate_conditions

Les `gate_conditions` sont un attribut optionnel d'une étape dans le champ `execution_steps` (JSON CLOB) d'une Action.

### Schéma d'une condition

```json
{
  "type": "maintenance_window | time_window | approval_granted | target_state",
  "description": "Description lisible (optionnel)",
  "timeout_hours": 48,
  "on_timeout": "FAIL | SKIP"
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `type` | string | **Oui** | Type de condition : `maintenance_window`, `time_window`, `approval_granted`, `target_state` |
| `description` | string | Non | Description lisible pour l'utilisateur |
| `timeout_hours` | number | Non | Délai maximum d'attente en heures (doit être > 0) |
| `on_timeout` | string | Non | Comportement si timeout : `FAIL` (échouer) ou `SKIP` (ignorer l'étape) |

## Types de conditions supportés

### 1. maintenance_window

Attend la plage de maintenance des serveurs cibles (via l'inventaire).

```json
{
  "type": "maintenance_window",
  "description": "Attendre la plage de maintenance des serveurs cibles",
  "timeout_hours": 72,
  "on_timeout": "FAIL"
}
```

**Évaluation** : interroge l'inventaire via `InventoryService.get_next_maintenance_window(target_id)` pour chaque `ExecutionTarget`. Si au moins un serveur n'est pas dans sa plage, condition = NON SATISFAITE. Le contexte retourné inclut `next_possible_at`.

### 2. time_window

Attend un créneau horaire spécifique.

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

**Évaluation** : vérifie que l'heure actuelle (dans le timezone spécifié) est entre `after` et `before`.

### 3. approval_granted

Attend une approbation manuelle.

```json
{
  "type": "approval_granted",
  "description": "Attendre l'approbation manuelle d'un DBA",
  "timeout_hours": 48,
  "on_timeout": "FAIL"
}
```

**Évaluation** : vérifie qu'une approbation a été accordée pour cette étape d'exécution.

### 4. target_state

Attend qu'une cible soit dans un état donné.

```json
{
  "type": "target_state",
  "required_state": "MAINTENANCE",
  "description": "Attendre que le serveur cible soit en mode maintenance",
  "timeout_hours": 12,
  "on_timeout": "SKIP"
}
```

**Évaluation** : interroge l'inventaire pour vérifier l'état de la cible.

## Cycle de vie d'une étape WAITING

```
PENDING → WAITING → RUNNING → COMPLETED/FAILED
                  ↘ (timeout) → FAILED/SKIPPED
```

1. **Création** : le WorkflowRuntime détecte `gate_conditions` dans la définition de l'étape
2. **WAITING** : l'ExecutionStep est créé avec `status='WAITING'` et un contexte d'attente dans `output`
3. **Évaluation périodique** : la tâche Celery Beat `evaluate_waiting_gates` vérifie les conditions
4. **Déblocage** : quand toutes les conditions sont satisfaites, l'étape passe en RUNNING
5. **Timeout** : si `timeout_hours` expire, l'étape passe en FAILED ou SKIPPED selon `on_timeout`

### Contexte d'attente (ExecutionStep.output)

Quand une étape est en WAITING, son champ `output` contient :

```json
{
  "waiting_since": "2026-02-10T15:30:00Z",
  "gate_conditions": [
    {
      "type": "maintenance_window",
      "timeout_hours": 72,
      "on_timeout": "FAIL"
    }
  ],
  "gate_status": [
    {
      "type": "maintenance_window",
      "satisfied": false,
      "reason": "En attente d'évaluation",
      "next_evaluation_at": null
    }
  ]
}
```

## Exemple complet

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

Dans cet exemple, l'étape 2 (deploy) attend la plage de maintenance avant de s'exécuter. L'étape 1 s'exécute normalement, puis le workflow s'arrête à l'étape 2 en WAITING.

## Validation

La validation des `gate_conditions` est effectuée côté backend lors de la création ou modification d'une action :

- `gate_conditions` doit être un tableau JSON (peut être vide)
- Chaque condition doit avoir un champ `type` valide
- Si `timeout_hours` est présent, il doit être un nombre > 0
- Si `on_timeout` est présent, il doit être `FAIL` ou `SKIP`

Les champs spécifiques par type (ex: `after`, `before` pour `time_window`) sont validés par les evaluators correspondants.

## Limitations

- **Pas d'évaluation synchrone** : les gates sont évaluées périodiquement par une tâche Celery Beat, pas en temps réel
- **Types limités** : seuls 4 types de conditions sont supportés dans cette version
- **Pas de conditions composées** : toutes les conditions doivent être satisfaites (ET logique), pas de OU
- **Champs spécifiques non validés** : les champs propres à chaque type (ex: `after`, `timezone`) sont validés uniquement lors de l'évaluation

## Évaluation périodique des gates (Story 25.3)

### Tâche Celery Beat `evaluate_waiting_gates`

La tâche `evaluate_waiting_gates` est exécutée périodiquement par Celery Beat pour évaluer les étapes en WAITING et les débloquer lorsque les conditions sont satisfaites.

**Configuration** (`idp_backend/celery.py`) :

```python
app.conf.beat_schedule = {
    'evaluate-waiting-gates': {
        'task': 'executions.tasks.evaluate_waiting_gates',
        'schedule': float(os.getenv('CELERY_BEAT_EVALUATE_GATES_INTERVAL', '60.0')),
    },
}
```

**Variable d'environnement** : `CELERY_BEAT_EVALUATE_GATES_INTERVAL` (défaut: 60 secondes)

**Démarrage** :

```bash
# Worker Celery
celery -A idp_backend worker --loglevel=info

# Celery Beat (scheduler)
celery -A idp_backend beat --loglevel=info
```

### Flux d'évaluation

```
Celery Beat (60s) → evaluate_waiting_gates
  ↓
Sélection ExecutionStep WHERE status='WAITING' AND execution.status='RUNNING'
  ↓ (pour chaque étape)
GateEvaluator.evaluate(step)
  ├── Vérifier timeout_hours → si dépassé → FAILED/SKIPPED + audit
  ├── _check_maintenance_window(step) → InventoryService
  ├── _check_time_window(step) → (futur)
  └── _check_approval_granted(step) → (futur)
  ↓
Si TOUTES conditions satisfaites:
  step.status = RUNNING, started_at = now()
  retry_workflow_step.apply_async() → exécution réelle
  Audit: EXECUTION_STEP_GATE_SATISFIED
  ↓
Si conditions NON satisfaites:
  Mise à jour output avec gate_status, last_evaluated_at
  Log: evaluate_waiting_gates_step_still_waiting
```

### GateEvaluator

Service dans `executions/gate_evaluator.py` :

```python
class GateEvaluator:
    def evaluate(self, step) -> tuple[bool, dict]:
        """Évalue toutes les gate_conditions d'un step WAITING."""
    def _check_maintenance_window(self, step, condition) -> tuple[bool, dict]:
        """Vérifie que TOUTES les cibles sont dans leur fenêtre de maintenance."""
    def _check_timeout(self, step, condition) -> tuple[bool, str | None]:
        """Vérifie si le timeout_hours est dépassé."""
```

### Exemples de gate_status retournés

**Conditions satisfaites** :

```json
{
  "gates": [
    {
      "type": "maintenance_window",
      "satisfied": true,
      "reason": "All targets in maintenance window",
      "details": [
        {"target_id": "SRV-01", "is_active": true, "reason": "Within maintenance window"}
      ]
    }
  ],
  "timeout_triggered": false
}
```

**Conditions non satisfaites** :

```json
{
  "gates": [
    {
      "type": "maintenance_window",
      "satisfied": false,
      "reason": "One or more targets outside maintenance window",
      "next_possible_at": "2026-02-11T22:00:00Z",
      "details": [
        {"target_id": "SRV-01", "is_active": false, "next_start": "2026-02-11T22:00:00Z"}
      ]
    }
  ],
  "timeout_triggered": false
}
```

**Timeout déclenché** :

```json
{
  "gates": [],
  "timeout_triggered": true,
  "action": "FAILED",
  "timeout_hours": 48
}
```

### Logs structlog émis

| Événement | Niveau | Description |
|-----------|--------|-------------|
| `evaluate_waiting_gates_start` | INFO | Début d'évaluation, nombre d'étapes WAITING |
| `evaluate_waiting_gates_step_satisfied` | INFO | Étape débloquée (toutes conditions satisfaites) |
| `evaluate_waiting_gates_step_still_waiting` | INFO | Étape toujours en attente |
| `evaluate_waiting_gates_step_timeout` | INFO | Timeout déclenché |
| `evaluate_waiting_gates_error` | ERROR | Erreur d'évaluation sur une étape |
| `evaluate_waiting_gates_complete` | INFO | Fin d'évaluation, résumé |
| `evaluate_waiting_gates_step_execution_triggered` | INFO | Exécution réelle déclenchée via retry_workflow_step |

### Audit Trail

| Action Type | Description |
|-------------|-------------|
| `EXECUTION_STEP_GATE_SATISFIED` | Gate conditions satisfaites, étape passe WAITING → RUNNING |
| `EXECUTION_STEP_GATE_TIMEOUT` | Timeout gate expiré, étape passe en FAILED/SKIPPED |

## Références

- Story 25.1 : ExecutionTarget (fondation cibles explicites)
- Story 25.2 : Condition Gates (statut WAITING + schéma gate_conditions)
- Story 25.3 : Tâche Celery Beat evaluate_waiting_gates (évaluation et déblocage)

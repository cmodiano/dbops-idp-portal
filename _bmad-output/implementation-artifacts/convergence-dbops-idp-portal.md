# Convergence DBOps → IDP Portal : Intégration des forces

## Contexte

IDP Portal est notre plateforme cible. DBOps, conçu avec un background DBA, apporte des patterns d'orchestration enterprise que le portail ne couvre pas encore. Ce document décrit les fonctionnalités à intégrer et leurs implications.

---

## 1. Condition Gates sur les étapes d'exécution

### Problème actuel

Aujourd'hui, les `execution_steps` d'une action sont exécutées séquentiellement (ou via branching) sans aucune notion de **précondition**. Une étape démarre dès que la précédente est terminée.

Or, certaines opérations DBA nécessitent des conditions spécifiques :
- Être dans une **plage de maintenance** du serveur cible
- Qu'un **ticket ServiceNow** soit approuvé
- Que le serveur soit dans un **état spécifique** (standby, arrêté, etc.)

> **Note** : la dépendance séquentielle entre étapes (« l'étape B attend que A soit terminée ») est déjà gérée par le workflow runtime via le branching (`on_success_step_id`). Les condition gates couvrent les **préconditions externes** au workflow.

### Solution : le pattern "Condition Gate"

Ajouter un concept de **gate** (porte conditionnelle) sur chaque étape d'exécution. Une gate bloque l'étape tant que ses conditions ne sont pas remplies.

#### Modèle conceptuel

```
ExecutionStep existant
├── step_order, step_name, step_type, status
└── NOUVEAU : gate_conditions (JSON)

Gate conditions = liste de conditions à satisfaire AVANT que l'étape ne démarre
```

#### Structure JSON des conditions

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
      "name": "Déployer le patch",
      "type": "platform",
      "referenced_action_id": 15,
      "gate_conditions": [
        {
          "type": "maintenance_window",
          "description": "Attendre la plage de maintenance du serveur cible"
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

#### Types de conditions supportés

| Type | Source | Description |
|------|--------|-------------|
| `maintenance_window` | Inventaire (par serveur) | Le moment actuel est dans la plage de maintenance du/des serveurs cibles. L'inventaire expose une fonction `get_next_maintenance_window(server)` qui retourne la prochaine plage — permet d'afficher à l'utilisateur **quand** l'étape pourra démarrer |
| `time_window` | Paramètre inline | Un créneau horaire fixe est atteint (ex: `{"after": "22:00", "before": "06:00"}`) |
| `approval_granted` | ServiceNow / Manuel | Un ticket de changement est approuvé |
| `target_state` | Inventaire / API | Le serveur cible est dans un état donné (ex: `status = MAINTENANCE`) |

### Comment fonctionne l'attente ?

Le pattern est du **polling conditionnel**, pas du blocking actif. C'est le même principe que DBOps utilise avec succès.

#### Flux d'exécution avec gate

```
┌─────────────┐
│  Étape N-1  │
│  COMPLETED  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│   Étape N       │
│ status: WAITING │◄──── Nouveau statut
└──────┬──────────┘
       │
       ▼
┌──────────────────────────┐
│  Évaluation des gates    │◄──── Tâche périodique (Celery Beat)
│  Toutes satisfaites ?    │      Intervalle : configurable (ex: 60s)
└──────┬───────────────────┘
       │
  NON ─┤── Reste en WAITING, log l'état, ré-évalue au prochain tick
       │
  OUI ─┤
       ▼
┌─────────────┐
│   Étape N   │
│ status: RUNNING │
└─────────────┘
```

#### Implémentation côté Django

**1. Nouveau statut `WAITING` sur `ExecutionStep`**

```python
class ExecutionStepStatus(models.TextChoices):
    PENDING = 'PENDING'
    WAITING = 'WAITING'      # ← NOUVEAU : gate conditions non remplies
    RUNNING = 'RUNNING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'
    SKIPPED = 'SKIPPED'
```

**2. Tâche Celery Beat périodique**

```python
# executions/tasks.py
@shared_task
def evaluate_waiting_gates():
    """
    Évalue les gates de toutes les étapes en WAITING.
    Appelée périodiquement par Celery Beat (ex: toutes les 60 secondes).
    """
    waiting_steps = ExecutionStep.objects.filter(
        status='WAITING',
        execution__status='RUNNING'
    ).select_related('execution__action')

    evaluator = GateEvaluator()
    for step in waiting_steps:
        conditions = get_gate_conditions(step)
        satisfied, context = evaluator.evaluate(step, conditions)

        if satisfied:
            step.status = 'RUNNING'
            step.started_at = timezone.now()
            step.save()
            execute_step.delay(step.id)
        else:
            # Mettre à jour le contexte d'attente (affiché au frontend)
            step.set_output({
                "waiting_since": step.created_at.isoformat(),
                "gate_status": context,
                # Ex: {"maintenance_window": {"next_possible_at": "2025-01-12T22:00:00Z"}}
            })
            step.save()
            # Notifier le frontend via WebSocket
            notify_step_waiting(step, context)
```

**3. Évaluateur de conditions**

```python
# executions/gate_evaluator.py

class GateEvaluator:
    """Évalue les conditions de gate pour une étape."""

    def evaluate(self, step: ExecutionStep, conditions: list[dict]) -> tuple[bool, dict]:
        """
        Retourne (all_satisfied, context).
        Le context contient les infos pour afficher à l'utilisateur
        POURQUOI on attend et QUAND ça pourra démarrer.
        """
        results = {}
        all_ok = True
        for cond in conditions:
            satisfied, ctx = self._check(step, cond)
            results[cond["type"]] = ctx
            if not satisfied:
                all_ok = False
        return all_ok, results

    def _check(self, step, condition) -> tuple[bool, dict]:
        match condition["type"]:
            case "maintenance_window":
                return self._check_maintenance_window(step)
            case "time_window":
                return self._check_time_window(condition)
            case "approval_granted":
                return self._check_approval(step)
            case _:
                return False, {"reason": f"Type inconnu: {condition['type']}"}

    def _check_maintenance_window(self, step) -> tuple[bool, dict]:
        """
        Interroge l'inventaire pour vérifier si le moment actuel
        est dans la plage de maintenance des serveurs cibles.

        L'inventaire expose get_next_maintenance_window(server) qui retourne :
        - { "start": datetime, "end": datetime, "is_active": bool }
        - is_active=True signifie qu'on est DANS la plage maintenant

        Retourne (satisfied, context) où context contient les infos
        pour afficher à l'utilisateur QUAND l'étape pourra démarrer.
        """
        targets = step.execution.targets.all()  # via ExecutionTarget
        inventory_service = InventoryService()
        now = timezone.now()
        next_windows = []

        for target in targets:
            window = inventory_service.get_next_maintenance_window(
                target.target_id
            )
            if not window:
                return False, {"reason": f"Aucune plage de maintenance "
                               f"définie pour {target.target_name}"}
            if not window["is_active"]:
                next_windows.append({
                    "target": target.target_name,
                    "next_start": window["start"],
                    "next_end": window["end"],
                })

        if next_windows:
            # Prochaine fenêtre commune = la plus tardive des starts
            earliest_possible = max(w["next_start"] for w in next_windows)
            return False, {
                "reason": "Hors plage de maintenance",
                "next_possible_at": earliest_possible,
                "windows": next_windows,
            }

        return True, {"reason": "Dans la plage de maintenance"}
```

**4. Modification du `WorkflowRuntime`**

Dans `workflow_runtime.py`, avant d'exécuter une étape, vérifier si elle a des `gate_conditions` :

```python
def _execute_step(self, step_def):
    gate_conditions = step_def.get("gate_conditions", [])
    if gate_conditions:
        # Créer l'ExecutionStep en WAITING au lieu de RUNNING
        exec_step = ExecutionStep.objects.create(
            execution=self.execution,
            step_order=step_def["order"],
            step_name=step_def["name"],
            step_type=step_def.get("type", "platform"),
            status="WAITING",
        )
        # Le WorkflowRuntime se suspend ici.
        # La tâche Celery Beat reprendra quand les gates seront OK.
        return "WAITING"
    else:
        # Exécution immédiate (comportement actuel)
        ...
```

### Timeout et sécurité

Une gate ne doit pas attendre indéfiniment :

```json
{
  "type": "maintenance_window",
  "timeout_hours": 48,
  "on_timeout": "FAIL"
}
```

Si le timeout expire, l'étape passe en `FAILED` (ou `SKIPPED` selon la config), et le workflow suit la branche `on_error_step_id`.

### Notification

Quand une étape entre en `WAITING` :
- Log dans `ExecutionStep.output` : raison de l'attente, prochaine évaluation
- WebSocket notification au frontend : affichage temps réel de l'état d'attente
- Optionnel : notification (email/Teams) si l'attente dépasse un seuil

---

## 2. Overrides par environnement

### Problème actuel

Dans IDP Portal, l'environnement est un simple champ `CharField` sur `Execution`. Il n'y a pas de moyen de dire "cette action nécessite un ticket ServiceNow en PROD mais pas en DEV".

### Ce que DBOps fait

Table `operation_environment_override` : pour chaque opération, on peut surcharger les exigences par environnement (ticket obligatoire, plage de maintenance requise, opération interdite, etc.).

### Solution pour IDP Portal

Étendre le JSON `change_type_config` de `Action` (qui existe déjà par environnement) pour inclure des flags de comportement :

```json
{
  "prod": {
    "change_type": "normal",
    "template_id": "CHG_TPL_001",
    "requires_maintenance_window": true,
    "requires_approval": true,
    "allowed": true
  },
  "staging": {
    "change_type": "standard",
    "requires_maintenance_window": false,
    "requires_approval": false,
    "allowed": true
  },
  "dev": {
    "allowed": true,
    "requires_maintenance_window": false,
    "requires_approval": false
  }
}
```

**Impact** : Pas de nouvelle table. On enrichit le champ `OracleJSONField` existant + la logique de validation dans `executions/utils.py`.

---

## 3. Mutex inter-actions (exclusion mutuelle)

### Problème actuel

IDP Portal n'a aucune notion d'incompatibilité entre actions. On peut lancer deux actions incompatibles sur le même serveur simultanément (ex: un patching et un backup sur la même base).

> **Note** : le type `MUST_COMPLETE_BEFORE` de DBOps n'est pas repris ici — le mécanisme de workflow (chaînage d'étapes avec branching) couvre déjà ce besoin. On se concentre sur le **mutex** : empêcher deux actions incompatibles de tourner en parallèle.

### Ce que DBOps fait

- Table `operation_dependency` avec type `MUST_NOT_RUN_WITH`
- Flag `same_target` : la contrainte ne s'applique que si c'est le même serveur cible
- Validation au moment de la soumission ET dans le scheduler (fonction `validate_mutex`)

### Solution pour IDP Portal

```python
class ActionMutex(models.Model):
    """Exclusion mutuelle entre deux actions."""

    class Meta:
        db_table = 'ACTION_MUTEX'
        unique_together = ('action', 'incompatible_with')

    action = models.ForeignKey(Action, on_delete=models.CASCADE,
                               related_name='mutex_rules')
    incompatible_with = models.ForeignKey(Action, on_delete=models.CASCADE,
                                         related_name='mutex_references')
    same_target = models.BooleanField(default=True)
    # True  = interdit seulement si même serveur cible
    # False = interdit globalement (rare, ex: migration de schéma global)
    description = models.CharField(max_length=500, blank=True)
```

**Validation à la soumission** : quand un utilisateur soumet une exécution, on vérifie :

```python
def validate_mutex(action, targets):
    """Vérifie qu'aucune action incompatible n'est en cours sur les mêmes cibles."""
    mutex_rules = ActionMutex.objects.filter(action=action)
    for rule in mutex_rules:
        running = Execution.objects.filter(
            action=rule.incompatible_with,
            status__in=['RUNNING', 'PENDING_APPROVAL', 'SUBMITTED'],
        )
        if rule.same_target:
            # Vérifier seulement si même cible (via ExecutionTarget)
            running = running.filter(
                targets__target_id__in=[t.target_id for t in targets]
            )
        if running.exists():
            raise MutexViolationError(
                f"L'action '{rule.incompatible_with.name}' est en cours "
                f"sur la même cible. Exécution impossible."
            )
```

**Bénéfice clé** : la table relationnelle permet des requêtes performantes avec jointures sur `ExecutionTarget` — c'est ce qui justifie d'avoir d'abord implémenté le modèle de cible (§4).

---

## 4. Modèle de cible générique (Target-First)

### Problème actuel

IDP Portal n'a pas de modèle de liaison entre une exécution et ses cibles. Les cibles sont implicites dans les paramètres JSON.

### Ce que DBOps fait

- Table `operation_request_target` : (request_id, target_type, target_id, target_metadata)
- Table `target_type_registry` : métadonnées pour résoudre les types de cibles
- Permet le multi-target, la validation d'existence, le pattern matching RBAC

### Solution pour IDP Portal

```python
class ExecutionTarget(models.Model):
    """Liaison explicite entre une exécution et ses cibles."""

    class Meta:
        db_table = 'EXECUTION_TARGETS'
        unique_together = ('execution', 'target_type', 'target_id')

    execution = models.ForeignKey(Execution, on_delete=models.CASCADE,
                                  related_name='targets')
    target_type = models.CharField(max_length=50)  # SERVER, DATABASE, PDB, SCHEMA
    target_id = models.CharField(max_length=200)   # ID opaque vers l'inventaire
    target_name = models.CharField(max_length=255)  # Snapshot du nom pour affichage
    target_metadata = models.TextField(null=True)    # JSON snapshot (env, technology, etc.)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Bénéfices** :
- Requêtes directes : "toutes les exécutions sur le serveur X"
- Validation RBAC sur les cibles au moment de la soumission
- Vérification des mutex par cible (`MUST_NOT_RUN_WITH` + `same_target`)
- Support multi-target natif (patcher 10 serveurs en une exécution)
- Les condition gates `maintenance_window` savent quels serveurs vérifier

---

## 5. Stratégies de déploiement

### Problème actuel

IDP Portal exécute les étapes séquentiellement (ou avec branching). Il n'y a pas de concept de "exécuter cette action sur 10 serveurs en rolling batches de 2".

### Ce que DBOps fait

Table `deployment_strategy` + `operation_strategy_mapping` : stratégies PARALLEL, SERIAL, ROLLING, topology-aware (RAC, DataGuard).

### Solution pour IDP Portal

Ce sujet est plus avancé et dépend du modèle de cible générique (§4). La stratégie de déploiement intervient quand une exécution a **plusieurs targets**. Elle définit :

- **L'ordre** : parallèle, séquentiel, rolling (par batch)
- **La gestion d'erreur** : stop au premier échec ou continuer
- **La validation inter-batch** : pause pour vérification entre chaque batch

Ceci peut être modélisé comme un champ JSON sur l'action ou une table dédiée selon la complexité souhaitée. À traiter dans un epic ultérieur une fois que le modèle de target et les condition gates sont en place.

---

## 6. Deny explicite dans le RBAC

### Problème actuel

`ProfileTargetPermission` ne supporte que des listes positives (LIST, PATTERN, ALL). Pas moyen de dire "accès à tout SAUF les serveurs de prod critiques".

### Ce que DBOps fait

`api_client_target_permission` avec `granted` (0=deny, 1=allow) et `priority` pour l'ordre d'évaluation.

### Solution pour IDP Portal

Ajouter à `ProfileTargetPermission` :

```python
# Nouveau champ
exclusion_patterns_json = models.TextField(null=True, blank=True)
# JSON array de patterns à exclure, ex: ["PROD-CRITICAL-*", "DR-*"]
```

Logique d'évaluation : **allow first, then exclude**. Plus simple qu'un système de priorités, suffisant pour le cas d'usage portail.

---

## 7. Résumé des impacts

### Nouvelles tables

| Table | Priorité | Dépendance |
|-------|----------|------------|
| `EXECUTION_TARGETS` | Haute | Aucune |
| `ACTION_MUTEX` | Moyenne | `EXECUTION_TARGETS` (pour `same_target`) |

### Modifications de tables existantes

| Table | Modification | Priorité |
|-------|-------------|----------|
| `EXECUTION_STEPS` | Nouveau statut `WAITING` | Haute |
| `PROFILE_TARGET_PERMISSIONS` | Champ `exclusion_patterns_json` | Basse |

### Modifications de champs JSON

| Champ | Modification | Priorité |
|-------|-------------|----------|
| `Action.execution_steps` | Support `gate_conditions` par étape | Haute |
| `Action.change_type_config` | Flags `requires_maintenance_window`, `requires_approval`, `allowed` | Moyenne |

### Nouveaux composants

| Composant | Type | Priorité |
|-----------|------|----------|
| `GateEvaluator` | Service Python | Haute |
| `evaluate_waiting_gates` | Tâche Celery Beat | Haute |
| Gate conditions validators | Validation catalog | Haute |
| WebSocket notifications WAITING | Frontend | Moyenne |

### Ordre d'implémentation recommandé

```
1. ExecutionTarget (table + API)                    ── Fondation
   └─ permet de savoir QUELS serveurs sont ciblés

2. Condition Gates + statut WAITING                 ── Cœur
   ├─ gate_conditions dans execution_steps JSON
   ├─ GateEvaluator service
   ├─ Celery Beat task
   └─ maintenance_window gate (lecture inventaire)

3. Overrides par environnement                      ── Gouvernance
   └─ enrichir change_type_config

4. Mutex inter-actions                               ── Sécurité opérationnelle
   ├─ Table ACTION_MUTEX
   └─ Validation mutex à la soumission (dépend de §1 pour ExecutionTarget)

5. Deny explicite RBAC                              ── Affinement
   └─ exclusion_patterns sur ProfileTargetPermission

6. Stratégies de déploiement                        ── Avancé
   └─ nécessite 1 + 2 + 4 en place
```

---

## 8. Ce qu'on NE reprend PAS de DBOps

| Feature DBOps | Raison de l'exclusion |
|--------------|----------------------|
| PL/SQL packages (logique métier en DB) | La logique reste en Python — plus testable, plus maintenable |
| ORDS comme API | DRF est supérieur en flexibilité et outillage |
| Dispatch PUSH via UTL_HTTP | Celery gère la dispatch côté Python, plus fiable |
| Materialized views dashboard | Les dashboards sont dans le frontend React, agrégation via DRF |
| Partitionnement Oracle | À évaluer plus tard si les volumes l'exigent (pas critique au départ) |
| APEX UI | Le frontend React + Ant Design est notre choix |
| Target type registry (table) | On peut le faire via configuration Django ou enum — plus simple |

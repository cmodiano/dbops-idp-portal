# ADR-007 : Architecture Steps Unifiée — Change Management, Gates, Evaluations et Approbations comme Steps de Workflow

**Date :** 2026-03-02
**Statut :** Proposé
**Décideurs :** Équipe IDP Portal

## Contexte

### Le problème métier

Le portail IDP doit orchestrer des workflows complexes impliquant plusieurs systèmes :
inventaire (API), ServiceNow (change management), plateformes d'exécution (AAP, Terraform,
GitHub Actions), et des décisions humaines (approbations). Aujourd'hui, AAP orchestre
lui-même une partie de ce cycle (interroger l'inventaire, créer le change ServiceNow,
exécuter le patching, fermer le change). Le portail ne fait que déclencher un job AAP
et ne contrôle pas le flux.

**L'objectif est que le portail devienne le plan de contrôle central** : il orchestre,
les plateformes exécutent. Comme un workflow GitHub Actions ou un playbook Ansible
avec `register`, chaque étape produit des données consommables par les étapes suivantes.

### Les limitations de l'architecture actuelle

L'architecture actuelle repose sur des **hooks et mécanismes cachés** plutôt que
sur des steps explicites dans le workflow :

#### 1. Le changement ServiceNow est un pre-hook, pas un step

**Fichier :** `executions/container_workflow_runtime.py:470-551`

```python
def _create_servicenow_change_if_required(self, environment: str) -> None:
    # ...
    change_number = svc.create_change(
        short_description=f"IDP Portal — {self.action.name}",         # statique
        description=f"Exécution automatisée {self.execution.id}...",   # statique
    )
```

Le changement est créé **avant tout step** (`run()` ligne 361), avec des données statiques
(nom de l'action, ID d'exécution). Il ne peut pas utiliser des données dynamiques qui
seraient produites par un step precedent (ex: liste de bases impactees, numero de patch).
Il n'apparait pas dans la timeline des steps dans l'UI.

#### 2. Les gates bloquent mais ne branchent pas

**Fichier :** `executions/gate_evaluator.py:37-158`

Les gates (`maintenance_window`, `approval_granted`) mettent un step en statut WAITING.
Le Celery Beat task (`executions/tasks/gates.py`) evalue periodiquement. Quand toutes
les conditions sont satisfaites, le step reprend. Mais les gates ne peuvent pas **router
vers des chemins différents** selon le résultat.

```python
# gate_evaluator.py:135-143
case 'approval_granted':
    if not requires_approval:
        satisfied = True
    else:
        satisfied = False
        context = {'reason': "mécanisme d'approbation non implémenté"}
```

L'approbation est un placeholder (`"non implemente"`).

#### 3. L'evaluation de policies est un post-step hook, pas un step

**Fichier :** `executions/workflow_step_executor.py:491-632`

Le `RuleEngine` (`executions/rule_engine.py`) analyse l'output d'un step via des
`OutputInterpreters` (Terraform plan, AAP) et evalue des business rules. Mais le
résultat ne peut que **bloquer** (WAITING pour approval) ou **laisser passer**.
Il ne peut pas brancher vers un chemin different.

```python
# workflow_step_executor.py:567-569
if policy_decision.require_approval:
    execution_step.status = ExecutionStepStatus.WAITING  # bloque, pas de branchement
```

#### 4. L'approbation est un statut global, pas un step

**Fichier :** `executions/models.py:116-143`

```python
status = PENDING_APPROVAL         # statut global de l'exécution
approved_by = ForeignKey(User)    # qui
approved_at = DateTimeField()     # quand
approval_comment = CharField()    # commentaire
```

L'exécution entière passe en `PENDING_APPROVAL`. L'approbateur ne sait pas **ce qu'il
approuve** (un plan Terraform ? un patching ? le workflow entier ?). Il n'a pas de
contexte sur les étapes précédentes.

Fichiers impactes : `executions/views/approval_views.py` (lignes 33-217),
`executions/views/execution_views.py` (ligne 186-188).

#### 5. Pas d'output forwarding entre steps

**Fichier :** `executions/container_workflow_runtime.py:118-150`

```python
def _get_step_parameters(self, step):
    global_params = {k: v for k, v in params.items()
                     if k not in ('workflow_step_parameters', '_env_config')}
    step_params = wsp.get(order_key, {}).get("parameters", {})
    merged = {**global_params, **step_params}
    return merged
```

Les paramètres d'un step viennent du payload initial (`workflow_step_parameters`) ou
des paramètres globaux. **Aucun mécanisme ne permet d'utiliser l'output d'un step
precedent comme input du step suivant.**

L'output est stocke dans `ExecutionStep.output` (CLOB JSON, `models.py:295`) via
`set_output()` (`models.py:324-329`), mais il n'est jamais relu par le runtime pour
alimenter les steps suivants.

#### 6. Tous les steps sont de type PLATFORM

**Fichier :** `executions/models.py:249-255`

```python
class ExecutionStepType(models.TextChoices):
    VAULT = 'vault', 'Vault'
    SERVICENOW = 'servicenow', 'ServiceNow'      # existe, jamais utilise
    PLATFORM = 'platform', 'Platform'
    PREREQUISITE = 'prerequisite', 'Prerequisite'
    VERIFICATION = 'verification', 'Verification'
```

Le type `SERVICENOW` existe déjà dans l'enum mais n'est jamais utilise par les runtimes.
Dans `container_workflow_runtime.py:214` et `workflow_step_executor.py:86,138`, tout
est code en dur `step_type='platform'` ou `ExecutionStepType.PLATFORM`.

#### 7. Le branchement existe mais est deconnecte des evaluations

**Fichier :** `executions/workflow_runtime.py:241-315`

```python
def _resolve_next_step(self, current_step, outcome):
    if is_success and 'on_success_step_id' in current_step:
        return current_step.get('on_success_step_id')
    if (not is_success) and 'on_error_step_id' in current_step:
        return current_step.get('on_error_step_id')
```

Le branchement conditionnel (`on_success_step_id` / `on_error_step_id`) existe dans
`WorkflowRuntime` mais il est base sur le résultat du step **plateforme** (job AAP
reussi/echoue), pas sur l'evaluation d'un output.

### Resume du diagnostic

| Mecanisme | Statut actuel | Probleme |
|-----------|---------------|----------|
| Change ServiceNow | Pre-hook (`container_workflow_runtime.py:470`) | Donnees statiques, invisible dans timeline |
| Gate maintenance_window | Hook pre-step (`gate_evaluator.py:128`) | Bloque mais ne branche pas |
| Gate approval | Placeholder (`gate_evaluator.py:135`) | Non implemente |
| Evaluation policies | Post-step hook (`workflow_step_executor.py:491`) | Bloque mais ne branche pas |
| Approbation | Statut global (`Execution.PENDING_APPROVAL`) | Pas de contexte, pas granulaire |
| Output forwarding | Inexistant | Steps isoles, pas de chainage de données |
| Branching | Existe (`workflow_runtime.py:241`) | Deconnecte des evaluations et gates |

**Ces mécanismes fonctionnent individuellement mais ne forment pas un systeme integre.**

---

## Decision

### Tout devient un step. Le branching est unifie.

Transformer tous les mécanismes caches (change management, gates, evaluations,
approbations) en steps explicites du workflow. Chaque step produit un output
consommable par les steps suivants via un contexte partage `steps.*`.

Le branchement (`on_success_step_id` / `on_error_step_id`) déjà present dans
`WorkflowRuntime` devient le mécanisme de routage unifie pour tous les types de steps.

### Types de steps

Cinq types de steps, classes en deux categories alignees sur `IntegrationRole`
(Story 29.1, `integrations/models.py:75-78`) :

#### Steps avec appel externe

| `step_type` | Role | Synchrone ? | Creation child Execution ? |
|-------------|------|-------------|----------------------------|
| `platform` | Executer un job (AAP, GHA, Terraform) | Non (trigger/poll) | Oui (existant) |
| `service_call` | Appeler un service (ServiceNow, Vault, Jira) | Oui | Non — inline |
| `http_request` | Appeler une API brute (inventaire, CMDB) | Oui | Non — inline |

#### Steps internes (pas d'appel externe)

| `step_type` | Role | Synchrone ? | Creation child Execution ? |
|-------------|------|-------------|----------------------------|
| `evaluation` | Analyser l'output d'un step precedent | Oui | Non — inline |
| `gate` | Attendre une condition (maintenance window, approval) | Non (WAITING) | Non — inline |

### Pourquoi `service_call` generique et non `servicenow_change`

L'architecture d'integrations distingue déjà les roles (`integrations/models.py:75-78`) :

```python
class IntegrationRole(models.TextChoices):
    PLATFORM = 'platform', "Plateforme d'exécution"
    SERVICE = 'service', 'Service consomme'
```

Les types d'integration (`IntegrationType`, lignes 58-72) incluent : `servicenow`,
`vault`, `jira`, `inventory`, etc. Créer un type de step par service (`servicenow_change`,
`servicenow_close`, `vault_read`, `jira_create`) couplerait le moteur de workflow a des
services specifiques et violerait OCP.

Le step `service_call` est generique. C'est la combinaison `integration_type` + `operation`
qui determine le comportement :

```json
{
  "step_type": "service_call",
  "integration_type": "servicenow",
  "operation": "create_change"
}
```

L'ajout d'un nouveau service (ex: PagerDuty) ne nécessite aucune modification du runtime :
il suffit d'enregistrer le type d'integration et d'implementer la classe de service.

### Output forwarding entre steps

Chaque step produit un output stocke dans `ExecutionStep.output` (CLOB JSON existant).
Le runtime maintient un contexte partage `_step_outputs: dict[str, dict]` clef par
`step_id`.

Deux mécanismes de mapping :

- **`output_mapping`** : Extrait des valeurs de l'output brut du step via JSONPath
  et les expose dans `_step_outputs[step_id]`.
- **`input_mapping`** : Resout des references `{{ steps.<step_id>.<path> }}` dans les
  paramètres d'un step a partir de `_step_outputs`.

Analogie directe :
- GitHub Actions : `${{ steps.<id>.outputs.<name> }}`
- Ansible : `register: result` puis `{{ result.stdout }}`

### Conditions per-environment sur les steps

Le champ `change_type_config` sur l'Action (`catalog/models.py:220`) definit des regles
per-environment pour le change management. Dans la nouvelle architecture, cette logique
migre vers une `condition` sur chaque step :

```json
{
  "step_id": "create-change",
  "step_type": "service_call",
  "condition": { "environment_in": ["production", "pre-production"] }
}
```

Si la condition n'est pas remplie, le step passe en statut `SKIPPED`
(`ExecutionStepStatus.SKIPPED`, déjà defini dans `models.py:265`).

Les steps suivants qui référencent l'output d'un step SKIPPED reçoivent une chaîne
vide : `_step_outputs[step_id] = {}` et le template `{{ steps.create-change.change_number }}`
résout à `''` (Jinja2 finalize convertit None en chaîne vide).

### Approbation comme step gate

Les champs d'approbation sur `Execution` (`approved_by`, `approved_at`,
`approval_comment` — `models.py:129-143`) et le statut `PENDING_APPROVAL`
(`models.py:21`) sont remplaces par un step `gate` de type `approval`.

La source de vérité passe de l'Execution au `ExecutionStep`. Cela permet :
- Plusieurs approbations dans un meme workflow (une apres le plan, une avant le deploy)
- Un contexte pour l'approbateur (output des steps precedents)
- Un branchement si rejet (vers un chemin de rollback/abort)

---

## Schéma de la définition d'un workflow

### Exemple complet : Patching Oracle

```json
{
  "item_type": "workflow",
  "execution_steps": [
    {
      "step_id": "discovery",
      "order": 1,
      "name": "Query inventory",
      "step_type": "http_request",
      "config": {
        "url": "https://inventory.corp/api/v1/patch-scope",
        "method": "GET",
        "headers": { "Accept": "application/json" },
        "params": { "engine": "oracle", "patch_eligible": true }
      },
      "output_mapping": {
        "databases": "$.data.databases",
        "patch_number": "$.data.latest_patch.number",
        "cmdb_ci": "$.data.cmdb_ci"
      }
    },
    {
      "step_id": "create-change",
      "order": 2,
      "name": "Create ServiceNow Change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "create_change",
      "condition": {
        "environment_in": ["production", "pre-production"]
      },
      "input_mapping": {
        "short_description": "Patching {{ steps.discovery.patch_number }} — {{ steps.discovery.databases | length }} databases",
        "cmdb_ci": "{{ steps.discovery.cmdb_ci }}",
        "u_patch_number": "{{ steps.discovery.patch_number }}",
        "u_impacted_databases": "{{ steps.discovery.databases | join(', ') }}"
      },
      "output_mapping": {
        "change_number": "$.number",
        "sys_id": "$.sys_id"
      }
    },
    {
      "step_id": "pre-check",
      "order": 3,
      "name": "Pre-patch validation",
      "step_type": "platform",
      "referenced_action_id": 100,
      "input_mapping": {
        "extra_vars": {
          "databases": "{{ steps.discovery.databases }}"
        }
      },
      "output_mapping": {
        "health_report": "$.artifacts.health_report"
      }
    },
    {
      "step_id": "evaluate-health",
      "order": 4,
      "name": "Check pre-patch health",
      "step_type": "evaluation",
      "input_mapping": {
        "artifact": "{{ steps.pre-check.health_report }}"
      },
      "policy_id": 7,
      "on_success_step_id": "wait-window",
      "on_error_step_id": "abort-change"
    },
    {
      "step_id": "wait-window",
      "order": 5,
      "name": "Wait for maintenance window",
      "step_type": "gate",
      "gate_type": "maintenance_window",
      "condition": {
        "environment_in": ["production"]
      },
      "timeout_hours": 72,
      "on_timeout": "FAIL",
      "on_success_step_id": "apply-patch",
      "on_error_step_id": "abort-change"
    },
    {
      "step_id": "apply-patch",
      "order": 6,
      "name": "Apply patch",
      "step_type": "platform",
      "referenced_action_id": 200,
      "input_mapping": {
        "extra_vars": {
          "change_id": "{{ steps.create-change.change_number }}",
          "databases": "{{ steps.discovery.databases }}",
          "patch_number": "{{ steps.discovery.patch_number }}"
        }
      }
    },
    {
      "step_id": "close-change",
      "order": 7,
      "name": "Close change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "close_change",
      "condition": {
        "environment_in": ["production", "pre-production"]
      },
      "input_mapping": {
        "change_id": "{{ steps.create-change.change_number }}"
      },
      "on_success_step_id": null
    },
    {
      "step_id": "abort-change",
      "name": "Abort — cancel change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "cancel_change",
      "condition": {
        "environment_in": ["production", "pre-production"]
      },
      "input_mapping": {
        "change_id": "{{ steps.create-change.change_number }}"
      }
    }
  ]
}
```

### Exemple : Terraform avec evaluation et approbation conditionnelle

```json
{
  "execution_steps": [
    {
      "step_id": "tf-plan",
      "order": 1,
      "name": "Terraform Plan",
      "step_type": "platform",
      "referenced_action_id": 300,
      "output_mapping": {
        "plan": "$.artifacts.plan_json",
        "resource_count": "$.artifacts.resource_count"
      }
    },
    {
      "step_id": "check-plan",
      "order": 2,
      "name": "Analyze Plan",
      "step_type": "evaluation",
      "input_mapping": {
        "artifact": "{{ steps.tf-plan.plan }}"
      },
      "policy_id": 5,
      "on_success_step_id": "create-change",
      "on_error_step_id": "request-approval"
    },
    {
      "step_id": "request-approval",
      "order": 3,
      "name": "DBA Approval Required",
      "step_type": "gate",
      "gate_type": "approval",
      "timeout_hours": 48,
      "on_timeout": "FAIL",
      "context_from": ["tf-plan", "check-plan"],
      "on_success_step_id": "create-change",
      "on_error_step_id": null
    },
    {
      "step_id": "create-change",
      "order": 4,
      "name": "Create ServiceNow Change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "create_change",
      "condition": {
        "environment_in": ["production"]
      },
      "input_mapping": {
        "short_description": "Terraform apply — {{ steps.tf-plan.resource_count }} resources"
      },
      "output_mapping": {
        "change_number": "$.number"
      }
    },
    {
      "step_id": "tf-apply",
      "order": 5,
      "name": "Terraform Apply",
      "step_type": "platform",
      "referenced_action_id": 301,
      "input_mapping": {
        "extra_vars": {
          "change_id": "{{ steps.create-change.change_number }}"
        }
      }
    },
    {
      "step_id": "close-change",
      "order": 6,
      "name": "Close Change",
      "step_type": "service_call",
      "integration_type": "servicenow",
      "operation": "close_change",
      "condition": {
        "environment_in": ["production"]
      },
      "input_mapping": {
        "change_id": "{{ steps.create-change.change_number }}"
      }
    }
  ]
}
```

### Flux d'exécution — Terraform en production (plan non conforme)

```text
tf-plan ──► check-plan ──► request-approval ──► create-change ──► tf-apply ──► close-change
(platform)  (evaluation)   (gate/approval)      (service_call)    (platform)   (service_call)
 COMPLETED   ERROR          WAITING...           COMPLETED         COMPLETED    COMPLETED
             "destroy       approval recue
              detected"     on_success ─┘
```

### Flux d'exécution — Terraform en staging (plan conforme)

```text
tf-plan ──► check-plan ──► [create-change SKIPPED] ──► tf-apply ──► [close-change SKIPPED]
(platform)  (evaluation)   (condition non remplie)      (platform)   (condition non remplie)
 COMPLETED   SUCCESS
             on_success ───────────────────────────────┘
```

---

## Details des modifications

### 1. Modele ExecutionStep — nouveaux champs pour l'approbation

**Fichier :** `executions/models.py:268-330`

Ajouter sur `ExecutionStep` les champs qui vivent aujourd'hui sur `Execution` :

```python
class ExecutionStep(models.Model):
    # ... champs existants ...

    # Nouveaux champs pour gate/approval (migres depuis Execution)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='approved_steps',
        db_column='APPROVED_BY'
    )
    approved_at = models.DateTimeField(null=True, blank=True, db_column='APPROVED_AT')
    approval_comment = models.CharField(
        max_length=1000, null=True, blank=True,
        db_column='APPROVAL_COMMENT'
    )
```

**Migration Oracle :** Ajouter les colonnes `APPROVED_BY`, `APPROVED_AT`,
`APPROVAL_COMMENT` a la table `EXECUTION_STEPS`.

**Note :** Les champs `approved_by`, `approved_at`, `approval_comment` sur le modele
`Execution` (`models.py:129-143`) sont conserves temporairement pour backward
compatibility mais ne sont plus la source de vérité. Le statut `PENDING_APPROVAL` sur
`Execution` est derive : si au moins un step est en WAITING avec `gate_type: approval`,
l'exécution est en attente d'approbation.

### 2. Enum ExecutionStepType — nouveaux types

**Fichier :** `executions/models.py:249-255`

```python
class ExecutionStepType(models.TextChoices):
    # Existants
    VAULT = 'vault', 'Vault'
    SERVICENOW = 'servicenow', 'ServiceNow'
    PLATFORM = 'platform', 'Platform'
    PREREQUISITE = 'prerequisite', 'Prerequisite'
    VERIFICATION = 'verification', 'Verification'
    # Nouveaux
    SERVICE_CALL = 'service_call', 'Service Call'
    HTTP_REQUEST = 'http_request', 'HTTP Request'
    EVALUATION = 'evaluation', 'Evaluation'
    GATE = 'gate', 'Gate'
```

**Migration Oracle :** Modifier la CHECK constraint sur `EXECUTION_STEPS.STEP_TYPE`.

### 3. Output Context dans ContainerWorkflowRuntime

**Fichier :** `executions/container_workflow_runtime.py`

#### 3a. Ajout du contexte partage

```python
class ContainerWorkflowRuntime:
    def __init__(self, execution, execution_service=None):
        # ... existant ...
        self._step_outputs: dict[str, dict] = {}  # NOUVEAU: contexte partage
```

#### 3b. Résolution des input_mapping

Nouveau module : `executions/template_resolver.py`

```python
class StepTemplateResolver:
    """Resout les {{ steps.<step_id>.<path> }} dans les input_mapping."""

    def __init__(self, step_outputs: dict[str, dict]):
        self._step_outputs = step_outputs

    def resolve(self, input_mapping: dict) -> dict:
        """Parcourt le dict et resout les templates {{ steps.X.Y }}."""
        # Utilise string.Template ou jinja2.sandbox.SandboxedEnvironment
        # selon le besoin (voir section Choix techniques)
        ...
```

Le `SandboxedEnvironment` de Jinja2 est recommande pour :
- Support des filtres (`| join(', ')`, `| length`, `| first`)
- Sécurité (sandboxed, pas d'acces aux attributs Python)
- Familiarite (meme syntaxe que Ansible et les templates Django)

#### 3c. Extraction des output_mapping

Nouveau module : `executions/output_extractor.py`

```python
class OutputExtractor:
    """Extrait des valeurs de l'output brut via JSONPath."""

    def extract(self, raw_output: dict, output_mapping: dict) -> dict:
        """Applique le mapping JSONPath et retourne un dict de valeurs nommees."""
        # Ex: {"databases": "$.data.databases"} → {"databases": ["DB1", "DB2"]}
        # Utilise jsonpath-ng ou une implémentation simple basee sur les cles
        ...
```

Pour le JSONPath, deux options :
- **Simple :** Résolution par cles (`$.data.databases` → `output["data"]["databases"]`)
  suffisante pour 90% des cas. Zero dependance externe.
- **Complet :** Bibliothèque `jsonpath-ng` pour les expressions avancees
  (`$.data.databases[*].name`). Dependance additionnelle.

**Recommandation :** Commencer par la resolution simple (dot-notation), ajouter
`jsonpath-ng` si le besoin se manifeste.

#### 3d. Dispatcher de step types dans _execute_step

**Fichier :** `executions/container_workflow_runtime.py:173-339`

La methode `_execute_step()` actuelle ne gere que les steps `platform`. Elle doit
dispatcher selon le `step_type` de la définition du workflow :

```python
def _execute_step(self, step):
    step_type = step.get('step_type', 'platform')

    # Résoudre les input_mapping depuis _step_outputs
    resolver = StepTemplateResolver(self._step_outputs)
    input_mapping = step.get('input_mapping', {})
    resolved_params = resolver.resolve(input_mapping) if input_mapping else {}

    # Evaluer la condition (environment_in, etc.)
    if not self._evaluate_condition(step):
        return self._skip_step(step)

    # Dispatcher selon le type
    match step_type:
        case 'platform':
            result = self._execute_platform_step(step, resolved_params)
        case 'service_call':
            result = self._execute_service_call_step(step, resolved_params)
        case 'http_request':
            result = self._execute_http_request_step(step, resolved_params)
        case 'evaluation':
            result = self._execute_evaluation_step(step, resolved_params)
        case 'gate':
            result = self._execute_gate_step(step, resolved_params)
        case _:
            raise ValueError(f"Unknown step_type: {step_type}")

    # Extraire les outputs via output_mapping
    step_id = step.get('step_id')
    if step_id:
        extractor = OutputExtractor()
        output_mapping = step.get('output_mapping', {})
        # Handlers : envelope {raw_output: ...} ou dict brut
        raw = result.get('raw_output', result) if isinstance(result, dict) else {}
        extracted = extractor.extract(raw, output_mapping)
        self._step_outputs[step_id] = extracted

    return result
```

### 4. Step handlers — implémentation de chaque type

#### 4a. `platform` — existant, a refactorer

**Fichier actuel :** `executions/container_workflow_runtime.py:173-339`

Le code existant de `_execute_step()` est extrait dans `_execute_platform_step()`.
Le comportement ne change pas : creation d'une child execution, delegation a
`SimulationService` ou au trigger async.

#### 4b. `service_call` — nouveau handler

**Nouveau :** `executions/step_handlers/service_call_handler.py`

```python
class ServiceCallHandler:
    """Execute un appel synchrone a un service (IntegrationRole.SERVICE)."""

    def execute(self, step_config, resolved_params, execution, correlation_id):
        """
        1. Résoudre l'integration par integration_type ou integration_id
        2. Instancier le service (ServiceNowService, VaultService, etc.)
        3. Appeler l'operation (create_change, close_change, read_secret, etc.)
        4. Retourner le résultat brut
        """
        integration_type = step_config.get('integration_type')
        operation = step_config.get('operation')

        # Résolution de l'integration (meme logique que _create_servicenow_change_if_required)
        integration = self._resolve_integration(step_config)

        # Instanciation du service via registry
        service = self._get_service(integration)

        # Appel de l'operation
        method = getattr(service, operation)
        result = method(**resolved_params)

        return result
```

Le mapping `integration_type` → classe de service suit le meme pattern que
`AdapterRegistry` (`adapters/registry.py`) mais pour les services :

| integration_type | Classe de service | Operations |
|-----------------|-------------------|------------|
| `servicenow` | `ServiceNowService` | `create_change`, `update_change`, `close_change`, `get_change_status` |
| `vault` | `VaultService` | `read_secret`, `write_secret` |
| `jira` | `JiraService` (futur) | `create_issue`, `update_issue` |

#### 4c. `http_request` — nouveau handler

**Nouveau :** `executions/step_handlers/http_request_handler.py`

```python
class HttpRequestHandler:
    """Execute un appel HTTP brut (pas d'integration necessaire)."""

    def execute(self, step_config, resolved_params, execution, correlation_id):
        """
        1. Lire la config (url, method, headers, params)
        2. Executer la requete HTTP via httpx
        3. Retourner le corps JSON de la reponse
        """
        config = step_config.get('config', {})
        url = config['url']
        method = config.get('method', 'GET').upper()
        headers = config.get('headers', {})

        with httpx.Client(timeout=30) as client:
            if method == 'GET':
                resp = client.get(url, headers=headers, params=config.get('params'))
            elif method == 'POST':
                resp = client.post(url, headers=headers, json=resolved_params)
            resp.raise_for_status()
            return resp.json()
```

**Sécurité :** Le `http_request` handler doit valider l'URL contre une allowlist
configurable (pas d'appels vers des URLs arbitraires). Voir la section Sécurité.

#### 4d. `evaluation` — reutilise le RuleEngine existant

**Nouveau :** `executions/step_handlers/evaluation_handler.py`

```python
class EvaluationHandler:
    """Evalue l'output d'un step precedent via RuleEngine."""

    def execute(self, step_config, resolved_params, execution, correlation_id):
        """
        1. Charger la policy (par policy_id ou inline)
        2. Appeler RuleEngine.evaluate()
        3. Mapper la decision sur SUCCESS/ERROR pour le branching
        """
        from executions.rule_engine import RuleEngine
        from catalog.models import BusinessRulePolicy

        # Charger la policy
        policy_id = step_config.get('policy_id')
        if policy_id:
            policy_obj = BusinessRulePolicy.objects.get(id=policy_id)
            policy = policy_obj.policy_json
        else:
            policy = step_config.get('policy', {})

        # RuleEngine fait tout le travail (interpreters + evaluation)
        engine = RuleEngine()
        decision = engine.evaluate(action_proxy, step_proxy, resolved_params.get('artifact'))

        return {
            'decision': 'requires_approval' if decision.require_approval else 'auto_approved',
            'decision_reason': decision.decision_reason,
            'matched_criteria': decision.matched_criteria,
            # Le runtime mappe 'requires_approval' → ExecutionStatus.FAILED (on_error_step_id)
            #                    'auto_approved' → ExecutionStatus.COMPLETED (on_success_step_id)
        }
```

Les `OutputInterpreters` existants (`TerraformPlanInterpreter`,
`AAPOutputInterpreter` dans `executions/interpreters/`) sont reutilises tels quels.

#### 4e. `gate` — reutilise le GateEvaluator existant

**Nouveau :** `executions/step_handlers/gate_handler.py`

```python
class GateHandler:
    """Cree un step en WAITING. Le Celery Beat task evalue periodiquement."""

    def execute(self, step_config, resolved_params, execution, correlation_id):
        """
        1. Créer le ExecutionStep en WAITING
        2. Stocker gate_conditions dans step.output
        3. Retourner un statut WAITING (le runtime ne passe pas au step suivant)
        """
        gate_type = step_config.get('gate_type')  # maintenance_window, approval

        gate_conditions = [{
            'type': gate_type,
            'timeout_hours': step_config.get('timeout_hours'),
            'on_timeout': step_config.get('on_timeout', 'FAIL'),
        }]

        # Pour approval: stocker le context_from pour l'UI
        if gate_type == 'approval':
            context_from = step_config.get('context_from', [])
            # context_from liste les step_id dont l'output doit etre affiche a l'approbateur
            gate_conditions[0]['context_from'] = context_from

        return {
            'status': 'WAITING',
            'gate_conditions': gate_conditions,
        }
```

Le `GateEvaluator` existant (`executions/gate_evaluator.py`) et la tache Celery Beat
(`executions/tasks/gates.py`) evaluent les steps WAITING. Quand satisfait :
- `maintenance_window` : le step passe en RUNNING puis COMPLETED
- `approval` : un utilisateur appelle `POST /executions/{id}/steps/{step_id}/approve/`

### 5. Endpoint d'approbation par step

**Fichier a modifier :** `executions/views/approval_views.py`

Nouveau endpoint en complement de l'existant :

```text
POST /executions/{execution_id}/steps/{step_id}/approve/
POST /executions/{execution_id}/steps/{step_id}/reject/
```

Payload :
```json
{
  "comment": "Plan conforme, j'approuve le deploy"
}
```

L'endpoint :
1. Valide que le step est en WAITING avec `gate_type: approval`
2. Met a jour `step.approved_by`, `step.approved_at`, `step.approval_comment`
3. Passe le step en COMPLETED (approve) ou FAILED (reject)
4. Le runtime reprend (le step a un `on_success_step_id` / `on_error_step_id`)

L'endpoint existant `POST /executions/{id}/approve/` (execution-level) est conserve
pour backward compatibility. Il approuve le premier step en WAITING de type approval
dans l'exécution.

### 6. Condition per-environment

**Nouveau :** `executions/step_handlers/condition_evaluator.py`

```python
class StepConditionEvaluator:
    """Evalue si un step doit etre execute ou SKIPPED."""

    def should_execute(self, step_config, execution) -> bool:
        condition = step_config.get('condition')
        if not condition:
            return True

        # environment_in: verifie si l'environment de l'exécution est dans la liste
        env_list = condition.get('environment_in')
        if env_list and execution.environment not in env_list:
            return False

        # when: expression template evaluee (futur)
        # when_expr = condition.get('when')
        # if when_expr: ...

        return True
```

Quand un step est SKIPPED :
- `ExecutionStep` est cree avec `status=SKIPPED`
- `_step_outputs[step_id]` est un dict vide `{}`
- Le runtime passe au step suivant (pas de branchement, traite comme SUCCESS)

### 7. Migration du pre-hook ServiceNow

**Fichier :** `executions/container_workflow_runtime.py:470-551`

La methode `_create_servicenow_change_if_required()` est **supprimee**. Les appels
dans `run()` (ligne 361) et `run_sync()` (ligne 433) sont supprimes.

Le change management est desormais un step `service_call` dans la définition du workflow.

Pour les actions **simples** (pas workflow, un seul step plateforme) qui ont un
`change_type_config` avec `required: true`, le runtime genere automatiquement un
wrapper workflow implicite :

```text
[create-change] → [execute-action] → [close-change]
```

Ceci assure la backward compatibility pour les actions existantes qui ne sont pas
encore migrees vers le format workflow avec steps explicites.

### 8. ServiceNowService — implémentation des operations manquantes

**Fichier :** `services/servicenow_service.py`

#### 8a. `create_change()` — enrichissement du payload

```python
def create_change(
    self,
    change_model_code=None,
    change_type=None,
    short_description="",
    description="",
    **extra_fields,          # NOUVEAU: champs additionnels dynamiques
) -> dict:                   # MODIFIE: retourne dict au lieu de str
    payload = {
        "short_description": short_description,
        "description": description,
        "type": change_type or "normal",
    }
    if change_model_code:
        payload["chg_model"] = change_model_code
    payload.update(extra_fields)  # NOUVEAU: champs dynamiques (cmdb_ci, u_patch_number, etc.)

    # ... appel API existant ...

    # MODIFIE: retourner le dict complet (number + sys_id) pour output_mapping
    result = resp.json().get('result', {})
    return {
        'number': result.get('number', ''),
        'sys_id': result.get('sys_id', ''),
    }
```

#### 8b. `close_change()` — implémentation

```python
def close_change(self, change_id: str, close_code: str = "successful", **kwargs) -> dict:
    url = f"{self.base_url}/api/now/table/change_request"
    # Rechercher le change par number
    resp = client.get(url, params={"number": change_id, "sysparm_limit": 1})
    sys_id = resp.json()['result'][0]['sys_id']

    # Fermer le change
    update_url = f"{self.base_url}/api/now/table/change_request/{sys_id}"
    payload = {
        "state": "3",          # Closed
        "close_code": close_code,
        "close_notes": kwargs.get("close_notes", "Closed by IDP Portal"),
    }
    resp = client.patch(update_url, json=payload)
    return {"closed": True, "sys_id": sys_id}
```

#### 8c. `cancel_change()` — nouvelle operation

```python
def cancel_change(self, change_id: str, reason: str = "", **kwargs) -> dict:
    # Similaire a close_change mais avec state = "4" (Cancelled)
    ...
```

### 9. Service Registry pour les service_call

**Nouveau :** `services/registry.py`

```python
class ServiceRegistry:
    """Registry mapping integration_type → service class."""

    _services: dict[str, type] = {}

    @classmethod
    def register(cls, integration_type: str, service_class: type):
        cls._services[integration_type] = service_class

    @classmethod
    def get_service(cls, integration):
        service_class = cls._services.get(integration.type)
        if not service_class:
            raise ValueError(f"No service registered for type '{integration.type}'")
        auth_headers = build_auth_headers(integration)
        return service_class(base_url=integration.base_url, auth_headers=auth_headers)

# Enregistrement
ServiceRegistry.register('servicenow', ServiceNowService)
ServiceRegistry.register('vault', VaultService)
```

Suit le meme pattern que `AdapterRegistry` (`adapters/registry.py`) mais pour les
services (`IntegrationRole.SERVICE`).

### 10. Structure de fichiers — nouveaux modules

```text
executions/
├── step_handlers/                    # NOUVEAU: un handler par step_type
│   ├── __init__.py
│   ├── platform_handler.py           # Extrait de container_workflow_runtime._execute_step()
│   ├── service_call_handler.py       # Appel service via ServiceRegistry
│   ├── http_request_handler.py       # Appel HTTP brut
│   ├── evaluation_handler.py         # RuleEngine wrapper
│   ├── gate_handler.py               # Creation step WAITING
│   └── condition_evaluator.py        # Evaluation des conditions per-environment
├── template_resolver.py              # NOUVEAU: resolution {{ steps.X.Y }}
├── output_extractor.py               # NOUVEAU: extraction JSONPath
services/
├── registry.py                       # NOUVEAU: ServiceRegistry
├── servicenow_service.py             # MODIFIE: close_change, cancel_change, extra_fields
```

---

## Sécurité

### http_request — validation d'URL

Le step `http_request` permet d'appeler des URLs arbitraires. Pour prevenir les
attaques SSRF (Server-Side Request Forgery) :

- **Allowlist d'hotes** : Configurable via `settings.ALLOWED_HTTP_REQUEST_HOSTS`.
  Seuls les hotes dans la liste sont autorises.
- **Blocklist de reseaux** : Les IPs privees (10.x, 172.16.x, 192.168.x, 127.x)
  sont bloquees par defaut sauf si explicitement autorisees.
- **Schéma HTTPS obligatoire** en production (`DEBUG=False`).

### template_resolver — sandboxing

Le resolver de templates `{{ steps.X.Y }}` utilise `jinja2.sandbox.SandboxedEnvironment`
pour prevenir l'exécution de code arbitraire. Seuls les filtres explicitement
autorises sont disponibles (`join`, `length`, `first`, `last`, `default`).

### service_call — validation d'operation

Le `ServiceCallHandler` valide que l'`operation` demandee existe sur la classe de
service avant de l'appeler. Les methodes prefixees par `_` (privees) ne sont jamais
appelables.

---

## Consequences

### Positives

- **Le portail devient le plan de controle central** : toutes les interactions avec
  les services externes sont orchestrees par le portail, pas par les plateformes.
- **Tracabilite complete** : chaque step (ServiceNow, gate, evaluation, approbation)
  apparait dans la timeline avec son statut, sa duree, son output.
- **Donnees dynamiques dans les changes** : le changement ServiceNow peut inclure la
  liste des databases impactees, le numero de patch, le CI — pas juste le nom de l'action.
- **Approbation contextuelle** : l'approbateur voit l'output du plan Terraform ou de
  la pre-validation, pas juste "Execution #42".
- **Conditions per-environment sur les steps** : plus propre que `change_type_config`.
  Reutilise le statut SKIPPED existant.
- **Extensibilite OCP** : ajouter un nouveau service = enregistrer dans ServiceRegistry.
  Pas de modification du runtime.
- **Reutilisation maximale** : RuleEngine, GateEvaluator, OutputInterpreters, branching
  sont reutilises tels quels. Pas de reecriture.

### Negatives

- **Complexite du runtime** : le `ContainerWorkflowRuntime` passe de "boucle simple
  sur des child executions" a "dispatcher multi-type avec output forwarding".
  Mitigation : extraction dans des handlers separes (SRP).
- **Dependance Jinja2** : le template resolver ajoute une dependance sur Jinja2
  (ou `string.Template` si on limite la syntaxe). Jinja2 est déjà une dependance
  transitive de Django mais pas utilisee directement.
- **Migration des workflows existants** : les actions existantes avec `change_type_config`
  doivent etre migrees vers le format step-based. Mitigation : wrapper automatique
  pour backward compatibility.
- **Gestion des steps async** : les steps `platform` sont async (trigger/poll) tandis
  que les autres sont synchrones. Le runtime doit gerer les deux modes dans la meme
  boucle. Pour les steps `platform`, le runtime doit attendre la completion de la child
  execution avant de passer au step suivant (polling ou callback).

### Neutres

- Les champs `approved_by`, `approved_at`, `approval_comment` sur `Execution` sont
  deprecies mais conserves pour backward compatibility.
- Le statut `PENDING_APPROVAL` sur `Execution` devient un statut derive.
- Les champs `change_type_config` et `gate_config` sur `Action` sont deprecies au
  profit de la définition dans `execution_steps`.

---

## Alternatives Considerees

### Alternative 1 : API externe avec paramètres pre-resolus

- **Description :** L'orchestration reste dans AAP. AAP interroge l'inventaire,
  recupere les données, puis appelle `POST /api/v1/executions/` avec tous les paramètres
  (y compris les champs ServiceNow) déjà resolus. Le portail ne fait que relayer.
- **Raison du rejet :** Le portail reste un proxy passif. Pas de tracabilite des etapes
  intermediaires. Les plateformes continuent de parler entre elles directement
  (AAP → ServiceNow) au lieu de passer par le portail.

### Alternative 2 : Types de steps specifiques par service (servicenow_change, vault_read, etc.)

- **Description :** Chaque operation de chaque service a son propre type de step dans
  le runtime (`servicenow_change`, `servicenow_close`, `vault_read`, `jira_create`).
- **Raison du rejet :** Viole OCP. L'ajout d'un nouveau service nécessite de modifier
  le runtime. Le nombre de types de steps explose. Un type generique `service_call`
  avec `integration_type` + `operation` est plus extensible.

### Alternative 3 : Garder les hooks et ajouter un mécanisme d'enrichissement

- **Description :** Conserver le pre-hook ServiceNow et les post-step policies, mais
  ajouter un mécanisme de template dans `change_type_config` pour resoudre des
  paramètres depuis l'exécution.
- **Raison du rejet :** Ne resout pas le problème fondamental : les hooks s'executent
  avant ou apres les steps, pas entre eux. L'output forwarding est impossible sans
  transformer les hooks en steps. Le branchement conditionnel post-evaluation est
  impossible.

---

## Plan d'implémentation

### Phase 1 : Fondations (prerequis pour tout le reste)

1. **Output context + template resolver** : `_step_outputs`, `StepTemplateResolver`,
   `OutputExtractor`
2. **Condition evaluator** : `StepConditionEvaluator` avec `environment_in`
3. **Step dispatcher** : Refactoring de `_execute_step()` pour dispatcher par `step_type`

### Phase 2 : Step handlers

4. **`service_call` handler** + `ServiceRegistry`
5. **`http_request` handler** (avec validation SSRF)
6. **`evaluation` handler** (reutilise RuleEngine)
7. **`gate` handler** (reutilise GateEvaluator)

### Phase 3 : Approbation et ServiceNow

8. **Endpoint d'approbation par step** (`/steps/{step_id}/approve/`)
9. **`ServiceNowService.close_change()`** et `cancel_change()`
10. **Migration du pre-hook** : suppression de `_create_servicenow_change_if_required()`

### Phase 4 : Backward compatibility et migration

11. **Wrapper automatique** pour actions simples avec `change_type_config`
12. **Deprecation** des champs `change_type_config`, `gate_config`, `approved_by/at/comment`
    sur Execution
13. **Migration des workflows existants** vers le format step-based

---

## References

- `executions/container_workflow_runtime.py` — Runtime actuel des workflows conteneur
- `executions/workflow_runtime.py` — Runtime avec branching (on_success/on_error)
- `executions/workflow_step_executor.py` — Executeur de steps avec policy evaluation
- `executions/gate_evaluator.py` — Evaluateur de gates (maintenance_window, approval)
- `executions/rule_engine.py` — Moteur de regles avec OutputInterpreters
- `executions/models.py` — ExecutionStep, ExecutionStepType, ExecutionStepStatus
- `catalog/models.py` — Action, execution_steps, change_type_config, gate_config
- `integrations/models.py` — Integration, IntegrationRole (PLATFORM vs SERVICE)
- `services/servicenow_service.py` — ServiceNowService (create_change, close_change stub)
- `adapters/registry.py` — AdapterRegistry (pattern a suivre pour ServiceRegistry)

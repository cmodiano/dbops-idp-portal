# Parallel Group — Documentation développeur

> ⚠️ **OBSOLÈTE depuis Story 67.2**
>
> Le mécanisme `parallel_group` (step_type dédié) a été **supprimé du runtime** dans Story 67.2.
> Le parallélisme est désormais géré via le **fan-out explicite** :
> attribuer 2+ valeurs à `on_success_step_ids` ou `on_error_step_ids` d'un step ordinaire
> déclenche automatiquement une exécution parallèle via `ThreadPoolExecutor`.
>
> **Référence architecture** : `docs/architecture/parallel-workflow-actions-analysis.md` — Option B "Fan-out explicite"
>
> Cette page est conservée à titre d'historique et pour la rétrocompatibilité
> de l'export/import CaC (`catalog/services_export_import.py`).

Story 65.1–65.7 | Epic 65 — Workflow Parallel Group (Phase 1 MVP)

---

## 1. Vue d'ensemble

Un `parallel_group` est un type de step de workflow qui exécute plusieurs sous-steps
**en parallèle** via `ThreadPoolExecutor`. Une fois tous les sous-steps terminés
(fan-in), le runtime route vers `on_all_success_step_id` (tous OK) ou
`on_any_error_step_id` (au moins un FAILED — comportement fail-fast).

Cas d'usage typique : exécuter plusieurs backups indépendants simultanément avant
d'appliquer un patch, réduisant le temps total d'exécution.

---

## 2. Schéma JSON du `parallel_group`

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `step_id` | `string` | Oui | Identifiant unique dans le workflow (utilisé pour le routing) |
| `step_type` | `"parallel_group"` | Oui | Discriminant du type de step |
| `name` | `string` | Non | Libellé affiché dans l'UI et les logs |
| `parallel_steps` | `array[string]` | Oui | Liste de `step_id` des membres (min. 2, distincts) |
| `on_all_success_step_id` | `string \| null` | Non | `step_id` suivant si tous les membres réussissent (null = fin) |
| `on_any_error_step_id` | `string \| null` | Non | `step_id` suivant si au moins un membre échoue (null = fin) |
| `condition` | `object` | Non | Condition d'exécution (identique aux autres step_types) |

Les membres (étapes référencées dans `parallel_steps`) sont des steps ordinaires
(`platform`, `service_call`, `http_request`, `evaluation`) et **ne doivent pas** avoir
de `on_success_step_id` / `on_error_step_id` (le runtime ne les suit pas dans ce contexte).

---

## 3. Diagramme de flux d'exécution

```
                    ┌──────────────┐
                    │ parallel_group│
                    │   (step_id)  │
                    └──────┬───────┘
                           │ fan-out (ThreadPoolExecutor)
             ┌─────────────┼──────────────┐
             ▼             ▼              ▼
        ┌─────────┐  ┌─────────┐   ┌─────────┐
        │ member 1│  │ member 2│   │ member N│
        │(platform│  │(platform│   │ ...     │
        │ /svc/..)│  │ /svc/..)│   │         │
        └────┬────┘  └────┬────┘   └────┬────┘
             └─────────────┴──────────────┘
                           │ fan-in (as_completed)
                    ┌──────┴───────┐
                    │ all succeeded?│
                    └──────┬───────┘
               yes ◄───────┴───────► no
                │                    │
   on_all_success_step_id    on_any_error_step_id
          (next step)              (rollback)
```

---

## 4. Exemple complet YAML CaC

```yaml
apiVersion: idp/v1
kind: Action
metadata:
  name: pre-patch-workflow
spec:
  engine: AAP
  platform: AAP
  status: published
  item_type: workflow
  requires_target: false
  execution_steps:
    - step_id: pg-backup
      step_type: parallel_group
      name: Backups parallèles
      parallel_steps:
        - step-backup-db
        - step-backup-config
      on_all_success_step_id: step-apply-patch
      on_any_error_step_id: step-rollback

    - step_id: step-backup-db
      step_type: platform
      name: Backup DB
      referenced_action_id: 10

    - step_id: step-backup-config
      step_type: platform
      name: Backup Config
      referenced_action_id: 11

    - step_id: step-apply-patch
      step_type: platform
      name: Apply Patch
      referenced_action_id: 12
      on_success_step_id: null

    - step_id: step-rollback
      step_type: platform
      name: Rollback
      referenced_action_id: 13
      on_success_step_id: null
```

> **Note Phase 1** : les steps membres de type `platform` requièrent un `referenced_action_id`
> (FK entier vers `Action.id`). La résolution `nom d'action → ID` n'est pas automatique à
> l'import CaC en Phase 1 — les IDs doivent être connus à l'avance. Un export via
> `export_action_yaml()` d'un workflow existant produit un YAML directement réimportable
> (round-trip complet).

---

## 5. Contraintes de validation

Validées par `catalog.validation.validate_workflow_steps()` (Story 65.1) :

| Règle | Détail |
|-------|--------|
| **Min. 2 membres** | `parallel_steps` doit contenir au moins 2 `step_id` distincts |
| **Refs valides** | Chaque `step_id` dans `parallel_steps` doit exister dans le workflow |
| **Pas d'auto-référence** | Le `step_id` du `parallel_group` ne peut pas être dans `parallel_steps` |
| **Pas de nesting** | `parallel_steps` ne peut pas contenir un autre `step_type: parallel_group` |
| **Pas de gates** | `parallel_steps` ne peut pas contenir un `step_type: gate` (bloquant) |
| **Membres sans routing** | Les membres ne doivent pas avoir `on_success_step_id` / `on_error_step_id` |
| **Routing valide** | `on_all_success_step_id` et `on_any_error_step_id` doivent référencer des steps existants et non-membres |
| **Exit point** | Le workflow doit avoir au moins un exit point (un step ou parallel_group avec une ref null) |
| **Pas de cycle** | Détection DFS des cycles dans les chemins de branchement |

Ces règles s'appliquent **aussi bien à l'API REST** (via `services.py`) **qu'à l'import CaC**
(via `services_export_import.py` depuis Story 65.7).

---

## 6. Comportement runtime

**Fichier** : `executions/container_workflow_runtime.py` — méthode `_execute_parallel_group()`

### Fail-fast

Dès qu'un sous-step échoue (FAILED), le `parallel_group` retourne FAILED après que
tous les futures sont terminés (`as_completed`). Il n'y a pas d'annulation des threads
en cours — ils s'exécutent jusqu'à leur propre fin. Le routing suit alors
`on_any_error_step_id`.

### Thread-safety

- Les écritures dans `_step_outputs` sont protégées par `_step_outputs_lock` (RLock).
- Les allocations de `step_order` et l'incrément de `_transition_count` sont pré-alloués
  sous `_step_lock` avant le lancement des threads.
- Chaque thread appelle `close_old_connections()` pour isoler les connexions DB.

### Configuration

```python
# settings.py (optionnel — défaut : 5)
PARALLEL_GROUP_MAX_WORKERS = 5
```

### Création des ExecutionStep

Un `ExecutionStep` est créé pour **chaque sous-step** d'un `parallel_group`. Aucune
ligne n'est créée pour le `parallel_group` lui-même. Le champ `config_step_id` stocke
le `step_id` de la config workflow pour un matching robuste (voir section 7).

---

## 7. Frontend — Matching `WorkflowStep ↔ ExecutionStep`

**Fichier** : `executions/models.py` (champ `config_step_id`, commit `ebf9209`)

Le champ `config_step_id` de `ExecutionStep` stocke le `step_id` de la configuration
workflow (ex. `"step-backup-db"`). Il permet un matching robuste step config ↔ step
execution :

- **Priorité** : matching via `config_step_id` (stable, issu de la config YAML)
- **Fallback** : matching via `step_name` (fragile si le nom change)

Les utilitaires frontend `parallelGroupUtils.ts` utilisent `step_name` pour le matching
(acceptable en Phase 1 car `config_step_id` n'est pas exposé dans l'API frontend).

---

## 8. CaC — Export / Import round-trip

### Export

`export_action_yaml()` sérialise `execution_steps` tel quel depuis le champ JSON Oracle.
Le `parallel_group` est inclus avec tous ses champs (`parallel_steps`,
`on_all_success_step_id`, `on_any_error_step_id`).

### Import avec validation (Story 65.7)

`import_action_yaml()` appelle `validate_workflow_steps()` quand :
- `spec.execution_steps` est présent, ET
- `spec.item_type == "workflow"`

Un YAML invalide (ex. `parallel_steps` avec 1 seul élément) lève une `InvalidStateError`
avec `code="INVALID_WORKFLOW_STEPS"`.

Un `item_type != "workflow"` (ex. `"action"`) n'est **pas validé** (comportement identique
au flux API REST).

---

## 9. Limitations Phase 1

| Limitation | Détail |
|------------|--------|
| **Pas de DAG complet** | Pas de graph arbitraire — le routing reste séquentiel entre groupes |
| **Pas de gates dans le groupe** | `step_type: gate` interdit dans `parallel_steps` (bloquant → incompatible ThreadPoolExecutor) |
| **Pas de nesting** | Un `parallel_group` ne peut pas être membre d'un autre `parallel_group` |
| **Fail-fast uniquement** | Pas d'option "continuer malgré les erreurs" (continue-on-error) |
| **Pas d'annulation partielle** | Les threads en cours ne sont pas annulés si un frère échoue |
| **config_step_id non exposé frontend** | Le matching frontend reste basé sur `step_name` |

---

## 10. Fichiers clés

| Chemin | Rôle |
|--------|------|
| `catalog/validation.py` | `validate_workflow_steps()` — règles structurelles + cycles |
| `catalog/services_export_import.py` | Export/import CaC avec validation parallel_group (Story 65.7) |
| `catalog/services.py` | API REST — appel `validate_workflow_steps()` via serializer |
| `catalog/tests/test_parallel_group_validation.py` | Tests unitaires validation (Story 65.1) |
| `catalog/tests/test_services_export_import.py` | Tests CaC export/import + `ExportImportParallelGroupTests` (Story 65.7) |
| `executions/container_workflow_runtime.py` | Runtime — `_execute_parallel_group()`, `_execute_step_for_parallel()` |
| `executions/models.py` | `ExecutionStep.config_step_id` — matching robuste (commit ebf9209) |
| `executions/tests/test_container_workflow_runtime_parallel.py` | Tests runtime parallèle (Story 65.2) |
| `src/components/workflow/parallelGroupUtils.ts` | Utilitaires frontend matching + statut agrégé |
| `src/components/workflow/workflowConversion.ts` | Conversion TypeScript ↔ backend format |

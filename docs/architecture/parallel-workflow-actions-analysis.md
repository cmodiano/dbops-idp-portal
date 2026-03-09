# Analyse : Actions parallèles dans les workflows

**Date** : 2026-03-08
**Contexte** : Évaluer la complexité d'ajouter le support d'exécution parallèle de steps dans notre moteur de workflow, en s'inspirant des solutions du marché.

> **Implémentation réalisée :** L'Option A (Parallel Group MVP) a été implémentée dans l'Epic 65 (Stories 65.1–65.7).
> Documentation d'implémentation : [`idp-portal/django_backend/docs/parallel-group.md`](../../idp-portal/django_backend/docs/parallel-group.md)

---

## 1. État actuel de notre codebase

### 1.1 Architecture actuelle

Notre système de workflow repose sur :

| Composant | Fichier | Rôle |
|-----------|---------|------|
| **Modèle de données** | `catalog/models.py` → `Action` | `item_type='workflow'`, `execution_steps` (JSON CLOB) |
| **Runtime linéaire** | `executions/workflow_runtime.py` → `WorkflowRuntime` | Boucle `while` séquentielle avec branching success/error |
| **Runtime conteneur** | `executions/container_workflow_runtime.py` → `ContainerWorkflowRuntime` | Itération `for step in self.workflow_steps` — **purement séquentiel** |
| **Modèle d'exécution** | `executions/models.py` → `ExecutionStep` | `step_order` (INTEGER, unique par exécution) |
| **UI Builder** | `components/admin/WorkflowBuilderCanvas.tsx` | React Flow avec nodes et edges (success/error handles) |
| **Conversion** | `utils/workflowConversion.ts` | `WorkflowStep[]` ↔ React Flow nodes/edges |

### 1.2 Schéma JSON actuel d'un step

```json
{
  "order": 1,
  "step_id": "uuid-1",
  "step_type": "platform",
  "name": "Backup DB",
  "referenced_action_id": 42,
  "on_success_step_id": "uuid-2",
  "on_error_step_id": "uuid-error",
  "retry_enabled": true,
  "retry_max_attempts": 3,
  "retry_interval_seconds": 60,
  "retry_backoff_multiplier": 2.0
}
```

### 1.3 Limites actuelles — Pourquoi le parallélisme n'est pas supporté

1. **Branching = exclusif** : `on_success_step_id` et `on_error_step_id` pointent vers **UN SEUL** step chacun — pas de fan-out.

2. **Exécution séquentielle** :
   - `WorkflowRuntime.run()` : boucle `while` qui suit `current_step_id → next_step_id` (un seul chemin actif).
   - `ContainerWorkflowRuntime._execute_workflow_steps()` : boucle `for step in self.workflow_steps` — itère séquentiellement.

3. **`step_order` unique** : `unique_together = [['execution', 'step_order']]` — un seul step peut avoir un `step_order` donné. Pas de notion de steps au même "niveau".

4. **UI** : `WorkflowStepNode` a 2 source handles (`success` et `error`), chacun connecté à **un seul** target. Pas de multi-connexion depuis un même handle.

5. **Pas de notion de "join"** : Aucun mécanisme pour attendre que N branches se terminent avant de continuer (barrier/join/synchronize).

---

## 2. Comment les solutions du marché gèrent le parallélisme

### 2.1 GitHub Actions — `needs` + matrice de jobs

**Modèle** : DAG implicite via la propriété `needs` sur chaque job.

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    steps: [...]

  test-unit:
    needs: build          # démarre après build
    runs-on: ubuntu-latest

  test-integration:
    needs: build          # démarre après build (parallèle avec test-unit)
    runs-on: ubuntu-latest

  deploy:
    needs: [test-unit, test-integration]  # attend les 2 (join)
    runs-on: ubuntu-latest
```

**Points clés** :
- **Fan-out** : Plusieurs jobs peuvent déclarer `needs: [même-job]` → exécution parallèle
- **Join** : Un job avec `needs: [A, B]` attend que A ET B soient terminés
- **Granularité** : Le parallélisme est au niveau **job** (pas step)
- **Pas de runtime complex** : GitHub orchestre via un scheduler qui résout le DAG

### 2.2 Argo Workflows (Kubernetes) — DAG template

**Modèle** : Templates DAG explicites avec `dependencies`.

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Workflow
spec:
  templates:
  - name: diamond
    dag:
      tasks:
      - name: A
        template: echo
      - name: B
        dependencies: [A]
        template: echo
      - name: C
        dependencies: [A]    # B et C en parallèle après A
        template: echo
      - name: D
        dependencies: [B, C] # D attend B et C (join)
        template: echo
```

**Points clés** :
- **DAG explicite** : Chaque task déclare ses `dependencies[]`
- Le contrôleur Argo résout le graphe et lance les tasks éligibles (deps satisfaites)
- Supporte aussi `steps` (séquentiel) ET `dag` (parallèle)
- **UI** : Visualisation native en DAG avec statuts temps réel

### 2.3 Apache Airflow — DAG Python

**Modèle** : Opérateurs liés par `>>` (bitshift) ou `.set_downstream()`.

```python
from airflow import DAG
from airflow.operators.python import PythonOperator

with DAG('parallel_example') as dag:
    start = PythonOperator(task_id='start', ...)

    branch_a = PythonOperator(task_id='branch_a', ...)
    branch_b = PythonOperator(task_id='branch_b', ...)

    join = PythonOperator(task_id='join', ...)

    start >> [branch_a, branch_b] >> join
    # start → fan-out vers A et B (parallèle) → join attend les 2
```

**Points clés** :
- `>>` vers une liste = fan-out (parallèle)
- Liste `>>` vers un task = join (barrier)
- Le scheduler Airflow poll le DAG et lance les tasks dont les deps sont satisfaites
- **Trigger rules** : `all_success`, `one_success`, `all_done`, etc.

### 2.4 n8n — Branches visuelles

**Modèle** : Noeud avec **multiples outputs** connectés à différents noeuds.

- Un noeud peut avoir plusieurs connexions sortantes → exécution parallèle des branches
- Pas de "join" explicite — chaque branche est indépendante par défaut
- Merge node pour combiner les résultats de branches parallèles

**Points clés** :
- **UI-first** : Très visuel, drag-and-drop
- Un output connecté à N noeuds = fan-out
- `Merge` node explicite pour le join (modes: Append, Combine, Choose Branch, etc.)

### 2.5 Temporal.io — Parallélisme programmatique

**Modèle** : Code (Go/Java/Python/TypeScript), pas de DAG déclaratif.

```python
# Python SDK
async def parallel_workflow(ctx):
    result_a = workflow.start_activity("task_a", ...)
    result_b = workflow.start_activity("task_b", ...)

    # Attendre les deux (join)
    a, b = await asyncio.gather(result_a, result_b)

    await workflow.execute_activity("final_task", ...)
```

**Points clés** :
- Parallélisme natif via `asyncio.gather()` ou `Promise.all()`
- Pas de notion de DAG — c'est du code, les développeurs contrôlent tout
- Join = `await` sur toutes les promises/futures
- **Très flexible** mais nécessite du code (pas de UI builder)

### 2.6 Prefect — Task dependencies + `.map()`

```python
from prefect import flow, task

@task
def process_item(item):
    return item * 2

@flow
def parallel_flow():
    items = [1, 2, 3, 4, 5]
    results = process_item.map(items)  # Parallèle automatique
    # results est une liste de futures
```

**Points clés** :
- `.map()` = fan-out automatique
- `.submit()` = lancement async (parallèle)
- `.result()` = join (attendre le résultat)
- DAG implicite par les dépendances de données

---

## 3. Synthèse des patterns

| Pattern | Utilisé par | Description |
|---------|------------|-------------|
| **DAG avec `dependencies[]`** | Argo, Airflow, Prefect | Chaque step déclare ses prérequis. Le scheduler résout et lance les steps éligibles |
| **`needs` / références inverses** | GitHub Actions | Chaque job déclare de quoi il dépend (identique au DAG) |
| **Multi-output connections** | n8n | Un noeud connecté à N noeuds = fan-out visuel |
| **Code-based (gather/all)** | Temporal, Prefect | Le développeur contrôle le parallélisme dans le code |
| **Join/Barrier node** | n8n (Merge), Argo, Airflow | Un step qui attend N prédécesseurs avant de démarrer |

**Consensus du marché** : Le pattern dominant est le **DAG avec dependencies** — c'est la solution la plus flexible et la plus proche de notre architecture existante.

---

## 4. Proposition d'implémentation pour notre codebase

### 4.1 Approche recommandée : DAG avec `depends_on`

Transformer notre modèle de branching linéaire en un **DAG** où chaque step déclare ses dépendances.

#### Nouveau schéma JSON pour un step :

```json
{
  "order": 1,
  "step_id": "backup-db",
  "step_type": "platform",
  "name": "Backup DB",
  "referenced_action_id": 42,
  "depends_on": [],
  "on_success_step_id": null,
  "on_error_step_id": "rollback-step",
  "retry_enabled": true
}
```

**Nouveaux champs** :

| Champ | Type | Description |
|-------|------|-------------|
| `depends_on` | `string[]` | Liste de `step_id` dont ce step dépend. Vide = step initial (root). |

**Règles** :
- Un step démarre quand **TOUS** ses `depends_on` sont `COMPLETED`
- Si un `depends_on` est `FAILED`, le step est `SKIPPED` (ou suit la politique d'erreur)
- Steps sans `depends_on` sont des roots (démarrent en premier)
- Steps avec les mêmes `depends_on` s'exécutent en parallèle

#### Exemple de workflow parallèle :

```json
[
  {
    "step_id": "start",
    "name": "Validate Environment",
    "depends_on": []
  },
  {
    "step_id": "backup-db",
    "name": "Backup Database",
    "depends_on": ["start"]
  },
  {
    "step_id": "backup-config",
    "name": "Backup Config Files",
    "depends_on": ["start"]
  },
  {
    "step_id": "apply-patch",
    "name": "Apply Database Patch",
    "depends_on": ["backup-db", "backup-config"]
  },
  {
    "step_id": "verify",
    "name": "Run Verification",
    "depends_on": ["apply-patch"]
  }
]
```

```
        [start]
       /       \
  [backup-db]  [backup-config]   ← parallèle
       \       /
    [apply-patch]                ← join (attend les 2)
         |
      [verify]
```

### 4.2 Changements backend requis

#### A. Modèle de données

| Fichier | Changement | Complexité |
|---------|-----------|------------|
| Migration SQL `V115` | Aucune migration structurelle — `depends_on` est dans le JSON CLOB `EXECUTION_STEPS` | Faible |
| `ExecutionStep` model | Ajouter un champ `parallel_group` ou utiliser un même `step_order` pour les steps parallèles | Moyenne |
| | **Alternative** : Relaxer la contrainte `unique_together = [['execution', 'step_order']]` | Moyenne |

#### B. Runtime Engine (`container_workflow_runtime.py`)

C'est le changement le **plus complexe**. Il faut passer d'une boucle `for` séquentielle à un **scheduler DAG**.

```python
# Pseudo-code du nouveau runtime
class ParallelWorkflowRuntime:
    def _execute_workflow_steps(self) -> ExecutionStatus:
        dag = self._build_dag(self.workflow_steps)
        completed_steps: set[str] = set()
        failed_steps: set[str] = set()

        while not dag.all_done():
            # Trouver les steps éligibles (deps satisfaites)
            eligible = dag.get_eligible_steps(completed_steps, failed_steps)

            if not eligible:
                break  # Deadlock ou tout terminé

            # Exécuter en parallèle (ThreadPoolExecutor ou asyncio)
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(self._execute_step, step): step
                    for step in eligible
                }
                for future in as_completed(futures):
                    step = futures[future]
                    status = future.result()
                    if status == ExecutionStatus.COMPLETED:
                        completed_steps.add(step['step_id'])
                    elif status == ExecutionStatus.FAILED:
                        failed_steps.add(step['step_id'])

        # Déterminer le statut final
        if failed_steps:
            return ExecutionStatus.FAILED
        return ExecutionStatus.COMPLETED
```

**Estimation de complexité** : **Élevée**

Sous-tâches :
1. Construction du DAG à partir du JSON
2. Résolution des steps éligibles (topological sort partiel)
3. Exécution parallèle (ThreadPoolExecutor ou Celery group)
4. Gestion des erreurs par branche (fail-fast vs continue)
5. Join/barrier logic
6. Intégration avec le système de cancellation existant
7. Intégration avec les gates (WAITING) en mode parallèle
8. Thread-safety sur `_step_outputs` (accès concurrent)
9. Mise à jour du `step_order` pour supporter les steps parallèles

#### C. Validation (`validators/workflow_validator.py`)

| Validation | Description |
|-----------|-------------|
| Détection de cycles dans le DAG | Algorithme de Kahn ou DFS (déjà existant côté frontend, à porter backend) |
| Vérification que `depends_on` référence des `step_id` existants | Nouveau |
| Détection de deadlocks (dépendances circulaires) | Nouveau |
| Au moins un step root (sans `depends_on`) | Nouveau |

#### D. Système de gates en parallèle

Complexité supplémentaire : Si un step parallèle est un `gate` (approval/maintenance_window), le runtime doit :
1. Marquer ce step comme WAITING
2. Continuer les autres branches en parallèle (celles qui ne dépendent pas du gate)
3. Quand le gate est résolu, reprendre les steps qui en dépendaient

### 4.3 Changements frontend requis

#### A. `WorkflowStepNode.tsx`

- Ajouter un **handle d'entrée supplémentaire** ou permettre **multiples connexions** vers le même handle d'entrée (pour le join)
- Ajouter un handle de sortie "next" (en plus de success/error) ou permettre **multiples connexions** depuis le handle success

#### B. `workflowConversion.ts`

- `reactFlowToWorkflowSteps()` : Calculer `depends_on` à partir des edges entrantes (au lieu de `on_success_step_id`)
- `workflowStepsToReactFlow()` : Convertir `depends_on` en edges entrantes multiples

#### C. `workflowValidation.ts`

- Adapter la détection de cycles au modèle DAG
- Valider les `depends_on`
- Ajouter validation de la structure parallèle (pas de step orphelin)

#### D. `useWorkflowGraph.ts`

- `onConnect` : Permettre multiple edges sortantes depuis un même source handle
- Supprimer la logique qui filtre les edges existantes du même sourceHandle

#### E. `WorkflowExecutionGraph.tsx`

- Adapter la visualisation pour afficher les steps parallèles côte à côte
- Afficher les barres de progression parallèles

#### F. Nouveau : `ParallelGroupNode` ou layout horizontal

Pour que l'UI rende visuellement clair que des steps sont parallèles, il faudrait :
- Soit un layout automatique (dagre/elk) qui positionne les noeuds en parallèle
- Soit un noeud "groupe parallèle" explicite (comme n8n)

### 4.4 Backward compatibility

| Aspect | Impact |
|--------|--------|
| Workflows existants sans `depends_on` | Aucun impact — traités comme chaîne linéaire (chaque step dépend du précédent par `order`) |
| `on_success_step_id` / `on_error_step_id` | Conservés pour le branching conditionnel — `depends_on` gère le parallélisme, les branches gèrent les chemins conditionnels |
| `step_order` | Utilisé comme tiebreaker pour l'ordre d'affichage, plus comme ordre d'exécution strict |
| CaC (YAML export/import) | Doit supporter le nouveau champ `depends_on` |

---

## 5. Estimation de complexité

### Effort global

| Composant | Estimation | Risque |
|-----------|-----------|--------|
| Schema JSON (ajout `depends_on`) | **S** (1-2 jours) | Faible |
| Backend DAG scheduler | **XL** (5-8 jours) | Élevé — concurrence, thread-safety, gates |
| Backend validation | **M** (2-3 jours) | Moyen |
| Frontend multi-connexion | **L** (3-5 jours) | Moyen — React Flow support natif |
| Frontend layout parallèle | **L** (3-5 jours) | Moyen — dagre/elk layout |
| Frontend execution graph | **M** (2-3 jours) | Moyen |
| Tests unitaires + intégration | **L** (3-5 jours) | Moyen |
| Documentation / CaC | **S** (1-2 jours) | Faible |
| **TOTAL** | **20-33 jours** | |

### Facteurs de risque

1. **Thread-safety** : `_step_outputs` partagé entre threads parallèles. Nécessite un `threading.Lock` ou un `ConcurrentDict`.
2. **Gate + Parallélisme** : Le gate WAITING actuel arrête tout le workflow. En mode parallèle, il ne devrait bloquer que les steps qui en dépendent.
3. **Cancellation cascade** : Annuler un workflow parallèle nécessite d'annuler toutes les branches en cours.
4. **Observabilité** : Les WebSocket events (`WORKFLOW_EVENTS`) doivent refléter les steps parallèles en temps réel.
5. **Base Oracle** : La contrainte `unique_together = [['execution', 'step_order']]` doit être relâchée ou contournée.

---

## 6. Alternatives simplifiées

### Option A : "Parallel Group" (comme n8n)

Au lieu d'un DAG complet, introduire un **noeud de groupe parallèle** qui encapsule N steps.

```json
{
  "step_id": "parallel-backup",
  "step_type": "parallel_group",
  "name": "Backups parallèles",
  "parallel_steps": ["backup-db", "backup-config"],
  "on_all_success_step_id": "apply-patch",
  "on_any_error_step_id": "rollback"
}
```

**Avantages** : Plus simple, pas besoin de DAG complet
**Inconvénients** : Pas de parallélisme imbriqué, moins flexible

**Estimation** : 12-18 jours

### Option B : "Fan-out / Fan-in" explicite

Ajouter deux nouveaux `step_type` : `fan_out` et `fan_in`.

```json
[
  { "step_id": "start", "step_type": "platform", "on_success_step_id": "fork" },
  { "step_id": "fork", "step_type": "fan_out", "parallel_targets": ["a", "b", "c"] },
  { "step_id": "a", "step_type": "platform", "on_success_step_id": "join" },
  { "step_id": "b", "step_type": "platform", "on_success_step_id": "join" },
  { "step_id": "c", "step_type": "platform", "on_success_step_id": "join" },
  { "step_id": "join", "step_type": "fan_in", "wait_for": ["a", "b", "c"], "on_success_step_id": "end" }
]
```

**Avantages** : Explicite, facile à comprendre dans l'UI
**Inconvénients** : Verbeux, nécessite des nœuds supplémentaires

**Estimation** : 15-22 jours

---

## 7. Recommandation

### Approche progressive en 2 phases

**Phase 1 — Option A "Parallel Group"** (MVP)
- Plus simple à implémenter
- Couvre 80% des cas d'usage (fan-out simple après un step → fan-in avant le step suivant)
- Pas de changement de schéma majeur (le parallel_group est un step_type spécial)
- Le runtime lance les sous-steps avec `ThreadPoolExecutor` et attend `as_completed()`
- L'UI affiche un noeud "groupe" qui s'expand pour montrer les sous-steps

**Phase 2 — DAG complet avec `depends_on`** (si les besoins le justifient)
- Ajouter `depends_on` au schéma JSON
- Refactorer le runtime vers un DAG scheduler
- Offrir un parallélisme arbitraire (pas limité aux groupes)

### Décision à prendre

La question clé est : **Quels cas d'usage concrets ont besoin du parallélisme ?**

- Si c'est principalement "lancer 2-3 backups en parallèle avant de continuer", l'Option A suffit.
- Si c'est des DAG complexes avec des diamants, des joins partiels, etc., il faut le DAG complet.

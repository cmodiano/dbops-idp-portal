# Epic 76 : Reconcile Crash Recovery — Reprise et robustesse du réconciliateur

**Date :** 2026-03-12  
**Statut :** Draft  
**Périmètre :** `executions/tasks/reconcile.py`, `executions/tasks/gates.py`, `executions/container_workflow_runtime.py`

---

## 1. Contexte et problème

Après un crash du backend, le réconciliateur (`reconcile_stale_executions`) détecte les exécutions RUNNING orphelines et tente de les récupérer. Plusieurs lacunes critiques empêchent une reprise complète :

| Scénario | Comportement actuel | Attendu |
|----------|--------------------|---------|
| Crash pendant un job platform (avec `platform_job_id`) | ✅ Polling réattaché, reprise possible | OK |
| Crash pendant un gate WAITING | ✅ `evaluate_waiting_gates` continue normalement | OK |
| **Crash entre deux étapes** | ❌ Marqué FAILED, pas de reprise | Reprendre depuis la dernière étape complétée |
| Crash pendant une étape non-platform (service_call, http, eval) | ❌ Étape marquée FAILED, pas de retry | Option de retry ou reprise |
| Crash d'une exécution enfant | ❌ Non détecté par le réconciliateur | Inclure les enfants dans le périmètre |
| Workflow long (> 10 min) sain | ⚠️ Risque de faux positif (stale) | Détection plus précise |

---

## 2. Lacunes détaillées

### 2.1 Crash entre deux étapes → FAILED sans reprise

**Problème :** Si l'app crashe après que l'étape N est terminée mais avant que l'étape N+1 démarre, le réconciliateur trouve une exécution RUNNING sans aucune étape RUNNING et marque l'exécution FAILED — sans tenter de reprendre depuis la dernière étape complétée.

**Cause :** Le code `resume_container_workflow_from_gate` montre exactement comment reconstruire le contexte (`_step_outputs`) et reprendre — ce mécanisme n'est pas réutilisé dans le chemin « no running step ».

### 2.2 `_step_outputs` en mémoire uniquement

Le dictionnaire des sorties d'étapes (utilisé pour les `input_mapping` des étapes suivantes) n'est pas persisté directement. Il est reconstruit depuis la DB uniquement dans le chemin gate-resume — pas dans le réconciliateur de crash.

### 2.3 Détection de staleness imprécise

Le réconciliateur utilise `created_at < now - 10min` (pas de `updated_at`, pas de heartbeat). Un workflow long mais sain (> 10 min) peut être incorrectement marqué stale. Le seuil `RECONCILE_STALE_THRESHOLD_MINUTES` doit être configuré manuellement.

### 2.4 Exécutions enfants ignorées

Le réconciliateur filtre sur `parent_execution__isnull=True`. Si une exécution enfant crashe, son parent reste bloqué indéfiniment.

### 2.5 Actions individuelles — reprise du polling

Pour les steps RUNNING avec `platform_job_id`, le polling est réattaché. Il faut s'assurer que le polling est correctement rétabli lorsque l'action individuelle était en cours d'exécution (vérifier le cas des child executions dont `platform_job_id` = child_execution_id).

---

## 3. Objectifs de l'Epic

1. **Reprise crash entre étapes** : Adopter la même logique que `resume_container_workflow_from_gate` pour reprendre au lieu de marquer FAILED.
2. **Exécutions enfants** : Inclure les exécutions enfants dans le périmètre du réconciliateur.
3. **Détection staleness** : Améliorer la détection (updated_at, heartbeat ou seuil configurable).
4. **Actions individuelles** : Vérifier et documenter le comportement du polling pour les actions individuelles RUNNING.

---

## 4. Stories

### Story 76.1 — Reprise crash entre étapes (container workflow)

**Priorité :** Haute  
**Effort estimé :** M

**Description :**  
Quand le réconciliateur trouve une exécution RUNNING sans étape RUNNING, au lieu de marquer FAILED immédiatement, vérifier si c'est un container workflow (ADR-007). Si oui, reprendre en réutilisant la logique de `resume_container_workflow_from_gate` :

- Reconstruire `_step_outputs` depuis les `ExecutionStep` COMPLETED en DB (via `OutputExtractor`).
- Calculer la prochaine vague d'étapes à partir du graphe de dépendances (`get_next_step_ids`, `apply_join_policy`).
- Reprendre l'exécution via `ContainerWorkflowRuntime._execute_workflow_steps()`.

**Acceptance criteria :**
- AC1 : Exécution RUNNING, aucune étape RUNNING, container workflow avec étapes COMPLETED → reprise automatique (pas de FAILED).
- AC2 : Si la prochaine vague est vide (workflow terminé) → marquer l'exécution COMPLETED.
- AC3 : Si ce n'est pas un container workflow ou reprise impossible → fallback sur `_mark_execution_failed` (comportement actuel).
- AC4 : Tests unitaires couvrant le scénario crash entre étapes.

**Fichiers impactés :** `executions/tasks/reconcile.py`, `executions/tasks/gates.py` (extraction logique commune si pertinent).

---

### Story 76.2 — Inclusion des exécutions enfants dans le réconciliateur

**Priorité :** Moyenne  
**Effort estimé :** S

**Description :**  
Actuellement, le réconciliateur filtre `parent_execution__isnull=True` et ne traite que les exécutions racine. Une exécution enfant (workflow step avec child execution) qui crashe laisse le parent bloqué.

**Acceptance criteria :**
- AC1 : Le réconciliateur traite aussi les exécutions avec `parent_execution_id` non null (exécutions enfants).
- AC2 : Pour une exécution enfant RUNNING stale : appliquer la même logique (reattach polling si platform_job_id, ou reprise si crash entre étapes pour workflow enfant).
- AC3 : Ne pas dupliquer le traitement si le parent et l'enfant sont tous deux stale — éviter les conflits (ordre de traitement, idempotence).
- AC4 : Tests couvrant le scénario enfant stale.

**Fichiers impactés :** `executions/tasks/reconcile.py`.

---

### Story 76.3 — Amélioration de la détection de staleness

**Priorité :** Moyenne  
**Effort estimé :** M

**Description :**  
Remplacer ou compléter le critère `created_at < now - threshold` par une détection plus précise pour éviter les faux positifs sur les workflows longs mais sains.

**Options à évaluer :**
- Ajouter un champ `updated_at` sur `Execution` (migration) et l'utiliser comme signal de fraîcheur.
- Ajouter un heartbeat (mise à jour périodique de `updated_at` pendant l'exécution).
- Conserver `created_at` mais documenter le seuil et permettre une configuration par environnement.

**Acceptance criteria :**
- AC1 : Un workflow sain de plus de 10 minutes n'est pas marqué stale à tort.
- AC2 : Le seuil reste configurable via `RECONCILE_STALE_THRESHOLD_MINUTES` (ou équivalent).
- AC3 : Si `updated_at` est ajouté : migration + mise à jour du champ à chaque progression significative (step start/complete).
- AC4 : Documentation de la stratégie de staleness dans le module reconcile.

**Fichiers impactés :** `executions/tasks/reconcile.py`, `executions/models.py` (si migration), `executions/container_workflow_runtime.py` (si heartbeat).

---

### Story 76.4 — Vérification du polling pour actions individuelles RUNNING

**Priorité :** Basse  
**Effort estimé :** S

**Description :**  
S'assurer que le polling est correctement réattaché lorsque une action individuelle (step platform avec `platform_job_id`) était RUNNING au moment du crash. Vérifier les cas limites :
- Step platform dans un container workflow : `platform_job_id` = child_execution_id (pas un vrai job AAP/TC).
- Action simple (non-workflow) : `platform_job_id` = ID du job sur la plateforme.

**Acceptance criteria :**
- AC1 : Documenter le comportement actuel du reattach pour chaque type (action simple vs step platform workflow).
- AC2 : Si le reattach ne fonctionne pas pour les steps platform workflow (child_execution_id), proposer une stratégie (ex. : vérifier le statut du child, le marquer FAILED si stale).
- AC3 : Tests ou scénarios de validation pour le reattach sur action individuelle.

**Fichiers impactés :** `executions/tasks/reconcile.py`, documentation.

---

### Story 76.5 — Retry pour étapes non-platform (service_call, http, eval)

**Priorité :** Basse  
**Effort estimé :** M

**Description :**  
Actuellement, une étape RUNNING sans `platform_job_id` (service_call, http_request, evaluation) est marquée FAILED car il n'y a pas de job à réattacher. Ces étapes s'exécutent de façon synchrone ; en cas de crash pendant l'exécution, un retry serait possible.

**Acceptance criteria :**
- AC1 : Définir une stratégie (retry automatique vs FAILED) pour les steps RUNNING sans platform_job_id.
- AC2 : Si retry : ré-exécuter l'étape (avec gardes idempotence si applicable).
- AC3 : Si pas de retry : conserver le comportement actuel (FAILED) et documenter.
- AC4 : Tests pour le scénario choisi.

**Fichiers impactés :** `executions/tasks/reconcile.py`, `executions/container_workflow_runtime.py` (si retry).

---

## 5. Dépendances et ordre de réalisation

| Story | Dépendances | Ordre suggéré |
|-------|-------------|---------------|
| 76.1 | Aucune | 1 |
| 76.2 | Aucune | 2 |
| 76.3 | Aucune (peut être en parallèle) | 2 ou 3 |
| 76.4 | 76.1 (contexte) | 3 |
| 76.5 | 76.1 (pattern de reprise) | 4 |

---

## 6. Références

- `executions/tasks/reconcile.py` — Implémentation actuelle
- `executions/tasks/gates.py` — `resume_container_workflow_from_gate`, logique de reprise
- `executions/container_workflow_runtime.py` — `_step_outputs`, `_execute_workflow_steps`
- `executions/container_routing.py` — `get_next_step_ids`
- `executions/container_parallel.py` — `apply_join_policy`
- ADR-007 — Workflow step-based change management

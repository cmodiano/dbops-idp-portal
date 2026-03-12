# ADR-011 : Workflow — Parallélisme via Fan-Out Multi-Connexion

**Date :** 2025-09-01
**Statut :** Accepté
**Décideurs :** Équipe IDP Portal

## Contexte

Le portail IDP doit orchestrer des workflows où plusieurs étapes peuvent s'exécuter
en parallèle (ex : patch plusieurs serveurs simultanément, lancer plusieurs vérifications
en même temps).

**Epic 65** a introduit un type de step dédié `parallel_group` : un step spécial contenant
une liste de `parallel_steps` (les membres du groupe), avec un routing distinct pour le
succès global (`on_all_success_step_id`) et l'échec partiel. Ce mécanisme présentait
plusieurs problèmes.

## Problème du `parallel_group` (Epic 65)

1. **UX en deux temps** : l'utilisateur devait créer un `parallel_group` *puis* y ajouter
   des membres — opération en deux étapes non intuitive sur le canvas.

2. **Représentation visuelle ambiguë** : les membres du groupe apparaissaient comme des
   steps isolés sur le canvas ; la relation de groupe n'était pas visuellement évidente.

3. **Type de step artificiel** : `parallel_group` est un meta-step sans correspondance
   dans la réalité métier — il n'exécute rien, il orchestre uniquement.

4. **Schéma JSON hétérogène** : le `parallel_group` utilisait `parallel_steps: string[]`
   (liste de step_ids membres), incompatible avec le routage classique
   `on_success_step_id`/`on_error_step_id`.

## Décision

**Fan-out explicite via multi-connexion** : le parallélisme est exprimé directement dans
le graphe du workflow via plusieurs connexions depuis le même port de sortie. Le graphe
est la source de vérité — plus besoin d'un type de step dédié.

### Schéma JSON du step (Epic 67)

Remplacement du singulier par le pluriel pour tous les steps :

| Ancien (Epic 65) | Nouveau (Epic 67) | Sémantique |
|-----------------|-------------------|------------|
| `on_success_step_id: string` | `on_success_step_ids: string[]` | 1 connexion = séquentiel, 2+ = parallèle |
| `on_error_step_id: string` | `on_error_step_ids: string[]` | Idem sur branche erreur |
| — | `join_policy: string` | Politique de convergence |

```json
{
  "step_id": "step-deploy",
  "step_type": "platform",
  "on_success_step_ids": ["step-verify-a", "step-verify-b"],
  "on_error_step_ids": ["step-rollback"]
}
```

### `join_policy` (Epic 67, Story 67.8)

Lorsque plusieurs branches parallèles convergent vers un même step, la `join_policy`
détermine la condition d'exécution :

| Valeur | Condition | Défaut |
|--------|-----------|--------|
| `all_success` | Tous les prédécesseurs OK | ✓ |
| `one_success` | Au moins un prédécesseur OK | |
| `all_done` | Tous terminés (peu importe le statut) | |
| `all_failed` | Tous les prédécesseurs en échec | |
| `one_failed` | Au moins un prédécesseur en échec | |

### Runtime : `ContainerWorkflowRuntime`

L'exécution utilise un algorithme BFS par **vagues** (`executions/container_workflow_runtime.py`) :

1. **Vague 1 step** : exécution séquentielle directe (optimisation — évite `ThreadPoolExecutor`)
2. **Vague 2+ steps** : `_execute_fan_out()` avec `ThreadPoolExecutor(max_workers=PARALLEL_GROUP_MAX_WORKERS)`
3. **`ParallelContext`** : contexte thread-safe passé à chaque step pour l'attribution de l'ordre

`PARALLEL_GROUP_MAX_WORKERS` (défaut : 5, configurable) limite le parallélisme maximum.
En test (`test_settings.py`), la valeur est 1 pour éviter les conflits SQLite multi-threads.

### Rétrocompatibilité

Les workflows créés avant Epic 67 avec `on_success_step_id` (singulier) continuent de
fonctionner : si `on_success_step_ids` est absent, le moteur traite `on_success_step_id`
comme `[on_success_step_id]` (tableau d'un élément).

### Migration (Story 67.6)

La commande `python manage.py migrate_parallel_group` convertit les workflows existants
contenant des steps `parallel_group` en équivalents multi-connexion :

1. Localise les steps `step_type: 'parallel_group'` dans les `execution_steps` de toutes les actions
2. Modifie le prédécesseur du `parallel_group` pour pointer directement vers les membres
   (`on_success_step_ids` = anciens `parallel_steps`)
3. Supprime le step `parallel_group` du workflow
4. Options : `--dry-run` (prévisualisation) et `--action-name=<nom>` (ciblage)

## Conséquences

### Positives
- UX naturelle : relier deux steps depuis le même port = parallélisme immédiat
- Le graphe visuel représente fidèlement le comportement d'exécution
- `join_policy` expressive et configurable par step convergent
- Suppression d'un type de step artificiel (`parallel_group`) — modèle conceptuel simplifié
- Compatible avec le routing existant (BFS + fan-out transparent)

### Négatives
- `join_policy` limitée aux prédécesseurs de la **vague courante** — les convergences
  cross-waves (prédécesseurs dans des vagues BFS différentes) ne sont pas supportées
- Les gates (`RUNNING`) en fan-out sont traitées comme `FAILED` — le support complet
  des gates dans les branches parallèles est reporté
- `ThreadPoolExecutor` partage les connexions DB Django par thread — `close_old_connections()`
  appelé en début de chaque sous-tâche (thread-safety)

### Neutres
- `PARALLEL_GROUP_MAX_WORKERS = 5` configurable par environnement
- La commande `migrate_parallel_group` est idempotente et supporte `--dry-run`

## Alternatives Considérées

### Alternative 1 : Argo Workflows / n8n-style DAG avec `depends_on` explicite

- **Description :** Modèle de DAG avec déclaration explicite des dépendances
  (`depends_on: [step-a, step-b]`) plutôt que des connexions
- **Raison du rejet :** Moins intuitif pour les utilisateurs non-techniques. L'approche
  multi-connexion (graphe = source de vérité) est plus naturelle et alignée avec les
  standards du marché (GitHub Actions `needs:`, Temporal workflows).

### Alternative 2 : Conserver `parallel_group` avec amélioration UX

- **Description :** Améliorer l'UX du `parallel_group` Epic 65 (auto-création, meilleure
  représentation visuelle)
- **Raison du rejet :** La complexité du type artificiel `parallel_group` persiste.
  Le consensus d'équipe était que le modèle multi-connexion est intrinsèquement plus
  simple et extensible.

### Alternative 3 : Celery group/chord pour le parallélisme

- **Description :** Utiliser les primitives Celery `group()` et `chord()` pour
  l'orchestration parallèle
- **Raison du rejet :** Le runtime conteneur gère le parallélisme en mémoire (un seul
  processus worker). L'overhead Celery pour chaque step individuel serait disproportionné
  et nécessiterait une refonte majeure du runtime.

## Références

- `executions/container_workflow_runtime.py` — Runtime parallèle (`_execute_fan_out`, `_apply_join_policy`, `ParallelContext`)
- `catalog/management/commands/migrate_parallel_group.py` — Commande de migration (Story 67.6)
- `catalog/serializers.py:535` — Suppression de `parallel_group` de l'enum `step_type`
- `idp_backend/settings.py:816-818` — `PARALLEL_GROUP_MAX_WORKERS`
- `docs/parallel-group.md` — Documentation technique (marquée obsolète, conservée pour référence)
- Epic 65 — Introduction `parallel_group` (phase 1)
- Epic 67 — Migration vers multi-connexion fan-out (phase 2)
- Story 67.2 — Suppression `parallel_group` du runtime, introduction BFS-wave
- Story 67.3 — `join_policy` pour les steps convergents
- Story 67.6 — Commande `migrate_parallel_group`
- Story 67.8 — `all_failed` / `one_failed` join policies
- ADR-007 — Architecture steps unifiée (workflow step-based)

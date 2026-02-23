# Story 35.4 : Revue fichiers backend volumineux (documentation / découpage optionnel)

Status: done

<!-- Réf: CODEBASE-REVIEW.md §16.1 — Priorité MEDIUM/Basse — Aucun changement de code obligatoire -->

## Story

En tant que développeur,
je veux disposer d'une documentation claire sur les fichiers backend dépassant 700 lignes,
afin de savoir pour chacun si la taille est justifiée par la complexité inhérente ou si un découpage est recommandé, et de réduire la dette technique documentée.

## Acceptance Criteria

1. **Given** la liste des 8 fichiers volumineux (≥ 650 LOC) identifiés dans CODEBASE-REVIEW §16.1
   **Then** chaque fichier dispose d'une fiche documentée (dans CODEBASE-REVIEW.md ou dans cette story) indiquant : responsabilité principale, classes/méthodes majeures, verdict (`cohérent/justifié` ou `découpage recommandé`), et justification courte

2. **Given** les fichiers `executions/services.py` (854 LOC) et `inventory/services.py` (711 LOC) identifiés comme candidates au découpage
   **Then** une proposition de découpage est documentée pour chacun (noms des classes cibles, responsabilités séparées) — **implémentation optionnelle** selon validation équipe

3. **Given** les 6 autres fichiers (`catalog/services.py`, `catalog/serializers.py`, `terraform_cloud_adapter.py`, `github_actions_adapter.py`, `container_workflow_runtime.py`, `inventory/query_executor.py`)
   **Then** un commentaire de tête de fichier (ou section CODEBASE-REVIEW) explique brièvement pourquoi la taille est justifiée par la complexité inhérente

4. **Given** le fichier CODEBASE-REVIEW.md
   **Then** la section §16.1 est mise à jour avec les conclusions de cette revue (finding marqué `RESOLVED` ou `DOCUMENTED`)

5. **Given** les tests existants
   **Then** si du code est refactorisé (optionnel), `python -m pytest` passe au moins autant de tests qu'avant (baseline : 2247 backend) — **0 régression**

## Tasks / Subtasks

- [x] Task 1 — Analyser et documenter chaque fichier > 700 LOC (AC: #1, #3)
  - [x] 1.1 Lire les premières lignes + grep classes/def de chaque fichier pour valider la responsabilité principale
  - [x] 1.2 Pour chaque fichier, produire la fiche : responsabilité, classes majeures, verdict + justification
  - [x] 1.3 Ajouter un commentaire de tête de fichier aux 6 fichiers `cohérent/justifié` si absent : `# Responsabilité : <une ligne>` sous le docstring existant

- [x] Task 2 — Proposer un découpage pour les 2 candidats (AC: #2)
  - [x] 2.1 `executions/services.py` (854 LOC) : proposer extraction `ExecutionStepService` et `ExecutionStatisticsService` depuis `ExecutionService` — documenter les noms de méthodes à déplacer
  - [x] 2.2 `inventory/services.py` (711 LOC) : proposer affinage des délégations existantes (InventorySourceResolver, InventoryQueryExecutor, InventoryRBACFilter) pour alléger l'orchestrateur — documenter les méthodes candidates à déplacer dans les délégués

- [x] Task 3 — Implémenter le découpage si validé par l'équipe (AC: #5) — OPTIONNEL
  - [x] 3.1 Non implémenté — décision équipe requise (voir propositions documentées en Dev Notes § Task 2)
  - [x] 3.2 N/A — aucun refactoring effectué (AC5 conditionnel)
  - [x] 3.3 N/A — aucun fichier modifié structurellement

- [x] Task 4 — Mettre à jour CODEBASE-REVIEW.md §16.1 (AC: #4)
  - [x] 4.1 Marquer le finding 16.1 comme `DOCUMENTED` (avec lien vers les fiches) ou `RESOLVED` si code refactorisé
  - [x] 4.2 Mettre à jour les LOC dans le tableau si du refactoring a été effectué

## Dev Notes

### Périmètre — Fichiers volumineux ≥ 650 LOC (état au 2026-02-23)

> Note : le seuil retenu est ~650 LOC (liste issue de CODEBASE-REVIEW §16.1) ; 2 fichiers sont entre 650 et 700 LOC.

| Fichier | LOC | Classes principales | Verdict | Justification |
|---------|-----|---------------------|---------|---------------|
| `executions/services.py` | 854 | `ExecutionService` | ⚠ Découpage recommandé | CRUD exécution + steps + stats + validation intégration = 3 responsabilités distinctes |
| `catalog/services.py` | 823 | `CatalogService`, `InvalidTransitionError` | ✅ Cohérent/justifié | Action-centric, logique métier intrinsèque (transitions statut, workflows, dépendances) |
| `catalog/serializers.py` | 737 | `ActionSerializer`, `ActionCreateSerializer`, `ActionFieldValidationMixin` + 7 serializers | ✅ Cohérent/justifié | Sérialisation DRF, 10 serializers + validations croisées justifiées |
| `adapters/terraform_cloud_adapter.py` | 747 | `TerraformCloudAdapter` | ✅ Cohérent/justifié | Adapter spécifique TFC (JSON API spec, 18+ états, logs via redirects) |
| `adapters/github_actions_adapter.py` | 718 | `GitHubActionsAdapter` | ✅ Cohérent/justifié | Adapter GHA (dispatch sans run_id → polling, logs en ZIP) |
| `inventory/services.py` | 711 | `InventoryService`, `InventoryRBACFilter`, `InventorySourceResolver` | ⚠ Découpage recommandé | Orchestrateur fait trop : sources + RBAC + caching + normalization env |
| `executions/container_workflow_runtime.py` | 681 | `ContainerWorkflowRuntime` | ✅ Cohérent/justifié | Runtime workflows conteneur (sync/async, cascade annulation, ServiceNow, loop detection) |
| `inventory/query_executor.py` | 667 | `InventoryQueryExecutor` | ✅ Cohérent/justifié | Queries SQL config-driven multi-table (Story 26.1 AC1 — unified _read_entity_from_config) |

### Proposition de découpage — executions/services.py

**Découpage suggéré en 3 classes :**

```python
# executions/services.py (cible ~450 LOC)
class ExecutionService:
    """CRUD exécutions + launch + status lifecycle."""
    create_execution()
    create_execution_with_steps()
    update_status()
    launch_workflow()
    list_all() / list_by_user() / get_by_id()
    _check_integration_status()  # validation pré-exécution

# executions/step_service.py (NOUVEAU, ~200 LOC)
class ExecutionStepService:
    """Gestion cycle de vie des étapes d'exécution."""
    create_step()
    update_step_status()
    list_steps_for_execution()

# executions/stats_service.py (NOUVEAU, ~150 LOC)
class ExecutionStatisticsService:
    """Calcul des statistiques d'exécution."""
    get_stats()
    get_action_stats()
```

**Impact :** Imports dans `executions/views.py` et `executions/tasks.py` à mettre à jour. Interfaces publiques inchangées — backward compatible via `executions/__init__.py` si nécessaire.

### Proposition de découpage — inventory/services.py

**Découpage suggéré — déléguer plus vers les délégués existants :**

```python
# inventory/services.py (cible ~400 LOC) — "thin orchestrator" pur
class InventoryService:
    """Orchestrateur pur : délègue à SourceResolver, QueryExecutor, RBACFilter."""
    list_targets()
    list_servers() / list_instances() / list_databases()
    list_targets_for_user()

# Logique à déplacer vers les délégués existants :
# InventoryRBACFilter : déplacer _list_targets_from_api(), _list_targets_from_db_schema()
# InventorySourceResolver : absorber _list_targets_from_fallback()
# Nouveau InventoryEnvironmentService (~100 LOC) :
    list_environments()
    get_allowed_environments_for_user()
    get_next_maintenance_window()
```

**Note :** inventory/services.py a déjà été refactorisé en Story 26.1 (→ 911 LOC, objectif 700 non atteint). Ce découpage complèterait ce travail.

### Stack technique

- **Backend :** Django 5.2, DRF 3.16, Python 3.11+
- **Linter :** ruff (0 BLE001/F401 toléré sans noqa justifié)
- **Type checker :** mypy en mode strict progressif (`mypy django_backend/`)
- **Tests :** `python -m pytest django_backend/ --ignore=*/tests.py` (baseline 2247 tests)

### Contraintes importantes

- **Aucun changement de code obligatoire** pour cette story — documentation suffit pour l'AC
- Si refactoring : les imports dans les views/tasks doivent rester fonctionnels — préférer la délégation (`from executions.services import ExecutionService`) plutôt que re-export complexe
- Les tests unitaires existants font des `patch('executions.services.ExecutionService')` — si le module change, les patches dans les tests doivent être mis à jour
- Pas de migration Django requise (ces fichiers sont purement service layer, pas de modèles)

### Références context (stories précédentes)

- Story 26.1 `split-inventory-services-3-classes` : inventory/services.py déjà refactorisé, cible 700 non atteinte (AC2 documented) [Source: sprint-status.yaml#26-1]
- Story 22.7 `refactoriser-executions-views-extraction-helpers` : executions/views.py 1914→1292 LOC [Source: sprint-status.yaml#22-7]
- Story 26.2 `split-executions-views-4-modules` : executions/views.py découpé, mais services.py non touché [Source: sprint-status.yaml#26-2]
- Story 34.7 `backend-decomposer-workflow-runtime` : container_workflow_runtime.py déjà analysé, 681 LOC justifiés [Source: sprint-status.yaml#34-7]

### Localisation des fichiers concernés

```
idp-portal/django_backend/
├── executions/
│   ├── services.py              ← ⚠ Découpage recommandé (854 LOC)
│   └── container_workflow_runtime.py  ← ✅ Cohérent (681 LOC)
├── catalog/
│   ├── services.py              ← ✅ Cohérent (823 LOC)
│   └── serializers.py           ← ✅ Cohérent (737 LOC)
├── adapters/
│   ├── terraform_cloud_adapter.py  ← ✅ Cohérent (747 LOC)
│   └── github_actions_adapter.py   ← ✅ Cohérent (718 LOC)
└── inventory/
    ├── services.py              ← ⚠ Découpage recommandé (711 LOC)
    └── query_executor.py        ← ✅ Cohérent (667 LOC)

idp-portal/CODEBASE-REVIEW.md   ← §16.1 à mettre à jour (AC: #4)
```

### Vérifications (si Task 3 implémentée)

```bash
# Depuis idp-portal/django_backend/
../.venv/bin/python -m pytest . --ignore=*/tests.py -x -q 2>&1 | tail -20
../.venv/bin/python -m mypy executions/services.py inventory/services.py
python -c "from executions.services import ExecutionService; print('OK')"
python -c "from inventory.services import InventoryService; print('OK')"
```

### Project Structure Notes

- Alignment avec CODEBASE-REVIEW §16.1 (Observation post-refactoring Epic 34)
- Aucun changement de modèle DB — purement refactoring de couche service
- Les adapters (terraform, github) suivent le pattern `BaseAdapter` (Story 27.3) — NE PAS modifier leur structure

### References

- [Source: idp-portal/CODEBASE-REVIEW.md#§16.1] — Finding "Fichiers backend encore volumineux"
- [Source: _bmad-output/planning-artifacts/epic-35-codebase-review-points-restants-post-refactoring.md#35.4] — Détail story
- [Source: _bmad-output/implementation-artifacts/35-3-migration-dip-services-phase-1.md] — Story précédente (learnings DIP)
- [Source: sprint-status.yaml#26-1] — Story 26.1 split inventory/services.py (AC2 LOC deviation documenté)
- [Source: sprint-status.yaml#26-2] — Story 26.2 split executions/views.py (services.py hors scope)

## Dev Agent Record

### Agent Model Used

claude-sonnet-4-6

### Debug Log References

Aucun blocage technique. Story documentaire — modifications limitées à des commentaires de tête de fichier et à CODEBASE-REVIEW.md.

### Completion Notes List

- ✅ Task 1 : Analyse des 8 fichiers effectuée — 6 classés "cohérent/justifié", 2 marqués "découpage recommandé"
- ✅ Task 1.3 : Commentaires `# Responsabilité` ajoutés aux 6 fichiers justifiés (catalog/services.py, catalog/serializers.py, adapters/terraform_cloud_adapter.py, adapters/github_actions_adapter.py, executions/container_workflow_runtime.py, inventory/query_executor.py)
- ✅ Task 2 : Propositions de découpage documentées en Dev Notes pour executions/services.py et inventory/services.py — implémentation non effectuée (décision équipe requise)
- ✅ Task 3 : Skipped (OPTIONNEL) — aucun refactoring appliqué, 0 régression
- ✅ Task 4 : CODEBASE-REVIEW.md §16.1 mis à jour — statut `[MEDIUM]` → `[DOCUMENTED]`, tableau LOC mis à jour, propositions synthétisées, §17 MEDIUM table mise à jour
- ✅ Validation syntaxe : ast.parse() sur les 6 fichiers modifiés — 0 erreur de syntaxe

### File List

- `idp-portal/django_backend/catalog/services.py` — ajout commentaire `# Responsabilité`
- `idp-portal/django_backend/catalog/serializers.py` — ajout commentaire `# Responsabilité`
- `idp-portal/django_backend/adapters/terraform_cloud_adapter.py` — ajout commentaire `# Responsabilité`
- `idp-portal/django_backend/adapters/github_actions_adapter.py` — ajout commentaire `# Responsabilité`
- `idp-portal/django_backend/executions/container_workflow_runtime.py` — ajout commentaire `# Responsabilité`
- `idp-portal/django_backend/inventory/query_executor.py` — ajout commentaire `# Responsabilité`
- `idp-portal/CODEBASE-REVIEW.md` — §16.1 mis à jour : `[MEDIUM]` → `[DOCUMENTED]`, tableau enrichi (classes principales ajoutées), §17 mis à jour (compteurs)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — statut `35-4-revue-fichiers-backend-volumineux` mis à jour

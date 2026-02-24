# Story 38.1: Quick wins backend — N+1, double update, TODO, log

Status: done

## Story

As a membre de l'équipe technique,
I want corriger les 4 findings backend à effort faible/trivial (NEW-BE-1, NEW-BE-2, NEW-BE-3, NEW-BE-5),
so that la qualité du code est maintenue, les N+1 supprimés, les TODOs obsolètes nettoyés et les logs enrichis pour le debugging.

## Acceptance Criteria

1. **NEW-BE-1 — N+1 supprimé** : `_validate_workflow_can_be_published()` utilise `Action.objects.in_bulk()` au lieu d'un `Action.objects.get()` en boucle. Une seule requête DB au lieu de N.
2. **NEW-BE-2 — Double update fusionné** : Les deux `.update()` consécutifs dans `container_workflow_runtime.py` sont fusionnés en un seul appel `.update()`.
3. **NEW-BE-3 — TODO obsolète supprimé** : Le commentaire TODO « These endpoints are not yet implemented » dans `executions/services.py` est supprimé (les endpoints existent dans `approval_views.py`).
4. **NEW-BE-5 — Log enrichi** : Le log `unknown_execution_status_for_audit` inclut `execution_id` pour faciliter le debugging.
5. **Aucune régression** : Les tests existants passent. Comportement inchangé (validation workflow, runtime conteneur, audit).

## Tasks / Subtasks

- [x] Task 1 — NEW-BE-1 : Fix N+1 dans `_validate_workflow_can_be_published` (AC: #1)
  - [x] 1.1 Remplacer la boucle `Action.objects.get(id=ref_id)` par `Action.objects.in_bulk(ref_ids)`
  - [x] 1.2 Adapter le code pour itérer sur le dict `found_actions` (missing = clé absente du dict)
  - [x] 1.3 Vérifier que les tests existants passent
- [x] Task 2 — NEW-BE-2 : Fusionner double `.update()` (AC: #2)
  - [x] 2.1 Combiner les deux `.update()` en un seul avec `status=COMPLETED, started_at=now, completed_at=now`
  - [x] 2.2 Vérifier que les tests existants passent
- [x] Task 3 — NEW-BE-3 : Supprimer TODO obsolète (AC: #3)
  - [x] 3.1 Supprimer le bloc de commentaire TODO lignes 435-438
  - [x] 3.2 Optionnel : vérifier que `approval_views.py` contient bien les endpoints `/approve` et `/reject`
- [x] Task 4 — NEW-BE-5 : Ajouter `execution_id` au log (AC: #4)
  - [x] 4.1 Ajouter `execution_id=execution.id` au `logger.warning()` concerné
  - [x] 4.2 Vérifier que les tests existants passent
- [x] Task 5 — Validation globale (AC: #5)
  - [x] 5.1 Lancer `pytest` sur les modules `catalog` et `executions`

## Dev Notes

### NEW-BE-1 — N+1 dans `_validate_workflow_can_be_published()`

**Fichier :** `catalog/services.py` lignes 62-73

**Code actuel (N+1) :**
```python
for ref_id in ref_ids:
    try:
        ref_action = Action.objects.get(id=ref_id)  # ← N requêtes
    except Action.DoesNotExist:
        missing.append(ref_id)
        continue
    if ref_action.status != ActionStatus.PUBLISHED:
        not_published.append({
            "referenced_action_id": ref_id,
            "action_name": ref_action.name,
            "status": ref_action.status,
        })
```

**Pattern existant à réutiliser** — `executions/utils/workflow_parsing.py` lignes 239-249 :
```python
int_ref_ids = [int(r) for r in referenced_action_ids]
found_actions: dict[int, Action] = Action.objects.in_bulk(int_ref_ids)
missing_ids: list[int] = []
not_published: list[dict] = []
for ref_id in int_ref_ids:
    ref_action = found_actions.get(ref_id)
    if ref_action is None:
        missing_ids.append(ref_id)
```

**Fix :** Appliquer le même pattern `in_bulk` — une seule requête, itérer sur le dict.

---

### NEW-BE-2 — Double `.update()` dans container_workflow_runtime

**Fichier :** `executions/container_workflow_runtime.py` lignes 318-327

**Code actuel :**
```python
now = timezone.now()
Execution.objects.filter(id=child_execution.id).update(
    status=ExecutionStatus.RUNNING,
    started_at=now,
)
completed_at = timezone.now()
Execution.objects.filter(id=child_execution.id).update(
    status=ExecutionStatus.COMPLETED,
    completed_at=completed_at,
)
```

**Problème :** 2 round-trips DB. Le statut RUNNING n'est jamais visible (immédiatement écrasé par COMPLETED). Deux appels `timezone.now()` redondants.

**Fix :** Fusionner en un seul `.update()` :
```python
now = timezone.now()
Execution.objects.filter(id=child_execution.id).update(
    status=ExecutionStatus.COMPLETED,
    started_at=now,
    completed_at=now,
)
```

---

### NEW-BE-3 — TODO obsolète

**Fichier :** `executions/services.py` lignes 435-438

**Code actuel :**
```python
# TODO (Story 7.4): Approval transitions must use dedicated endpoints:
#   - PENDING_APPROVAL → RUNNING via POST /api/v1/executions/{id}/approve
#   - PENDING_APPROVAL → REJECTED via POST /api/v1/executions/{id}/reject
#   These endpoints are not yet implemented.
```

**Problème :** Les endpoints existent déjà dans `approval_views.py`. Le TODO est obsolète.

**Fix :** Supprimer le bloc de 4 lignes de commentaire. Le garde-fou de sécurité (lignes 428-434, PENDING_APPROVAL → SUBMITTED interdit) reste en place.

---

### NEW-BE-5 — Log sans `execution_id`

**Fichier :** `executions/services.py` lignes 503-509

**Code actuel :**
```python
if not audit_action_type:
    logger.warning(
        "unknown_execution_status_for_audit",
        status=new_status,
        correlation_id=get_correlation_id()
    )
    audit_action_type = AuditActionType.EXECUTION_SUBMITTED  # Fallback
```

**Fix :** Ajouter `execution_id=execution.id` :
```python
logger.warning(
    "unknown_execution_status_for_audit",
    execution_id=execution.id,
    status=new_status,
    correlation_id=get_correlation_id()
)
```

### Project Structure Notes

- Backend : `idp-portal/django_backend/`
- Modules concernés : `catalog/`, `executions/`
- Logging : structlog JSON (structuré), intégré Splunk
- ORM : Django ORM standard pour les modèles `Action`, `Execution`
- Pattern `in_bulk` déjà validé dans `workflow_parsing.py`

### References

- [Source: idp-portal/CODEBASE-REVIEW.md §17 — Audit #3 nouveaux findings]
- [Source: _bmad-output/planning-artifacts/epic-38-codebase-review-audit-3-corrections.md — Story 38.1]
- [Source: idp-portal/django_backend/catalog/services.py — lignes 62-73]
- [Source: idp-portal/django_backend/executions/container_workflow_runtime.py — lignes 318-327]
- [Source: idp-portal/django_backend/executions/services.py — lignes 435-438, 503-509]
- [Source: idp-portal/django_backend/executions/utils/workflow_parsing.py — lignes 239-249 (pattern in_bulk)]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

Aucun problème rencontré.

### Completion Notes List

- **Task 1 (NEW-BE-1):** Remplacé la boucle `Action.objects.get()` N+1 par `Action.objects.in_bulk()` dans `_validate_workflow_can_be_published()`. Pattern identique à celui déjà utilisé dans `workflow_parsing.py`. 413 tests catalog passent.
- **Task 2 (NEW-BE-2):** Fusionné les deux `.update()` consécutifs en un seul appel dans `container_workflow_runtime.py`. Le statut RUNNING intermédiaire (jamais visible) est supprimé, un seul `timezone.now()` utilisé. 716 tests executions passent.
- **Task 3 (NEW-BE-3):** Supprimé le bloc TODO obsolète (4 lignes) dans `executions/services.py`. Vérifié que les endpoints `/approve` et `/reject` existent dans `executions/views/approval_views.py`.
- **Task 4 (NEW-BE-5):** Ajouté `execution_id=execution.id` au `logger.warning("unknown_execution_status_for_audit")` dans `executions/services.py`.
- **Task 5 (Validation):** 1129 tests passent (catalog + executions), 0 échecs, 3 skipped. Aucune régression.

### File List

- `idp-portal/django_backend/catalog/services.py` — modifié (N+1 → in_bulk)
- `idp-portal/django_backend/executions/container_workflow_runtime.py` — modifié (double update → single update)
- `idp-portal/django_backend/executions/services.py` — modifié (TODO supprimé + execution_id ajouté au log)

## Senior Developer Review (AI)

**Reviewer:** Cyrille — 2026-02-23
**Verdict:** ✅ Approuvé avec fix mineur appliqué

### Résumé

4 ACs vérifiées contre le code réel et les diffs git. Toutes les tasks marquées [x] sont confirmées implémentées. Les endpoints `/approve` et `/reject` existent bien dans `approval_views.py`.

### Findings

| # | Sévérité | Description | Statut |
|---|----------|-------------|--------|
| M1 | MEDIUM | `services.py:434-435` — Double ligne commentaire vide après suppression du TODO | ✅ Fixé |
| L1 | LOW | `catalog/services.py:60` — Conversion `int()` sans gestion d'erreur explicite (comportement équivalent à l'original) | Action item |
| L2 | LOW | Aucun nouveau test unitaire pour le refactor `in_bulk` | Action item |

### Review Follow-ups (AI)

- [ ] [AI-Review][LOW] Ajouter gestion d'erreur explicite sur `int()` conversion dans `_validate_workflow_can_be_published` [catalog/services.py:60]
- [ ] [AI-Review][LOW] Ajouter test unitaire dédié pour le chemin `in_bulk` (mix actions existantes/manquantes/non-publiées) [catalog/services.py:61]

## Change Log

- 2026-02-23: Implémentation story 38.1 — 4 quick wins backend (NEW-BE-1, NEW-BE-2, NEW-BE-3, NEW-BE-5). Toutes les ACs satisfaites, 1129 tests passent sans régression.
- 2026-02-23: Code review (AI) — 1 MEDIUM fixé (double ligne commentaire vide), 2 LOW comme action items.

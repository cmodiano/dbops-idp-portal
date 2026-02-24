# Epic 38 : Codebase Review Audit #3 — Corrections des issues ouvertes

**En tant qu'**équipe technique,  
**je veux** corriger les issues restantes identifiées dans le CODEBASE-REVIEW (audit #3, 2026-02-23),  
**afin de** maintenir la qualité du code, réduire les N+1, supprimer les TODOs obsolètes et consolider les duplications résiduelles.

---

## Contexte

**Source :** `idp-portal/CODEBASE-REVIEW.md` — sections 17 (Audit #3 — Nouveaux findings), 18 (Récapitulatif par priorité).

**Bilan audit #3 :** 99/105 findings résolus. **6 issues ouvertes** (2 MEDIUM, 4 LOW) + 1 INFO. Aucune issue CRITICAL ni sécurité. Les corrections ciblent :
- **Backend :** N+1 dans `_validate_workflow_can_be_published`, double `.update()` redondant (container workflow), TODO obsolète, log sans `execution_id`, `asyncio.run()` dans Celery.
- **Frontend :** Consolidation STATUS_CONFIG résiduel (SOLID-FE-10), nested key props redondants (NEW-FE-1).
- **Backlog :** Audit `except Exception` résiduels (16.2), migration DIP services (SOLID-FE-4 — effort élevé).

---

## Portée (scope)

- Quick wins backend (NEW-BE-1, NEW-BE-2, NEW-BE-3, NEW-BE-5).
- Quick wins frontend (SOLID-FE-10, NEW-FE-1).
- Backend async / logging (NEW-BE-4).
- Optionnel : audit 16.2 (except Exception), SOLID-FE-4 (DIP) en backlog.

---

## Definition of Done (epic)

- [ ] NEW-BE-1 : N+1 supprimé dans `_validate_workflow_can_be_published()` (in_bulk).
- [ ] NEW-BE-2 : Double `.update()` fusionné en un seul dans container_workflow_runtime.
- [ ] NEW-BE-3 : TODO obsolète supprimé ou mis à jour (executions/services.py).
- [ ] NEW-BE-5 : Log `unknown_execution_status_for_audit` inclut `execution_id`.
- [ ] SOLID-FE-10 : STATUS_CONFIG résiduel consolidé (au moins 3 des 5 composants depuis execution-status.ts ou extension documentée).
- [ ] NEW-FE-1 : Nested key props redondants corrigés (TopNav).
- [ ] NEW-BE-4 (backlog) : asyncio.run() remplacé par async_to_sync dans polling.py.

---

## Stories

| # | Story | Issues | Priorité |
|---|-------|--------|----------|
| 38.1 | Quick wins backend — N+1, double update, TODO, log | NEW-BE-1, NEW-BE-2, NEW-BE-3, NEW-BE-5 | Haute |
| 38.2 | Consolidation STATUS_CONFIG résiduel (frontend) | SOLID-FE-10, 16.4 | Haute |
| 38.3 | Frontend — Nested key props TopNav | NEW-FE-1 | Moyenne |
| 38.4 | Backend — asyncio.run → async_to_sync (Celery polling) | NEW-BE-4 | Basse |
| 38.5 | Audit except Exception résiduels (documentation) | 16.2 | Backlog |
| 38.6 | Migration DIP services — composants vers hooks | SOLID-FE-4 | Backlog |

---

## Détail des stories

### Story 38.1 : Quick wins backend — N+1, double update, TODO, log

**Objectif :** Corriger les 4 findings backend à effort faible/trivial (NEW-BE-1, NEW-BE-2, NEW-BE-3, NEW-BE-5).

**NEW-BE-1 [MEDIUM] — N+1 dans `_validate_workflow_can_be_published()`**
- **Fichier :** `catalog/services.py` (lignes 62-73).
- **Problème :** Boucle `for ref_id in ref_ids` avec `Action.objects.get(id=ref_id)` → N requêtes.
- **Fix :** Remplacer par `Action.objects.in_bulk(ref_ids)` (pattern déjà utilisé dans `workflow_parsing.py:241`).

**NEW-BE-2 [MEDIUM] — Double `.update()` redondant**
- **Fichier :** `executions/container_workflow_runtime.py` (lignes 317-326).
- **Problème :** Deux `.update()` consécutifs sur la même exécution (RUNNING puis COMPLETED) — redondant, 2x `timezone.now()`.
- **Fix :** Fusionner en un seul `.update(status=COMPLETED, started_at=now, completed_at=now)` (ou équivalent selon le flux).

**NEW-BE-3 [LOW] — TODO obsolète**
- **Fichier :** `executions/services.py` (lignes 435-438).
- **Problème :** Commentaire « These endpoints are not yet implemented » alors que `approval_views.py` les implémente.
- **Fix :** Supprimer ou mettre à jour le commentaire.

**NEW-BE-5 [LOW] — Log sans execution_id**
- **Fichier :** `executions/services.py` (lignes 504-507).
- **Problème :** Log `unknown_execution_status_for_audit` sans `execution_id` — debugging difficile.
- **Fix :** Ajouter `execution_id=execution_id` (ou champ id approprié) au log.

**Critères d'acceptation :**
- Les 4 corrections sont appliquées ; les tests existants passent.
- Aucune régression sur le comportement (validation workflow, runtime conteneur, audit).

---

### Story 38.2 : Consolidation STATUS_CONFIG résiduel (frontend)

**Objectif :** Réduire la duplication des mappings de statut (SOLID-FE-10, 16.4). Au moins 3 des 5 composants utilisent une source partagée ou une extension documentée.

**Composants concernés :**
- `ExecutionView.tsx` (ligne ~45) — status exécution → importer ou étendre depuis `utils/execution-status.ts`.
- `StepDetailDrawer.tsx` (ligne ~22) — status step → idem.
- `WorkflowExecutionGraph.tsx` (ligne ~52) — couleurs nœuds graph → consolider si possible.
- `IntegrationsTable.tsx` (ligne ~16) — status intégration (domaine différent) : documenter pourquoi config local conservé.
- `ComparisonExecutionsDrawer.tsx` (ligne ~36) — cas spécialisé : documenter ou importer si aligné.

**Critères d'acceptation :**
- Au moins 3 des 5 composants utilisent une source partagée (`execution-status.ts`) ou une extension documentée.
- Les 2 restants ont un commentaire expliquant pourquoi le config local est conservé (domaine différent / cas spécialisé).
- Pas de régression visuelle (couleurs, libellés statut).

---

### Story 38.3 : Frontend — Nested key props TopNav

**Objectif :** Corriger NEW-FE-1 — clés React redondantes (key sur button + wrapper) dans `TopNav.tsx` (lignes 155-203).

**Critères d'acceptation :**
- Une seule `key` pertinente par élément listé (pas de nested key redondante).
- Comportement et rendu inchangés ; tests existants passent.

---

### Story 38.4 : Backend — asyncio.run → async_to_sync (Celery polling)

**Objectif :** Remplacer `asyncio.run()` par `async_to_sync()` (asgiref) dans `executions/tasks/polling.py` (lignes 313, 320) pour éviter les conflits event loop dans les tâches Celery (NEW-BE-4).

**Critères d'acceptation :**
- Les appels concernés utilisent `async_to_sync()` (pattern déjà utilisé ailleurs dans le projet).
- Les tests de polling (et tâches Celery concernées) passent ; pas de régression.

---

### Story 38.5 : Audit except Exception résiduels (documentation)

**Objectif :** Documenter ou justifier les 77 occurrences de `except Exception` dans le backend (40 fichiers). Vérifier que chaque cas est soit `noqa: BLE001` avec justification, soit remplacé par une exception plus spécifique (16.2).

**Critères d'acceptation :**
- Liste (ou tableau) des fichiers/lignes audités avec statut : OK (documenté/justifié) ou FIX (corrigé).
- Aucun `except Exception` avalant l'erreur sans trace (log ou remontée) sans justification documentée.
- Optionnel : corrections ciblées sur les fichiers les plus sensibles (ex. container_workflow_runtime, services).

---

### Story 38.6 : Migration DIP services — composants vers hooks (backlog)

**Objectif :** Réduire le couplage direct aux services (SOLID-FE-4). Migration progressive des ~25 composants qui importent directement `admin_service`, `catalog_service`, `execution_service` vers hooks ou injection (props/context). Effort élevé — à traiter par lots.

**Périmètre (exemples CODEBASE-REVIEW) :**
- `ExecutionWizard.tsx`, `ActionWizard.tsx`, `WorkflowStepsEditor.tsx`, `ProfileForm.tsx`, `ProfileWizard.tsx`, `IntegrationForm.tsx`, etc.
- Pattern cible : même approche que `useCatalogState`, `useAuditFilters`, `useExecutionWizardState` — logique dans un hook, services injectés ou fournis par un context.

**Critères d'acceptation :**
- Liste des composants choisis pour un premier lot (5–8 composants) avec justification.
- Au moins 3 composants migrés vers hook ou DI (plus d'import direct du service dans le composant).
- Tests existants verts ; pas de régression.

**Note :** Cette story peut rester en backlog jusqu'à planification d'un sprint dédié.

---

## Références

- `idp-portal/CODEBASE-REVIEW.md` — §17 (Audit #3), §18 (Récapitulatif), §14–16 (SOLID, observations).
- Epic 34, 35 — précédentes vagues de corrections Codebase Review.

# Epic 88 — Correction des findings de la revue de code (Audit #8)

**Date :** 2026-03-16  
**Statut :** Backlog  
**Référence :** `idp-portal/CODEBASE-REVIEW.md` §27 — Audit #8 post-refactoring Stories 83–87  
**Objectif :** Corriger les 27 findings ouverts identifiés dans l'Audit #8 de la revue exhaustive du codebase IDP Portal.

---

## Contexte

L'Audit #8 (2026-03-16) a identifié 27 findings ouverts suite au refactoring majeur des Stories 83–87 (~156 commits). Ces findings couvrent :

- **Backend :** 2 HIGH, 13 MEDIUM, 12 LOW (sécurité, bugs, performance, code smells, Celery, gestion d'erreurs, architecture, tests)
- **Frontend :** Bugs, performance, code smells, gestion d'erreurs, accessibilité, types

**Priorités recommandées (extrait §27.5) :**
1. **Sprint immédiat (quick wins)** : BUG-BE-01, ERR-BE-01, CELERY-BE-01, SEC-BE-01, BUG-FE-01, ERR-FE-01
2. **Refactoring structurel** : SMELL-BE-01, SMELL-BE-02, SMELL-FE-01, PERF-FE-01
3. **Backlog** : ARCH-BE-01/02, A11Y-FE-01/02, TYPE-FE-01

---

## Stories

### Story 88-1 : Quick fixes backend — Bugs critiques et sécurité

**Objectif :** Corriger les findings HIGH et MEDIUM critiques du backend identifiés dans l'Audit #8.

**Findings couverts :**
- **BUG-BE-01** (HIGH) — `orchestrator.py:232-238` : Variable `updated` utilisée hors du scope `transaction.atomic()` → risque `NameError`. Initialiser `updated = 0` et `final_status = None` avant le bloc.
- **ERR-BE-01** (MEDIUM) — `orchestrator.py` : 4 × `except Exception: pass` sans logging. Remplacer par `logger.debug("...", exc_info=True)`.
- **CELERY-BE-01** (MEDIUM) — `core/tasks.py` : `flush_splunk_logging_handler` sans `soft_time_limit` ni `time_limit`. Ajouter via `CELERY_TASK_TIME_LIMITS`.
- **SEC-BE-01** (MEDIUM) — `polling.py:65-73` : Mise à jour de statut non-atomique dans `_mark_execution_polling_exhausted`. Appliquer pattern CAS.

**Critères d'acceptation :**
- [ ] BUG-BE-01 : Variables initialisées avant bloc atomic, test edge case ajouté (TEST-BE-01)
- [ ] ERR-BE-01 : Tous les `except Exception: pass` loguent avec `exc_info=True`
- [ ] CELERY-BE-01 : `flush_splunk_logging_handler` a `soft_time_limit` et `time_limit`
- [ ] SEC-BE-01 : `_mark_execution_polling_exhausted` utilise pattern CAS (compare-and-swap)
- [ ] Tous les tests existants passent

---

### Story 88-2 : Quick fixes frontend — Bugs et erreurs

**Objectif :** Corriger les findings MEDIUM du frontend identifiés dans l'Audit #8.

**Findings couverts :**
- **BUG-FE-01** (MEDIUM) — `ActionWizard.tsx:376` : `selectedTags.length >= 0` toujours vrai. Corriger → `selectedTags.length > 0` ou comparaison avec tags originaux.
- **ERR-FE-01** (MEDIUM) — `useCapabilities.ts:65-81` : Pas de retry sur l'échec du fetch capabilities. Ajouter 1–2 tentatives automatiques.

**Critères d'acceptation :**
- [ ] BUG-FE-01 : Tags mis à jour uniquement si modifiés (comparaison avec état initial)
- [ ] ERR-FE-01 : Retry automatique (1–2 tentatives) sur fetch capabilities avec backoff
- [ ] Tests unitaires mis à jour / ajoutés
- [ ] Tous les tests frontend passent

---

### Story 88-3 : Bugs et erreurs restants (backend + frontend)

**Objectif :** Corriger les bugs et erreurs logiques restants.

**Findings couverts :**
- **BUG-BE-02** (MEDIUM) — `orchestrator.py:159-160,176-177` : Exceptions avalées dans `_force_finalize_execution`. Ajouter logging.
- **BUG-BE-03** (MEDIUM) — `orchestrator.py:248-250,269` : Même avalage dans `_finalize_execution_if_done`. Ajouter logging.
- **BUG-FE-02** (MEDIUM) — `useExecutionDetail.ts:62-63` : Catch silencieux sur fetch détail action. Ajouter logging.
- **BUG-FE-03** (LOW) — `SchemaFormRenderer.tsx:237-238` : Désynchronisation état interne `MappingEditor` si `value` change externalement.
- **ERR-FE-02** (LOW) — `help_service.ts:46-48` : Erreur transformée en contenu vide sans logging.
- **ERR-FE-03** (LOW) — `execution_inventory.ts:93-122` : Mutation d'objet Error complexe. Créer classe `InventoryUnavailableError`.

**Critères d'acceptation :**
- [ ] Tous les blocs `except Exception: pass` loguent ou sont documentés
- [ ] BUG-FE-03 : `MappingEditor` resynchronise si `value` change (useEffect)
- [ ] ERR-FE-03 : Classe `InventoryUnavailableError` créée, usage migré
- [ ] Tests ajoutés pour les cas edge

---

### Story 88-4 : Sécurité restante (LOW)

**Objectif :** Corriger les findings de sécurité LOW restants.

**Findings couverts :**
- **SEC-BE-02** (LOW) — `core/views.py:154,160` : Bypass health check hardcodé pour Vault/ServiceNow locaux. Documenter ou externaliser en config.
- **SEC-BE-03** (LOW) — `http_request_handler.py:150-160` : Timeout HTTP non borné. Plafonner (ex. `max(timeout, 300)`).
- **SEC-FE-01** (LOW) — `AuthContext.tsx:22-23` : Token mock dev dans le source. Renforcer garde `VITE_DEV_AUTH` ou déplacer hors source.

**Critères d'acceptation :**
- [ ] SEC-BE-02 : Adresses localhost documentées ou configurables
- [ ] SEC-BE-03 : Timeout HTTP plafonné (ex. 300s max)
- [ ] SEC-FE-01 : Garde explicite ou token mock hors source
- [ ] Aucune régression sur les health checks

---

### Story 88-5 : Refactoring God class — container_workflow_runtime

**Objectif :** Réduire la taille de `container_workflow_runtime.py` (1928 LOC) en extrayant des responsabilités.

**Findings couverts :**
- **SMELL-BE-01** (HIGH) — God class : orchestration, gestion exécutions enfant, dispatch plateforme, extraction output, broadcast, intégration ServiceNow.

**Approche recommandée :**
- Extraire `PlatformStepExecutor` pour le dispatch plateforme
- Extraire helpers pour broadcast et extraction output
- Conserver orchestration principale dans le runtime

**Critères d'acceptation :**
- [ ] `container_workflow_runtime.py` < 800 LOC (ou découpage en sous-modules cohérents)
- [ ] Responsabilités clairement séparées (orchestration vs dispatch vs broadcast)
- [ ] Tous les tests d'exécution passent
- [ ] Aucune régression fonctionnelle

---

### Story 88-6 : Refactoring code smells — trigger.py, ActionWizard, useWorkflowGraph

**Objectif :** Extraire les duplications et réduire la complexité des méthodes/composants volumineux.

**Findings couverts :**
- **SMELL-BE-02** (MEDIUM) — `trigger.py:159-301` : God method avec gestion d'erreurs dupliquée (SoftTimeLimitExceeded, AdapterTimeoutError, Exception). Extraire helper `_handle_trigger_error()`.
- **SMELL-FE-01** (MEDIUM) — `ActionWizard.tsx` (604 LOC) : Extraire `handleSave` dans hook `useActionWizardSave`.
- **SMELL-FE-02** (MEDIUM) — `useWorkflowGraph.ts` (527 LOC) : Hook volumineux. Documenter ou extraire sous-hooks si pertinent.

**Critères d'acceptation :**
- [ ] SMELL-BE-02 : Helper `_handle_trigger_error()` extrait, 3 blocs remplacés par appel unique
- [ ] SMELL-FE-01 : `useActionWizardSave` créé, `ActionWizard` < 500 LOC
- [ ] SMELL-FE-02 : Complexité documentée ou sous-hooks extraits
- [ ] Tests existants passent

---

### Story 88-7 : Performance — ServiceNow client, useCapabilities par nœud

**Objectif :** Optimiser les performances identifiées dans l'Audit #8.

**Findings couverts :**
- **PERF-BE-01** (LOW) — `servicenow_service.py` : Nouveau `httpx.Client` par appel. Réutiliser un client partagé ou pool.
- **PERF-FE-01** (MEDIUM) — `WorkflowStepNode.tsx:101-358` : `useCapabilities()` appelé par nœud (20+ instances). Passer capabilities via contexte.

**Critères d'acceptation :**
- [ ] PERF-BE-01 : Client HTTP réutilisé (module-level ou injecté)
- [ ] PERF-FE-01 : Contexte `CapabilitiesContext` ou prop drilling depuis parent, 1 seul fetch
- [ ] Pas de régression sur les temps de réponse
- [ ] Tests de charge ou manuels validés

---

### Story 88-8 : Architecture — Imports canoniques, modules de routage

**Objectif :** Aligner les imports et supprimer les duplications de modules de routage.

**Findings couverts :**
- **ARCH-BE-01** (LOW) — `container_workflow_runtime.py:49-50` : Imports depuis shims (`step_handlers.condition_evaluator`, `step_handlers.registry`) au lieu de `executions.app.handlers.*`.
- **ARCH-BE-02** (LOW) — `container_routing.py` vs `domain/workflow_graph.py` : Logique chevauchante. Consolider ou documenter la séparation.

**Critères d'acceptation :**
- [ ] ARCH-BE-01 : Imports migrés vers `executions.app.handlers.*`
- [ ] ARCH-BE-02 : Duplication éliminée ou documentée (ADR si pertinent)
- [ ] Aucune régression sur le routing des workflows

---

### Story 88-9 : Qualité — Accessibilité, types, design tokens

**Objectif :** Corriger les findings LOW d'accessibilité, de typage et de design.

**Findings couverts :**
- **A11Y-FE-01** (LOW) — `ExecutionView.tsx` : Couleurs hex hardcodées (`#E5E7EB`, etc.). Migrer vers design tokens.
- **A11Y-FE-02** (LOW) — `WorkflowStepNode.tsx` : Palette `STEP_TYPE_COLORS` et `executionBorderColors` hardcodées. Variante dark mode.
- **TYPE-FE-01** (LOW) — `TargetSelector.tsx:40`, `TargetSelectionStep.tsx:77` : `any` dans les types de ref. Remplacer par types spécifiques (`HTMLInputElement`, `InputRef`).

**Critères d'acceptation :**
- [ ] A11Y-FE-01/02 : Couleurs via `var(--ant-*)` ou design tokens
- [ ] TYPE-FE-01 : Refs typées correctement
- [ ] Dark mode vérifié sur les composants modifiés
- [ ] Aucun `any` résiduel dans les refs ciblées

---

## Récapitulatif des findings par story

| Story | Findings | Sévérité |
|-------|----------|----------|
| 88-1 | BUG-BE-01, ERR-BE-01, CELERY-BE-01, SEC-BE-01, TEST-BE-01 | 1 HIGH, 4 MEDIUM |
| 88-2 | BUG-FE-01, ERR-FE-01 | 2 MEDIUM |
| 88-3 | BUG-BE-02, BUG-BE-03, BUG-FE-02, BUG-FE-03, ERR-FE-02, ERR-FE-03 | 3 MEDIUM, 3 LOW |
| 88-4 | SEC-BE-02, SEC-BE-03, SEC-FE-01 | 3 LOW |
| 88-5 | SMELL-BE-01 | 1 HIGH |
| 88-6 | SMELL-BE-02, SMELL-FE-01, SMELL-FE-02 | 3 MEDIUM |
| 88-7 | PERF-BE-01, PERF-FE-01 | 1 LOW, 1 MEDIUM |
| 88-8 | ARCH-BE-01, ARCH-BE-02 | 2 LOW |
| 88-9 | A11Y-FE-01, A11Y-FE-02, TYPE-FE-01 | 3 LOW |

**Total :** 27 findings couverts.

---

## Ordre de priorité recommandé

1. **88-1** (quick wins backend) — Bloquant potentiel BUG-BE-01
2. **88-2** (quick wins frontend)
3. **88-3** (bugs restants)
4. **88-4** (sécurité LOW)
5. **88-5** (refactoring God class) — Effort élevé
6. **88-6** (code smells)
7. **88-7** (performance)
8. **88-8** (architecture)
9. **88-9** (qualité)

---

## Références

- `idp-portal/CODEBASE-REVIEW.md` — §27 Audit #8 (2026-03-16)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` — Suivi des stories

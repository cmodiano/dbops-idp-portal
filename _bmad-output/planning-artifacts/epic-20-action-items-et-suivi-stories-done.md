# Epic 20 : Action items et suivi — Restant des stories marquées « done »

**En tant que** équipe de développement,  
**je veux** identifier et traiter les action items, follow-ups et known issues laissés ouverts dans les stories déjà marquées « done »,  
**afin de** réduire la dette technique, restaurer la confiance dans les tests et finaliser les éléments non bloquants documentés lors des code reviews.

---

## Contexte

Lors des code reviews et rétrospectives des Epics 1 à 19 et M, de nombreux action items, known limitations et follow-ups ont été documentés mais non implémentés. Ces éléments ont été jugés non bloquants pour marquer les stories « done », mais ils représentent une dette technique à traiter.

---

## Portée (scope)

### Catégories identifiées

1. **Tests en échec** — Fixtures User obsolètes, 40+ catalog tests, 3 workflow_runtime tests, AC8 18.7 (95% non atteint)
2. **Follow-ups code review** — M-4 (Task 12, environnement tests), M-10 (WebSocket, CI/CD), 17-12 (Redis pub/sub), 17-2 (Phase 4)
3. **Known limitations** — 16-4 (time.sleep/Celery), 17-4 (OracleJSONField catalog/workflow tests)
4. **Epic M rétrospective** — Checklist endpoints, ADRs, couverture M-5/M-6
5. **Tâches restantes** — 5-7 (Tasks 3, 4, 6), 15-4 (signatures rapports)
6. **Documentation** — M-4 (documentation fichiers modifiés), 17-16 (3 CRITICAL code review)

---

## Stories proposées

### Story 20.1 : Corriger fixtures User et tests catalog/workflow (KNOWN ISSUES 17.4, 18.7)

**En tant que** développeur,  
**je veux** corriger les fixtures User obsolètes et les tests catalog/workflow qui échouent,  
**afin de** restaurer la suite de tests et atteindre l’objectif AC8 18.7 (≥95% pass).

**Sources :** 17-4 (40+ catalog tests, 3 workflow_runtime), 18-7 (AC8 82.4% → 95%)

**Acceptance Criteria:**
- 40+ catalog tests passent (fixtures User alignées sur modèle custom)
- 3 workflow_runtime tests passent (investigation fixtures)
- Suite backend ≥95% pass (cible 18.7)
- KNOWN_ISSUES.md mis à jour

---

### Story 20.2 : M-4 — Validation parité contractuelle et environnement tests

**En tant que** équipe technique,  
**je veux** finaliser les action items de la story M-4 (API REST catalogue),  
**afin de** valider la parité avec FastAPI et stabiliser l’environnement de tests.

**Sources :** m-4-api-rest-catalogue-et-admin-actions-tags.md (Action Items 4)

**Acceptance Criteria:**
- [HIGH] Environnement Python/Django configuré pour exécuter catalog/tests/*.py
- [MEDIUM] Task 12 — Validation parité contractuelle FastAPI/DRF réalisée (test manuel ou automatisé)
- [MEDIUM] Documentation des fichiers modifiés par autres stories
- [LOW] Refactoring tests style cohérent (pytest vs Django TestCase)
- ExecutionService.get_action_stats() ou get_stats(action_id) si manquant

---

### Story 20.3 : 16-4 — Migrer retry vers Celery (ou alternative asynchrone)

**En tant que** équipe ops,  
**je veux** remplacer `time.sleep()` bloquant dans le moteur retry par une solution asynchrone (Celery ou équivalent),  
**afin de** éviter de bloquer le worker Django en production à fort volume.

**Sources :** 16-4-moteur-retry-backoff-exponentiel.md (H4 Known Limitation, high tech debt)

**Acceptance Criteria:**
- time.sleep() retiré du workflow_runtime retry
- Utilisation de Celery apply_async(countdown=...) ou alternative (Huey, ARQ, etc.)
- Tests d’intégration avec délais réels (H5)
- Documentation backoff clarifiée (H7)
- Cache Redis optionnel pour statut annulation (M1) si volume élevé

---

### Story 20.4 : 17-2 Phase 4 — Optimisations ExecutionWizard et métriques

**En tant que** développeur frontend,  
**je veux** compléter la Phase 4 du refactoring ExecutionWizard et les métriques de performance,  
**afin de** atteindre la cible AC3 (<300 lignes) et valider les gains de bundle/perf.

**Sources :** 17-2-code-review-findings.md (HIGH-1, MEDIUM-1, MEDIUM-3, MEDIUM-5, LOW-3)

**Acceptance Criteria:**
- ExecutionWizard <300 lignes (ou justification acceptée)
- usePatternResolver extrait de useTargetInventory
- WorkflowStepsRenderer extrait de ParametersFormStep
- Coverage hooks mesurée et documentée
- Bundle size mesurée (webpack-bundle-analyzer ou équivalent)

---

### Story 20.5 : Epic M — Checklist endpoints, ADRs, couverture tests

**En tant que** équipe,  
**je veux** implémenter les action items de la rétrospective Epic M,  
**afin de** améliorer la qualité et l’onboarding des développeurs.

**Sources :** epic-m-retrospective.md (Action Items 1-5)

**Acceptance Criteria:**
- Checklist standard pour nouveaux endpoints (validations, sécurité)
- Revu sécurité renforcée dès le développement initial
- ADRs documentés pour patterns choisis
- Couverture tests M-5 et M-6 à 85%

---

### Story 20.6 : 5-7 — Finaliser workflow conteneur (Tasks 3, 4, 6)

**En tant que** équipe produit,  
**je veux** finaliser les tâches restantes de la story 5-7 (workflow conteneur actions),  
**afin de** compléter l’exécution engine, l’admin UI et les tests.

**Sources :** 5-7-workflow-conteneur-actions-icone-catalogue.md (Tasks 3, 4, 6 pending)

**Acceptance Criteria:**
- Task 3 : Moteur d’exécution workflows (si applicable)
- Task 4 : Admin UI workflows (si applicable)
- Task 6 : Tests complets

---

### Story 20.7 : M-10 et 17-12 — Follow-ups non bloquants

**En tant que** équipe,  
**je veux** traiter les follow-ups documentés dans M-10 et 17-12,  
**afin de** améliorer la robustesse et la scalabilité.

**Sources :** m-10 (WebSocket test, CI/CD auto-deploy), 17-12 (Redis pub/sub multi-instance)

**Acceptance Criteria:**
- M-10 : Tests WebSocket ou documentation proxy Nginx
- M-10 : CI/CD auto-deploy documenté ou implémenté
- 17-12 : Redis pub/sub pour sync multi-instance feature flags (ou documenté hors scope MVP)

---

### Story 20.8 : 15-4 et 17-16 — Documentation et conformité

**En tant que** équipe qualité,  
**je veux** finaliser les éléments de documentation et conformité restants,  
**afin de** clôturer les rapports de validation et les standards frontend.

**Sources :** 15-4 (signatures rapports validation), 17-16 (3 CRITICAL code review)

**Acceptance Criteria:**
- 15-4 : Signatures réelles pour rapports validation ou exigence AC5 ajustée
- 17-16 : 3 CRITICAL code review résolus et documentés

---

## Priorisation recommandée

| Story   | Priorité | Impact |
|---------|----------|--------|
| 20.1    | Haute    | Restaure confiance tests |
| 20.2    | Haute    | Validation M-4 complète |
| 20.3    | Moyenne  | Production à fort volume |
| 20.4    | Moyenne  | Qualité frontend |
| 20.5    | Moyenne  | Qualité processus |
| 20.6    | Basse    | Complétion 5-7 |
| 20.7    | Basse    | Améliorations incrémentales |
| 20.8    | Basse    | Documentation/validation |

---

## Dépendances techniques

- Celery ou alternative async pour 20.3
- UserFactory / fixtures alignées sur modèle User custom
- Documentation Epic M et ADRs

---

## Phase

Tech Debt / Quality — Post-MVP, amélioration continue

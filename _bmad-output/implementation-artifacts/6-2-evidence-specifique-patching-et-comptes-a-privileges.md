# Story 6.2 : Evidence spécifique patching et comptes à privilèges

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a spécialiste sécurité,
I want des traces d'audit enrichies pour les opérations de patching et les créations de comptes à privilèges,
So that je dispose d'evidence spécifique pour les contrôles SOC1 les plus exigeants.

## Acceptance Criteria

1. **AC1** — Given une exécution de type "patching" se termine, When l'entrée d'audit est générée, Then les champs additionnels sont capturés : version source, version cible, résultat du patch, composants modifiés.
2. **AC2** — Given une exécution de type "création de compte à privilèges" se termine, When l'entrée d'audit est générée, Then les champs additionnels sont capturés : justification, approbateur, scope des privilèges accordés.
3. **AC3** — Les détails supplémentaires sont stockés dans la colonne DETAILS (CLOB JSON) de AUDIT_LOG (pas de nouvelle colonne).
4. **AC4** — La structure JSON des détails est documentée pour chaque type d'action auditable (patching, compte à privilèges).
5. **AC5** — FR31 et FR32 sont satisfaites.

## Tasks / Subtasks

- [x] **Task 1** (AC: 1, 3, 4) — Identification des actions patching et enrichissement evidence
  - [x] 1.1 Définir la convention d'identification des actions "patching" (ex. tag catalogue "patching" ou champ métadonnée action) ; documenter dans le code ou la config.
  - [x] 1.2 Lors de l'écriture EXECUTION_COMPLETED / EXECUTION_FAILED, si l'action est de type patching : enrichir le payload `details` passé à `audit_repository.create_entry` avec les clés : `version_source`, `version_target`, `patch_result`, `components_modified` (valeurs issues des paramètres d'exécution ou des outputs d'étapes).
  - [x] 1.3 Documenter la structure JSON "patching" (ex. dans Dev Notes ou docstring audit_repository / schéma partagé).
- [x] **Task 2** (AC: 2, 3, 4) — Identification des actions compte à privilèges et enrichissement evidence
  - [x] 2.1 Définir la convention d'identification des actions "création de compte à privilèges" (ex. tag "compte-privileges" ou métadonnée).
  - [x] 2.2 Lors de l'écriture EXECUTION_COMPLETED / EXECUTION_FAILED, si l'action est de type compte à privilèges : enrichir `details` avec : `justification`, `approbateur`, `privilege_scope` (valeurs depuis paramètres ou contexte).
  - [x] 2.3 Documenter la structure JSON "compte à privilèges".
- [x] **Task 3** (AC: 5) — Tests
  - [x] 3.1 Tests unitaires : execution_service (ou point d'appel audit) — exécution patching → entrée audit avec details contenant version_source/version_target/patch_result/components_modified.
  - [x] 3.2 Tests unitaires : exécution "compte à privilèges" → entrée audit avec justification, approbateur, privilege_scope.
  - [x] 3.3 S'assurer qu'une action sans tag/convention ne modifie pas la structure existante (rétrocompatibilité).

## Dev Notes

- **Contexte Story 6.1** : AUDIT_LOG est déjà étendu (V028) avec EXECUTION_*, entity_type execution, correlation_id, IP. `audit_repository.create_entry()` accepte un `details` (dict → CLOB JSON). Aucune nouvelle migration SQL nécessaire si on ne fait qu'enrichir le contenu de DETAILS.
- **Où enrichir** : Dans `execution_service` au moment des appels existants qui écrivent EXECUTION_COMPLETED et EXECUTION_FAILED (après récupération du résultat et des paramètres). Passer un `details` enrichi selon le type d'action (déterminé par tags ou métadonnées de l'action depuis le catalogue).
- **Source des champs** : Pour patching : paramètres d'exécution (ex. `version_source`, `version_target`) et/ou sortie des étapes (résultat, composants modifiés). Pour comptes à privilèges : paramètres (justification, approbateur) et/ou contexte RBAC. Si un champ n'est pas disponible, ne pas inventer ; documenter quelles clés sont optionnelles.
- **Tags catalogue** : Les actions ont des tags (ACTIONS_CATALOG + ACTION_TAGS). Utiliser un tag conventionnel (ex. `patching`, `compte-privileges`) pour identifier le type d'action est cohérent avec l'existant ; alternative : champ dédié en métadonnée si le produit le prévoit.

### Project Structure Notes

- Fichiers à modifier (sans créer de nouvelle table) :
  - `app/services/execution_service.py` — enrichir les appels `audit_repository.create_entry` pour EXECUTION_COMPLETED et EXECUTION_FAILED avec un `details` étendu selon type d'action (patching / compte à privilèges).
  - `app/repositories/catalog_repository.py` ou couche qui expose les infos action (tags/métadonnées) — s'assurer que le service d'exécution peut savoir si l'action est "patching" ou "compte à privilèges".
  - Optionnel : `app/repositories/audit_repository.py` — docstrings ou constantes décrivant les structures JSON des details (patching, compte-privileges).
  - `backend/tests/unit/test_execution_service.py` et/ou `test_execution_api.py` — tests audit avec details enrichis.
- Pas de migration Flyway : la colonne DETAILS existe déjà (V004/V028).

### Developer context — garde-fous

- **Stack** : Backend Python 3.12+, FastAPI, python-oracledb, Oracle. Réutiliser uniquement l'existant (audit_repository, execution_service).
- **DB** : Aucune modification de schéma. Utiliser uniquement la colonne DETAILS (CLOB JSON) de AUDIT_LOG.
- **API** : Aucun nouvel endpoint. Comportement interne à l'écriture d'audit.
- **Réutilisation** : S'appuyer sur les appels existants à `audit_repository.create_entry` dans execution_service ; ne pas dupliquer la logique d'insert, seulement enrichir le dict `details` avant l'appel.
- **Rétrocompatibilité** : Les exécutions dont l'action n'est ni patching ni compte à privilèges doivent continuer à produire les mêmes entrées qu'aujourd'hui (même structure details que Story 6.1).

### Previous Story Intelligence (6.1)

- **Fichiers modifiés en 6.1** : `database/migrations/V028__audit_log_execution_traces.sql`, `app/repositories/audit_repository.py`, `app/api/v1/executions.py`, `app/services/execution_service.py`, tests unitaires audit + execution.
- **Pattern à réutiliser** : `create_entry(..., details=dict)` avec DETAILS en CLOB JSON ; pas d'UPDATE/DELETE sur AUDIT_LOG ; correlation_id et ip_address déjà propagés. Pour 6.2, uniquement enrichir le `details` passé à `create_entry` selon le type d'action.
- **Code review 6.1** : client_ip propagé à toutes les entrées ; user_id en str pour SERVICENOW ; list_entries gère CLOB bytes (decode UTF-8). Ne pas réintroduire de régression sur ces points.

### Architecture Compliance

- **AUDIT_LOG** : Append-only conservé ; aucune nouvelle colonne ; utilisation exclusive de DETAILS (JSON) pour les champs additionnels.
- **Repository** : audit_repository reste INSERT + SELECT only ; pas de nouvelle méthode ; signature create_entry inchangée (details reste un dict libre).
- **Execution flow** : Enrichissement au même endroit que les appels EXECUTION_COMPLETED / EXECUTION_FAILED dans execution_service (pas dans les routes API).
- **Naming** : Clés JSON en snake_case (version_source, version_target, patch_result, components_modified, justification, approbateur, privilege_scope). Cohérent avec l'API et l'architecture.

### References

- [Source: _bmad-output/planning-artifacts/epics.md — Epic 6, Story 6.2]
- [Source: idp-portal/backend/app/repositories/audit_repository.py — create_entry, details CLOB]
- [Source: idp-portal/backend/app/services/execution_service.py — appels EXECUTION_COMPLETED / EXECUTION_FAILED]
- [Source: idp-portal/database/migrations/V004 et V028 — AUDIT_LOG, DETAILS]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

N/A — Implémentation directe sans problèmes majeurs.

### Completion Notes List

**2026-01-31** — Story 6.2 implémentée avec succès.

**Conventions définies :**
- Tag `patching` : identifie une action de patching
- Tag `compte-privileges` : identifie une action de création de compte à privilèges

**Structures JSON documentées (DETAILS CLOB AUDIT_LOG) :**

1. **Patching evidence** (actions avec tag "patching") :
   ```json
   {
     "status": "COMPLETED|FAILED",
     "steps_summary": [...],
     "version_source": "19.3.0",
     "version_target": "19.21.0",
     "patch_result": "success|failed",
     "components_modified": ["oracle-db", "grid-infra"]
   }
   ```

2. **Compte à privilèges evidence** (actions avec tag "compte-privileges") :
   ```json
   {
     "status": "COMPLETED|FAILED",
     "steps_summary": [...],
     "justification": "Maintenance planifiée - ticket INC0012345",
     "approbateur": "john.manager@company.com",
     "privilege_scope": "DBA|SYSDBA|..."
   }
   ```

3. **Actions régulières** (sans tag spécial) : structure inchangée (rétrocompatibilité).

**Tests ajoutés :**
- `TestPatchingEvidenceAudit` : 2 tests (completed + failed)
- `TestPrivilegeAccountEvidenceAudit` : 2 tests (completed + failed)
- `TestRegularActionAuditRetrocompat` : 1 test

**Résultat :** 31/31 tests execution_service passent.

### File List

- `idp-portal/backend/app/services/execution_service.py` — Ajout import catalog_repository, constantes PATCHING_TAG/PRIVILEGE_ACCOUNT_TAG, helper functions _build_patching_evidence/_build_privilege_account_evidence, enrichissement audit details, error handling pour catalog_repository, warning logs pour champs SOC1 manquants
- `idp-portal/backend/app/repositories/catalog_repository.py` — Utilise get_tags_for_action() existant (docstring mise à jour pour Story 6.2)
- `idp-portal/backend/tests/unit/test_execution_service.py` — Ajout fixture mock_catalog_repository, 4 classes de tests (7 tests total: patching, privilege, retrocompat, catalog failure resilience)

### Change Log

- 2026-01-31: Implémentation Story 6.2 — Evidence spécifique patching et comptes à privilèges dans AUDIT_LOG DETAILS
- 2026-01-31: Code review adversarial — 10 issues corrigés (1 CRITICAL, 5 MEDIUM, 4 LOW):
  - CRITICAL: File List complétée avec catalog_repository.py
  - MEDIUM: Null safety ajoutée pour get_tags_for_action (or [])
  - MEDIUM: Error handling ajouté pour catalog_repository failures (try-except + fallback)
  - MEDIUM: Warning logs ajoutés pour champs SOC1 manquants (patching_evidence_incomplete, privilege_account_evidence_incomplete)
  - MEDIUM: Tests ajoutés pour catalog_repository failure resilience (2 tests)
  - LOW: Docstring catalog_repository mise à jour avec référence Story 6.2
  - 33/33 tests passent

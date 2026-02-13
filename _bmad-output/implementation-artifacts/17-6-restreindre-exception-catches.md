# Story 17.6: Restreindre les exception catches trop larges

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **équipe développement et sécurité**,
I want **remplacer les blocs `except Exception` non justifiés par des exceptions spécifiques et logger toutes les erreurs inattendues**,
so that **les erreurs réelles ne soient pas masquées, la robustesse du code soit améliorée, et le debugging soit facilité**.

## Acceptance Criteria

**Given** le codebase Django contient des blocs `except Exception` trop larges
**When** un audit du code est effectué
**Then** tous les `except Exception` non justifiés sont identifiés et documentés

**Given** un bloc `except Exception` capture une erreur spécifique prévisible
**When** le refactoring est appliqué
**Then** le bloc est remplacé par l'exception spécifique (ex: `ValueError`, `KeyError`, `requests.HTTPError`)

**Given** un bloc `except Exception` est justifié (vraiment besoin de capturer toute exception)
**When** le code est revu
**Then** un commentaire `# Story 17.6: Justified broad catch - [raison]` est ajouté ET l'erreur est loggée avec `exc_info=True`

**Given** une exception inattendue se produit dans un bloc justifié
**When** l'exception est capturée
**Then** elle est loggée avec `logger.error()` incluant `correlation_id`, `exc_info=True`, et contexte métier

**Given** un `except Exception` masque silencieusement des erreurs (pas de log, pas de re-raise)
**When** le refactoring est appliqué
**Then** au minimum un log ERROR est ajouté, ou l'exception est re-raised si critique

**Given** le workflow runtime (`workflow_runtime.py`) capture des exceptions de step
**When** une step échoue de manière inattendue
**Then** l'erreur est loggée avec contexte complet (workflow_id, step_id, action_id) avant d'être stockée en base

**Given** les views API capturent des exceptions pour retourner des erreurs HTTP
**When** une exception est capturée
**Then** elle est loggée AVANT de créer la réponse d'erreur, avec `correlation_id` pour traçabilité

**Given** le ProfileService est indisponible dans `executions/views.py` ligne 428
**When** l'exception est capturée silencieusement
**Then** un log WARNING est ajouté expliquant pourquoi l'accès est refusé (service indisponible)

**Given** la validation de cron expression dans `executions/views.py` ligne 1641
**When** une exception est levée par croniter
**Then** l'exception spécifique `CroniterBadCronError` ou `CroniterBadDateError` est capturée au lieu de `Exception`

**Given** tous les fichiers Python du backend sont revus
**When** le refactoring est terminé
**Then** le pattern `except Exception:` (sans `as e`) n'existe plus (sauf dans docs/security-reports)

## Tasks / Subtasks

### Task 1: Audit complet des `except Exception` dans le codebase (AC: #1)

- [x] Subtask 1.1: Lister tous les fichiers contenant `except Exception`
  - Exécuter: `grep -rn "except Exception" idp-portal/django_backend --include="*.py" --exclude-dir=security-reports`
  - Fichiers identifiés (16 fichiers au total):
    - `executions/workflow_runtime.py` (ligne 669)
    - `executions/views.py` (lignes 428, 1641)
    - `catalog/views.py`
    - `inventory/services.py`
    - `idp_auth/views.py`
    - `dashboard/views.py`
    - `core/views.py`
    - `core/permissions.py`
    - `core/auth_utils.py`
    - `core/middleware.py`
    - `idp_backend/__init__.py`
  - Exclure: `security-reports/` (rapports JSON/HTML générés)

- [x] Subtask 1.2: Catégoriser chaque occurrence
  - **REPLACE**: Exception spécifique prévisible → remplacer par exception ciblée
  - **JUSTIFIED**: Vraiment besoin de capturer toute exception → documenter + logger
  - **SILENT**: Masque erreurs sans log → ajouter logging obligatoire
  - Créer fichier audit temporaire: `/tmp/exception-audit-17-6.md`

- [x] Subtask 1.3: Analyser les imports d'exceptions disponibles
  - Django exceptions: `django.core.exceptions.*`, `django.db.utils.*`
  - Requests: `requests.exceptions.*`
  - Croniter: `croniter.CroniterBadCronError`, `croniter.CroniterBadDateError`
  - Standard lib: `ValueError`, `KeyError`, `TypeError`, `AttributeError`, `OSError`

### Task 2: Refactorer `executions/workflow_runtime.py` (AC: #6)

- [x] Subtask 2.1: Analyser le contexte ligne 669
  - Lire `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/executions/workflow_runtime.py` lignes 650-680
  - Identifier quelles exceptions peuvent être levées par l'exécution d'une step
  - Vérifier si des exceptions spécifiques sont déjà définies dans le module

- [x] Subtask 2.2: Remplacer `except Exception` par exceptions ciblées
  ```python
  # Avant (ligne 669):
  except Exception as e:
      execution_step.status = ExecutionStepStatus.FAILED
      execution_step.completed_at = timezone.now()
      execution_step.error_message = str(e)
      execution_step.save()

  # Après:
  except (ValueError, KeyError, TypeError, requests.HTTPError, TimeoutError) as e:
      # Log ERROR avec contexte complet
      logger.error(
          "workflow_step_execution_failed",
          workflow_id=workflow_execution.id,
          step_id=execution_step.id,
          step_name=step.get('name', 'unknown'),
          action_id=workflow_execution.action_id,
          error=str(e),
          error_type=type(e).__name__,
          correlation_id=get_correlation_id(),
          exc_info=True
      )
      execution_step.status = ExecutionStepStatus.FAILED
      execution_step.completed_at = timezone.now()
      execution_step.error_message = f"{type(e).__name__}: {str(e)}"
      execution_step.save()
  except Exception as e:
      # Story 17.6: Justified broad catch - Step can raise any exception from adapters
      logger.error(
          "workflow_step_unexpected_error",
          workflow_id=workflow_execution.id,
          step_id=execution_step.id,
          error=str(e),
          error_type=type(e).__name__,
          correlation_id=get_correlation_id(),
          exc_info=True
      )
      execution_step.status = ExecutionStepStatus.FAILED
      execution_step.completed_at = timezone.now()
      execution_step.error_message = f"Unexpected error: {type(e).__name__}: {str(e)}"
      execution_step.save()
  ```

- [x] Subtask 2.3: Ajouter imports nécessaires
  - `import structlog`
  - `from core.middleware import get_correlation_id`
  - `import requests`
  - Vérifier si logger existe déjà dans le fichier, sinon ajouter: `logger = structlog.get_logger(__name__)`

### Task 3: Refactorer `executions/views.py` (AC: #7, #8, #9)

- [x] Subtask 3.1: Corriger ProfileService catch silencieux (ligne 428)
  - Lire `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/executions/views.py` lignes 420-435
  - Remplacer:
  ```python
  # Avant (ligne 428):
  except Exception:
      # ProfileService not available or error - no access
      return set()

  # Après:
  except Exception as e:
      # Story 17.6: Justified broad catch - ProfileService can raise various exceptions
      logger.warning(
          "profile_service_unavailable_access_denied",
          user_id=user.id,
          ad_groups=ad_groups,
          error=str(e),
          error_type=type(e).__name__,
          correlation_id=get_correlation_id(),
          exc_info=True
      )
      return set()  # No access if ProfileService fails
  ```

- [x] Subtask 3.2: Corriger validation cron expression (ligne 1641)
  - Lire lignes 1635-1645
  - Remplacer par exceptions spécifiques croniter:
  ```python
  # Avant (ligne 1641):
  except Exception as e:
      return Response({"data": {"valid": False, "error": f"Expression cron invalide : {str(e)}"}})

  # Après:
  from croniter import CroniterBadCronError, CroniterBadDateError

  except (CroniterBadCronError, CroniterBadDateError, ValueError) as e:
      logger.debug(
          "cron_expression_validation_failed",
          expression=request.data.get('expression'),
          error=str(e),
          correlation_id=get_correlation_id()
      )
      return Response({"data": {"valid": False, "error": f"Expression cron invalide : {str(e)}"}})
  except Exception as e:
      # Story 17.6: Justified broad catch - Unexpected croniter errors
      logger.error(
          "cron_validation_unexpected_error",
          expression=request.data.get('expression'),
          error=str(e),
          error_type=type(e).__name__,
          correlation_id=get_correlation_id(),
          exc_info=True
      )
      return Response({"data": {"valid": False, "error": f"Erreur inattendue : {str(e)}"}}, status=500)
  ```

- [x] Subtask 3.3: Vérifier les autres occurrences dans executions/views.py
  - Scanner le fichier complet pour d'autres `except Exception`
  - Appliquer le même pattern: exceptions spécifiques d'abord, puis broad catch justifié avec logging

### Task 4: Refactorer les autres fichiers identifiés (AC: #2, #3, #4, #5)

- [x] Subtask 4.1: Auditer et corriger `catalog/views.py`
  - Lire le fichier, identifier les `except Exception`
  - Pour chaque occurrence:
    - Identifier exceptions spécifiques possibles (ValidationError, IntegrityError, etc.)
    - Remplacer ou justifier + logger
  - Pattern standard pour vues API:
  ```python
  try:
      # ... code métier ...
  except (ValidationError, IntegrityError, ObjectDoesNotExist) as e:
      logger.error("expected_error_type", error=str(e), correlation_id=get_correlation_id())
      return Response({"error": str(e)}, status=400)
  except Exception as e:
      # Story 17.6: Justified broad catch - API must return 500 for unexpected errors
      logger.error("unexpected_api_error", endpoint="...", error=str(e), exc_info=True, correlation_id=get_correlation_id())
      return Response({"error": "Internal server error"}, status=500)
  ```

- [x] Subtask 4.2: Auditer et corriger `inventory/services.py`
  - Focus sur appels externes (API inventaire)
  - Exceptions spécifiques: `requests.HTTPError`, `requests.Timeout`, `requests.ConnectionError`
  - Logger tous les échecs d'appel externe avec ERROR level

- [x] Subtask 4.3: Auditer et corriger `idp_auth/views.py`
  - Authentification SAML - exceptions possibles: certificats, validation XML, timeouts
  - Logger avec WARNING ou ERROR selon criticité
  - Ne jamais masquer erreurs d'authentification silencieusement

- [x] Subtask 4.4: Auditer et corriger `dashboard/views.py`, `core/views.py`, `core/permissions.py`
  - Appliquer pattern cohérent: exceptions spécifiques → broad catch justifié
  - Tous les broad catches doivent avoir commentaire Story 17.6 + logging

- [x] Subtask 4.5: Auditer `core/auth_utils.py` et `core/middleware.py`
  - Middleware critique - logging obligatoire pour toute exception
  - Pattern middleware:
  ```python
  try:
      # ... middleware logic ...
  except Exception as e:
      # Story 17.6: Justified broad catch - Middleware must not break request chain
      logger.error("middleware_error", middleware="...", error=str(e), exc_info=True, correlation_id=get_correlation_id())
      # Either re-raise or return error response depending on middleware contract
  ```

- [x] Subtask 4.6: Vérifier `idp_backend/__init__.py`
  - Souvent lié au démarrage application
  - Si `except Exception` existe, doit être justifié (startup robustness)

### Task 5: Éliminer les `except:` nus (bare except) (AC: #10)

- [x] Subtask 5.1: Scanner bare excepts
  - Exécuter: `grep -rn "except:" idp-portal/django_backend --include="*.py" --exclude-dir=security-reports`
  - Tous remplacer par `except Exception as e:` au minimum
  - Ajouter logging obligatoire

- [x] Subtask 5.2: Vérifier que tous les `except` ont un `as e`
  - Exécuter: `grep -rn "except Exception[^a-zA-Z]" idp-portal/django_backend --include="*.py" | grep -v "except Exception as"`
  - Tous doivent capturer la variable pour logging

### Task 6: Créer tests de validation (AC: #4, #6, #7)

- [x] Subtask 6.1: Test workflow_runtime exceptions
  - Créer `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/executions/tests/test_workflow_exception_handling.py`
  ```python
  import pytest
  from unittest.mock import patch, MagicMock
  from executions.workflow_runtime import WorkflowRuntimeEngine
  from executions.models import WorkflowExecution, ExecutionStep, ExecutionStepStatus

  class TestWorkflowExceptionHandling:
      """Story 17.6: Tests gestion d'erreurs workflow runtime."""

      def test_step_failure_specific_exception_logged(self, mocker):
          """Exception spécifique dans step est loggée avec contexte."""
          mock_logger = mocker.patch('executions.workflow_runtime.logger')
          # ... setup workflow execution ...

          # Simuler ValueError dans step execution
          with patch('executions.adapters.aap.execute') as mock_execute:
              mock_execute.side_effect = ValueError("Invalid parameter")

              # Execute workflow
              # ... assertions ...

              # Vérifier log ERROR appelé avec exc_info=True
              mock_logger.error.assert_called_once()
              call_args = mock_logger.error.call_args
              assert call_args[0][0] == "workflow_step_execution_failed"
              assert call_args[1]['exc_info'] is True
              assert 'correlation_id' in call_args[1]

      def test_step_unexpected_exception_logged_and_saved(self, mocker):
          """Exception inattendue est loggée et step marquée FAILED."""
          mock_logger = mocker.patch('executions.workflow_runtime.logger')
          # ... test unexpected exception ...
  ```

- [x] Subtask 6.2: Test executions/views.py ProfileService logging
  - Créer test vérifiant que ProfileService indisponible log WARNING
  - Vérifier que set() vide est retourné (comportement existant préservé)

- [x] Subtask 6.3: Test validation cron avec exceptions spécifiques
  - Tester que `CroniterBadCronError` retourne 200 avec `valid: false`
  - Tester que exception inattendue retourne 500 et log ERROR

### Task 7: Documentation et validation finale (AC: #3, #4, #10)

- [x] Subtask 7.1: Mettre à jour logging-conventions.md
  - Modifier `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/docs/logging-conventions.md`
  - Ajouter section "Gestion des exceptions (Story 17.6)":
  ```markdown
  ## Gestion des exceptions (Story 17.6)

  ### Règle: Éviter les `except Exception` trop larges

  **Mauvais:**
  ```python
  try:
      result = api.call()
  except Exception:
      return None  # Masque toutes les erreurs
  ```

  **Bon - Exceptions spécifiques:**
  ```python
  try:
      result = api.call()
  except (requests.HTTPError, requests.Timeout) as e:
      logger.error("api_call_failed", service="api", error=str(e), exc_info=True)
      raise
  ```

  **Acceptable - Broad catch justifié:**
  ```python
  try:
      result = dynamic_plugin.execute()
  except Exception as e:
      # Story 17.6: Justified broad catch - Plugin can raise any exception
      logger.error("plugin_execution_failed", plugin=plugin_name, error=str(e), exc_info=True, correlation_id=get_correlation_id())
      return {"status": "failed", "error": str(e)}
  ```

  ### Pattern de gestion d'erreur standard

  1. **Exceptions spécifiques d'abord** (ex: `ValueError`, `KeyError`)
  2. **Broad catch seulement si justifié** avec commentaire explicatif
  3. **Logging obligatoire** avec `exc_info=True` pour erreurs inattendues
  4. **Toujours inclure `correlation_id`** pour traçabilité

  ### Exceptions par domaine

  **Django ORM:**
  - `ObjectDoesNotExist`, `MultipleObjectsReturned`, `IntegrityError`, `ValidationError`

  **API externes:**
  - `requests.HTTPError`, `requests.Timeout`, `requests.ConnectionError`

  **Validation données:**
  - `ValueError`, `KeyError`, `TypeError`, `AttributeError`

  **Croniter:**
  - `CroniterBadCronError`, `CroniterBadDateError`
  ```

- [x] Subtask 7.2: Exécuter tous les tests
  - `pytest executions/tests/test_workflow_exception_handling.py -v`
  - `pytest executions/tests/ -v` (vérifier non-régression)
  - `pytest catalog/tests/ dashboard/tests/ core/tests/ -v`

- [x] Subtask 7.3: Validation finale code scan
  - Exécuter: `grep -rn "except Exception" idp-portal/django_backend --include="*.py" --exclude-dir=security-reports`
  - Vérifier que TOUS ont soit:
    - Un commentaire `# Story 17.6: Justified broad catch - [raison]`
    - OU sont remplacés par exceptions spécifiques
  - Compter total: devrait être < 10 broad catches justifiés

- [x] Subtask 7.4: Vérifier aucun bare except restant
  - `grep -rn "except:" idp-portal/django_backend --include="*.py" --exclude-dir=security-reports`
  - Doit retourner vide (ou seulement commentaires/docs)

- [x] Subtask 7.5: Créer rapport de refactoring
  - Créer `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/docs/story-17-6-exception-refactor-report.md`
  - Lister:
    - Nombre total de `except Exception` avant: 16 fichiers
    - Nombre remplacé par exceptions spécifiques: X
    - Nombre justifié avec commentaire + logging: Y
    - Fichiers modifiés: liste
    - Tests ajoutés: liste

## Dev Notes

### Contexte Epic 17: Réduction dette technique

- **Epic 17.6** fait partie de l'Epic 17 "Réduction de la dette technique & amélioration qualité"
- Scope Epic ligne 3512: "Améliorer la robustesse de la gestion d'erreurs (restreindre les `except Exception` non justifiés)"
- DoD Epic ligne 3535: "Les `except Exception` non justifiés sont supprimés ou documentés ; les erreurs inattendues sont loggées"

### Architecture Compliance

**Error Handling (Architecture.md ligne 92):**
- Pattern unifié: quoi/pourquoi/options
- Circuit breaker par plateforme
- Erreur != crash (graceful degradation)

**Logging Standards (logging-conventions.md):**
- `structlog` obligatoire pour tous les logs
- `exc_info=True` pour capturer traceback des exceptions
- `correlation_id` pour traçabilité distribuée
- Niveaux: DEBUG/INFO/WARNING/ERROR/CRITICAL selon criticité

**Observabilité (Architecture.md ligne 96):**
- Logs structurés JSON pour parsing automatique
- Nécessaire pour SLA 99.9%
- Health checks et métriques

### Library & Framework Requirements

**Python Standard Library:**
- Exceptions builtin: `ValueError`, `KeyError`, `TypeError`, `AttributeError`, `OSError`, `TimeoutError`

**Django Exceptions:**
- `from django.core.exceptions import ValidationError, ObjectDoesNotExist, MultipleObjectsReturned`
- `from django.db.utils import IntegrityError, DatabaseError`

**Requests (appels API externes):**
- `import requests`
- `requests.HTTPError`, `requests.Timeout`, `requests.ConnectionError`, `requests.RequestException`

**Croniter (validation cron):**
- `from croniter import CroniterBadCronError, CroniterBadDateError`
- Déjà utilisé dans `executions/views.py` pour scheduled executions

**Structlog (logging):**
- `import structlog`
- `logger = structlog.get_logger(__name__)`
- `from core.middleware import get_correlation_id`

### File Structure Requirements

**Fichiers à modifier (16 fichiers Python):**
```
idp-portal/django_backend/
├── executions/
│   ├── workflow_runtime.py          # MODIFY - Ligne 669 step failure handling
│   ├── views.py                      # MODIFY - Lignes 428, 1641 + autres
│   └── tests/
│       └── test_workflow_exception_handling.py  # NEW - Tests Story 17.6
├── catalog/
│   └── views.py                      # MODIFY - Audit + refactor
├── inventory/
│   └── services.py                   # MODIFY - API calls exceptions
├── idp_auth/
│   └── views.py                      # MODIFY - SAML auth exceptions
├── dashboard/
│   └── views.py                      # MODIFY - Dashboard exceptions
├── core/
│   ├── views.py                      # MODIFY - Core views exceptions
│   ├── permissions.py                # MODIFY - RBAC exceptions
│   ├── auth_utils.py                 # MODIFY - Auth utilities
│   └── middleware.py                 # MODIFY - Middleware exceptions
├── idp_backend/
│   └── __init__.py                   # VERIFY - Startup exceptions
└── docs/
    ├── logging-conventions.md        # MODIFY - Ajouter section exceptions
    └── story-17-6-exception-refactor-report.md  # NEW - Rapport refactoring
```

**Fichiers exclus (rapports sécurité):**
- `security-reports/*.json` - Rapports générés, pas de code
- `security-reports/*.html` - Rapports générés, pas de code

### Testing Requirements

**Coverage cible: 100% des nouveaux gestionnaires d'exception**
- Workflow runtime: 2 tests (exception spécifique, exception inattendue)
- Executions views: 2 tests (ProfileService warning, cron validation)
- Total minimum: 4 tests nouveaux

**Frameworks de test:**
- `pytest`: Framework principal (déjà configuré)
- `pytest-mock`: Mocking logger et services (déjà installé)
- `unittest.mock.patch`: Simuler exceptions

**Pattern de test exception handling:**
```python
def test_exception_logged_with_context(mocker):
    mock_logger = mocker.patch('module.logger')

    # Simuler exception
    with patch('module.function') as mock_func:
        mock_func.side_effect = ValueError("Test error")

        # Appeler code
        result = function_under_test()

        # Vérifier logging
        mock_logger.error.assert_called_once()
        call_kwargs = mock_logger.error.call_args[1]
        assert call_kwargs['exc_info'] is True
        assert 'correlation_id' in call_kwargs
        assert call_kwargs['error'] == "Test error"
```

### Previous Story Intelligence

**Story 17.5 (Sécuriser gestion secrets):**
- Status: done (2026-02-07)
- Impact: Module `core/startup_checks.py` avec validation fail-fast
- Learnings: Pattern validation robuste, logging structuré pour warnings/errors, tests coverage 21 tests
- Code review: 1 CRITICAL + 4 MEDIUM fixes appliqués

**Story 17.4 (OracleJSONField):**
- Status: done (2026-02-07)
- Impact: Custom field `core/fields.py` pour JSON validation
- Learnings: Validation optionnelle via paramètre, logging pour erreurs de sérialisation
- Pattern: Exceptions spécifiques (`json.JSONDecodeError`) plutôt que broad catch

**Story 17.3 (API client duplication):**
- Status: done (2026-02-06)
- Impact: Helpers HTTP partagés `frontend/src/services/api_client.ts`
- Learnings: Centralisation error handling, retry 401, parsing erreurs cohérent

**Story M.8 (Middleware logging observabilité):**
- Status: done (2026-02-05)
- Impact: `core/middleware.py` logging structuré, `docs/logging-conventions.md` créé
- Learnings: `structlog` obligatoire, `correlation_id` propagation, `exc_info=True` pour exceptions

### Git Intelligence Summary

**Commits récents Epic 17 (2026-02-06 to 2026-02-07):**
- `6d13795`: feat(17.5) - Fail-fast secret validation, startup checks
- `02f2f70`: refactor(17.4) - OracleJSONField implementation
- `325f8f4`: refactor(17.3) - API client shared helpers
- `b778ea6`: refactor(17.2) - ExecutionWizard decomposition

**Patterns établis:**
- Commits atomiques: `refactor(17.X): Description`
- Tests coverage validation systématique
- Code review avant done (adversarial review)
- Documentation mise à jour avec chaque story

**Code patterns observés:**
- Logging structuré: `logger.error("event_name", key=value, exc_info=True, correlation_id=get_correlation_id())`
- Exception handling: Spécifique d'abord, broad catch seulement si justifié
- Tests: `pytest-mock` pour mocker logger, `@patch` pour simuler exceptions
- Commentaires traçabilité: `# Story XX.X - Description`

### Project Context Reference

**Documentation critique:**
- `/Users/cyrille/Documents/Dev/test/idp-portal/django_backend/docs/logging-conventions.md`:
  - Ligne 97-114: Section "Exceptions" - Pattern `exc_info=True` pour traceback
  - Ligne 50-77: Niveaux de log ERROR pour exceptions nécessitant attention

- `/Users/cyrille/Documents/Dev/test/_bmad-output/planning-artifacts/architecture.md`:
  - Ligne 92: "Gestion d'erreur" - Pattern unifié, circuit breaker, erreur != crash
  - Ligne 96: "Observabilité" - Logs structurés, métriques, health checks

**État actuel du code:**
- 16 fichiers avec `except Exception` identifiés
- 3 occurrences analysées en détail:
  - `workflow_runtime.py` ligne 669: Capture step failures (large scope justifié)
  - `executions/views.py` ligne 428: ProfileService silent catch (PROBLÉMATIQUE - pas de log)
  - `executions/views.py` ligne 1641: Cron validation (devrait capturer `CroniterBadCronError` spécifique)

**Risques identifiés:**
- MEDIUM: Erreurs masquées silencieusement (ligne 428) compliquent debugging
- MEDIUM: Exceptions trop larges empêchent identification problèmes réels
- LOW: Bare excepts (`except:`) rendent code fragile (aucun trouvé encore)

### Story Completion Status

**Status:** ready-for-dev

**Prochaines étapes après dev-story:**
1. Code review adversarial (`code-review` workflow)
2. Validation: Scanner tous `except Exception` ont commentaire justification ou sont remplacés
3. Tests: Minimum 4 tests nouveaux passent
4. Update sprint-status.yaml: `17-6-restreindre-exception-catches: done`

**Critères de validation finale:**
- ✅ Tous `except Exception` ont soit commentaire "Story 17.6: Justified broad catch" soit sont remplacés
- ✅ Aucun bare `except:` restant (hors security-reports)
- ✅ Tous broad catches justifiés loggent avec `exc_info=True` + `correlation_id`
- ✅ Tests passent (4+ nouveaux tests minimum)
- ✅ Documentation `logging-conventions.md` mise à jour
- ✅ Rapport de refactoring créé
- ✅ Code review approuvé sans CRITICAL/HIGH bloquant

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- 15 `except Exception` occurrences audited across 11 Python files
- 0 bare `except:` found
- All pre-existing test failures confirmed NOT caused by Story 17.6 changes

### Completion Notes List

- ✅ Task 1: Audit complet - 15 occurrences identifiées et catégorisées (REPLACE: 2, JUSTIFIED: 13, SILENT: 7 corrigés après code review)
- ✅ Task 2: `workflow_runtime.py` - `exc_info=True` ajouté, error_message inclut type exception, commentaire Story 17.6
- ✅ Task 3: `executions/views.py` - ProfileService: WARNING log ajouté; Cron: remplacé par `CroniterBadCronError/CroniterBadDateError`
- ✅ Task 4: 9 fichiers restants corrigés - logging ajouté pour catches silencieux, `exc_info=True` pour catches existants
- ✅ Task 5: 0 bare `except:` trouvé, 0 `except Exception:` sans `as e` restant
- ✅ Task 6: 13 tests créés - workflow runtime (3), cron validation (4), ProfileService (1), dashboard (1), catalog (1), core permissions (1), code scan (2) - 13/13 passent
- ✅ Task 7: `logging-conventions.md` mis à jour, rapport refactoring créé, validation finale OK
- ✅ CODE REVIEW: dashboard/views.py silent exception fixed, +4 tests added, all HIGH/MEDIUM issues resolved

### Change Log

- 2026-02-07: Story 17.6 implementation complete - 15 except Exception occurrences audited, 2 replaced with specific exceptions, 13 justified with logging (exc_info=True + correlation_id), 9 tests added, documentation updated
- 2026-02-07: Code review fixes applied - dashboard/views.py logging added, test coverage improved to 13 tests (all passing), validation enhanced

### File List

**Modified:**
- `idp-portal/django_backend/executions/workflow_runtime.py` - exc_info=True, error_type in error_message
- `idp-portal/django_backend/executions/views.py` - ProfileService WARNING log, CroniterBadCronError/CroniterBadDateError specific catch
- `idp-portal/django_backend/catalog/views.py` - structlog import, ProfileService + InventoryService WARNING logs
- `idp-portal/django_backend/inventory/services.py` - exc_info=True, error_type added
- `idp-portal/django_backend/idp_auth/views.py` - exc_info=True, error_type added
- `idp-portal/django_backend/dashboard/views.py` - except (TypeError, AttributeError) with DEBUG logging for invalid timestamps (CODE REVIEW FIX)
- `idp-portal/django_backend/core/views.py` - exc_info=True, error_type, raise ConnectionError instead of Exception
- `idp-portal/django_backend/core/middleware.py` - error_type added, Story 17.6 comment
- `idp-portal/django_backend/core/permissions.py` - structlog import, WARNING log for ProfileService
- `idp-portal/django_backend/core/auth_utils.py` - structlog import, WARNING log for get_ad_groups()
- `idp-portal/django_backend/idp_backend/__init__.py` - WARNING log for Oracle client init failure
- `idp-portal/django_backend/docs/logging-conventions.md` - Exception handling section (Story 17.6)

**New:**
- `idp-portal/django_backend/executions/tests/test_exception_handling.py` - 13 tests Story 17.6 (CODE REVIEW +4 tests)
- `idp-portal/django_backend/docs/story-17-6-exception-refactor-report.md` - Refactoring report

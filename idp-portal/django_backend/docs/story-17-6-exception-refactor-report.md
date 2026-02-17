# Story 17.6 - Rapport de refactoring des exceptions

## Résumé

- **Date**: 2026-02-07
- **Scope**: Audit et refactoring de tous les `except Exception` dans le backend Django
- **Fichiers audités**: 11 fichiers Python
- **Occurrences trouvées**: 15 `except Exception`

## Résultats

| Catégorie | Nombre | Action |
|-----------|--------|--------|
| REPLACE (exceptions spécifiques) | 2 | Remplacés par exceptions ciblées |
| JUSTIFIED (broad catch documenté + loggé) | 13 | Commentaire Story 17.6 + `exc_info=True` ajouté |
| SILENT (pas de log) | 0 restant | Tous corrigés avec logging |
| Bare except (`except:`) | 0 | Aucun trouvé |
| `except Exception:` sans `as e` | 0 restant | Tous corrigés |

## Détail des modifications

### Remplacés par exceptions spécifiques (REPLACE)

1. **`dashboard/views.py:353`** - Calcul durée exécution
   - Avant: `except Exception:`
   - Après: `except (TypeError, AttributeError):`

2. **`executions/views.py:1641`** - Validation cron expression
   - Avant: `except Exception as e:`
   - Après: `except (CroniterBadCronError, CroniterBadDateError, ValueError) as e:`

### Broad catches justifiés avec logging ajouté (JUSTIFIED)

| Fichier | Ligne | Contexte | Améliorations |
|---------|-------|----------|---------------|
| `workflow_runtime.py` | 669 | Step execution failure | `exc_info=True`, commentaire 17.6, `error_type` dans error_message |
| `executions/views.py` | 428 | ProfileService indisponible | `as e` ajouté, WARNING log avec `exc_info=True` |
| `catalog/views.py` | 168 | ProfileService indisponible | `as e` ajouté, WARNING log avec `exc_info=True` |
| `catalog/views.py` | 212 | InventoryService indisponible | `as e` ajouté, WARNING log avec `exc_info=True` |
| `core/views.py` | 61 | Health check Oracle | `exc_info=True`, `error_type` ajoutés |
| `core/views.py` | 86 | Health check Vault | `exc_info=True`, `error_type` ajoutés |
| `core/views.py` | 116 | Health check ServiceNow | `exc_info=True`, `error_type` ajoutés |
| `inventory/services.py` | 337 | Oracle inventory read | `exc_info=True`, `error_type` ajoutés |
| `core/middleware.py` | 155 | Request logging middleware | `error_type` ajouté, commentaire 17.6 |
| `idp_auth/views.py` | 291 | ProfileService permissions | `exc_info=True`, `error_type` ajoutés |
| `core/permissions.py` | 51 | ProfileService DBOPS check | `as e` ajouté, WARNING log |
| `core/auth_utils.py` | 27 | get_ad_groups() | `as e` ajouté, WARNING log |
| `idp_backend/__init__.py` | 23 | Oracle client init | `as e` ajouté, WARNING log |

### Améliorations supplémentaires

- `core/views.py`: `raise Exception()` remplacé par `raise ConnectionError()` pour Vault et ServiceNow health checks
- Import `CroniterBadCronError`, `CroniterBadDateError` ajouté dans `executions/views.py`
- Import `structlog`, `get_correlation_id` ajouté dans `catalog/views.py`, `core/permissions.py`, `core/auth_utils.py`

## Tests ajoutés

| Test | Fichier | Description |
|------|---------|-------------|
| `test_unexpected_exception_logged_with_exc_info` | `test_exception_handling.py` | Workflow runtime logge `exc_info=True` pour exceptions inattendues |
| `test_unexpected_exception_saves_error_type_in_step` | `test_exception_handling.py` | ExecutionStep.error_message contient le type d'exception |
| `test_validation_error_caught_by_specific_handler` | `test_exception_handling.py` | ValueError toujours attrapé par handler spécifique |
| `test_invalid_cron_returns_validation_error` | `test_exception_handling.py` | Cron invalide retourne 200 avec valid=false |
| `test_valid_cron_returns_valid_true` | `test_exception_handling.py` | Cron valide retourne 200 avec valid=true |
| `test_missing_expression_returns_400` | `test_exception_handling.py` | Expression manquante retourne 400 |
| `test_profile_service_failure_logs_warning` | `test_exception_handling.py` | ProfileService failure logge WARNING |
| `test_no_bare_except_in_codebase` | `test_exception_handling.py` | Aucun bare except dans le codebase |
| `test_no_except_exception_without_as_e` | `test_exception_handling.py` | Tous les except Exception ont `as e` |

**Total: 9 tests ajoutés, 9/9 passent**

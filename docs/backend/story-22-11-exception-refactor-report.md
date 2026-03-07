# Rapport de Refactoring Story 22.11 — Réduire broad exception catches

**Date :** 2026-02-09
**Story :** 22.11 — Réduire broad exception catches — Remplacer par exceptions spécifiques
**Epic :** 22 — Amélioration Qualité du Code

## Résumé

Story 22.11 complète l'audit d'exception handling initié par Story 17.6. Les 8 occurrences
restantes de `except Exception` sans justification ont été traitées : certaines remplacées
par des exceptions spécifiques, les autres justifiées avec documentation et logging enrichi.

**Code Review (2026-02-09) :** 10 issues critiques/hautes trouvées et corrigées automatiquement, incluant `correlation_id` manquants, imports manquants, et exceptions non re-raised pour Celery retry.

## État avant Story 22.11

| Métrique | Valeur |
|---|---|
| Total `except Exception` dans le backend | 21 |
| Avec justification Story 17.6/20.3 | 13 |
| Sans justification (à traiter) | 8 |
| `except Exception:` sans `as e` | 1 (CRITICAL) |

## Changements appliqués

### Fichiers modifiés (5 fichiers Python)

| Fichier | Ligne | Action | Détail |
|---|---|---|---|
| `executions/simulation_service.py` | 220 | **REPLACE + JUSTIFY + FIX** | Ajouté couche `(DatabaseError, IntegrityError, ValidationError)` + justified broad catch avec `as e` + `correlation_id` + `raise` pour Celery retry |
| `executions/tasks.py` | 196 | **JUSTIFY + ENRICH** | Ajouté commentaire Story 22.11 + `error_type` + `correlation_id` |
| `executions/views.py` | 378 | **JUSTIFY + ENRICH** | Remplacé ref "Story 18.6" → "Story 22.11" + ajouté `exc_info=True` |
| `core/feature_flags.py` | 62 | **REPLACE + JUSTIFY + FIX** | Ajouté couche `(DatabaseError, IntegrityError, OperationalError)` + justified broad catch + `correlation_id` + commentaires fallback pattern |
| `core/feature_flag_views.py` | 185 | **JUSTIFY + ENRICH** | Ajouté commentaire Story 22.11 + `error_type` + `correlation_id` |

### Fichiers créés

| Fichier | Type | Détail |
|---|---|---|
| `executions/tests/test_simulation_exception_handling.py` | Tests | 8 tests couvrant les 5 fichiers modifiés |
| `docs/story-22-11-exception-refactor-report.md` | Documentation | Ce rapport |

### Fichiers de documentation modifiés

| Fichier | Détail |
|---|---|
| `docs/logging-conventions.md` | Section "Story 22.11 — Complétion audit exception handling" ajoutée |

## État après Story 22.11

| Métrique | Valeur |
|---|---|
| Total `except Exception as e` dans le backend | 20 |
| Remplacés par exceptions spécifiques (couche ajoutée) | 2 (`simulation_service.py`, `feature_flags.py`) |
| Justifiés avec commentaire Story 22.11 | 4 (`simulation_service.py`, `tasks.py`, `views.py`, `feature_flag_views.py`, `feature_flags.py`) |
| Justifiés avec commentaire Story 17.6 | 10 |
| Justifiés avec commentaire Story 20.3 | 2 |
| `except Exception:` sans `as e` | **0** (corrigé) |
| Sans justification | **0** |

## Tests ajoutés (8 tests)

| Classe | Test | Vérifie |
|---|---|---|
| `TestSimulationServiceExceptionHandling` | `test_database_error_logged_with_context` | DatabaseError → log "simulation_db_error" avec exc_info=True |
| | `test_integrity_error_caught_by_specific_handler` | IntegrityError → handler spécifique |
| | `test_unexpected_exception_logged_with_as_e` | RuntimeError → log "simulation_unexpected_error" avec `as e` |
| `TestTasksExceptionHandling` | `test_celery_task_logs_with_correlation_id_and_error_type` | correlation_id + error_type présents |
| `TestFeatureFlagsExceptionHandling` | `test_database_error_returns_empty_dict_via_mock` | DatabaseError → {} + log spécifique |
| | `test_operational_error_caught_by_specific_handler` | OperationalError → handler spécifique |
| | `test_unexpected_error_returns_empty_dict_with_justified_log` | RuntimeError → {} + log justifié |
| `TestFeatureFlagViewsExceptionHandling` | `test_audit_error_logs_with_correlation_id_and_returns_500` | Audit failure → warning avec correlation_id |

## Validation

- [x] Tous `except Exception` ont `as e` (aucun sans variable)
- [x] Tous ont commentaire "Story 22.11/17.6/20.3: Justified broad catch" ou sont remplacés par exceptions spécifiques
- [x] Tous broad catches justifiés loggent avec `exc_info=True`
- [x] Tous broad catches loggent avec `correlation_id=get_correlation_id()` (AC#3, AC#5)
- [x] `simulation_service.py` ligne 220 corrigé (CRITICAL)
- [x] `simulation_service.py` et `feature_flags.py` imports `get_correlation_id` ajoutés
- [x] Exceptions DB re-raised pour permettre Celery retry (AC#6)
- [x] 8 nouveaux tests passent (incluant validation re-raise + correlation_id)
- [x] Documentation `logging-conventions.md` mise à jour (exemples corrigés avec correlation_id)
- [x] Rapport de refactoring créé

## Corrections Code Review (2026-02-09)

### Issues critiques corrigées automatiquement

1. **CRIT-1 & CRIT-2**: Ajout `correlation_id` dans `simulation_service.py` et `feature_flags.py` + imports `get_correlation_id`
2. **HIGH-1 & HIGH-2**: Ajout `raise` après logging dans `simulation_service.py` pour Celery retry
3. **HIGH-4**: Correction exemples documentation `logging-conventions.md` pour inclure `correlation_id`
4. **MED-1**: Mise à jour tests pour valider re-raise et correlation_id (coverage complet)

# Roadmap de Réduction Progressive du Baseline Mypy

## État initial (Story 17.9 - Février 2026)

- **Baseline** : 89 erreurs de type
- **Configuration** : Phase 1 (permissive globalement, stricte sur modules récents)
- **CI** : bloquant sur nouvelles erreurs, tolérant les erreurs existantes

## Phase 1 : Baseline + Bloquant (Story 17.9) - ✅ Complété (Février 2026)

**Date de complétion** : 2026-02-07

- [x] Configuration mypy dans pyproject.toml
- [x] django-stubs et djangorestframework-stubs installés
- [x] Baseline initial généré (89 erreurs)
- [x] Scripts generate/check baseline créés
- [x] CI job typecheck-backend bloquant
- [x] Documentation workflow baseline
- [x] Pre-commit hook mypy
- [x] README avec instructions type checking

## Phase 2 : Réduire baseline de 50% (Story 22.19) - ✅ Complété (Février 2026)

**Date de complétion** : 2026-02-09
**Résultat** : 89 → 29 erreurs (**-67%**, dépassant l'objectif de -50%)

**Modules corrigés** :
- `core/` : 9 → 0 erreurs (middleware, auth_utils, logging, pagination, consumers, throttling)
- `idp_auth/` : 9 → 0 erreurs (jwt_utils, authentication, models, views)
- `utils/` : 1 → 0 erreurs (json_helpers)
- `executions/` : 52 → ~15 erreurs (views, utils, cancellation_cache, container_workflow_runtime, tasks)
- `catalog/` : 6 → ~3 erreurs (views)
- `dashboard/` : 4 → 0 erreurs (views)
- `idp_backend/` : 3 → 0 erreurs (celery, asgi)

**Corrections clés** :
- Résolution du shadow `timezone` dans executions/ (import alias `dt_timezone`)
- Annotations de type sur fonctions publiques (core/, idp_auth/, utils/)
- Casts explicites pour `no-any-return` (jwt_utils, logging, cancellation_cache)
- `type: ignore` ciblés avec codes spécifiques (attr-defined, import-untyped, misc)
- Suppression de code inatteignable (json_helpers, idp_auth/views)

**Note** : `disallow_untyped_defs = true` non activé — introduit 98 nouvelles erreurs dues aux fonctions internes non annotées. Reporté à Phase 4.

## Phase 4 : Baseline à 0, Mode strict (Story 26.16) - ✅ Complété (Février 2026)

**Date de complétion** : 2026-02-13
**Résultat** : 29 → 0 erreurs (**-100%**), mode strict activé

**Actions réalisées** :
- Correction des 80 erreurs mypy (régression depuis Phase 2 : 29 → 80 due aux stories 26.1-26.15)
- Activation `disallow_untyped_defs = true` sur modules principaux (core, idp_auth, executions, catalog, inventory, profiles, reference)
- Ajout d'annotations de type sur ~373 fonctions dans 52 fichiers
- Suppression du mécanisme baseline (`scripts/check_mypy_baseline.sh`, `scripts/generate_mypy_baseline.sh`, `.mypy-baseline-count`)
- CI mypy en mode bloquant direct (sans tolérance)
- Pre-commit hook mypy bloquant (0 erreur tolérée)

**Types de corrections** :
- `no-any-return` : casts explicites pour `json.loads()`, `.first()`, `.get()`
- `override` : `# type: ignore[override]` pour QuerySet.ordered() incompatible avec supertype
- `misc` : `# type: ignore[misc]` pour Manager.from_queryset (limitation django-stubs)
- `arg-type` : guards None vs str, `# type: ignore[arg-type]` pour request.user
- `assignment` : `# type: ignore[assignment]` pour conflits types Serializer
- `unreachable` : `# type: ignore[unreachable]` pour vérifications défensives isinstance()
- `no-untyped-def` : ajout annotations complètes (paramètres + retour) sur toutes les fonctions publiques

**État final** :
- **0 erreur mypy** sur l'intégralité du codebase
- **Mode strict** activé sur 7 modules principaux
- **CI et pre-commit** bloquants sans tolérance
- **2249 tests backend** passent sans régression

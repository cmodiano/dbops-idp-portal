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

**Note** : `disallow_untyped_defs = true` non activé — introduit 98 nouvelles erreurs dues aux fonctions internes non annotées. Reporté à Phase 3/4.

## Phase 3 : Réduire baseline de 80% (Août 2026 - 6 mois cumulés)

**Objectif** : Réduire de 89 à ~18 erreurs (-80%) — baseline actuel : 29
**Date cible** : Août 2026
**Erreurs restantes à corriger** : ~11

**Modules restants** :
- `executions/` : ~15 erreurs (services, models, remaining views)
- `reference/` : ~5 erreurs
- `integrations/` : ~4 erreurs
- `catalog/` : ~3 erreurs restantes
- `inventory/` : ~2 erreurs

**Actions** :
- Annoter fonctions dans executions/services et models
- Corriger erreurs `override` (Manager/QuerySet)
- Activer `disallow_untyped_defs = true` sur core/, idp_auth/, utils/ (fonctions internes à annoter d'abord)

## Phase 4 : Baseline à 0, Mode strict (Février 2027 - 12 mois cumulés)

**Objectif** : 0 erreurs, mode strict complet
**Date cible** : Février 2027
**Velocity cible** : ~6 erreurs corrigées/mois + refactoring strict

**Actions** :
- Corriger toutes les erreurs restantes
- Activer `disallow_untyped_defs = true` globalement
- Activer `disallow_any_generics = true`
- Activer `strict_settings = true` dans django-stubs
- Supprimer le mécanisme baseline (plus nécessaire)
- Mypy en mode `--strict` sur tout le codebase

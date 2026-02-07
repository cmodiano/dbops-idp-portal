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

## Phase 2 : Réduire baseline de 50% (Mai 2026 - 3 mois)

**Objectif** : Réduire de 89 à ~45 erreurs (-50%)
**Date cible** : Mai 2026
**Velocity cible** : ~15 erreurs corrigées/mois

**Modules prioritaires** :
- `core/` : middleware, auth_utils, permissions, logging
- `idp_auth/` : jwt_utils, authentication, models
- `utils/` : json_helpers

**Actions** :
- Annoter les fonctions publiques de core/ et idp_auth/
- Corriger les erreurs `no-any-return` (casts explicites)
- Corriger les erreurs `var-annotated` (annotations manquantes)
- Activer `disallow_untyped_defs = true` sur core/ et idp_auth/

## Phase 3 : Réduire baseline de 80% (Août 2026 - 6 mois cumulés)

**Objectif** : Réduire de 89 à ~18 erreurs (-80%)
**Date cible** : Août 2026
**Velocity cible** : ~12 erreurs corrigées/mois

**Modules** :
- `catalog/` : models, services, views
- `executions/` : services, views
- `integrations/` : services, validation
- `inventory/` : services

**Actions** :
- Annoter tous les services et views
- Corriger les erreurs `override` (Manager/QuerySet)
- Activer `disallow_untyped_defs = true` sur tous les modules applicatifs

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

# Architecture Decision Records (ADRs) — IDP Portal

> **Format :** [Michael Nygard ADR](https://github.com/joelparkerhenderson/architecture-decision-record)
> **Contexte :** Décisions architecturales du projet IDP Portal — initialement issues de la migration FastAPI → Django REST Framework (Epic M, février 2026), puis enrichies par les décisions post-migration (DI, Workflow Steps, etc.)

## Index des ADRs

| ADR | Titre | Statut | Date |
|-----|-------|--------|------|
| [ADR-001](adr-001-django-orm-vs-sql-brut.md) | Choix Django ORM vs SQL brut pour la couche données | Accepté | 2026-02-03 |
| [ADR-002](adr-002-structure-apps-django.md) | Structure en Apps Django Modulaires | Accepté | 2026-02-03 |
| [ADR-003](adr-003-migration-repositories-vers-services.md) | Migration Repositories FastAPI vers Services Django | Accepté | 2026-02-03 |
| [ADR-004](adr-004-gestion-champs-json-oracle.md) | Gestion des Champs JSON avec Oracle Database | Accepté | 2026-02-03 |
| [ADR-005](adr-005-strategie-tests-pytest-django.md) | Stratégie de Tests avec pytest-django | Accepté | 2026-02-03 |
| [ADR-006](adr-006-dependency-injection.md) | Injection de dépendances pour les services principaux (Option A) | Accepté | 2026-02-21 |
| [ADR-007](adr-007-workflow-step-based-change-management.md) | Architecture Steps Unifiée — Change Management, Gates, Evaluations et Approbations | Proposé | 2026-03-02 |

## Comment ajouter un nouvel ADR

1. Copier le [template](adr-template.md)
2. Numéroter séquentiellement (ADR-006, ADR-007, etc.)
3. Nommer le fichier : `adr-NNN-titre-court.md`
4. Mettre à jour cet index
5. Statut initial : `Proposé` → `Accepté` après validation équipe

## Quand créer un ADR

- Choix de technologie ou framework
- Pattern architectural significatif
- Décision ayant un impact sur plusieurs apps ou développeurs
- Compromis technique nécessitant documentation pour les futurs développeurs

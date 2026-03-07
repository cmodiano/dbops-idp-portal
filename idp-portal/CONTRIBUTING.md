# Contribuer à IDP Portal

## Avant de soumettre une PR

Vérifiez les checklists suivantes avant chaque Pull Request :

| Checklist | Portée |
|-----------|--------|
| [Checklist SOLID](../docs/backend/standards/solid-checklist.md) | Conformité SRP, OCP, DIP, ISP, LSP |
| [Checklist nouvel endpoint DRF](../docs/backend/standards/endpoint-checklist.md) | Validation, RBAC, audit trail, format réponse |
| [Pre-PR security checklist](../docs/backend/security-django/pre-pr-checklist.md) | Sécurité, injection, secrets, CORS |

## Guides techniques

- [Documentation backend](../docs/backend/README-django.md) — Architecture, API, observabilité, RBAC
- [Conformité SOLID](../docs/backend/solid-guidelines.md) — Patterns SRP/OCP/LSP/ISP/DIP avec exemples du code réel
- [ADR-006 — Injection de dépendances](../docs/backend/decisions/adr-006-dependency-injection.md) — Référence canonique pour DIP (Option A)
- [Conventions de logging](../docs/backend/logging-conventions.md) — structlog, correlation_id
- [Guide mypy](../docs/backend/mypy-developer-guide.md) — Typage statique progressif

## Décisions d'architecture (ADRs)

Les ADRs se trouvent dans `docs/backend/decisions/`. Créer un ADR pour toute décision d'architecture significative.

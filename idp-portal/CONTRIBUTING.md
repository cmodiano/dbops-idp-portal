# Contribuer à IDP Portal

## Avant de soumettre une PR

Vérifiez les checklists suivantes avant chaque Pull Request :

| Checklist | Portée |
|-----------|--------|
| [Checklist SOLID](django_backend/docs/standards/solid-checklist.md) | Conformité SRP, OCP, DIP, ISP, LSP |
| [Checklist nouvel endpoint DRF](django_backend/docs/standards/endpoint-checklist.md) | Validation, RBAC, audit trail, format réponse |
| [Pre-PR security checklist](django_backend/docs/security/pre-pr-checklist.md) | Sécurité, injection, secrets, CORS |

## Guides techniques

- [Documentation backend](django_backend/docs/README.md) — Architecture, API, observabilité, RBAC
- [Conformité SOLID](django_backend/docs/solid-guidelines.md) — Patterns SRP/OCP/LSP/ISP/DIP avec exemples du code réel
- [ADR-006 — Injection de dépendances](django_backend/docs/decisions/adr-006-dependency-injection.md) — Référence canonique pour DIP (Option A)
- [Conventions de logging](django_backend/docs/logging-conventions.md) — structlog, correlation_id
- [Guide mypy](django_backend/docs/mypy-developer-guide.md) — Typage statique progressif

## Décisions d'architecture (ADRs)

Les ADRs se trouvent dans `django_backend/docs/decisions/`. Créer un ADR pour toute décision d'architecture significative.

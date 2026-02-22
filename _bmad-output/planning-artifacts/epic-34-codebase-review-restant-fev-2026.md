# Epic 34 : Corrections restantes — Codebase Review IDP Portal (mise à jour 21 février 2026)

**En tant que** équipe de développement,  
**je veux** traiter les points restants du CODEBASE-REVIEW (nouveaux findings §13 + audit SOLID §14–15),  
**afin de** réduire la dette technique, respecter SOLID et corriger les derniers bugs identifiés.

---

## Contexte

**Source :** `idp-portal/CODEBASE-REVIEW.md` (mise à jour 2026-02-21)

**Périmètre :** Backend Django + Frontend React

**Bilan :** 70 findings résolus ; **26 ouverts** dont :
- 1 CRITICAL (SOLID-FE-1 — ExecutionTimeline god component)
- 9 HIGH (bugs Ant Design résiduels, SOLID-BE-1/2/3, SOLID-FE-2/3/4/5)
- 13 MEDIUM (NEW-1, NEW-3, SOLID-BE-4 à 9, SOLID-FE-6 à 10)
- 4 LOW (SOLID-BE-10/11, SOLID-FE-11, INCON-2 documenté)

**Priorités recommandées dans le document :**
- **Sprint immédiat (quick wins) :** SOLID-BE-8, SOLID-BE-11, SOLID-FE-5, SOLID-FE-10, BUG-FE-1b/2b
- **Sprint suivant :** SOLID-BE-3, SOLID-BE-4, SOLID-FE-1, SOLID-FE-2, SOLID-FE-3
- **Backlog structurel :** SOLID-BE-1, SOLID-BE-2, SOLID-BE-5, SOLID-FE-4

---

## Stories

| # | Story | Issues couvertes | Priorité |
|---|-------|------------------|----------|
| 34.1 | Quick wins Backend — DI, queryset, validation | SOLID-BE-8, NEW-1, SOLID-BE-11 | Haute |
| 34.2 | Quick wins Frontend — notification, status, Ant Design | SOLID-FE-5, SOLID-FE-10, BUG-FE-1b/2b | Haute |
| 34.3 | Backend — Cache RBAC, split services, LSP serializers | NEW-3, SOLID-BE-4, SOLID-BE-6 | Moyenne |
| 34.4 | Backend — RuntimeRegistry, Webhooks DI | SOLID-BE-7, SOLID-BE-9 | Moyenne |
| 34.5 | Backend — Poller générique unifié | SOLID-BE-3 | Moyenne |
| 34.6 | Backend — Éclater executions/utils.py | SOLID-BE-1 | Backlog |
| 34.7 | Backend — Décomposer workflow_runtime.py | SOLID-BE-2 | Backlog |
| 34.8 | Backend — Décomposer inventory/services.py | SOLID-BE-5 | Backlog |
| 34.9 | Frontend — Variant context, WorkflowStepsEditor | SOLID-FE-6, SOLID-FE-8 | Moyenne |
| 34.10 | Frontend — useCatalogState (CatalogPage) | SOLID-FE-2 | Haute |
| 34.11 | Frontend — useAuditFilters + composants (AuditPage) | SOLID-FE-3 | Haute |
| 34.12 | Frontend — Découper ExecutionTimeline (god component) | SOLID-FE-1 | Critique |
| 34.13 | Frontend — DIP services, props, ExecutionWizard | SOLID-FE-4, SOLID-FE-7, SOLID-FE-9 | Backlog |
| 34.14 | Frontend — Tests manquants composants critiques | SOLID-FE-11 | Basse |
| 34.15 | Backend — ISP BaseAdapter (optionnel) | SOLID-BE-10 | Basse |

---

## Références

- `idp-portal/CODEBASE-REVIEW.md` — sections 13 (Nouveaux findings), 14 (SOLID Backend), 15 (SOLID Frontend), 16 (Récapitulatif)
- Epic 30 (corrections première vague) — déjà traité
- Epic 33 (conformité SOLID) — registry, découpage tasks/views, DI partiel

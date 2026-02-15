# Story 29.3 : Alignement REF_ENGINES ↔ engine_type inventaire

Status: backlog

<!-- Note: Un seul référentiel pour les moteurs DB : REF_ENGINES utilisé par catalogue ET inventaire. -->

## Story

En tant que **système**,
je veux **un référentiel unique pour les moteurs de base de données (REF_ENGINES) utilisé à la fois par le catalogue d'actions et l'inventaire des cibles**,
afin que **les filtres et les profils RBAC par engine_type soient cohérents et alignés**.

## Acceptance Criteria

**AC1 — Alignement engine_type sur REF_ENGINES**

**Given** REF_ENGINES contient les moteurs (Oracle, SQL Server, Azure SQL, DB2, CosmosDB, etc.),
**When** l'inventaire expose des cibles avec attribut engine_type,
**Then** engine_type doit être aligné sur les codes REF_ENGINES (convention : minuscules/snake_case, ex. oracle, sql_server),
**And** la documentation du mapping inventaire (InventoryMapper) décrit comment mapper les colonnes sources vers les valeurs REF_ENGINES.

**AC2 — API et utilisation**

**And** GET /api/v1/reference/engines retourne la liste des valeurs valides pour engine_type,
**And** les profils (filter_by_attribute_json avec engine_type) et filtres API inventaire utilisent les mêmes valeurs.

**AC3 — Tests**

**And** des tests valident la cohérence des valeurs engine_type avec REF_ENGINES.

## Tasks / Subtasks

- [ ] Task 1 — REF_ENGINES
  - [ ] 1.1 S'assurer que REF_ENGINES contient Oracle, SQL Server, Azure SQL, DB2, CosmosDB (+ autres moteurs métier)
  - [ ] 1.2 Documenter la convention de nommage (CODE en base vs engine_type pour inventaire : minuscules, snake_case)

- [ ] Task 2 — Documentation mapping inventaire
  - [ ] 2.1 Documenter dans docs/ ou implementation-artifacts/ comment InventoryMapper mappe les colonnes sources vers engine_type
  - [ ] 2.2 Lister les valeurs engine_type valides (= REF_ENGINES)

- [ ] Task 3 — Cohérence RBAC et filtres
  - [ ] 3.1 Vérifier que filter_by_attribute_json (engine_type) utilise des valeurs alignées REF_ENGINES
  - [ ] 3.2 Vérifier les filtres API inventaire (?engine_type=)

- [ ] Task 4 — Tests
  - [ ] 4.1 Test : valeurs engine_type dans inventaire sont sous-ensemble ou égal à REF_ENGINES
  - [ ] 4.2 Test : GET /reference/engines retourne la liste complète

## Dev Notes

### Contexte

- **Epic 29** : Clarification modèle Plateformes / Moteurs / Services.
- Actuellement engine_type (inventaire) n'a pas de référentiel central ; REF_ENGINES (catalogue) en a un. Objectif : une seule source de vérité.

### Convention de mapping

- REF_ENGINES.CODE (ex. "Oracle", "SQL Server") → engine_type inventaire (ex. "oracle", "sql_server")
- Définir et documenter la transformation (toLowerCase, remplacement espaces par _)

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 29.
- [Source: idp-portal/docs/rapport-bases-moteurs-technologies-integrations.md] — Section 2.4 engine_type.
- [Source: idp-portal/django_backend/reference/models.py] — RefEngine.
- [Source: idp-portal/django_backend/inventory/] — InventoryMapper, filtres.

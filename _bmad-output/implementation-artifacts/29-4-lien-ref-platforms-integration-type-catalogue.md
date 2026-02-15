# Story 29.4 : Lien explicite REF_PLATFORMS ↔ IntegrationTypeCatalogue

Status: backlog

<!-- Note: Garantir la cohérence action.platform (REF_PLATFORMS) ↔ integration.type (IntegrationTypeCatalogue). -->

## Story

En tant que **système**,
je veux **un lien formel entre REF_PLATFORMS (codes plateformes pour le catalogue d'actions) et les types d'intégration (IntegrationTypeCatalogue)**,
afin que **la cohérence action.platform ↔ integration.type soit garantie et documentée**.

## Acceptance Criteria

**AC1 — Mapping REF_PLATFORMS ↔ IntegrationTypeCatalogue**

**Given** REF_PLATFORMS contient les plateformes (AAP, GitHub Actions, Azure DevOps, Terraform Cloud, Tower),
**When** une action référence une intégration de type plateforme,
**Then** action.platform (REF_PLATFORMS.CODE) et integration.type (IntegrationTypeCatalogue) doivent être cohérents,
**And** un mapping explicite est documenté ou implémenté (table de liaison, config, ou convention documentée),
**And** REF_PLATFORMS est complété si nécessaire (Tower, Terraform Cloud) pour couvrir tous les types plateforme du catalogue.

**AC2 — Validation backend**

**And** la validation backend (création/édition action) vérifie la cohérence platform ↔ integration.type quand les deux sont renseignés.

**AC3 — Tests**

**And** des tests valident le mapping et la validation.

## Tasks / Subtasks

- [ ] Task 1 — Compléter REF_PLATFORMS
  - [ ] 1.1 Vérifier que REF_PLATFORMS inclut : AAP, GitHub Actions, Azure DevOps, Terraform Cloud, Tower
  - [ ] 1.2 Ajouter les entrées manquantes (migration SQL ou fixture) si nécessaire

- [ ] Task 2 — Mapping explicite
  - [ ] 2.1 Créer document ou config décrivant le mapping : REF_PLATFORMS.CODE ↔ IntegrationTypeCatalogue.code
  - [ ] 2.2 Exemples : AAP ↔ aap, "GitHub Actions" ↔ github_actions, "Terraform Cloud" ↔ terraform_cloud, etc.

- [ ] Task 3 — Validation backend
  - [ ] 3.1 Dans le serializer/service catalogue (create/update action), si integration_id et platform sont fournis : vérifier cohérence
  - [ ] 3.2 Retourner 400 avec message explicite si incohérence (ex. platform=AAP mais integration.type=servicenow)

- [ ] Task 4 — Tests
  - [ ] 4.1 Test : action avec integration plateforme + platform cohérent → OK
  - [ ] 4.2 Test : action avec integration plateforme + platform incohérent → 400
  - [ ] 4.3 Test : mapping documenté couvre tous les types plateforme

## Dev Notes

### Contexte

- **Epic 29** : Clarification modèle Plateformes / Moteurs / Services.
- Actuellement la cohérence REF_PLATFORMS ↔ IntegrationTypeCatalogue est implicite (noms proches mais pas identiques : "Terraform" vs "terraform_cloud").

### Mapping proposé

| REF_PLATFORMS.CODE | IntegrationTypeCatalogue.code |
|--------------------|------------------------------|
| AAP                | aap                          |
| Tower              | tower                        |
| GitHub Actions     | github_actions               |
| Azure DevOps       | azure_devops                 |
| Terraform Cloud    | terraform_cloud              |

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 29.
- [Source: idp-portal/docs/rapport-bases-moteurs-technologies-integrations.md] — Section 2.2, 3.2.
- [Source: idp-portal/django_backend/reference/models.py] — RefPlatform.
- [Source: idp-portal/django_backend/catalog/serializers.py] — Validation platform.

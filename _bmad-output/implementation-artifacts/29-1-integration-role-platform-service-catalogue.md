# Story 29.1 : Champ integration_role (platform/service) dans IntegrationTypeCatalogue

Status: backlog

<!-- Note: Distinguer plateformes d'exécution (AAP, GitHub Actions, etc.) des services consommés (Vault, ServiceNow, Jira, Splunk) via un champ integration_role. -->

## Story

En tant que **DBOPS**,
je veux **que le catalogue d'intégrations distingue explicitement les plateformes d'exécution (AAP, GitHub Actions, etc.) des services consommés (Vault, ServiceNow, Jira, Splunk)**,
afin que **les formulaires et règles métier puissent traiter correctement chaque type d'intégration**.

## Acceptance Criteria

**AC1 — Champ integration_role sur IntegrationTypeCatalogue**

**Given** le modèle IntegrationTypeCatalogue existant,
**When** on étend le catalogue pour catégoriser les types,
**Then** un champ **integration_role** est ajouté avec les valeurs `platform` | `service`,
**And** les fixtures sont mises à jour : plateformes = aap, github_actions, azure_devops, terraform_cloud, tower ; services = vault, servicenow, jira, splunk,
**And** l'API GET /api/v1/integrations/types/ expose le champ integration_role,
**And** un paramètre optionnel `?role=platform` ou `?role=service` permet de filtrer les types.

**AC2 — Frontend et tests**

**And** le frontend formulaire Admin Intégrations peut optionnellement grouper ou distinguer visuellement plateformes vs services,
**And** des tests valident le chargement des fixtures et la réponse API.

## Tasks / Subtasks

- [ ] Task 1 — Backend : champ et migration
  - [ ] 1.1 Ajouter champ integration_role (CharField, choices platform|service) sur modèle IntegrationTypeCatalogue
  - [ ] 1.2 Créer migration Django pour la colonne
  - [ ] 1.3 Exposer le champ dans le serializer et l'API GET /integrations/types/

- [ ] Task 2 — Fixtures
  - [ ] 2.1 Mettre à jour integration_type_catalogue.json et fixtures des types individuels avec integration_role
  - [ ] 2.2 Plateformes : aap, github_actions, azure_devops, terraform_cloud, tower
  - [ ] 2.3 Services : vault, servicenow, jira, splunk (ajouter splunk si absent)

- [ ] Task 3 — API filtre par role
  - [ ] 3.1 Ajouter paramètre query `role` (platform|service) sur endpoint GET /integrations/types/
  - [ ] 3.2 Filtrer les résultats selon le rôle demandé

- [ ] Task 4 — Frontend (optionnel)
  - [ ] 4.1 Grouper ou distinguer visuellement les types plateformes vs services dans le formulaire Admin Intégrations

- [ ] Task 5 — Tests
  - [ ] 5.1 Tests chargement fixtures avec integration_role
  - [ ] 5.2 Tests API : réponse inclut integration_role, filtre ?role= fonctionne

## Dev Notes

### Contexte

- **Epic 29** : Clarification modèle Plateformes / Moteurs / Services.
- **Plateformes** : où l'action s'exécute (AAP, GitHub Actions, Azure DevOps, Terraform Cloud, Tower).
- **Services** : consommés par les actions ou intégrations (Vault = credentials, ServiceNow = tickets, Jira = issues, Splunk = logs).

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 29.
- [Source: idp-portal/docs/rapport-bases-moteurs-technologies-integrations.md] — Rapport de clarification.
- [Source: idp-portal/django_backend/integrations/] — Modèles et fixtures existants.

# Story 27.10 : Adapter Jira comme service — fixture et JiraService

Status: backlog

<!-- Note: Jira comme service consommé par les actions (create_issue, update_issue), similaire à ServiceNow. -->

## Story

En tant que **système backend** (ou action d'exécution),
je veux **un service Jira (JiraService) et une configuration d'intégration Jira dans le catalogue, pour créer et mettre à jour des issues depuis les étapes d'action**,
afin que **une action puisse appeler Jira (comme ServiceNow) pour créer une issue, mettre à jour son statut, etc.**.

## Acceptance Criteria

**AC1 — Fixture et catalogue**

**Given** le catalogue d'intégration existant (IntegrationTypeCatalogue),
**When** on ajoute Jira,
**Then** une **fixture** jira_integration_type (ou entrée dans integration_type_catalogue) définit le type `jira` avec les actions : create_issue, update_issue, get_issue_status (ou équivalent selon API Jira),
**And** les paramètres requis et optionnels sont documentés (projet, type issue, résumé, description, statut, etc.).

**AC2 — JiraService**

**Given** une configuration d'intégration Jira valide (base_url, credential_ref pour API token ou PAT),
**When** une étape d'action appelle le service Jira,
**Then** le **JiraService** (ou JiraAdapter) implémente les actions : créer une issue, mettre à jour une issue, récupérer le statut,
**And** l'authentification Jira (API token, OAuth, Basic) est supportée selon les standards Jira Cloud / Server,
**And** le service est consommable depuis le moteur d'exécution (étape de type jira) comme ServiceNow.

**AC3 — Admin et tests**

**And** Jira apparaît dans le menu Admin > Intégrations (type jira) pour créer et éditer les configurations,
**And** le seed_integration_types ou équivalent inclut jira dans les types attendus,
**And** des tests unitaires (mock API Jira) valident le JiraService.

## Tasks / Subtasks

- [ ] Task 1 — Fixture Jira
  - [ ] 1.1 Créer jira_integration_type.json (ou ajouter dans integration_type_catalogue.json)
  - [ ] 1.2 Définir type jira avec actions : create_issue, update_issue, get_issue_status
  - [ ] 1.3 Documenter required_params et optional_params pour chaque action (projet, issuetype, summary, description, assignee, status, etc.)
  - [ ] 1.4 Ajouter jira à seed_integration_types expected_types

- [ ] Task 2 — JiraService
  - [ ] 2.1 Créer services/jira.py (ou adapters/services/jira_service.py) avec classe JiraService
  - [ ] 2.2 Implémenter create_issue(project, issuetype, summary, description, ...)
  - [ ] 2.3 Implémenter update_issue(issue_key, fields={...})
  - [ ] 2.4 Implémenter get_issue_status(issue_key)
  - [ ] 2.5 Authentification : API token (Bearer ou Basic), credential_ref depuis Vault
  - [ ] 2.6 Support Jira Cloud et/ou Jira Server (API REST v3 / v2)

- [ ] Task 3 — Intégration moteur d'exécution
  - [ ] 3.1 Brancher l'étape de type jira dans le moteur (comme servicenow)
  - [ ] 3.2 Résoudre credential_ref via VaultService pour obtenir le token Jira

- [ ] Task 4 — Admin et tests
  - [ ] 4.1 Vérifier que jira apparaît dans GET /integrations/types/
  - [ ] 4.2 Tests unitaires JiraService (mock requests / responses API Jira)
  - [ ] 4.3 Tests intégration : création intégration type jira, appel create_issue (mock)

## Dev Notes

### Contexte

- **Epic 27** : Adapters d'intégration backend.
- **Jira** = service (consommé), comme ServiceNow. Une action peut appeler Jira pour créer une issue, tracer une demande, etc.
- IntegrationType.JIRA existe déjà dans models.py ; il manque la fixture et l'implémentation.

### API Jira (référence)

- Jira Cloud REST API v3 : https://developer.atlassian.com/cloud/jira/platform/rest/v3/
- Endpoints typiques : POST /rest/api/3/issue (create), PUT /rest/api/3/issue/{issueIdOrKey} (update), GET /rest/api/3/issue/{issueIdOrKey} (get)

### Actions proposées

| Action         | Description                    | Params principaux                                      |
|----------------|--------------------------------|--------------------------------------------------------|
| create_issue   | Créer une issue                | project, issuetype, summary, description, assignee?    |
| update_issue   | Mettre à jour une issue        | issue_key, fields (status, assignee, comment, etc.)    |
| get_issue_status | Récupérer le statut d'une issue | issue_key                                            |

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 27.
- [Source: idp-portal/django_backend/integrations/models.py] — IntegrationType.JIRA.
- [Source: idp-portal/django_backend/integrations/fixtures/] — servicenow, vault pour modèle.
- [Source: idp-portal/django_backend/core/vault_service.py] — résolution credential_ref.

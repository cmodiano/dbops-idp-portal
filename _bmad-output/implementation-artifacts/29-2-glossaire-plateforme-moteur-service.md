# Story 29.2 : Glossaire produit Plateforme / Moteur / Service

Status: backlog

<!-- Note: Document de référence définissant les trois concepts et leurs exemples pour aligner les équipes. -->

## Story

En tant que **équipe produit et utilisateur**,
je veux **un glossaire documentant les trois concepts (Plateforme, Moteur, Service) avec des exemples concrets**,
afin que **tout le monde parle le même langage et évite les confusions**.

## Acceptance Criteria

**AC1 — Définition des trois termes**

**Given** un document de référence,
**When** on consulte le glossaire,
**Then** les trois termes sont définis clairement :
  - **Plateforme** : environnement où une action s'exécute (ex. AAP, GitHub Actions),
  - **Moteur** : technologie de base de données ciblée par l'action (ex. Oracle, SQL Server),
  - **Service** : système consommé par une action ou une intégration (ex. Vault pour credentials, ServiceNow pour tickets),

**And** des exemples sont fournis pour chaque catégorie (liste Plateformes, Moteurs, Services),
**And** le document explique la différence entre plateforme et service (exécution vs consommation).

**AC2 — Intégration documentation**

**And** le glossaire est intégré ou référencé dans la doc technique (docs/ ou implementation-artifacts/).

## Tasks / Subtasks

- [ ] Task 1 — Rédaction glossaire
  - [ ] 1.1 Créer document (ex. docs/glossaire-plateforme-moteur-service.md ou implementation-artifacts/)
  - [ ] 1.2 Définir Plateforme, Moteur, Service avec exemples
  - [ ] 1.3 Lister : Plateformes (AAP, GitHub Actions, Azure DevOps, Terraform Cloud, Tower), Moteurs (Oracle, SQL Server, Azure SQL, DB2, CosmosDB), Services (Vault, ServiceNow, Jira, Splunk)
  - [ ] 1.4 Expliquer la différence plateforme (exécute) vs service (consommé)

- [ ] Task 2 — Référencement
  - [ ] 2.1 Référencer le glossaire dans la doc existante (rapport bases moteurs, README, etc.)

## Dev Notes

### Contexte

- **Epic 29** : Clarification modèle Plateformes / Moteurs / Services.
- Ce glossaire résout les confusions identifiées dans rapport-bases-moteurs-technologies-integrations.md.

### Exemples à inclure

| Catégorie   | Exemples                                                |
|-------------|---------------------------------------------------------|
| Plateformes | AAP, GitHub Actions, Azure DevOps, Terraform Cloud, Tower |
| Moteurs     | Oracle, SQL Server, Azure SQL, DB2, CosmosDB            |
| Services    | Vault (credentials), ServiceNow (tickets), Jira (issues), Splunk (logs) |

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 29.
- [Source: idp-portal/docs/rapport-bases-moteurs-technologies-integrations.md].

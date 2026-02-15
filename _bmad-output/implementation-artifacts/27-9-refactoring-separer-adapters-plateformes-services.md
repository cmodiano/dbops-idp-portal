# Story 27.9 : Refactoring — séparer adapters plateformes et services

Status: backlog

<!-- Note: Structure de code reflétant le modèle métier : plateformes (exécution) vs services (consommés). -->

## Story

En tant que **équipe de développement**,
je veux **une structure de code qui distingue clairement les plateformes d'exécution (adapters/) des services consommés (services/)**,
afin que **on sache où ajouter une nouvelle intégration et que l'architecture reflète le modèle métier (plateforme = exécute, service = consommé)**.

## Acceptance Criteria

**AC1 — Structure plateformes vs services**

**Given** la structure actuelle (adapters/ avec AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud ; core/vault_service ; ServiceNow dans le flux d'exécution),
**When** on refactore,
**Then** les **plateformes** restent ou sont regroupées dans `adapters/platforms/` (ou `adapters/` dédié aux plateformes) : AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud,
**And** les **services** sont regroupés dans un module `services/` (ou `adapters/services/`) : Vault (déplacé depuis core/), ServiceNow, Splunk (Story 27.8),
**And** une factory ou point d'entrée permet d'obtenir le bon client selon le type (get_platform_adapter vs get_service_client ou équivalent),
**And** les imports et références sont mis à jour (core.vault_service → services.vault, etc.).

**AC2 — Documentation et tests**

**And** la documentation (README, integration-type-catalogue) reflète la nouvelle structure,
**And** les tests existants continuent de passer sans régression,
**And** la distinction plateforme vs service est documentée (glossaire ou doc technique).

## Tasks / Subtasks

- [ ] Task 1 — Créer structure services/
  - [ ] 1.1 Créer module services/ (django_backend/services/ ou adapters/services/)
  - [ ] 1.2 Déplacer core/vault_service.py → services/vault.py (ou services/vault_service.py)
  - [ ] 1.3 Créer services/__init__.py avec get_service_client() ou factory

- [ ] Task 2 — Structure adapters/ (optionnel)
  - [ ] 2.1 Option A : garder adapters/ tel quel (seulement plateformes)
  - [ ] 2.2 Option B : créer adapters/platforms/ et déplacer AAP, Tower, etc. dedans
  - [ ] 2.3 Mettre à jour get_platform_adapter() et imports

- [ ] Task 3 — Consolider services
  - [ ] 3.1 ServiceNow : extraire ou consolider dans services/servicenow.py si pertinent
  - [ ] 3.2 Splunk (Story 27.8) : prévoir services/splunk.py dans la structure

- [ ] Task 4 — Mise à jour imports
  - [ ] 4.1 Remplacer core.vault_service par services.vault (ou équivalent)
  - [ ] 4.2 Mettre à jour références dans moteur d'exécution, adapters, tests

- [ ] Task 5 — Documentation et tests
  - [ ] 5.1 Mettre à jour README, docs/integration-type-catalogue.md
  - [ ] 5.2 Documenter la distinction plateforme vs service
  - [ ] 5.3 Vérifier tous les tests passent

## Dev Notes

### Contexte

- **Epic 27** : Adapters d'intégration backend.
- **Plateformes** : où l'action s'exécute — AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud.
- **Services** : consommés par les actions — Vault (credentials), ServiceNow (tickets), Jira (issues), Splunk (logs).

### Structure proposée

```
django_backend/
├── adapters/              # Plateformes uniquement
│   ├── platforms/         # Optionnel : sous-dossier
│   │   ├── aap_adapter.py
│   │   ├── tower_adapter.py
│   │   └── ...
│   └── __init__.py        # get_platform_adapter()
├── services/              # Services consommés
│   ├── vault.py           # ex-core/vault_service
│   ├── servicenow.py
│   ├── jira.py            # Story 27.10
│   ├── splunk.py          # Story 27.8
│   └── __init__.py        # get_service_client()
```

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 27.
- [Source: idp-portal/django_backend/core/vault_service.py]
- [Source: idp-portal/docs/rapport-bases-moteurs-technologies-integrations.md]

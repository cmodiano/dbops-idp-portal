# Story 27.7 : Admin frontend — menu Intégrations expose tous les adapters (config backend, éditable via l'UI)

Status: backlog

<!-- Note: Les adapters (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud, Vault) doivent être disponibles dans Admin > Intégrations. La config (URLs, credential_ref) est côté backend ; le frontend permet de l'éditer mais n'est pas requis pour que les adapters fonctionnent. -->

## Story

En tant que **DBOPS admin**,
je veux **tous les types d'intégration (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud, Vault) être disponibles dans le menu Admin > Intégrations pour créer et éditer les configurations (URL, credential_ref, etc.)**,
afin que **je puisse gérer les intégrations depuis l'interface tout en sachant que les adapters fonctionnent indépendamment du frontend (config stockée côté backend)**.

## Acceptance Criteria

**AC1 — Catalogue backend : tous les types adapters exposés**

**Given** le catalogue backend des types d'intégration (IntegrationTypeCatalogue ou équivalent),
**When** on consulte la liste des types exposés à l'Admin,
**Then** les types correspondant aux adapters sont présents : **aap**, **tower** (Ansible Tower), **azure_devops**, **github_actions**, **terraform_cloud**, **vault** (ou codes alignés avec le backend),
**And** chaque type a les métadonnées nécessaires (libellé, actions autorisées, schéma config optionnel) pour le formulaire Admin.

**AC2 — Formulaire Admin : types, base_url, credential_ref**

**Given** un admin ouvre le menu Admin > Intégrations (existant),
**When** il crée ou édite une intégration,
**Then** il peut choisir le type parmi tous les adapters ci-dessus,
**And** il peut renseigner **base_url** (URL de la plateforme) et **credential_ref** (référence au secret, ex. vault:secret/data/...),
**And** les secrets ne sont jamais saisis ni affichés en clair dans le frontend — uniquement la référence (credential_ref) est éditée ; la résolution des secrets reste côté backend (VaultService, env).

**AC3 — Config backend uniquement ; adapters indépendants du frontend**

**Given** la configuration d'une intégration (URL, credential_ref, config optionnelle),
**When** elle est sauvegardée via l'Admin (ou via l'API backend),
**Then** elle est persistée côté **backend** (base de données, modèle Integration),
**And** les **adapters fonctionnent sans le frontend** : une config créée ou mise à jour via API, migration ou script suffit pour que les adapters (AAP, etc.) utilisent cette config,
**And** le menu Admin Intégrations est un **moyen d'édition** de cette même config backend, pas une dépendance obligatoire.

**AC4 — Champs spécifiques et tests**

**And** les champs spécifiques par type (ex. organisation, workspace_id pour Terraform Cloud ; owner/repo pour GitHub) sont documentés et, si nécessaire, exposés dans le formulaire ou dans config (JSON) éditable,
**And** des tests (backend + frontend) vérifient que les types sont bien listés et que la création/édition d'intégration persiste correctement.

## Tasks / Subtasks

- [ ] Task 1 — Backend : catalogue des types d'intégration (AC: 1)
  - [ ] 1.1 Vérifier ou étendre IntegrationTypeCatalogue (ou source de vérité des types) pour inclure : aap, tower, azure_devops, github_actions, terraform_cloud, vault
  - [ ] 1.2 Définir pour chaque type : code, libellé, actions autorisées (ex. trigger, get_status), schéma config JSON optionnel (base_url, credential_ref, champs spécifiques)
  - [ ] 1.3 S'assurer que l'API GET /api/v1/integration-types/ (ou équivalent) retourne bien ces types pour le frontend
  - [ ] 1.4 Migration ou fixture si les types sont en base ; sinon configuration statique documentée

- [ ] Task 2 — Frontend : menu Admin > Intégrations (AC: 2)
  - [ ] 2.1 Vérifier que IntegrationsAdminPanel / IntegrationForm utilisent bien le catalogue (useIntegrationTypes, getIntegrationTypes) pour la liste des types
  - [ ] 2.2 S'assurer que les nouveaux types (tower, azure_devops, github_actions, terraform_cloud, vault) apparaissent dans le Select "Type" du formulaire
  - [ ] 2.3 Garder les champs base_url et credential_ref (pas de champ "mot de passe" en clair) ; documenter que credential_ref = référence Vault ou env
  - [ ] 2.4 Si besoin : champs conditionnels ou config JSON par type (ex. organisation, project pour Azure DevOps ; owner, repo pour GitHub) — selon schéma backend

- [ ] Task 3 — Documentation et contrainte "adapters sans frontend" (AC: 3)
  - [ ] 3.1 Documenter dans la doc technique ou story que la config des intégrations est **backend** (table Integration) ; le frontend Admin est une interface d'édition optionnelle
  - [ ] 3.2 Vérifier que les adapters (AAP, etc.) lisent la config depuis le backend (DB / API) et non depuis le frontend ; aucun flux "frontend → adapter" direct
  - [ ] 3.3 Scénario de test ou note : création d'intégration via API uniquement → exécution avec adapter doit fonctionner sans avoir ouvert l'Admin

- [ ] Task 4 — Champs spécifiques par type (AC: 4)
  - [ ] 4.1 Lister les champs optionnels par type (Terraform Cloud : organization, workspace_id ; GitHub : owner, repo ; Azure DevOps : organization, project ; Vault : pas de base_url côté intégration si global, ou namespace)
  - [ ] 4.2 Les exposer soit dans le formulaire (champs dédiés) soit dans une zone config JSON éditable, selon conventions existantes (Story 24.x)
  - [ ] 4.3 Documenter dans docs ou Dev Notes le mapping type → champs

- [ ] Task 5 — Tests (AC: 4)
  - [ ] 5.1 Tests backend : liste des types retourne aap, tower, azure_devops, github_actions, terraform_cloud, vault ; création/update intégration avec ces types
  - [ ] 5.2 Tests frontend : useIntegrationTypes / getIntegrationTypes inclut les types ; formulaire permet de sélectionner chaque type et de sauvegarder base_url + credential_ref
  - [ ] 5.3 Test d'intégration (optionnel) : créer une intégration via Admin UI → vérifier qu'elle est utilisée par l'adapter (ex. AAP) lors d'une exécution

## Dev Notes

### Contexte métier

- **Epic 27** : Adapters d'intégration backend. Les stories 27.1 à 27.6 ajoutent ou prévoient les adapters (AAP, Tower, Azure DevOps, GitHub Actions, Terraform Cloud, VaultService). Cette story garantit que **tous ces types sont visibles et éditables** dans le menu **Admin > Intégrations** du frontend, tout en rappelant que **la config est backend** et que **les adapters ne dépendent pas du frontend**.
- **Contrainte clé** : Les URLs et les secrets (référence credential_ref) sont des **configs backend** ; le menu Intégrations permet de les **mettre à jour** via l'UI, mais on peut aussi les créer/mettre à jour via API ou scripts — les adapters fonctionnent dans tous les cas.

### Ce qui existe déjà

- **Frontend** : `IntegrationsAdminPanel`, `IntegrationsTable`, `IntegrationForm` (Story 2.28, 4.9, 24.2) ; `useIntegrationTypes()` / `getIntegrationTypes()` qui chargent le catalogue depuis le backend.
- **Backend** : Catalogue des types d'intégration (Story 24.1) ; API intégrations (CRUD) ; modèle Integration (type, name, base_url, credential_ref, config, etc.).
- **Références** : Story 24.1 (backend catalogue types), 24.2 (frontend restriction types + formulaire), 24.3 (statut, validation).

### Principe "config backend, UI optionnelle"

- **Source de vérité** : Table (ou modèle) Integration côté backend. Les adapters lisent la config via le service/repository d'intégrations (ex. get_by_id, get_by_type).
- **Admin UI** : Appelle les mêmes API (GET/POST/PATCH intégrations) pour afficher et modifier cette config. Aucune logique métier adapter ne dépend du frontend.
- **Secrets** : Le frontend ne manipule que **credential_ref** (chaîne type `vault:secret/data/...`). La résolution (VaultService.get_secret) est côté backend uniquement.

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 27, Stories 27.1 à 27.7.
- [Source: idp-portal/frontend/src/pages/admin/IntegrationsAdminPanel.tsx] — Panel Admin Intégrations.
- [Source: idp-portal/frontend/src/components/admin/IntegrationForm.tsx] — Formulaire type, base_url, credential_ref, useIntegrationTypes.
- [Source: idp-portal/frontend/src/hooks/useIntegrationTypes.ts] — Chargement catalogue types depuis backend.
- [Source: idp-portal/django_backend/integrations/] — API et modèle Integration, catalogue types (Story 24.1).

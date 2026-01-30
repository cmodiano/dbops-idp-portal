# Story 2.28 : Frontend — Section Admin Intégrations (liste, formulaire, icône)

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a **DBOPS**,
I want **une section Admin « Intégrations » avec liste des plateformes distantes, ajout/édition (type, nom, URL, credential ref, icône)**,
So that **je configure les instances AAP, Terraform, etc. et leur représentation visuelle (icône) depuis l'interface**.

## Acceptance Criteria

1. **AC1 — Onglet Intégrations visible**
   **Given** un DBOPS accède à la page Admin,
   **When** il consulte les onglets,
   **Then** un onglet « Intégrations » est visible (à côté de Actions et Profils).

2. **AC2 — Tableau liste des intégrations**
   **Given** un DBOPS ouvre l'onglet Intégrations,
   **When** la page se charge,
   **Then** un tableau liste les intégrations (colonnes : icône, nom, type, URL, date création) avec actions Modifier / Supprimer et un bouton « Nouvelle intégration ».

3. **AC3 — Formulaire création/édition**
   **Given** un DBOPS clique sur « Nouvelle intégration » ou « Modifier »,
   **When** un formulaire (ou modal) s'affiche,
   **Then** les champs sont : Type (select : AAP, ServiceNow, Terraform, Azure DevOps, Jira, GitHub Actions), Nom, URL de base, Référence credentials (optionnel, ex. chemin Vault ou nom logique), Icône (optionnel).

4. **AC4 — Champ icône avec aperçu**
   **Given** le champ Icône est configuré,
   **When** l'utilisateur saisit une valeur,
   **Then** soit il sélectionne un preset par type (icône associée au type : AAP, Terraform, etc.), soit il fournit une URL d'icône (image) ; l'icône choisie est affichée en aperçu dans le formulaire et dans la liste.

5. **AC5 — Soumission et validation**
   **Given** un DBOPS soumet le formulaire,
   **When** les validations passent (nom, URL requis ; type requis),
   **Then** l'appel API POST ou PUT est envoyé et la liste des intégrations est rafraîchie.

6. **AC6 — Suppression avec confirmation**
   **Given** un DBOPS clique sur « Supprimer »,
   **When** une modale de confirmation s'affiche,
   **Then** après confirmation, l'intégration est supprimée via DELETE et la liste est rafraîchie.

7. **AC7 — UX et cohérence**
   **And** UX cohérente avec les onglets Actions et Profils (Ant Design, formulaires, notifications succès/erreur).
   **And** les libellés sont en français.

## Tasks / Subtasks

- [x] Task 1 (AC: 1, 7) — Types TypeScript pour les intégrations
  - [x] 1.1 : Ajouter dans `frontend/src/types/api.ts` : `IntegrationType` (enum string : aap, servicenow, terraform, azuredevops, jira, github_actions), `IntegrationCreate`, `IntegrationUpdate`, `IntegrationResponse`, `IntegrationListItem`.
  - [x] 1.2 : Aligner les types avec le backend (models/integration.py) : id, type, name, base_url, credential_ref (optional), icon (optional), created_at, updated_at.

- [x] Task 2 (AC: 2, 3, 5, 6) — Service API intégrations
  - [x] 2.1 : Créer `frontend/src/services/integrations_service.ts` avec fonctions : `getIntegrations()`, `getIntegration(id)`, `createIntegration(payload)`, `updateIntegration(id, payload)`, `deleteIntegration(id)`.
  - [x] 2.2 : Utiliser `apiFetch` de `api_client.ts` avec routes `/admin/integrations` et `/admin/integrations/{id}`.

- [x] Task 3 (AC: 2, 6) — Composant IntegrationsTable
  - [x] 3.1 : Créer `frontend/src/components/admin/IntegrationsTable.tsx` avec colonnes : icône (avatar/image), nom, type (badge), URL (tronquée), date création.
  - [x] 3.2 : Actions par ligne : boutons Modifier et Supprimer.
  - [x] 3.3 : Supprimer avec Modal.confirm (même pattern que ProfilesTable).
  - [x] 3.4 : Bouton « Nouvelle intégration » dans le header du tableau.
  - [x] 3.5 : Exporter depuis `frontend/src/components/admin/index.ts`.

- [x] Task 4 (AC: 3, 4, 5) — Composant IntegrationForm (ou Modal)
  - [x] 4.1 : Créer `frontend/src/components/admin/IntegrationForm.tsx` ou `IntegrationModal.tsx` avec champs : Type (Select), Nom (Input), URL de base (Input), Référence credentials (Input optionnel), Icône (Input ou Select preset).
  - [x] 4.2 : Icône : afficher preview via Avatar (si URL) ou icône preset par type (ApiOutlined, CloudServerOutlined, etc.).
  - [x] 4.3 : Validation Ant Design Form : type requis, nom requis (min 1 char), base_url requis + format URL.
  - [x] 4.4 : Mode création (POST) et édition (PUT) via props.
  - [x] 4.5 : Exporter depuis `frontend/src/components/admin/index.ts`.

- [x] Task 5 (AC: 1, 7) — Intégration dans AdminPage
  - [x] 5.1 : Modifier `frontend/src/pages/AdminPage.tsx` : ajouter un 3e onglet « Intégrations » dans les Tabs.
  - [x] 5.2 : Ajouter états : `integrations`, `integrationsLoading`, `integrationModalOpen`, `editIntegration`.
  - [x] 5.3 : Implémenter handlers : `fetchIntegrations()`, `handleIntegrationEdit()`, `handleIntegrationDelete()`, `handleIntegrationSuccess()`, `handleIntegrationCancel()`.
  - [x] 5.4 : Afficher IntegrationsTable et IntegrationForm/Modal.
  - [x] 5.5 : Notifications succès/erreur en français.

- [x] Task 6 — Tests unitaires
  - [x] 6.1 : Créer `frontend/src/components/admin/IntegrationsTable.test.tsx` : affichage liste, actions Modifier/Supprimer, modale confirmation.
  - [x] 6.2 : Créer `frontend/src/components/admin/IntegrationForm.test.tsx` : validation champs, preview icône, soumission.
  - [x] 6.3 : Tests service : mock apiFetch pour CRUD intégrations.

## Dev Notes

- **Contexte** : Cette story complète la 2.27 (backend) en ajoutant le frontend Admin pour gérer la configuration des plateformes d'exécution. Les intégrations permettront ensuite de lier les execution_steps aux instances réelles (AAP, Terraform, etc.).
- **Pattern existant** : Suivre exactement le même pattern que les onglets Actions et Profils dans AdminPage.tsx — états, handlers, composants Table et Form/Modal.
- **Backend prêt** : Les routes `/api/v1/admin/integrations` sont déjà implémentées (Story 2.27) — voir `backend/app/api/v1/integrations.py`.

### Project Structure Notes

- **Nouveaux fichiers** :
  - `frontend/src/types/api.ts` (modifier) — ajouter types Integration*
  - `frontend/src/services/integrations_service.ts` (créer)
  - `frontend/src/components/admin/IntegrationsTable.tsx` (créer)
  - `frontend/src/components/admin/IntegrationsTable.test.tsx` (créer)
  - `frontend/src/components/admin/IntegrationForm.tsx` (créer)
  - `frontend/src/components/admin/IntegrationForm.test.tsx` (créer)
  - `frontend/src/components/admin/index.ts` (modifier) — exports
- **Fichier modifié** :
  - `frontend/src/pages/AdminPage.tsx` — ajout onglet Intégrations

### Architecture Compliance

- **Stack** : React 19, TypeScript, Ant Design 6.2, Vite 7.
- **Pattern API** : Service dédié (`integrations_service.ts`) utilisant `apiFetch` de `api_client.ts`. Réponses wrapper `{ data }` / `{ error }`.
- **Composants** : Organisation par feature dans `components/admin/`. Tests co-localisés.
- **Conventions** : snake_case dans JSON API, camelCase dans props React. Libellés en français.
- **Sécurité** : Routes protégées côté backend par `require_profile("dbops")`. Frontend assume authentification via AuthContext.

### Library/Framework Requirements

- **Ant Design** : Table, Button, Modal, Form, Input, Select, Avatar, Space, notification, Tag.
- **Ant Design Icons** : ApiOutlined (ou équivalent) pour icônes preset par type.
- **React** : useState, useEffect, useCallback pour gestion états et effets.

### File Structure Requirements

```
frontend/src/
├── types/
│   └── api.ts                          # Ajouter IntegrationType, IntegrationCreate, IntegrationUpdate, IntegrationResponse
├── services/
│   └── integrations_service.ts         # NOUVEAU — CRUD intégrations
├── components/admin/
│   ├── IntegrationsTable.tsx           # NOUVEAU — Tableau liste intégrations
│   ├── IntegrationsTable.test.tsx      # NOUVEAU — Tests tableau
│   ├── IntegrationForm.tsx             # NOUVEAU — Formulaire création/édition
│   ├── IntegrationForm.test.tsx        # NOUVEAU — Tests formulaire
│   └── index.ts                        # MODIFIER — exports
└── pages/
    └── AdminPage.tsx                   # MODIFIER — ajouter onglet Intégrations
```

### Testing Requirements

- **Vitest + React Testing Library** : Tests unitaires composants.
- **Cas de test IntegrationsTable** :
  - Affiche les colonnes (icône, nom, type, URL, date)
  - Affiche les boutons Modifier/Supprimer par ligne
  - Modal confirmation sur Supprimer
  - Bouton « Nouvelle intégration » présent
- **Cas de test IntegrationForm** :
  - Validation : type requis, nom requis, URL requis et format valide
  - Preview icône fonctionne (preset ou URL)
  - Mode création vs édition (props editIntegration)
  - Soumission appelle onSubmit

### Previous Story Intelligence (Story 2.27 — Backend Intégrations)

- **Backend complet** : Table INTEGRATIONS, modèles Pydantic, repository, routes API sous `/admin/integrations` avec protection DBOPS.
- **Types backend** : `IntegrationType` enum (aap, servicenow, terraform, azuredevops, jira, github_actions), `IntegrationResponse` avec id, type, name, base_url, credential_ref, icon, created_at, updated_at.
- **À réutiliser** : Aligner exactement les types frontend sur le backend pour éviter les incohérences.

### Pattern à suivre — Référence ProfilesTable.tsx

```typescript
// Structure similaire à ProfilesTable.tsx (lignes 1-96)
export interface IntegrationsTableProps {
  dataSource: IntegrationListItem[];
  loading?: boolean;
  onEdit: (record: IntegrationListItem) => void;
  onDelete: (record: IntegrationListItem) => Promise<void>;
  onNew: () => void;
}

// Colonnes: icône (Avatar), nom, type (Tag), URL, date création
// Actions: Modifier (Button link), Supprimer (Button link danger avec Modal.confirm)
```

### Pattern à suivre — Référence profiles_service.ts

```typescript
// Structure similaire à profiles_service.ts (lignes 20-45)
import { apiFetch } from './api_client';
import type { IntegrationCreate, IntegrationUpdate, IntegrationResponse } from '../types/api';

export async function getIntegrations(): Promise<IntegrationResponse[]> {
  const res = await apiFetch<IntegrationResponse[]>('/admin/integrations');
  return res ?? [];
}

export async function createIntegration(payload: IntegrationCreate): Promise<IntegrationResponse> {
  return apiFetch<IntegrationResponse>('/admin/integrations', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
// ... updateIntegration, deleteIntegration
```

### Icônes preset par type

| Type | Icône Ant Design suggérée | Couleur badge |
|------|---------------------------|---------------|
| aap | `ApiOutlined` ou `RocketOutlined` | #1890ff (blue) |
| servicenow | `CloudServerOutlined` | #52c41a (green) |
| terraform | `BuildOutlined` | #722ed1 (purple) |
| azuredevops | `BranchesOutlined` | #0078d4 (azure blue) |
| jira | `ProjectOutlined` | #0052cc (jira blue) |
| github_actions | `GithubOutlined` | #24292e (github dark) |

### Libellés français

| Élément | Libellé |
|---------|---------|
| Onglet | Intégrations |
| Bouton création | Nouvelle intégration |
| Colonne icône | Icône |
| Colonne nom | Nom |
| Colonne type | Type |
| Colonne URL | URL |
| Colonne date | Date de création |
| Action modifier | Modifier |
| Action supprimer | Supprimer |
| Titre modal création | Nouvelle intégration |
| Titre modal édition | Modifier l'intégration |
| Titre suppression | Supprimer l'intégration |
| Message suppression | Voulez-vous vraiment supprimer l'intégration « {name} » ? |
| Notification création | Intégration « {name} » créée avec succès |
| Notification modification | Intégration « {name} » mise à jour |
| Notification suppression | Intégration « {name} » supprimée |
| Placeholder nom | Nom de l'intégration |
| Placeholder URL | https://example.com/api |
| Placeholder credential | secret/idp/aap-prod (optionnel) |
| Label type | Type de plateforme |
| Label nom | Nom |
| Label URL | URL de base |
| Label credential | Référence credentials |
| Label icône | Icône |
| Validation nom requis | Le nom est requis |
| Validation URL requise | L'URL de base est requise |
| Validation URL format | L'URL doit être valide (commencer par http:// ou https://) |
| Validation type requis | Le type est requis |

### Types à ajouter dans api.ts

```typescript
// === Integration Types (Story 2.28) ===

/** Integration platform type (aligned with backend IntegrationType). */
export type IntegrationType = 'aap' | 'servicenow' | 'terraform' | 'azuredevops' | 'jira' | 'github_actions';

/** Labels for integration types (french). */
export const INTEGRATION_TYPE_LABELS: Record<IntegrationType, string> = {
  aap: 'AAP',
  servicenow: 'ServiceNow',
  terraform: 'Terraform',
  azuredevops: 'Azure DevOps',
  jira: 'Jira',
  github_actions: 'GitHub Actions',
};

export interface IntegrationCreate {
  type: IntegrationType;
  name: string;
  base_url: string;
  credential_ref?: string | null;
  icon?: string | null;
}

export interface IntegrationUpdate {
  type?: IntegrationType;
  name?: string;
  base_url?: string;
  credential_ref?: string | null;
  icon?: string | null;
}

export interface IntegrationResponse {
  id: number;
  type: IntegrationType;
  name: string;
  base_url: string;
  credential_ref: string | null;
  icon: string | null;
  created_at: string;
  updated_at: string;
}

/** Alias for list display (same as full response). */
export type IntegrationListItem = IntegrationResponse;
```

### Références

- [Source: _bmad-output/planning-artifacts/epics.md] Story 2.28 (lignes 1125–1155)
- [Source: idp-portal/frontend/src/pages/AdminPage.tsx] Pattern onglets Actions/Profils
- [Source: idp-portal/frontend/src/components/admin/ProfilesTable.tsx] Pattern tableau avec actions
- [Source: idp-portal/frontend/src/services/profiles_service.ts] Pattern service CRUD
- [Source: idp-portal/backend/app/models/integration.py] Types backend à aligner
- [Source: _bmad-output/planning-artifacts/architecture.md] Conventions snake_case API, composants admin

## Change Log

- **2026-01-29** : Implémentation complète (Tasks 1–6). Types Integration*, service CRUD, IntegrationsTable, IntegrationForm, onglet Admin Intégrations, tests unitaires.
- **2026-01-29** : Code review (AI) — 7 issues corrigées : extraction constantes partagées (INTEGRATION_TYPE_ICON_COLORS, INTEGRATION_TYPE_TAG_COLORS), accents français dans notifications, validation URL renforcée, bouton Actualiser ajouté, tests enrichis (edit mode, icon URL preview, onRefresh).

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

- Types Integration* ajoutés dans `api.ts` (IntegrationType, INTEGRATION_TYPE_LABELS, IntegrationCreate, IntegrationUpdate, IntegrationResponse, IntegrationListItem), alignés avec `backend/app/models/integration.py`.
- Service `integrations_service.ts` : getIntegrations, getIntegration, createIntegration, updateIntegration, deleteIntegration via apiFetch et routes `/admin/integrations` / `/admin/integrations/{id}`.
- IntegrationsTable : colonnes icône (Avatar si URL, sinon preset par type), nom, type (Tag), URL tronquée, date création ; actions Modifier/Supprimer ; Modal.confirm sur Supprimer ; bouton « Nouvelle intégration » dans le titre.
- IntegrationForm : Modal avec footer personnalisé ; champs Type (Select), Nom, URL de base, Référence credentials, Icône ; aperçu icône (Avatar ou preset) ; validation type/nom/base_url (URL http(s)) ; création vs édition via `editIntegration` ; erreurs de validation absorbées (pas de rejet) pour éviter unhandled rejections en tests.
- AdminPage : onglet « Intégrations », états et handlers (fetch, edit, delete, success, cancel, submit), IntegrationsTable + IntegrationForm ; notifications en français. Onglet « Profils » renommé en « Profils » (libellé FR).
- Tests : IntegrationsTable (colonnes, liste, onNew/onEdit/onDelete, Modal confirm, empty), IntegrationForm (validation, submit, onCancel, error prop), integrations_service (mock fetch, CRUD).

### File List

- `idp-portal/frontend/src/types/api.ts` (modified) — ajout INTEGRATION_TYPE_ICON_COLORS, INTEGRATION_TYPE_TAG_COLORS
- `idp-portal/frontend/src/services/integrations_service.ts` (new)
- `idp-portal/frontend/src/services/integrations_service.test.ts` (new)
- `idp-portal/frontend/src/components/admin/IntegrationsTable.tsx` (new) — code-review: bouton Actualiser, constantes partagées
- `idp-portal/frontend/src/components/admin/IntegrationsTable.test.tsx` (new) — code-review: +3 tests (icon URL, preset, onRefresh)
- `idp-portal/frontend/src/components/admin/IntegrationForm.tsx` (new) — code-review: validation URL renforcée, constantes partagées
- `idp-portal/frontend/src/components/admin/IntegrationForm.test.tsx` (new) — code-review: +3 tests (edit mode, icon preview URL, preset)
- `idp-portal/frontend/src/components/admin/index.ts` (modified)
- `idp-portal/frontend/src/pages/AdminPage.tsx` (modified) — code-review: accents français corrigés, onRefresh intégrations
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (modified)
- `_bmad-output/implementation-artifacts/2-28-frontend-admin-integrations-liste-formulaire-icone.md` (modified)


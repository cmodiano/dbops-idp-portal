# Story 2.6: Systeme de tags flexibles pour les actions

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a DBOPS,
I want assigner plusieurs tags flexibles a une action (ex: RAC, DATAGUARD, Provisioning),
So that les utilisateurs peuvent filtrer le catalogue de maniere dynamique sans categories fixes.

## Acceptance Criteria

1. **AC1 — Section Tags dans l'admin** : Given un DBOPS edite une action, When il accede a la section "Tags", Then il voit un champ multi-select avec auto-completion sur les tags existants.

2. **AC2 — Creation de tag a la volee** : Given le DBOPS saisit un nouveau tag qui n'existe pas, When il tape "RAC" et appuie sur Entree, Then le tag est cree automatiquement et assigne a l'action.

3. **AC3 — Affichage tags dans le tableau admin** : Given le DBOPS consulte la liste des actions dans l'admin, When il voit le tableau, Then les tags de chaque action sont affiches sous forme de chips.

4. **AC4 — Performance filtrage** : Given le catalogue contient 100+ actions, When un utilisateur filtre par tag, Then les resultats se chargent en < 1 seconde (NFR4).

5. **AC5 — Schema et API** : La table TAGS (id, name, created_at) et la table ACTION_TAGS (action_id, tag_id) sont creees via migration SQL (prochaine version apres V006, ex. V007). L'API GET /api/v1/tags retourne tous les tags existants. L'API PUT /api/v1/admin/actions/{id}/tags assigne les tags a une action. Les tags sont en lowercase, sans espaces (normalisation automatique). FR11c est satisfaite.

## Tasks / Subtasks

- [x] Task 1: Backend — Migration et modele Tags (AC: 5)
  - [x] 1.1: Creer migration SQL V007 : table TAGS (id NUMBER GENERATED ALWAYS AS IDENTITY PRIMARY KEY, name VARCHAR2(255) UNIQUE NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP). Table ACTION_TAGS (action_id NUMBER NOT NULL REFERENCES ACTIONS_CATALOG(id) ON DELETE CASCADE, tag_id NUMBER NOT NULL REFERENCES TAGS(id) ON DELETE CASCADE, PRIMARY KEY (action_id, tag_id)). Index sur TAGS(name), index sur ACTION_TAGS(action_id), ACTION_TAGS(tag_id).
  - [x] 1.2: Ajouter modeles Pydantic dans `backend/app/models/catalog.py` : TagCreate (name), TagResponse (id, name, created_at). Enrichir ActionDetail / ActionResponse avec champ tags: list[TagResponse] (ou list[str] pour simplicite).
  - [x] 1.3: Creer repository ou methodes dans catalog_repository pour : get_all_tags(), get_tags_for_action(action_id), set_action_tags(action_id, tag_ids), create_tag_if_not_exists(name) avec normalisation lowercase + trim + pas d'espaces.
  - [x] 1.4: Ecrire tests unitaires backend : modeles Tag, normalisation nom tag, repository get/set tags.

- [x] Task 2: Backend — API Tags et liaison actions (AC: 1, 2, 5)
  - [x] 2.1: Endpoint GET /api/v1/tags — retourne tous les tags (liste TagResponse). Route publique ou protegee selon RBAC (catalogue = tous, admin = tous).
  - [x] 2.2: Endpoint PUT /api/v1/admin/actions/{id}/tags — body: { "tag_ids": [1, 2, 3] } ou { "tag_names": ["rac", "dataguard"] }. Creer les tags manquants (create_tag_if_not_exists), puis remplacer les liaisons ACTION_TAGS pour cette action. Retourner action mise a jour avec liste tags.
  - [x] 2.3: Adapter GET /api/v1/admin/actions et GET /api/v1/admin/actions/{id} pour inclure les tags dans la reponse. Adapter GET /api/v1/catalog/actions (si existant) pour inclure les tags.
  - [x] 2.4: Ecrire tests API : GET /tags, PUT /admin/actions/{id}/tags (creation tag a la volee, normalisation), liste admin avec tags.

- [x] Task 3: Frontend — Section Tags dans ActionForm (AC: 1, 2)
  - [x] 3.1: Ajouter section "Tags" dans `frontend/src/components/admin/ActionForm.tsx`. Composant multi-select avec auto-completion : charger les tags existants via GET /api/v1/tags, permettre saisie libre + Entree pour ajouter un nouveau tag (appel PUT avec tag_names incluant le nouveau).
  - [x] 3.2: Afficher les tags selectionnes en chips avec possibilite de retirer. Normalisation cote affichage : lowercase, pas d'espaces (deja cote backend).
  - [x] 3.3: Persister les tags a la sauvegarde de l'action (PUT /admin/actions/{id}/tags ou integrer dans PUT/PATCH action si unifie). Charger les tags a l'ouverture de l'action en edition.
  - [x] 3.4: Ecrire tests ActionForm (ou composant TagsField) : rendu chips, ajout/suppression tag, appel API PUT tags.

- [x] Task 4: Frontend — Affichage tags dans le tableau admin (AC: 3)
  - [x] 4.1: Dans la liste des actions (AdminPage / tableau), ajouter une colonne "Tags" affichant les tags de chaque action sous forme de chips (Ant Design Tag).
  - [ ] 4.2: Optionnel : tri ou filtre par tag dans le tableau admin (si requis par AC3 — "les tags sont affiches" = colonne suffit).
  - [x] 4.3: Ecrire tests : colonne Tags presente, chips rendus.

- [x] Task 5: Types et catalogue (AC: 4, 5)
  - [x] 5.1: Mettre a jour `frontend/src/types/api.ts` : ActionDetail et types catalogue avec champ tags: string[] (ou TagResponse[]). S'assurer que AdminPreview et ActionCard (story 2.5) affichent deja les tags si le type les contient.
  - [x] 5.2: Verifier que GET /api/v1/catalog/actions (catalogue) retourne les tags pour chaque action afin que le filtrage futur (Epic 3) et NFR4 soient satisfaits. Index/requete optimisee si 100+ actions.
  - [x] 5.3: Regression : tous les tests existants passent (frontend + backend).

- [x] Task 6: Validation et Definition of Done (AC: tous)
  - [x] 6.1: Verifier AC1–AC5 manuellement ou par tests. NFR4 : requete catalogue avec filtre tag < 1 s (test perf optionnel ou assertion sur index).
  - [x] 6.2: Linter et tests complets. File List et Dev Agent Record a jour.

## Dev Notes

### Architecture Requirements

- **Repository Pattern** : SQL brut via python-oracledb, pas d'ORM. Catalog repository etendu ou nouveau tag_repository pour TAGS / ACTION_TAGS. [Source: architecture.md — Repository Pattern]
- **API format** : snake_case JSON, wrapper { "data": ... } / { "error": ... }. [Source: architecture.md — API format]
- **Cache catalogue** : TTL 5 min cote backend pour GET /catalog/actions ; GET /tags peut etre cache court (1–5 min) pour auto-completion. [Source: architecture.md — Cache in-memory]
- **RBAC** : Endpoints admin proteges (DBOPS). GET /api/v1/tags peut etre public pour catalogue ou protege. [Source: architecture.md — Controle d'acces]

### UX Specifications (from epics.md)

- **Section Tags** : Champ multi-select avec auto-completion sur les tags existants. Saisie "RAC" + Entree cree le tag et l'assigne.
- **Tableau admin** : Tags affiches sous forme de chips par action.
- **Performance** : Filtrage catalogue par tag < 1 s (NFR4) — index et requete optimisee.

### What Already Exists (DO NOT REIMPLEMENT)

| Element | Fichier | Statut |
|---|---|---|
| ActionForm | `frontend/src/components/admin/ActionForm.tsx` | Existe — AJOUTER section Tags |
| AdminPage | `frontend/src/pages/AdminPage.tsx` | Existe — tableau actions |
| catalog_repository | `backend/app/repositories/catalog.py` | Existe — etendre ou ajouter methodes tags |
| Models catalog | `backend/app/models/catalog.py` | Existe — ajouter Tag, enrichir Action avec tags |
| API admin | `backend/app/api/v1/admin.py` | Existe — ajouter routes tags |
| ActionCard / ImpactIndicator | Story 2.5 | Deja affichent tags si presentes dans donnees |

### What Needs to Be CREATED

| Element | Fichier | Description |
|---|---|---|
| Migration V007 | `database/migrations/V007_create_tags_and_action_tags.sql` | Tables TAGS, ACTION_TAGS |
| Tag models | `backend/app/models/catalog.py` | TagCreate, TagResponse, liaison ActionDetail.tags |
| Tag repository methods | `backend/app/repositories/catalog.py` ou tag_repository | get_all_tags, set_action_tags, create_tag_if_not_exists |
| GET /api/v1/tags | `backend/app/api/v1/` | Route tags (catalog ou admin selon choix) |
| PUT /api/v1/admin/actions/{id}/tags | `backend/app/api/v1/admin.py` | Assignation tags avec creation a la volee |
| Section Tags ActionForm | `frontend/src/components/admin/ActionForm.tsx` | Multi-select + chips |
| Colonne Tags tableau admin | Liste actions admin | Chips par action |

### Technical Stack (from architecture.md, story 2.5)

| Technology | Version | Role |
|---|---|---|
| React | 19.x | UI |
| Ant Design | 6.2 | Composants (Select mode tags, Tag) |
| FastAPI | 0.115+ | API |
| Pydantic | v2 | Modeles |
| python-oracledb | 3.4.1 Thin | Oracle |
| Vitest + RTL | - | Tests frontend |
| pytest + httpx | - | Tests backend |

### Previous Story Intelligence (2.5)

- **ActionCard** et **ActionDrawerPreview** affichent deja les tags si le type `ActionPreviewData` / `ActionDetail` contient `tags`. Verifier que le type inclut `tags?: string[]` et que les composants rendent des chips. Si absent, l’ajout du champ `tags` dans les types et l’affichage dans ActionCard/Drawer font partie de cette story.
- **ActionForm** utilise Form.useWatch() pour la preview ; les tags seront un champ du formulaire, a inclure dans l’objet envoye a AdminPreview.
- **Fichiers modifies en 2.5** : ActionCard.tsx, ActionDrawerPreview.tsx, AdminPreview.tsx, ActionForm.tsx, api.ts (ActionPreviewData), catalog/index.ts, shared/index.ts, admin/index.ts. Ne pas casser la preview ; ajouter Tags en section dediee dans le formulaire.

### Normalisation des tags

- **Regle metier** : lowercase, trim, remplacement espaces par rien (ou underscore selon produit). Ex. "RAC " → "rac", "Data Guard" → "dataguard" ou "data_guard" (a trancher : epics dit "sans espaces" → "dataguard").
- **Unicite** : TAGS.name UNIQUE. Avant insert, normaliser et faire INSERT ou SELECT existing.

### Project Structure Notes

- Migrations : `idp-portal/database/migrations/` — prochaine version V007 (V000–V006 existent ; epics mentionnait V004 pour TAGS mais V004 est deja audit_log).
- Backend : `idp-portal/backend/app/` — api/v1/, models/, repositories/, core/.
- Frontend : `idp-portal/frontend/src/` — components/admin/, components/catalog/, types/api.ts.

### References

- [Source: epics.md — Story 2.6, FR11c]
- [Source: architecture.md — Repository Pattern, API format, Cache]
- [Source: 2-5-preview-temps-reel-de-laction.md — ActionCard tags, ActionForm layout]

## Dev Agent Record

### Agent Model Used

(To be filled by Dev agent during implementation)

### Debug Log References

(To be filled by Dev agent)

### Completion Notes List

- Code review 2026-01-28 (bmad_bmm_code-review): fixes appliques (option 1).
  - Ajout GET /api/v1/tags et PUT /api/v1/admin/actions/{id}/tags. Router tags dans `app/api/v1/tags.py`, monte dans `main.py`.
  - Section Tags dans ActionForm : Select mode="tags", getTags/updateActionTags, persistance a la sauvegarde.
  - Colonne Tags dans AdminPage (chips). Types api.ts : tags sur ActionResponse, ActionDetail, ActionListItem.
  - admin_service : getTags(), updateActionTags(). Race condition create_tag_if_not_exists : catch IntegrityError, retry SELECT.
  - Tests : TestGetTags, TestUpdateActionTags (test_admin_api), TestActionTagsUpdateRequest (test_catalog_models), mock getTags/updateActionTags (ActionForm.test). Correction mock COUNT dans list_all_admin (SELECT COUNT(*) uniquement).
  - AC4 (filtrage par tag) : GET /catalog/actions?tags=rac,dataguard implemente. list_all(tags_filter=...), sous-requete INDEX sur TAGS/ACTION_TAGS. Tests test_list_all_with_tags_filter, test_list_catalog_actions_filter_by_tags.

### File List

- `idp-portal/database/migrations/V007_create_tags_and_action_tags.sql`
- `idp-portal/backend/app/models/catalog.py` — TagCreate, TagResponse, ActionTagsUpdateRequest, tags sur ActionResponse/ActionDetail/ActionListItem
- `idp-portal/backend/app/repositories/catalog_repository.py` — get_all_tags, get_tags_for_action, get_tags_for_actions, create_tag_if_not_exists (race fix), set_action_tags, tags dans list_all/list_all_admin/get_by_id
- `idp-portal/backend/app/api/v1/tags.py` — GET /tags (nouveau)
- `idp-portal/backend/app/api/v1/catalog.py` — GET /catalog/actions?tags= (AC4)
- `idp-portal/backend/app/api/v1/admin.py` — PUT /admin/actions/{id}/tags
- `idp-portal/backend/app/main.py` — router tags
- `idp-portal/frontend/src/types/api.ts` — tags sur ActionResponse, ActionListItem; TagResponse
- `idp-portal/frontend/src/services/admin_service.ts` — getTags, updateActionTags
- `idp-portal/frontend/src/components/admin/ActionForm.tsx` — section Tags, persistance
- `idp-portal/frontend/src/pages/AdminPage.tsx` — colonne Tags
- `idp-portal/backend/tests/unit/test_catalog_models.py` — Tag, ActionTagsUpdateRequest
- `idp-portal/backend/tests/unit/test_catalog_repository.py` — tags, mock COUNT fix
- `idp-portal/backend/tests/unit/test_admin_api.py` — TestGetTags, TestUpdateActionTags
- `idp-portal/backend/tests/unit/test_catalog_api.py` — test_list_catalog_actions_filter_by_tags (AC4)
- `idp-portal/frontend/src/components/admin/ActionForm.test.tsx` — mock getTags, updateActionTags

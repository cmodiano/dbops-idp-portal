# Story 3.4 : Documentation contextuelle d'une action

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que DBA,
je veux accéder à la documentation détaillée d'une action depuis sa fiche,
afin de comprendre en profondeur ce que fait l'action avant de l'exécuter.

## Acceptance Criteria

1. **Given** le DBA consulte la fiche d'une action dans le drawer **When** une documentation est disponible **Then** un onglet ou une section « Documentation » s'affiche dans le drawer avec le contenu Markdown rendu.

2. **Given** la documentation est longue **When** le DBA fait défiler le drawer **Then** le contenu est scrollable dans le drawer sans affecter la page principale.

3. **Given** aucune documentation n'est disponible **When** le DBA consulte la section Documentation **Then** un message « Aucune documentation disponible » s'affiche.

4. **And** la documentation est stockée en Markdown dans une colonne dédiée (ou description longue) de ACTIONS_CATALOG.

5. **And** le rendu Markdown supporte : titres, listes, blocs de code, tableaux.

6. **And** FR12 est satisfaite.

## Tasks / Subtasks

- [ ] **Task 1 — Backend : champ documentation** (AC: 4)
  - [ ] 1.1 Migration Flyway : ajouter colonne `DOCUMENTATION_MD` CLOB (nullable) à `ACTIONS_CATALOG`. Nom de fichier : `V022__add_documentation_md.sql`.
  - [ ] 1.2 Modèle Pydantic : ajouter `documentation_md: str | None` dans `ActionResponse`, `ActionDetail`, `ActionCreate` (optionnel à la création). Modèle SQL/mapping dans `catalog.py` et repository : inclure la colonne dans SELECT/INSERT/UPDATE.
  - [ ] 1.3 GET /api/v1/catalog/actions/{id} : retourner `documentation_md` dans la fiche détaillée (déjà inclus si colonne mappée).

- [ ] **Task 2 — Frontend : section Documentation dans le drawer** (AC: 1, 2, 3, 5)
  - [ ] 2.1 Dans `ActionDrawerPreview` (ou drawer parent) : ajouter une section « Documentation » sous la description courte (ou un onglet « Documentation » si le drawer utilise des Tabs). Contenu : rendu Markdown du champ `documentation_md`.
  - [ ] 2.2 Rendu Markdown : utiliser une librairie type `react-markdown` avec support titres (h1–h6), listes, blocs de code (syntax highlighting optionnel), tableaux. Sanitiser le HTML si la lib génère du HTML (éviter XSS).
  - [ ] 2.3 Zone documentation scrollable : conteneur avec `overflow-y: auto` et hauteur max pour que le scroll reste dans le drawer (AC2).
  - [ ] 2.4 Si `documentation_md` est vide ou null : afficher « Aucune documentation disponible » (AC3).

- [ ] **Task 3 — Admin : édition de la documentation** (hors scope strict FR12 — optionnel pour cohérence)
  - [ ] 3.1 Si l’admin édite une action (ActionWizard ou formulaire action) : ajouter un champ texte long (TextArea) ou éditeur Markdown pour `documentation_md`. Sauvegarder via PUT/PATCH existant.
  - [ ] 3.2 Sinon : laisser la possibilité d’alimenter la colonne via script/migration ou une story ultérieure.

- [ ] **Task 4 — Types et API client frontend** (AC: 1, 4)
  - [ ] 4.1 `api.ts` : ajouter `documentation_md?: string | null` dans `ActionResponse`, `ActionDetail`, `ActionPreviewData` (ou type utilisé par le drawer).
  - [ ] 4.2 `catalog_service` / appel GET action by id : s’assurer que la réponse inclut `documentation_md` (déjà le cas si le backend le renvoie).

- [ ] **Task 5 — Tests** (AC: tous)
  - [ ] 5.1 Backend : test unitaire GET /catalog/actions/{id} avec/sans `documentation_md` ; test création/update action avec `documentation_md`. Test migration V022.
  - [ ] 5.2 Frontend : test ActionDrawerPreview (ou drawer) — section Documentation affichée avec Markdown rendu ; état vide « Aucune documentation disponible » ; scroll dans le drawer.

## Dev Notes

- **FR12** : Tout utilisateur peut accéder à la documentation contextuelle d'une action.
- Stories 3.1–3.3 ont livré : catalogue avec modes cartes/liste, favoris, drawer 480px avec fiche (nom, description courte, impact, tags, paramètres, bouton Exécuter), recherche et filtres. En 3.4 on ajoute une section (ou onglet) « Documentation » dans le drawer avec contenu Markdown stocké en base.

### Ce qui existe déjà (à réutiliser)

- **Backend** : `ACTIONS_CATALOG` a `DESCRIPTION` VARCHAR2(4000) pour la description courte. Pas de colonne dédiée documentation longue. GET /catalog/actions/{id} dans `catalog.py` ; `catalog_repository` et modèles dans `models/catalog.py`.
- **Frontend** : `ActionDrawerPreview` affiche description, tags, paramètres, bouton Exécuter. Pas de section Documentation ni rendu Markdown. Drawer 480px géré dans `CatalogPage` (Ant Design Drawer).

### Developer Context — Patterns à respecter

- **API** : snake_case JSON, wrapper `{ "data": ... }` / `{ "error": ... }`. [Source: architecture]
- **Frontend** : données API en snake_case → camelCase au point d’usage. [Source: architecture]
- **Repository** : SQL brut via python-oracledb. [Source: architecture]
- **Drawer** : 480px à droite, role="dialog", focus trap (Ant Design Drawer). [Source: Story 3.2, UX]

### Architecture & technique

- **Stockage** : Nouvelle colonne `DOCUMENTATION_MD` CLOB nullable dans `ACTIONS_CATALOG`. Migration Flyway nommée `V022__add_documentation_md.sql` (numéro cohérent avec les migrations existantes V021).
- **Rendu Markdown** : `react-markdown` (ou équivalent) avec composants Ant Design pour cohérence visuelle. Optionnel : `remark-gfm` pour tableaux GitHub-style. Sanitisation : utiliser une config sûre (pas de `dangerouslySetInnerHTML` brut sur entrée utilisateur).
- **Scroll** : Le drawer Ant Design a déjà un body scrollable ; la section Documentation doit vivre dans ce body avec `overflow-y: auto` sur un conteneur interne si le contenu est long, pour ne pas affecter la page principale (AC2).

### Project Structure Notes

- **Backend** : `database/migrations/V022__add_documentation_md.sql` ; `app/models/catalog.py` ; `app/api/v1/catalog.py` ; `app/repositories/catalog_repository.py`.
- **Frontend** : `src/components/catalog/ActionDrawerPreview.tsx` (section Documentation + rendu Markdown) ; `src/types/api.ts` (documentation_md) ; dépendance `react-markdown` (et éventuellement `remark-gfm`). Tests : `ActionDrawerPreview.test.tsx`, `test_catalog_api.py`, `test_catalog_repository.py`.

### Previous Story Intelligence (3.3)

- **Fichiers modifiés** : `catalog.py` (liste + GET /catalog/tags), `CatalogPage.tsx` (recherche debounce, panneau filtres, chips), `catalog_service.ts`, `catalog_repository.py`. En 3.4 on ne modifie pas la liste ni les filtres ; on étend le **drawer** (fiche action) avec la section Documentation et on étend le **backend** (colonnes + API détail) pour exposer `documentation_md`.
- **Patterns** : Réutiliser le même style de section dans le drawer (Typography, Space, Divider si besoin). État vide avec `Empty` ou message texte « Aucune documentation disponible » comme pour « Aucun paramètre défini » en 3.2.

### Library / Framework Requirements

- **react-markdown** : Rendu Markdown côté client. Vérifier version compatible React 19 (projet utilise React 19). Si besoin, `remark-gfm` pour tableaux et listes tâches.
- Pas de librairie serveur pour le Markdown : le backend stocke et renvoie le texte brut ; le frontend assure le rendu et la sanitisation.

### Testing Requirements

- Backend : migration V022 appliquée sans erreur ; GET /catalog/actions/{id} retourne `documentation_md` ; création/mise à jour action avec `documentation_md` persiste en base.
- Frontend : avec `documentation_md` non vide, la section Documentation affiche le Markdown rendu (titres, listes, code) ; avec `documentation_md` null/vide, affichage « Aucune documentation disponible » ; pas de régression sur le reste du drawer (description, paramètres, Exécuter).

### References

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 3, Story 3.4, FR12, AC (onglet/section Documentation, Markdown, scroll, état vide, colonne ou description longue).
- [Source: idp-portal/backend/app/models/catalog.py] — ActionResponse, champs actuels.
- [Source: idp-portal/database/migrations/V002__create_actions_catalog.sql] — DESCRIPTION VARCHAR2(4000), pas de CLOB documentation.
- [Source: idp-portal/frontend/src/components/catalog/ActionDrawerPreview.tsx] — structure actuelle du drawer (description, tags, paramètres, bouton).
- [Source: idp-portal/frontend/src/types/api.ts] — ActionResponse, ActionDetail, ActionPreviewData.

## Dev Agent Record

### Agent Model Used

{{agent_model_name_version}}

### Debug Log References

### Completion Notes List

### File List

# Story 3.5 : Nuage de tags et clarté du bouton favori

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que DBA,
je veux filtrer le catalogue par un ou plusieurs tags via un nuage de tags coloré et comprendre clairement comment ajouter une action à mes favoris,
afin de naviguer dans un catalogue avec beaucoup de tags sans multiplication d’onglets et d’utiliser les favoris sans ambiguïté.

## Acceptance Criteria

1. **Given** le DBA est sur l’onglet Catalogue (hors vue « Mes actions ») **When** la page affiche la liste des actions **Then** un nuage de tags (tag cloud) s’affiche au-dessus de la grille/liste, contenant tous les tags présents sur les actions du catalogue (ou les tags disponibles côté API).

2. **Given** le nuage de tags est affiché **When** le DBA clique sur un tag **Then** ce tag est sélectionné (mise en évidence visuelle) et la liste des actions se filtre pour n’afficher que les actions portant ce tag. Le compteur « X actions » se met à jour (aria-live="polite").

3. **Given** un ou plusieurs tags sont déjà sélectionnés **When** le DBA clique sur un autre tag **Then** ce tag s’ajoute à la sélection et le filtre est une intersection (AND) : seules les actions ayant **tous** les tags sélectionnés sont affichées.

4. **Given** des tags sont sélectionnés **When** le DBA clique à nouveau sur un tag déjà sélectionné **Then** ce tag est désélectionné et la liste se met à jour en conséquence.

5. **Given** des tags sont sélectionnés **When** le DBA souhaite tout réinitialiser **Then** un contrôle « Réinitialiser les filtres » (ou équivalent) est disponible et désélectionne tous les tags.

6. **Given** le nuage de tags est affiché **Then** les tags ont une couleur ou un style distinct (nuage coloré) pour une lecture visuelle rapide ; le libellé de chaque tag est lisible et cliquable (bouton ou lien accessible).

7. **Given** le DBA consulte une ActionCard (grille ou liste) **When** il survole ou focus l’icône étoile (favori) **Then** un tooltip s’affiche : « Ajouter aux favoris » si l’action n’est pas en favori, « Retirer des favoris » si elle l’est déjà.

8. **Given** le bouton favori (icône étoile) est présent **Then** il possède un aria-label explicite : « Ajouter aux favoris » ou « Retirer des favoris » selon l’état, pour l’accessibilité.

9. **Given** le bouton favori est affiché **Then** l’état visuel est net : étoile vide (ou contour) = pas en favori, étoile pleine (ou couleur distincte) = en favori.

10. **And** l’onglet « Mes actions » (favoris + récents) reste inchangé : un seul onglet dédié, pas de modification de son comportement.

11. **And** l’API GET /api/v1/catalog/actions accepte déjà le paramètre `tags` (comma-separated) ; le frontend envoie les tags sélectionnés dans ce paramètre. Aucun changement API requis si déjà supporté.

12. **And** si l’API GET /api/v1/catalog/tags existe, l’utiliser pour alimenter le nuage ; sinon dériver les tags des actions retournées par le catalogue.

## Tasks / Subtasks

- [x] **Task 1 — Frontend : composant Nuage de tags (TagCloud)** (AC: 1, 2, 3, 4, 5, 6)
  - [x] 1.1 Créer un composant `TagCloud` (ou `TagFilterCloud`) dans `frontend/src/components/catalog/` : affichage des tags en nuage (flex wrap ou nuage visuel), chaque tag cliquable, état sélectionné/non sélectionné avec style distinct (couleur Ant Design Tag : `color` ou `checked`).
  - [x] 1.2 Gérer la sélection multiple : clic = toggle du tag ; état `selectedTags: string[]` remonté au parent (CatalogPage) via callback.
  - [x] 1.3 Ajouter un bouton ou lien « Réinitialiser les filtres » lorsque au moins un tag est sélectionné ; au clic, vider `selectedTags` et rafraîchir la liste (réutiliser la logique existante `resetFilters` si cohérent).
  - [x] 1.4 Intégrer TagCloud dans `CatalogPage` au-dessus de la grille/liste, pour la vue catalogue (onglets Tout, Provisioning, Patching, etc.). Pour l'onglet « Mes actions », ne pas afficher le nuage (comportement inchangé).
  - [x] 1.5 Lorsque la sélection de tags change, appeler `fetchCatalogActions` avec `tags: selectedTags` (tableau passé en paramètre query comma-separated côté service). Conserver les autres filtres (category, q, engine, environment, impact).

- [x] **Task 2 — Frontend : source des tags pour le nuage** (AC: 1, 12)
  - [x] 2.1 Utiliser GET /api/v1/catalog/tags (déjà exposé : `fetchCatalogTags()` dans `catalog_service.ts`) au chargement de la page catalogue pour alimenter le nuage. Réutiliser `tagsWithCounts` si déjà chargé dans CatalogPage.
  - [x] 2.2 Afficher dans le nuage le libellé du tag et optionnellement le count (ex. « RAC (3) »). Ne pas dériver les tags des actions si l'API tags existe (éviter double source).

- [x] **Task 3 — Frontend : clarté du bouton favori** (AC: 7, 8, 9)
  - [x] 3.1 Dans `CatalogPage.tsx`, sur le `Button` favori (icône HeartOutlined/HeartFilled) qui enveloppe chaque carte : ajouter un `Tooltip` Ant Design avec titre « Ajouter aux favoris » ou « Retirer des favoris » selon `isFav`. Ne pas supprimer l'`aria-label` déjà présent (AC8).
  - [x] 3.2 Vérifier que le bouton favori a bien `aria-label={isFav ? 'Retirer des favoris' : 'Ajouter aux favoris'}` (déjà en place ligne ~322).
  - [x] 3.3 Vérifier l'état visuel : HeartOutlined = pas en favori, HeartFilled avec couleur distincte (ex. #eb2f96) = en favori ; contraste suffisant pour WCAG 2.1 AA.

- [x] **Task 4 — Remplacer / compléter le filtrage par tags par TagCloud** (AC: 2, 4, 10)
  - [x] 4.1 Dans `CatalogPage` : pour la vue catalogue (hors « Mes actions »), afficher le composant TagCloud au-dessus de la grille/liste. Soit remplacer le panneau latéral « Tags » (Select multiple) par le nuage comme source unique des filtres tags pour cette vue, soit afficher le nuage en plus du panneau (décision UX : nuage en premier, panneau optionnel). L'objectif est d'éviter la multiplication d'onglets tout en gardant le filtrage multi-tags (AND).
  - [x] 4.2 S'assurer que le compteur « X actions » et `aria-live="polite"` sont mis à jour lors du filtrage par tags (réutiliser le même bloc que pour les autres filtres).

- [x] **Task 5 — Tests** (AC: tous)
  - [x] 5.1 Tests unitaires frontend : TagCloud — affichage des tags, toggle sélection, bouton Réinitialiser ; CatalogPage (ou extrait) — tooltip sur le bouton favori, aria-label présent.
  - [x] 5.2 Pas de changement backend : les tests existants GET /catalog/actions?tags=... et GET /catalog/tags restent valides.

## Dev Notes

- **FR11, FR11b** : Cette story affine le filtrage par tags (nuage + multi-sélection AND) et améliore la découvrabilité du bouton favori (tooltip + aria-label + état visuel).
- Éviter la multiplication d’onglets lorsque le nombre de tags augmente ; un nuage avec multi-sélection scale mieux qu’une liste d’onglets par tag.

### Ce qui existe déjà (à réutiliser)

- **Backend** : GET /api/v1/catalog/actions accepte `tags` (comma-separated). GET /api/v1/catalog/tags retourne `{ name, action_count }[]`. Aucun changement API requis.
- **Frontend** : `CatalogPage.tsx` — onglets (Tout, Provisioning, Patching, Administration, Monitoring, Mes actions), panneau filtres 240px avec Select multiple pour Tags, `fetchCatalogTags`, `fetchCatalogActions({ tags })`, `renderActionCard` avec bouton favori (HeartOutlined/HeartFilled) et `aria-label` déjà définis. Pas de Tooltip sur le bouton favori. Pas de composant TagCloud.

### Developer Context — Patterns à respecter

- **API** : snake_case JSON, wrapper `{ "data": ... }` / `{ "error": ... }`. [Source: architecture.md]
- **Frontend** : données API en snake_case ; props et state en camelCase au point d’usage. [Source: architecture.md]
- **Composants catalogue** : dans `frontend/src/components/catalog/`. Barrel export via `index.ts`. [Source: architecture.md]
- **WCAG 2.1 AA** : tooltip + aria-label sur contrôles interactifs ; aria-live pour compteur dynamique. [Source: architecture.md, epics]

### Architecture & technique

- **Pas de migration DB** : les tags existent déjà (ACTIONS_CATALOG, table ou colonne tags). Pas de nouveau endpoint.
- **TagCloud** : composant présentant une liste de tags cliquables (Ant Design `Tag` ou boutons), avec état « sélectionné » (style primary ou checked). Multi-sélection = filtre AND côté appel API.
- **Tooltip favori** : Ant Design `Tooltip` autour du `Button` favori dans `CatalogPage.renderActionCard`. Titre selon `isFav`.

### Project Structure Notes

- **Frontend** : `frontend/src/components/catalog/TagCloud.tsx` (nouveau), `TagCloud.test.tsx` (co-localisé). Modifications : `CatalogPage.tsx` (intégration TagCloud, Tooltip bouton favori). Services : `catalog_service.ts` déjà a `fetchCatalogTags` et `fetchCatalogActions` avec `tags` ; pas de changement.
- **Backend** : aucun fichier à modifier.

### Previous Story Intelligence (3.4)

- **Story 3.4** : Documentation contextuelle dans le drawer (DOCUMENTATION_MD, react-markdown). Fichiers modifiés : ActionDrawerPreview, catalog repository, migration V022. Pour 3.5 on ne touche pas au drawer ; on travaille sur la page catalogue (TagCloud, tooltip favori).
- **Stories 3.1–3.3** : Catalogue avec onglets, modes cartes/liste, favoris, panneau filtres (Tags, Engine, Environment, Impact), GET /catalog/tags, GET /catalog/actions avec tags/category/q/engine/environment/impact. Réutiliser les mêmes hooks et services ; ajouter uniquement le composant TagCloud et le tooltip favori.

### Library / Framework Requirements

- **Ant Design** : `Tag`, `Tooltip`, `Button` déjà utilisés. Pas de nouvelle dépendance. Vérifier que `Tooltip` enveloppe bien le bouton favori pour le focus clavier (accessibilité).
- **React 19** : compatible avec Ant Design 6.2 (déjà en place).

### Testing Requirements

- **Frontend** : tests unitaires TagCloud (affichage tags, clic toggle, Réinitialiser). Test CatalogPage ou renderActionCard : présence du Tooltip sur le bouton favori et aria-label.
- **Backend** : aucun test à ajouter ; les tests existants pour GET /catalog/actions?tags= et GET /catalog/tags suffisent.

### References

- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 3, Story 3.5, FR11, FR11b, AC nuage de tags + tooltip/aria-label favori.
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx] — renderActionCard (l.286–325), fetchCatalogTags (l.173), filterTags, resetFilters, CATEGORY_TABS, panneau filtres.
- [Source: idp-portal/frontend/src/services/catalog_service.ts] — fetchCatalogTags, fetchCatalogActions(params avec tags).
- [Source: idp-portal/backend/app/api/v1/catalog.py] — GET /tags (list_catalog_tags), GET /actions (list_catalog avec tags_filter).
- [Source: idp-portal/frontend/src/components/catalog/ActionCard.tsx] — pas de bouton favori dans ActionCard ; le favori est dans CatalogPage autour de la carte.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- TagCloud.test.tsx: Initial RED phase tests (11 tests) for AC1-6
- CatalogPage.test.tsx: Added Story 3.5 tests (6 tests) for AC1, AC2, AC6, AC8, AC9, AC10, AC12

### Completion Notes List

- ✅ Task 1: Created `TagCloud` component with Ant Design CheckableTag, multi-selection, reset button, keyboard accessibility
- ✅ Task 2: Reused existing `tagsWithCounts` from `fetchCatalogTags()` - displays "tag (count)" format
- ✅ Task 3: Added `Tooltip` wrapper on favorite button with dynamic title; verified aria-label and visual state (HeartFilled #eb2f96)
- ✅ Task 4: Integrated TagCloud in CatalogPage above grid (hidden for "Mes actions" tab); both TagCloud and sidebar Select sync via shared `filterTags` state
- ✅ Task 5: 11 unit tests for TagCloud + 6 integration tests for CatalogPage Story 3.5; all 328 frontend tests pass

### File List

- idp-portal/frontend/src/components/catalog/TagCloud.tsx (new)
- idp-portal/frontend/src/components/catalog/TagCloud.test.tsx (new)
- idp-portal/frontend/src/components/catalog/index.ts (modified - barrel export)
- idp-portal/frontend/src/pages/CatalogPage.tsx (modified - TagCloud integration, Tooltip on favorite)
- idp-portal/frontend/src/pages/CatalogPage.test.tsx (modified - Story 3.5 tests)

### Senior Developer Review (AI)

- **Date**: 2026-01-29
- **Outcome**: Approve (fixes applied)
- **Findings addressed**:
  - **MEDIUM** TagCloud: added `role="group"` and `aria-label="Filtres par tags"` on container (WCAG 2.1 AA).
  - **MEDIUM** CatalogPage: compteur « X actions » always visible; shows « Chargement… » during refetch (AC2).
  - **MEDIUM** CatalogPage.test: added test for AC7 (tooltip on favorite button hover) and test for counter during loading.
  - **MEDIUM** TagCloud.test: replaced brittle `.ant-tag-checkable` selector with `getByRole('group', { name: 'Filtres par tags' })` and query by `[tabindex="0"]`.
  - **LOW** TagCloud: added `aria-label="Réinitialiser les filtres par tags"` on Reset button.
  - **LOW** CatalogPage.test: strengthened AC9 test (assert HeartFilled color #eb2f96).

## Change Log

- **2026-01-29**: Story 3.5 implementation complete. Added TagCloud component for visual multi-tag filtering (AC1-6), Tooltip on favorite button (AC7-9), full test coverage (17 new tests). All 328 frontend tests pass.
- **2026-01-29**: Code review (AI). 4 MEDIUM + 2 LOW findings fixed: TagCloud ARIA group + Reset aria-label; CatalogPage counter visible during loading; tests AC7 tooltip, AC9 visual state, counter loading; TagCloud.test selector robustness.
- **2026-01-29**: Cleanup redundant UI elements. Removed duplicate Tags Select from sidebar filters panel (TagCloud is now the primary tag filtering UI). Removed obsolete category tabs (Provisioning, Patching, Administration, Monitoring) per Story 2.23 — categories were replaced with tags. Only "Tout" and "Mes actions" tabs remain. Removed category parameter from CatalogFilters interface and fetchCatalogActions service. All 24 CatalogPage tests and 13 catalog_service tests pass.

# Story 3.5 : Nuage de tags et clarté du bouton favori

Status: backlog

<!-- Story créée suite à feedback PM : remplacer les onglets par tag par un nuage de tags multi-sélection ; rendre l'ajout aux favoris explicite (tooltip, aria-label, état visuel). -->

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

12. **And** si l’API GET /api/v1/tags (ou équivalent) existe, l’utiliser pour alimenter le nuage ; sinon dériver les tags des actions retournées par le catalogue.

## Tasks / Subtasks

- [ ] **Task 1 — Frontend : composant Nuage de tags (TagCloud)** (AC: 1, 2, 3, 4, 5, 6)
  - [ ] 1.1 Créer un composant `TagCloud` (ou `TagFilterCloud`) : affichage des tags en nuage (flex wrap ou nuage visuel), chaque tag cliquable, état sélectionné/non sélectionné avec style distinct (couleur).
  - [ ] 1.2 Gérer la sélection multiple : clic = toggle du tag ; état `selectedTags: string[]` remonté au parent (CatalogPage).
  - [ ] 1.3 Ajouter un bouton ou lien « Réinitialiser les filtres » lorsque au moins un tag est sélectionné ; au clic, vider `selectedTags` et rafraîchir la liste.
  - [ ] 1.4 Intégrer dans `CatalogPage` au-dessus de la grille/liste ; remplacer ou compléter les onglets par catégorie (Tout, Provisioning, etc.) : pour la vue « catalogue principal », afficher TagCloud + liste ; conserver un onglet « Mes actions » pour favoris + récents.
  - [ ] 1.5 Appeler GET /api/v1/catalog/actions avec `tags` = tags sélectionnés (comma-separated) lorsque la sélection change ; conserver category si encore utilisé pour « Tout » vs autre.

- [ ] **Task 2 — Frontend : source des tags pour le nuage** (AC: 1, 12)
  - [ ] 2.1 Si GET /api/v1/tags existe : l’appeler au chargement de la page catalogue et utiliser la liste pour le nuage ; afficher le libellé (et optionnellement le count).
  - [ ] 2.2 Sinon : extraire les tags uniques des actions retournées par GET /api/v1/catalog/actions (premier chargement sans filtre) et les afficher dans le nuage ; mettre à jour si nécessaire après filtrage (tags des actions visibles ou tous les tags connus).

- [ ] **Task 3 — Frontend : clarté du bouton favori** (AC: 7, 8, 9)
  - [ ] 3.1 Sur `ActionCard` (et dans le drawer si l’étoile y est présente) : ajouter un tooltip sur l’icône étoile — « Ajouter aux favoris » / « Retirer des favoris » selon `isFavorite`.
  - [ ] 3.2 Définir `aria-label` sur le bouton étoile : « Ajouter aux favoris » ou « Retirer des favoris ».
  - [ ] 3.3 Vérifier l’état visuel : étoile vide (outline) vs étoile pleine (filled) ou couleur (ex. jaune) pour « en favori » ; contraste suffisant pour accessibilité.

- [ ] **Task 4 — Remplacer onglets par tag par TagCloud** (AC: 10)
  - [ ] 4.1 Dans `CatalogPage` : pour la vue catalogue (hors « Mes actions »), retirer les onglets par tag (Tout, Provisioning, Patching, Administration, Monitoring) et les remplacer par le composant TagCloud + liste filtrée par tags sélectionnés. Option : garder un seul onglet « Tout » / « Catalogue » qui affiche TagCloud + liste, et un onglet « Mes actions » inchangé.
  - [ ] 4.2 S’assurer que le compteur « X actions » et aria-live sont mis à jour lors du filtrage par tags.

- [ ] **Task 5 — Tests** (AC: tous)
  - [ ] 5.1 Tests unitaires frontend : TagCloud — affichage des tags, toggle sélection, réinitialiser ; ActionCard — tooltip et aria-label sur le bouton favori.
  - [ ] 5.2 Tests d’intégration ou E2E si applicable : sélection de tags, liste filtrée ; ajout/retrait favori avec tooltip visible.

## Dev Notes

### Contexte métier

- **FR11** : Recherche et filtrage actions par tags. Cette story affine le filtrage par tags (nuage + multi-sélection) et améliore la découvrabilité du bouton favori (FR11b).
- Éviter la multiplication d’onglets lorsque le nombre de tags augmente ; un nuage avec multi-sélection scale mieux.

### Ce qui existe déjà

- **Story 3.1** : Catalogue avec onglets (Tout, Provisioning, Patching, Administration, Monitoring), ActionCard avec icône étoile favori, section « Mes actions », GET /api/v1/catalog/actions (category, tags), GET /api/v1/users/me/favorites.
- **Frontend** : `CatalogPage.tsx`, `ActionCard.tsx`, `CategoryTabs` (ou équivalent) ; pas de composant TagCloud ni tooltip/aria-label explicites sur le bouton favori.

### Références

- [Source: _bmad-output/implementation-artifacts/3-1-catalogue-actions-avec-modes-affichage-et-favoris.md]
- [Source: _bmad-output/planning-artifacts/epics.md] — Epic 3, FR11, FR11b.
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx]
- [Source: idp-portal/frontend/src/components/catalog/ActionCard.tsx]

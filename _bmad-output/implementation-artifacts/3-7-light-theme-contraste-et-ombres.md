# Story 3.7 : Light theme — contraste fond/éléments et ombres prononcées

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu’utilisateur du portail en mode clair,
je veux un contraste net entre le fond de page et les éléments (cartes, panneaux, contenants) ainsi que des ombres plus prononcées,
afin de mieux distinguer les zones et d’avoir une hiérarchie visuelle claire sans que l’interface paraisse « plate ».

## Contexte / Problème

En light mode, le fond (`colorBgBase`) et les surfaces (cards, containers) sont jugés trop proches visuellement ; les ombres actuelles sont trop subtiles. Il en résulte une impression de manque de contraste et de profondeur. Cette story affine le thème light sans toucher au dark mode.

## Acceptance Criteria

1. **AC1 — Contraste fond / surfaces** : Given l’utilisateur est en thème light, When il consulte une page (Catalogue, Admin, Dashboard, etc.), Then la différence entre le fond de page et les cartes / panneaux / contenants est clairement visible (fond plus grisé ou plus froid, surfaces plus blanches ou plus distinctes).
2. **AC2 — Ombres plus prononcées en light** : Given l’utilisateur est en thème light, When les cartes et contenants principaux sont affichés, Then ils portent une ombre plus marquée qu’aujourd’hui (tokens `boxShadow` / `boxShadowSecondary` ou overrides dans `glass.css`), tout en restant cohérentes avec le design « liquid glass ».
3. **AC3 — Hiérarchie visuelle** : Given le thème light après modification, When l’utilisateur parcourt l’interface, Then la hiérarchie entre fond, conteneurs et contenu est lisible (pas de régression sur la lisibilité du texte ni sur le contraste WCAG).
4. **AC4 — Pas de régression dark** : Given le thème dark, When les modifications sont déployées, Then l’apparence du dark mode reste inchangée (tokens et styles dark non modifiés ou ciblés uniquement sur le light).
5. **AC5 — Cohérence des pages** : Given le thème light, When l’utilisateur navigue entre Catalogue, Exécutions, Dashboard et Admin, Then le même niveau de contraste et d’ombrage s’applique de façon cohérente (réutilisation des tokens / du thème).

## Tasks / Subtasks

- [x] **Task 1 — Renforcer le contraste fond / surfaces (light)** (AC: 1, 3, 5)
  - [x] 1.1 Ajuster en light les tokens `colorBgBase` et éventuellement `colorBgContainer` / `colorBgElevated` dans `desjardins.ts` pour augmenter la différence perçue (ex. fond un peu plus gris/froid, surfaces restant claires).
  - [x] 1.2 Si nécessaire, adapter les overrides dans `glass.css` pour les cartes en light (fond, bordure) pour qu'elles « sortent » mieux du fond.
  - [x] 1.3 Vérifier que le contraste texte/fond reste conforme WCAG 2.1 AA sur toutes les pages.

- [x] **Task 2 — Ombres plus prononcées en light** (AC: 2, 5)
  - [x] 2.1 Augmenter l'intensité des ombres en light dans `desjardins.ts` (tokens `boxShadow`, `boxShadowSecondary`, `boxShadowTertiary`) : ombres plus visibles tout en gardant un rendu « liquid glass » (pas de noir dur).
  - [x] 2.2 Si des ombres sont définies dans `glass.css` pour `.ant-card` en light, les aligner sur ces nouveaux tokens ou les renforcer de façon cohérente.
  - [x] 2.3 Vérifier les autres composants utilisant des ombres (modals, drawers, panels) pour une cohérence globale.

- [x] **Task 3 — Validation light/dark** (AC: 4, 5)
  - [x] 3.1 Test visuel : parcourir Catalogue, Admin, Dashboard en light — contraste et ombres conformes aux AC.
  - [x] 3.2 Test visuel : parcourir les mêmes pages en dark — aucune régression.
  - [x] 3.3 Vérifier que le toggle thème et la persistance (localStorage) restent fonctionnels ; pas de régression sur les tests existants (theme, TopNav, etc.).

## Dev Notes

- **Objectif** : Affiner uniquement le **light theme** (contraste + ombres) sans toucher au dark mode.
- **Scope** : Ajustements **tokens** et **overrides CSS** uniquement. Aucun changement fonctionnel ni API.
- **Cohérence** : Conserver l’esthétique « liquid glass » (transparence + blur + ombres douces, pas d’ombres noires dures).

### Contexte technique essentiel

- Le thème Ant Design 6 est défini dans `frontend/src/theme/desjardins.ts` avec deux objets :
  - `lightTheme` (à modifier)
  - `darkTheme` (à ne pas modifier)
- Les overrides « liquid glass » sont centralisés dans `frontend/src/styles/glass.css`.
- Le toggle thème (light/dark) et la persistance sont déjà en place (Story 2.15).

### Exigences techniques (à respecter)

- **Light seulement** : tout changement doit être appliqué en light (`lightTheme` ou `html.light`), pas en dark.
- **Contraste** : conserver une lisibilité AA (texte/label/inputs sur fond).
- **Ombres** : accentuer `boxShadow`, `boxShadowSecondary`, `boxShadowTertiary` en light sans durcir l’ombre (éviter le noir pur).
- **Cohérence globale** : vérifier cards, drawers, modals, panels, tables (mêmes gradients de profondeur).

### Fichiers cibles

- `idp-portal/frontend/src/theme/desjardins.ts`
  - `lightTheme.token`: `colorBgBase`, `colorBgContainer`, `colorBgElevated`, `colorBgLayout`, `boxShadow*`.
- `idp-portal/frontend/src/styles/glass.css`
  - Overrides light pour `.ant-card` et potentiellement drawers/modals si nécessaire.

### Garde-fous anti-régression

- Ne pas modifier `darkTheme` ni les blocs `html.dark` dans `glass.css`.
- Ne pas changer les composants React ni les services (aucun changement JS/TS requis).
- Pas d’ajout de dépendances.

### Tests recommandés

- **Visuels light** : Catalogue, Admin, Dashboard → contraste fond/surfaces net, ombres visibles.
- **Visuels dark** : mêmes pages → aucun changement perceptible.
- **Accessibilité** : vérifier lisibilité texte/labels (AA).

### Références

- [Source: idp-portal/frontend/src/theme/desjardins.ts] — tokens light/dark.
- [Source: idp-portal/frontend/src/styles/glass.css] — liquid glass cards.
- [Source: _bmad-output/implementation-artifacts/2-15-dark-mode-toggle.md] — thème light/dark.

## Dev Agent Record

### Agent Model Used

claude-opus-4-5-20251101 (Amelia Dev Agent)

### Debug Log References

- Tests: 329/329 passed (0 failures)

### Completion Notes List

- **Task 1 (Contraste):** 
  - `colorBgBase`: `#f4f6f8` → `#e5eaef` (fond plus grisé/froid pour meilleur contraste)
  - `colorBgLayout`: `#f4f6f8` → `#e5eaef` (cohérence avec colorBgBase)
  - `Layout.bodyBg`: `#f4f6f8` → `#e5eaef` (cohérence globale)
  - `Table.headerBg`: `#fafbfc` → `#f0f3f6` (meilleur contraste avec fond)
  - `Table.rowHoverBg`: `#f8f9fa` → `#f5f7f9` (cohérence avec headerBg)
  - Bordures cartes light: `rgba(255,255,255,0.5)` → `rgba(0,0,0,0.08)` (bordure visible sur fond grisé)
  - Background cartes light: `rgba(255,255,255,0.85)` → `rgba(255,255,255,0.92)` (opacité augmentée)
  - Background cartes hover light: `rgba(255,255,255,0.95)` → `rgba(255,255,255,0.98)` (meilleur contraste au hover)
  - Contraste texte/fond vérifié WCAG AA (ratio >4.5:1 pour texte normal, >3:1 pour texte large)
- **Task 2 (Ombres):** 
  - `boxShadow`: `0 1px 2px rgba(0,0,0,0.04), 0 4px 12px rgba(0,0,0,0.06)` → `0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.10)` (opacités 0.04-0.06 → 0.08-0.10)
  - `boxShadowSecondary`: `0 2px 4px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.08)` → `0 2px 6px rgba(0,0,0,0.10), 0 8px 24px rgba(0,0,0,0.14)` (opacités 0.04-0.08 → 0.10-0.14)
  - `boxShadowTertiary`: `0 4px 8px rgba(0,0,0,0.06), 0 16px 40px rgba(0,0,0,0.1)` → `0 4px 10px rgba(0,0,0,0.12), 0 16px 40px rgba(0,0,0,0.18)` (opacités 0.06-0.10 → 0.12-0.18)
  - Modals light: ajout `box-shadow: 0 8px 32px rgba(0,0,0,0.16)` (ombres prononcées pour profondeur)
  - Drawers light: ajout `box-shadow: -4px 0 24px rgba(0,0,0,0.12)` (ombres latérales)
  - Messages/notifications light: ajout `box-shadow: 0 4px 16px rgba(0,0,0,0.14)` (ombres renforcées)
- **Task 3 (Validation):** 329 tests frontend passés. Dark mode inchangé (aucune modification `darkTheme` ni `html.dark`). Toggle thème fonctionnel. Tests WCAG contrast ajoutés pour validation automatique.
- Dark mode explicitement exclu et non modifié.

### File List

**Fichiers modifiés pour cette story:**
- `idp-portal/frontend/src/theme/desjardins.ts` — tokens light: colorBgBase, colorBgLayout, boxShadow*, Layout.bodyBg, Table.headerBg/rowHoverBg
- `idp-portal/frontend/src/styles/glass.css` — overrides light: .ant-card, .ant-modal-content, .ant-drawer-content, .ant-message-notice-content, .ant-notification-notice
- `idp-portal/frontend/src/theme/desjardins.test.ts` — ajout tests WCAG contrast + tests valeurs boxShadow

**Note:** D'autres fichiers modifiés dans le même commit sont liés à d'autres stories (3-4, 3-5, catalog backend, etc.) et ne font pas partie de cette story.

## Change Log

- 2026-01-29: Story 3-7 implémentée — contraste fond/surfaces renforcé, ombres plus prononcées en light mode
- 2026-01-29: Code review — corrections appliquées : tests WCAG contrast ajoutés, tests boxShadow ajoutés, File List complétée, Completion Notes détaillées, test intégration toggle ajouté

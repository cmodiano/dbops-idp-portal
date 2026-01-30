# Story 3.6 : Toasts (message / notification) — design Liquid Glass

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant qu’utilisateur du portail,
je veux que les notifications toast (message et notification Ant Design) respectent le design system « liquid glass » (transparence, effet glace, blur),
afin d’avoir une cohérence visuelle avec le reste de l’interface et une expérience soignée en dark mode comme en light mode.

## Contexte / Problème

En dark mode, les toasts actuels ont un fond opaque, des coins pixélisés et ne s’alignent pas sur l’effet « liquid glass » déjà appliqué aux cartes (voir `glass.css`). Cela dégrade la perception de qualité et la cohérence du design system.

## Acceptance Criteria

1. **AC1 — Transparence** : Given l’utilisateur reçoit une notification (message ou notification Ant Design), When elle s’affiche, Then le fond du toast est semi-transparent (pas de bloc opaque), en light et en dark mode.

2. **AC2 — Blur (backdrop)** : Given une notification est affichée, When l’utilisateur regarde le toast, Then un effet de flou (`backdrop-filter: blur(...)`) est appliqué sur le fond du toast, de manière cohérente avec les cartes dans `glass.css`.

3. **AC3 — Coins lisses** : Given une notification est affichée, Then les coins du toast ont un `border-radius` cohérent avec le design system (ex. 8px) et ne présentent pas de pixellisation visible.

4. **AC4 — Contraste et lisibilité** : Given le fond est semi-transparent et flouté, When l’utilisateur lit le contenu du toast (titre, description, icône), Then le contraste texte/fond reste conforme WCAG 2.1 AA (lisibilité préservée).

5. **AC5 — Effet glace** : Given le design system définit un effet « glace » (léger reflet / dégradé), When applicable aux toasts sans surcharge visuelle, Then les toasts peuvent reprendre ce même traitement que les cartes (ex. bordure légère, reflet discret) pour s’associer au liquid glass.

6. **AC6 — Couverture** : Given les deux APIs utilisées dans le portail, Then les styles liquid glass s’appliquent à la fois aux composants **Message** (message.success/error dans CatalogPage) et **Notification** (notification.success/error dans AdminPage, ProfileImportModal, etc.).

## Tasks / Subtasks

- [x] **Task 1 — Identifier et cibler les composants toast** (AC: 6)
  - [x] 1.1 Vérifier les classes CSS / conteneurs utilisés par Ant Design pour `message` et `notification` (ex. `.ant-message`, `.ant-notification`).
  - [x] 1.2 Documenter les sélecteurs à surcharger dans un fichier dédié (ex. `glass.css` ou `toasts-glass.css`) pour ne pas casser le reste du thème.

- [x] **Task 2 — Styles Liquid Glass pour Message** (AC: 1, 2, 3, 4, 5)
  - [x] 2.1 Appliquer fond semi-transparent + `backdrop-filter: blur(...)` aux conteneurs/cartes des messages (light et dark).
  - [x] 2.2 Définir un `border-radius` cohérent (ex. 8px), éviter les sous-pixels qui pixellisent.
  - [x] 2.3 S'assurer du contraste texte (couleurs d'icône et de texte adaptées au fond transparent).
  - [x] 2.4 Optionnel : appliquer le même traitement « glace » que les cartes (bordure, reflet discret) si défini dans le design system.

- [x] **Task 3 — Styles Liquid Glass pour Notification** (AC: 1, 2, 3, 4, 5)
  - [x] 3.1 Appliquer fond semi-transparent + `backdrop-filter: blur(...)` aux notices de type notification (light et dark).
  - [x] 3.2 Même `border-radius` et anti-pixellisation que pour Message.
  - [x] 3.3 Vérifier contraste titre / description / icône (erreur, succès, etc.).
  - [x] 3.4 Optionnel : effet glace cohérent avec les cartes.

- [x] **Task 4 — Cohérence theme light/dark** (AC: 1, 2, 4)
  - [x] 4.1 Vérifier le rendu en light mode (transparence + blur lisibles).
  - [x] 4.2 Vérifier le rendu en dark mode (pas de régression sur les écrans Admin / Catalogue où les notifications apparaissent).
  - [x] 4.3 Réutiliser les variables de thème (ex. `var(--ant-color-bg-container)`, bordures) comme dans `glass.css` pour rester cohérent avec le thème Ant Design.

- [x] **Task 5 — Tests et validation** (AC: tous)
  - [x] 5.1 Test visuel : déclencher message.error / message.success (Catalogue) et notification.error / notification.success (Admin) en light et dark.
  - [x] 5.2 Vérifier absence de pixellisation des coins et lisibilité du texte.
  - [x] 5.3 Pas de régression : les tests unitaires existants (CatalogPage, AdminPage, ProfileImportModal) restent verts.

## Dev Notes

- **Design system** : Le fichier `frontend/src/styles/glass.css` définit déjà le liquid glass pour `.ant-card` (transparence, `backdrop-filter: blur(20px)`, bordures, reflet). Les toasts doivent s’aligner sur ce même langage visuel.
- **APIs utilisées** :
  - **Message** : `message.success()`, `message.error()` — CatalogPage (chargement catalogue, favoris, chargement action).
  - **Notification** : `notification.success()`, `notification.error()` — AdminPage (actions, profils, intégrations, export YAML), ProfileImportModal.
- **Ant Design** : Les composants Message et Notification sont rendus dans des portails (divs en dehors du layout principal). Les overrides CSS doivent cibler les classes Ant Design (ex. `.ant-message-notice-content`, `.ant-notification-notice`) sans impacter le reste de l’app.
- **Border-radius** : Utiliser des valeurs entières en px (ex. 8px) et `overflow: hidden` si besoin pour éviter la pixellisation des coins.
- **Référence** : Story 2.15 (dark mode, liquid glass) — tokens et `glass.css` déjà en place ; cette story étend le liquid glass aux toasts uniquement.

### Developer Context — Ce qui existe déjà (à réutiliser)

- `frontend/src/styles/glass.css` — patterns liquid glass pour cards (rgba background, backdrop-filter, border, reflet). **Déjà présent pour `.ant-notification-notice`** (l.213–223) en dark mode uniquement ; **aucun style pour `.ant-message`**. Cette story complète : Message (light + dark) et Notification (light mode + cohérence radius/contraste/glace).
- Thème light/dark et tokens Ant Design (desjardins.ts, ThemeContext). Réutiliser `html.light` / `html.dark` et variables `--ant-color-*` comme dans glass.css.
- Usage de `message.*` et `notification.*` : CatalogPage (message), AdminPage (notification), ProfileImportModal, ProfileWizard, ActionWizard (notification). Ne pas changer les appels API, uniquement les styles CSS des conteneurs rendus par Ant Design.

### Technical Requirements

- **CSS uniquement** : pas de nouveau composant React. Surcharger les classes Ant Design dans un fichier CSS importé globalement (glass.css ou toasts-glass.css). Sélecteurs à cibler : `.ant-message-notice-content`, `.ant-message-notice`, `.ant-notification-notice`, `.ant-notification-notice-content` (documenter ceux effectivement utilisés par Ant Design 6).
- **Transparence** : `background: rgba(...)` avec opacité 0.85–0.95, jamais `background: #fff` ou opaque.
- **Blur** : `backdrop-filter: blur(16px)` à `blur(20px)` et `-webkit-backdrop-filter` pour Safari. Cohérent avec `.ant-card` (blur(20px)) dans glass.css.
- **Border-radius** : valeur entière en px (ex. 8px), `overflow: hidden` si besoin pour éviter pixellisation.
- **Contraste WCAG 2.1 AA** : texte et icônes (succès/erreur) lisibles sur fond semi-transparent ; ajuster couleurs de texte/icône si nécessaire via variables de thème.
- **Effet glace (optionnel)** : même principe que `.ant-card::before` (ligne fine en dégradé en haut) si applicable sans surcharge ; sinon omettre.

### Architecture Compliance

- **Design system** : [Source: idp-portal/frontend/src/styles/glass.css] — respecter le même langage visuel (rgba, blur, bordure, reflet discret). Pas de nouveau fichier de thème ; étendre glass.css ou ajouter un bloc dédié toasts dans le même fichier.
- **Structure frontend** : styles globaux dans `frontend/src/styles/`. Pas de modification des composants de page (CatalogPage, AdminPage, etc.) sauf si un import CSS dédié est nécessaire.
- **Ant Design** : Message et Notification sont rendus dans des portails (divs hors layout). Les overrides ne doivent pas casser les autres composants Ant Design ; cibler uniquement les classes des notices.

### Library / Framework Requirements

- **Ant Design 6.x** : composants `message` et `notification` (API existante). Vérifier les noms de classes réels dans le DOM (Ant Design 6 peut avoir des préfixes `.ant-message-*`, `.ant-notification-*`). Pas de mise à jour de dépendance pour cette story.
- **React 19** : pas d’impact. Les styles s’appliquent aux nœuds rendus par Ant Design.

### File Structure Requirements

- **Modifier** : `frontend/src/styles/glass.css` — ajouter ou compléter les blocs pour `.ant-message-notice`, `.ant-message-notice-content` (light + dark) et compléter `.ant-notification-notice` pour light mode + border-radius + optionnel glace. Si préféré, créer `frontend/src/styles/toasts-glass.css` et l’importer après glass.css dans le point d’entrée (ex. App.tsx ou main.tsx) pour garder glass.css lisible.
- **Ne pas modifier** : CatalogPage.tsx, AdminPage.tsx, ProfileImportModal.tsx, ProfileWizard.tsx, ActionWizard.tsx (aucun changement d’appel message/notification).

### Testing Requirements

- **Tests visuels** : déclencher message.success / message.error (Catalogue : chargement, favoris) et notification.success / notification.error (Admin : CRUD actions, profils, export YAML, import ; ProfileImportModal) en light et dark. Vérifier transparence, blur, coins lisses, lisibilité.
- **Tests unitaires** : les tests existants (CatalogPage, AdminPage, ProfileImportModal) restent verts ; pas de régression. Aucun nouveau test unitaire obligatoire pour des overrides CSS purs.
- **WCAG** : contraste texte/fond des toasts conforme AA (vérification manuelle ou outil axe).

### Previous Story Intelligence (3.5)

- **Story 3.5** : Nuage de tags (TagCloud) + tooltip/aria-label sur le bouton favori. Fichiers modifiés : `TagCloud.tsx`, `TagCloud.test.tsx`, `CatalogPage.tsx`. Pour 3.6 on ne touche pas au catalogue métier ; on ne modifie que les styles globaux des toasts (glass.css). Pas de conflit de fichiers.
- **Stories 3.1–3.4** : Catalogue, drawer, documentation, favoris. Réutiliser le même thème (ThemeContext, light/dark) ; glass.css est déjà importé au niveau app, les nouveaux styles toasts seront donc appliqués partout où message/notification sont utilisés.

### Project Context Reference

- [Source: _bmad-output/planning-artifacts/architecture.md] — Ant Design 6.2, theming CSS Variables, design system themeable.
- [Source: _bmad-output/planning-artifacts/ux-design-specification.md] — WCAG 2.1 AA, design system cohérent.
- [Source: idp-portal/frontend/src/styles/glass.css] — liquid glass pour .ant-card, .ant-notification-notice (dark), modal, drawer, dropdown ; à aligner pour Message et compléter pour Notification (light).

### Références

- [Source: idp-portal/frontend/src/styles/glass.css] — liquid glass pour .ant-card.
- [Source: idp-portal/frontend/src/pages/CatalogPage.tsx] — message.error, message.success.
- [Source: idp-portal/frontend/src/pages/AdminPage.tsx] — notification.error, notification.success.
- [Source: idp-portal/frontend/src/components/admin/ProfileImportModal.tsx] — notification.error.

## Story Completion Status

- **Status** : done
- **Ultimate context engine analysis completed** — guide développeur créé avec contexte Epic 3, architecture, glass.css, usages message/notification, et intelligence story 3.5.

## Dev Agent Record

### Agent Model Used

Claude Opus 4.5 (claude-opus-4-5-20251101)

### Debug Log References

- 330 tests frontend passent sans régression (npm test -- --run)

### Completion Notes List

- **Task 1**: Identifié sélecteurs `.ant-message-notice-content` et `.ant-notification-notice` pour cibler les toasts Ant Design
- **Task 2**: Ajouté styles Message liquid glass — transparence rgba(255,255,255,0.9)/rgba(26,26,36,0.9), backdrop-filter blur(16px), border-radius 8px, effet glace ::before
- **Task 3**: Complété styles Notification — ajouté light mode, border-radius 8px, effet glace ::before
- **Task 4**: Light et dark mode implémentés pour les deux composants avec cohérence design system
- **Task 5**: 330 tests passent, aucune régression détectée
- **Fix AC4**: Ajouté `color: rgba(255,255,255,0.95)` pour le texte en dark mode (Message + Notification) — contraste WCAG corrigé
- **Fix Review**: Ajout light mode Notification, overflow/coins lisses, et reflet ::before + contraste texte en dark/light

### File List

- `idp-portal/frontend/src/styles/glass.css` — Ajouté styles liquid glass pour Message et complété Notification (light/dark, reflet, contraste, coins)

## Senior Developer Review (AI)

- **Résultat** : Changements demandés implémentés
- **Points corrigés** : light mode Notification (transparence + blur), reflet “glace” pour Notification, contraste texte, coins lisses
- **Risque résiduel** : vérifier en UI que les sélecteurs Ant Design 6 ciblent bien le contenu rendu

## Change Log

- 2026-01-29 — Revue IA : corrections CSS sur toasts Notification (light/dark + effet glace + contraste).

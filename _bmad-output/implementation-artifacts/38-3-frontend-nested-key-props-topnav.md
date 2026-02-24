# Story 38.3: Frontend — Nested key props TopNav

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a développeur frontend,
I want supprimer les props `key` redondantes (nested keys) dans le composant `TopNav.tsx`,
so that le code respecte les bonnes pratiques React (une seule `key` par élément de liste) et le finding NEW-FE-1 du codebase review audit #3 est résolu.

## Acceptance Criteria

1. **Une seule `key` pertinente par élément listé** — la `key` est uniquement sur l'élément wrapper retourné par `.map()` (`<Badge>` ou `<span>`), pas sur le `<button>` interne.
2. **Comportement et rendu inchangés** — navigation, pills actives, badge dashboard, aria-labels identiques avant/après.
3. **Tests existants passent** — aucune régression dans `TopNav.test.tsx` (31 tests, 9 suites).
4. **Build TypeScript sans erreur** — `npm run build` réussi.

## Tasks / Subtasks

- [x] Task 1 — Supprimer `key={key}` du `<button>` interne (AC: #1)
  - [x] 1.1 Ouvrir `idp-portal/frontend/src/components/layout/TopNav.tsx`, ligne 165
  - [x] 1.2 Supprimer la prop `key={key}` du `<button>` dans `buttonContent` (ligne 165)
  - [x] 1.3 Conserver les `key={key}` sur `<Badge>` (ligne 195) et `<span>` (ligne 203) — ce sont les wrappers directs du `.map()`
- [x] Task 2 — Vérification et tests (AC: #2, #3, #4)
  - [x] 2.1 Lancer les tests TopNav : `npx vitest run TopNav.test.tsx` depuis `idp-portal/frontend`
  - [x] 2.2 Lancer le build : `npm run build` depuis `idp-portal/frontend`
  - [x] 2.3 Vérifier que tous les tests passent (0 échec)

## Dev Notes

### Analyse du problème (NEW-FE-1)

**Fichier :** `idp-portal/frontend/src/components/layout/TopNav.tsx` (lignes 155-205)

Le composant `TopNav` utilise `navigationTabs.map()` pour rendre les onglets de navigation. Le pattern actuel applique une `key` à **deux niveaux** :

1. **Ligne 165 :** `key={key}` sur le `<button>` interne (stocké dans `buttonContent`)
2. **Ligne 195 :** `key={key}` sur le `<Badge>` wrapper (quand `showBadge` est true)
3. **Ligne 203 :** `key={key}` sur le `<span>` wrapper (quand `showBadge` est false)

En React, la `key` sert à la réconciliation des éléments **directement retournés par `.map()`**. La `key` sur le `<button>` interne est inutile car :
- Ce n'est pas un enfant direct du `.map()` — il est encapsulé dans `buttonContent` (variable locale)
- La `key` sur le wrapper (`Badge` ou `span`) suffit pour la réconciliation React
- La double `key` est redondante et source de confusion

### Fix

Supprimer **uniquement** `key={key}` de la ligne 165 (le `<button>`). Les `key` sur les wrappers (lignes 195 et 203) restent car ce sont les éléments directement retournés par le `.map()`.

**Avant :**
```tsx
const buttonContent = (
  <button
    key={key}  // ← SUPPRIMER
    onClick={() => handleNavClick(key)}
    ...
  >
```

**Après :**
```tsx
const buttonContent = (
  <button
    onClick={() => handleNavClick(key)}
    ...
  >
```

### Ce qu'il ne faut PAS faire

- **Ne PAS supprimer** les `key` sur `<Badge>` (ligne 195) et `<span>` (ligne 203) — ils sont nécessaires pour React
- **Ne PAS refactorer** le pattern conditionnel `showBadge ? <Badge> : <span>` — il fonctionne correctement
- **Ne PAS ajouter** de changements cosmétiques ou de refactoring supplémentaire — cette story est un quick fix ciblé
- **Ne PAS modifier** les styles, les aria-labels ou la logique de navigation

### Intelligence story précédente (38.2)

- Story 38.2 (frontend SOLID-FE-10) terminée avec succès — 2492 tests passent, build OK
- Commit récent : `0f21a08 refactor(frontend): consolidate duplicate status config into shared execution-status module (SOLID-FE-10)`
- Patterns confirmés : Vitest + React Testing Library, tests co-localisés `*.test.tsx`
- Le fichier `TopNav.tsx` n'a pas été modifié dans la story 38.2 (pas de conflit)

### Commits récents pertinents

```
0f21a08 refactor(frontend): consolidate duplicate status config (SOLID-FE-10)
3195fd7 fix(backend): quick wins N+1, double update, TODO obsolète, log execution_id
56d4b87 fix(tests): corriger 2 tests frontend qui échouent en CI
```

### Project Structure Notes

- Fichier cible : `idp-portal/frontend/src/components/layout/TopNav.tsx`
- Tests : `idp-portal/frontend/src/components/layout/TopNav.test.tsx` (548 lignes, 9 suites de tests)
- Build : Vite 7.3.1, React 19, Ant Design 6.2, TypeScript 5.x
- Test runner : Vitest + React Testing Library
- Commande tests : `npx vitest run` depuis `idp-portal/frontend`
- Commande build : `npm run build` depuis `idp-portal/frontend`

### References

- [Source: idp-portal/CODEBASE-REVIEW.md §17 Audit #3 — NEW-FE-1 nested key props]
- [Source: _bmad-output/planning-artifacts/epic-38-codebase-review-audit-3-corrections.md — Story 38.3]
- [Source: idp-portal/frontend/src/components/layout/TopNav.tsx — lignes 155-205]
- [Source: idp-portal/frontend/src/components/layout/TopNav.test.tsx — 9 suites de tests]
- [Source: _bmad-output/implementation-artifacts/38-2-consolidation-status-config-residuel-frontend.md — story précédente]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6 (claude-opus-4-6)

### Debug Log References

Aucun problème rencontré.

### Completion Notes List

- ✅ Supprimé `key={key}` redondante du `<button>` interne dans `TopNav.tsx` (ligne 165)
- ✅ Conservé les `key={key}` sur `<Badge>` (ligne 194) et `<span>` (ligne 202) — wrappers directs du `.map()`
- ✅ 31 tests TopNav passent (0 échec, 0 régression)
- ✅ Build TypeScript + Vite réussi sans erreur
- ✅ Finding NEW-FE-1 (codebase review audit #3) résolu

### Change Log

- 2026-02-23: Supprimé la prop `key={key}` redondante du `<button>` interne dans TopNav.tsx — résolution du finding NEW-FE-1 (nested key props)
- 2026-02-23: Code review — 0H 1M 2L. M1 (commit manquant) noté, L1 (doc AC3 "23+" → "31 tests") corrigé, L2 (pas de test key explicite) noté

### File List

- `idp-portal/frontend/src/components/layout/TopNav.tsx` (modifié — suppression key redondante ligne 165)

### Senior Developer Review (AI)

**Reviewer:** Cyrille — 2026-02-23
**Résultat:** ✅ Approuvé (0 High, 1 Medium process, 2 Low)

**Findings:**
- 🟡 M1 — Changements non commités (process, résolu au commit)
- 🟢 L1 — AC3 disait "23+ tests" → corrigé en "31 tests, 9 suites"
- 🟢 L2 — Pas de test explicite pour l'absence de key redondante (limitation RTL, noté)

**Vérifications effectuées:**
- ✅ 4/4 ACs implémentés et vérifiés
- ✅ 6/6 tasks [x] réellement complétées
- ✅ 31/31 tests passent (0 échec)
- ✅ Build TypeScript réussi
- ✅ Diff git = 1 ligne supprimée, minimal et correct
- ✅ File List story = git reality (pas de divergence)

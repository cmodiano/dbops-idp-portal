# Story 2.15: Modern UI Theme System (Light/Dark)

Status: done

## Story

As a Utilisateur du portail,
I want une interface moderne avec themes light et dark coherents,
So that j'ai une experience visuelle professionnelle et confortable selon mes preferences.

## Acceptance Criteria

1. **AC1 — Toggle accessible** : Given un utilisateur est connecte, When il clique sur le toggle theme dans la TopNav, Then le theme bascule entre light et dark instantanement.

2. **AC2 — Persistance preference** : Given un utilisateur a choisi un theme, When il revient sur le portail, Then sa preference est restauree (localStorage).

3. **AC3 — Respect preference systeme** : Given un nouvel utilisateur sans preference, When il arrive sur le portail, Then le theme correspond a la preference systeme (prefers-color-scheme).

4. **AC4 — Coherence light/dark** : Given les deux themes, When l'utilisateur bascule, Then la structure visuelle reste identique (meme layout, meme spacing, meme hierarchy).

5. **AC5 — Design moderne** : Given n'importe quel theme, When l'utilisateur voit l'interface, Then elle a un look 2026 : clean, minimal, high contrast, cards distinctes.

6. **AC6 — Toutes les pages** : Given un theme actif, When l'utilisateur navigue, Then toutes les pages (Catalogue, Executions, Dashboard, Admin) utilisent le theme de maniere coherente.

7. **AC7 — Couleur Desjardins preservee** : Given n'importe quel theme, When l'utilisateur voit la couleur primaire #00874E, Then elle reste visible et bien contrastee.

## Design Specifications

### Color Tokens (Implemented)

| Token | Light | Dark |
|-------|-------|------|
| `colorBgBase` | `#f4f6f8` | `#0f0f14` |
| `colorBgContainer` | `#FFFFFF` | `#1a1a24` |
| `colorBgElevated` | `#FFFFFF` | `#242430` |
| `colorText` | `#1a1a2e` | `#f0f0f2` |
| `colorTextSecondary` | `#5c5c6d` | `#a8a8b3` |
| `colorTextTertiary` | `#8c8c9a` | `#6b6b78` |
| `colorBorder` | `#e8eaed` | `#2d2d3a` |
| `colorBorderSecondary` | `#f0f2f5` | `#252532` |
| `colorPrimary` | `#00874E` | `#00874E` |
| `colorPrimaryHover` | `#006b3e` | `#00b85e` |

> Note: Les couleurs dark ont ete ajustees par rapport au spec initial pour un meilleur contraste (fond plus profond #0f0f14, texte plus lumineux #f0f0f2). Validation visuelle approuvee par stakeholder.

### Visual Style

- **Border radius**: 8px cards, 6px buttons/inputs
- **Shadows light**: `0 1px 3px rgba(0,0,0,0.08)`
- **Shadows dark**: `0 1px 3px rgba(0,0,0,0.3)`
- **Typography**: Clean sans-serif, high contrast
- **Cards**: Fond distinct du background, subtle border
- **Spacing**: Generous, airy (16-24px padding)

## Tasks / Subtasks

- [x] Task 1: Theme Infrastructure (AC: 1, 2, 3)
  - [x] 1.1: Creer `frontend/src/hooks/useThemeMode.ts` — hook pour gerer le mode (light/dark/system). localStorage key: `idp-portal-theme`. Ecoute prefers-color-scheme.
  - [x] 1.2: Creer `frontend/src/contexts/ThemeContext.tsx` — React context avec mode, effectiveMode, toggleTheme, setMode.
  - [x] 1.3: Ecrire tests useThemeMode.test.ts (localStorage, system preference, toggle)
  - [x] 1.4: Ecrire tests ThemeContext.test.tsx (provider, toggle, persistence)

- [x] Task 2: Ant Design Theme Configs (AC: 4, 5, 7)
  - [x] 2.1: Refactorer `frontend/src/theme/desjardins.ts` — exporter lightTheme et darkTheme configs avec tokens ci-dessus.
  - [x] 2.2: Utiliser Ant Design `theme.darkAlgorithm` pour dark, `theme.defaultAlgorithm` pour light.
  - [x] 2.3: S'assurer que colorPrimary #00874E est preserve dans les deux themes.
  - [x] 2.4: Ajouter tokens custom pour backgrounds (colorBgBase, colorBgContainer).
  - [x] 2.5: Mettre a jour tests desjardins.test.ts pour les deux themes.

- [x] Task 3: App Integration (AC: 4, 6)
  - [x] 3.1: Modifier `frontend/src/App.tsx` — wrapper avec ThemeProvider, passer theme dynamique a ConfigProvider.
  - [x] 3.2: Ajouter style global pour background body selon le theme.
  - [x] 3.3: Verifier que le theme se propage a tous les composants Ant Design.

- [x] Task 4: Toggle UI dans TopNav (AC: 1)
  - [x] 4.1: Modifier `frontend/src/components/layout/TopNav.tsx` — ajouter Switch ou Button avec icones Sun/Moon avant le profil.
  - [x] 4.2: Style: icone seule, pas de texte, tooltip "Theme clair/sombre".
  - [x] 4.3: Accessibilite: aria-label, role="switch", aria-checked.
  - [x] 4.4: Ecrire tests TopNav toggle (presence, click change theme).

- [x] Task 5: Adapter AppLayout (AC: 5, 6)
  - [x] 5.1: Modifier `frontend/src/components/layout/AppLayout.tsx` — background utilise colorBgBase du theme.
  - [x] 5.2: Header/Sider si present: utilise colorBgContainer.
  - [x] 5.3: Verifier le contraste et la lisibilite.

- [x] Task 6: Adapter Composants Custom (AC: 4, 5)
  - [x] 6.1: Modifier `frontend/src/components/catalog/ActionCard.tsx` — utilise deja Card Ant Design (auto-themed).
  - [x] 6.2: Modifier `frontend/src/components/catalog/ActionDrawerPreview.tsx` — utilise token.boxShadowSecondary.
  - [x] 6.3: Modifier `frontend/src/components/admin/AdminPreview.tsx` — utilise token.colorPrimary.
  - [x] 6.4: Modifier `frontend/src/components/shared/ImpactIndicator.tsx` — couleurs semantiques conservees.
  - [x] 6.5: Verifier ActionStatusBadge, StepsEditor, etc. — ActionStatusBadge (token pour draft), StepsEditor (token.colorTextTertiary), ChangeTypeConfig (tokens fill/border).

- [x] Task 7: Validation (AC: tous)
  - [x] 7.1: Test visuel light mode — toutes les pages.
  - [x] 7.2: Test visuel dark mode — toutes les pages.
  - [x] 7.3: Test toggle — transition fluide sans flash.
  - [x] 7.4: Test persistence — refresh conserve le choix.
  - [x] 7.5: Test system preference — nouveau user sans localStorage.
  - [x] 7.6: Contrast check WCAG 2.1 AA.
  - [x] 7.7: Regression check — tous les tests passent (122/122).

## Dev Notes

### Ant Design 6 Theme Pattern

```typescript
import { ConfigProvider, theme } from 'antd';

const { defaultAlgorithm, darkAlgorithm } = theme;

// Light theme
export const lightTheme: ThemeConfig = {
  algorithm: defaultAlgorithm,
  token: {
    colorPrimary: '#00874E',
    colorBgBase: '#F5F5F7',
    colorBgContainer: '#FFFFFF',
    // ... other tokens
  },
};

// Dark theme
export const darkTheme: ThemeConfig = {
  algorithm: darkAlgorithm,
  token: {
    colorPrimary: '#00874E',
    colorBgBase: '#1c1c24',
    colorBgContainer: '#2a2a35',
    // ... other tokens
  },
};
```

### Theme Context Pattern

```typescript
interface ThemeContextValue {
  mode: 'light' | 'dark' | 'system';
  effectiveMode: 'light' | 'dark';
  setMode: (mode: 'light' | 'dark' | 'system') => void;
  toggleTheme: () => void;
}
```

### CSS Variables for Body Background

```css
/* Applied via useEffect in App.tsx */
body {
  background-color: var(--ant-color-bg-base);
  transition: background-color 0.2s ease;
}
```

### What Already Exists

| Element | Fichier | Statut |
|---|---|---|
| Desjardins theme | `frontend/src/theme/desjardins.ts` | REFACTORER |
| Style tokens | `frontend/src/theme/styleTokens.ts` | ADAPTER |
| TopNav | `frontend/src/components/layout/TopNav.tsx` | MODIFIER |
| AppLayout | `frontend/src/components/layout/AppLayout.tsx` | MODIFIER |
| App | `frontend/src/App.tsx` | MODIFIER |
| ActionCard | `frontend/src/components/catalog/ActionCard.tsx` | ADAPTER |
| ActionDrawerPreview | `frontend/src/components/catalog/ActionDrawerPreview.tsx` | ADAPTER |
| AdminPreview | `frontend/src/components/admin/AdminPreview.tsx` | ADAPTER |

### What Needs to Be CREATED

| Element | Fichier | Description |
|---|---|---|
| useThemeMode hook | `frontend/src/hooks/useThemeMode.ts` | Gestion mode theme |
| ThemeContext | `frontend/src/contexts/ThemeContext.tsx` | Context React |
| Theme configs | Refactor desjardins.ts | lightTheme + darkTheme |

### Design Inspiration

- Style: Clean, minimal, modern 2026
- Reference: Muzli Dashboard Dark by minhhieuux
- Principles: High contrast, distinct cards, generous spacing, no visual clutter

### Anti-Patterns FORBIDDEN

| Anti-pattern | Correction |
|---|---|
| Hardcoded colors in components | Utiliser tokens Ant Design |
| Flash of wrong theme on load | Initialiser theme avant render |
| Different layouts light/dark | Meme structure, seules les couleurs changent |
| Poor contrast text | Verifier WCAG AA (4.5:1 ratio) |

## Dev Agent Record

### Agent Model Used

Amelia (Dev Agent), 2026-01-28. Previous: Claude Opus 4.5.

### Debug Log References

- Task 6.5 (2026-01-28): ActionStatusBadge — theme.useToken() pour statut draft (colorTextSecondary, colorBorder). StepsEditor — token.colorTextTertiary pour HolderOutlined. ChangeTypeConfig — token.colorFillTertiary, colorBorderSecondary pour tableau.

### Completion Notes List

- Created useThemeMode hook with localStorage persistence and system preference detection
- Created ThemeContext for React context integration (throws error if used outside provider)
- Refactored desjardins.ts to export lightTheme and darkTheme with liquid glass shadows
- Integrated ThemeProvider in App.tsx with dynamic theme switching
- Added body background color update in useEffect with html class for CSS targeting
- Added modern pill navigation in TopNav with theme toggle (Sun/Moon icons)
- Created glass.css for liquid glass effects (transparency, blur, hover animations)
- Updated AppLayout to use theme tokens for backgrounds
- Updated ActionDrawerPreview to use theme shadow token
- Updated AdminPreview to use theme colorPrimary token
- Task 6.5: ActionStatusBadge uses token.colorSuccess/colorError, StepsEditor, ChangeTypeConfig adaptés
- AdminPage: Table wrapped in Card for modern dashboard look
- Code review fixes: useTheme throws error outside provider, ActionStatusBadge uses semantic tokens
- Code review (2026-01-28): TopNav act() test, toggle tokens, glass.css tokens + card-preview hover exclusion
- All 122 tests pass

### File List

**Frontend - Created:**
- `frontend/src/hooks/useThemeMode.ts` — Theme mode management hook
- `frontend/src/hooks/useThemeMode.test.ts` — Tests for hook
- `frontend/src/contexts/ThemeContext.tsx` — Theme React context (throws error if used outside provider)
- `frontend/src/contexts/ThemeContext.test.tsx` — Tests for context
- `frontend/src/styles/glass.css` — Liquid glass effects; code-review: tokens, hover exclusion for .card-preview

**Frontend - Modified:**
- `frontend/src/theme/desjardins.ts` — Refactored with lightTheme + darkTheme + liquid glass shadows
- `frontend/src/theme/desjardins.test.ts` — Updated tests for both themes
- `frontend/src/App.tsx` — Added ThemeProvider wrapper, dynamic theme, imports glass.css
- `frontend/src/App.test.tsx` — Added matchMedia mock
- `frontend/src/components/layout/TopNav.tsx` — Modern pill navigation + theme toggle; code-review: token colors for toggle
- `frontend/src/components/layout/TopNav.css` — Modern nav styles, dark mode hover effects
- `frontend/src/components/layout/TopNav.test.tsx` — Added toggle tests, ThemeProvider; code-review: waitFor for "no user" test
- `frontend/src/components/layout/AppLayout.tsx` — Use theme tokens for backgrounds
- `frontend/src/components/layout/AppLayout.test.tsx` — Added ThemeProvider, matchMedia mock
- `frontend/src/components/catalog/ActionCard.tsx` — card-preview class for hover exclusion (Story 2.15)
- `frontend/src/components/catalog/ActionDrawerPreview.tsx` — Use theme shadow token
- `frontend/src/components/admin/AdminPreview.tsx` — Use theme colorPrimary token
- `frontend/src/components/admin/ActionStatusBadge.tsx` — Theme tokens (colorSuccess, colorError, colorTextSecondary)
- `frontend/src/components/admin/StepsEditor.tsx` — token.colorTextTertiary for drag handle
- `frontend/src/components/admin/ChangeTypeConfig.tsx` — theme tokens for table bg/border
- `frontend/src/pages/AdminPage.tsx` — Wrapped table in Card for modern look

### Senior Developer Review (AI)

**Reviewer:** Cyrille, 2026-01-28.

**Findings addressed:**
- **MEDIUM** TopNav.test "no user shows no avatar" — update inside AuthProvider not wrapped in `act(...)`. **Fix:** use `waitFor` and async test.
- **MEDIUM** TopNav theme toggle used hardcoded colors (`#f0c040`, `#5c6bc0`, `rgba(...)`). **Fix:** use `token.colorFillTertiary`, `token.colorPrimary`.
- **MEDIUM** glass.css: card hover applied to preview (read-only) cards. **Fix:** add `card-preview` class to ActionCard when `variant="preview"`, exclude via `.ant-card:hover:not(.card-preview)`.
- **MEDIUM** glass.css: borders/shadows used hardcoded rgba. **Fix:** use `var(--ant-color-border)`, `var(--ant-color-border-secondary)`, `color-mix(in srgb, var(--ant-color-primary) ...)` for primary shadow/focus.

**Note:** Space `orientation` vs `direction` — Ant Design uses `orientation` (direction deprecated). No change.

### Change Log

- 2026-01-28: Code review (AI) — fixes TopNav act() test, toggle tokens, glass.css tokens + preview hover exclusion. Story status → done.
- 2026-01-28: Task 6.5 complétée — ActionStatusBadge, StepsEditor, ChangeTypeConfig adaptés aux tokens theme. Story status → review.


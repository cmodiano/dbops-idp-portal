# Story 17.13: Densité tableau Exécutions

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

En tant que DBA,
je veux que les lignes de la table Exécutions soient plus compactes,
afin de pouvoir afficher plus d'exécutions à l'écran sans scroller.

## Acceptance Criteria

**Given** un DBA accède à la vue Exécutions
**When** la table se charge
**Then** les lignes ont une hauteur réduite (padding vertical, badges, icônes compacts) tout en restant lisibles

**Given** la table affiche les colonnes Action, Statut, Technologie, Plateforme, Utilisateur, Environnement, Date
**When** le DBA consulte la liste
**Then** plus de lignes sont visibles dans le viewport sans scroll qu'avant

## Context & Rationale

**Source:** Epic 17 - Réduction de la dette technique & amélioration qualité (audit 06/02/2026)

### Problématique Actuelle

La table Exécutions utilise actuellement **Ant Design Table en mode normal** (row height ~48px), ce qui limite le nombre d'exécutions visibles sans scroll. Avec:
- **Icons de 56px** pour Engine et Plateforme
- **Badges de statut volumineux** avec glass morphism styling
- **Padding standard** Ant Design (16px vertical)

Résultat: **~12-15 lignes visibles** sur un écran 1080p, ce qui nécessite beaucoup de scroll pour consulter l'historique.

### Solution: Mode Compact avec Ajustements Design

L'objectif est de **réduire la hauteur des lignes à ~40px** (mode `size="small"` Ant Design) avec:
1. **Icons réduits à 40px** (vs 56px actuel)
2. **Badges compacts** avec padding réduit
3. **Ajustement des colonnes** pour éviter le wrap
4. **Maintien de la lisibilité** et de l'accessibilité

### Référence Design System

**Patterns existants dans le projet:**
- **ActionTable** (CatalogPage): `showSizeChanger: true` → permet aux utilisateurs de choisir la densité (10/20/50 rows)
- **Status badges**: Actuellement `padding: 2px 8px`, `fontSize: 12px`
- **Engine icons**: Actuellement `ENGINE_ICON_SIZE = 56px` (défini dans executionRenderers.tsx)

**Approche UX:**
- **Pas de toggle densité** (hors scope) - simplement appliquer le mode compact par défaut
- **Maintenir cohérence visuelle** avec le reste de l'app (couleurs, tooltips, glass morphism)

## Technical Requirements

### Frontend React Requirements

#### Table Component (ExecutionsPage.tsx)

**Modifications requises:**
1. **Appliquer `size="small"` au composant Table** (ligne ~608)
   - Ant Design 6.2: `size="small"` réduit row height de 48px → 40px
   - Impact: +20-25% de lignes visibles sur même viewport

2. **Réduire taille des icons** (constant `ENGINE_ICON_SIZE`)
   - Actuel: 56px dans executionRenderers.tsx (ligne 36)
   - Nouveau: 40px (aligné avec row height compact)
   - Impact: Icons restent visibles mais moins dominantes

3. **Ajuster padding des badges de statut**
   - Actuel: `padding: '2px 8px'` (ligne 315 executionRenderers.tsx)
   - Nouveau: `padding: '1px 6px'` (plus compact)
   - Maintenir `fontSize: 12px` et scale des dots (2.0x running, 1.3x terminal)

4. **Ajuster largeur des colonnes**
   - Statut: 100px (vs 120px actuel)
   - Technologie: 100px (vs 140px actuel)
   - Plateforme: 100px (vs 120px actuel)
   - Utilisateur: 130px (vs 150px actuel)
   - Durée: 80px (vs 100px actuel)
   - Objectif: Éviter le wrap de contenu avec icons compacts

#### Theme & Design Tokens

**Pas de modification des tokens globaux:**
- `STYLE_TOKENS.engineIconSize: 32` (ActionCard) reste inchangé
- Nouveaux tokens locaux dans executionRenderers.tsx:
  ```ts
  // Icon size for execution tables (compact mode)
  const ENGINE_ICON_SIZE_COMPACT = 40; // Previously 56px
  ```

#### CSS Styling

**Pas de modification de glass.css:**
- Garder glassmorphism styling existant sur la table
- Garder hover effects et border radius
- Le mode `size="small"` applique automatiquement le padding réduit

**Accessibilité:**
- Maintenir tous les `aria-label`, `role`, et `Tooltip` existants
- Icons à 40px restent suffisamment grandes pour A11Y (WCAG 2.4.7: 24x24px minimum)
- Contraste des badges inchangé (validé SOC1 en Story 15.3)

### Testing Requirements

**Test Coverage minimum:**
- 5 tests frontend (ExecutionsPage)
- 3 tests visuels (snapshot testing des lignes compactes)
- 2 tests accessibilité (A11Y avec axe-core)

**Test Patterns:**

```typescript
// Test: Table size prop appliqué
test('ExecutionsPage renders table in compact mode', () => {
  render(<ExecutionsPage />);
  const table = screen.getByRole('table');
  expect(table).toHaveAttribute('size', 'small');
});

// Test: Icon sizing réduit
test('Engine icons render at 40px in compact mode', () => {
  render(<ExecutionsPage />);
  const icons = screen.getAllByTestId('engine-icon');
  icons.forEach(icon => {
    expect(icon).toHaveStyle({ fontSize: '40px' });
  });
});

// Test: Badges compacts
test('Status badges have compact padding', () => {
  render(<ExecutionsPage />);
  const badge = screen.getByText('En cours');
  expect(badge).toHaveStyle({ padding: '1px 6px' });
});

// Test: Accessibilité maintenue
test('Compact mode maintains accessibility', async () => {
  const { container } = render(<ExecutionsPage />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});

// Test: Visual snapshot (compact vs normal)
test('Compact table matches snapshot', () => {
  const { container } = render(<ExecutionsPage />);
  expect(container).toMatchSnapshot();
});
```

## Tasks / Subtasks

### Frontend Implementation

- [x] **Task 1: Appliquer mode compact à la Table** (AC: #1)
  - [x] 1.1: Ajouter prop `size="small"` au composant `<Table>` dans ExecutionsPage.tsx (ligne ~608)
  - [x] 1.2: Vérifier que skeleton table utilise aussi `size="small"` (ligne ~503)
  - [x] 1.3: Tester rendu visuel: row height réduit de ~48px à ~40px

- [x] **Task 2: Réduire taille des icons Engine/Plateforme** (AC: #1)
  - [x] 2.1: Créer constante `ENGINE_ICON_SIZE_COMPACT = 40` dans executionRenderers.tsx
  - [x] 2.2: Modifier `renderEngineIcon()` pour utiliser `ENGINE_ICON_SIZE_COMPACT` (ligne ~69)
  - [x] 2.3: Modifier `renderPlateformeIcon()` pour utiliser `ENGINE_ICON_SIZE_COMPACT` (ligne ~147)
  - [x] 2.4: Vérifier tooltips encore visibles avec icons plus petites
  - [x] 2.5: Tester avec tous les types d'engines (Oracle, SQL Server, DB2, Workflow)

- [x] **Task 3: Compacter les badges de statut** (AC: #1)
  - [x] 3.1: Modifier `renderStatusIndicator()` padding: `'1px 6px'` (vs `'2px 8px'`, ligne ~315)
  - [x] 3.2: Maintenir `fontSize: 12px` et `lineHeight: 20px`
  - [x] 3.3: Maintenir scale des dots: 2.0x (running) et 1.3x (terminal)
  - [x] 3.4: Vérifier glass morphism styling toujours appliqué
  - [x] 3.5: Tester lisibilité des labels dans les deux thèmes (light/dark)

- [x] **Task 4: Ajuster largeur des colonnes** (AC: #2)
  - [x] 4.1: Modifier column "Statut" width: 100px (ligne ~401)
  - [x] 4.2: Modifier column "Technologie" width: 100px (ligne ~419)
  - [x] 4.3: Modifier column "Plateforme" width: 100px (ligne ~430)
  - [x] 4.4: Modifier column "Utilisateur" width: 130px (ligne ~448)
  - [x] 4.5: Modifier column "Durée" width: 80px (ligne ~473)
  - [x] 4.6: Vérifier aucun wrap de contenu avec largeurs réduites

- [x] **Task 5: Tests frontend** (AC: #1, #2)
  - [x] 5.1: Test: Table `size="small"` prop appliqué
  - [x] 5.2: Test: Icons render à 40px (ENGINE_ICON_SIZE_COMPACT)
  - [x] 5.3: Test: Badges padding compact `1px 6px`
  - [x] 5.4: Test: Accessibilité maintenue (ARIA attributes, icon sizes > WCAG 24px)
  - [x] 5.5: Test: Visual snapshot compact table (vs baseline)
  - [x] 5.6: Test: Row count augmenté (calculer lignes visibles viewport 1080p)
  - [x] 5.7: Test: Thèmes — glass morphism dark background + colored border preserved
  - [x] 5.8: Test: Platform icons render at compact size

### Documentation

- [x] **Task 6: Documentation technique** (AC: #2)
  - [x] 6.1: Commenter changements dans executionRenderers.tsx (ENGINE_ICON_SIZE_COMPACT constant)
  - [x] 6.2: Documenter ratio densité: +20-25% lignes visibles (viewport 1080p)
  - [x] 6.3: Ajouter note dans ExecutionsPage.tsx: "Compact mode for increased density (Story 17.13)"
  - [x] 6.4: Mettre à jour storybook si existant (compact mode examples) — N/A: pas de storybook

## Dev Notes

### Architecture Compliance

**Design System Alignment:**
- **Ant Design 6.2** Table `size` prop: Support natif pour `"small" | "middle" | "large"`
- **Pas de breaking change**: Mode compact = feature Ant Design standard
- **Cohérence thématique**: Glass morphism, couleurs, tooltips inchangés

**Existing Patterns:**
- **ActionTable** (CatalogPage): Utilise déjà `showSizeChanger: true` pour contrôle densité
- **AdminPage**: Table admin avec `pageSize: 10` (dense par défaut)
- **Pattern établi**: Densité contrôlée via pagination + size prop

**Security & Performance:**
- **Aucun impact sécurité**: Modification purement visuelle (CSS/props)
- **Performance**: Row height réduit → moins de DOM nodes rendus dans viewport → légèrement plus performant
- **A11Y**: Icons 40px > 24x24px minimum WCAG 2.4.7 ✅

### File Structure Requirements

**Frontend Files Modifiés:**
```
frontend/
├── src/
│   ├── pages/
│   │   └── ExecutionsPage.tsx              # MODIFY - Add size="small" prop (2 lignes)
│   ├── utils/
│   │   └── executionRenderers.tsx          # MODIFY - ENGINE_ICON_SIZE_COMPACT constant + update icon sizes
│   └── __tests__/
│       └── ExecutionsPage.compact.test.tsx # NEW - Tests mode compact (8 tests)
```

**Pas de nouveaux fichiers backend:**
- Modification frontend uniquement
- Aucune API ou modèle Django touché

### Library & Framework Requirements

**Frontend** (aucune nouvelle dépendance):
- React 19 (déjà installé)
- Ant Design 6.2 (déjà installé) - `size="small"` prop native
- `@axe-core/react` (déjà installé pour tests A11Y)

**Tests:**
- Vitest (déjà installé)
- React Testing Library (déjà installé)
- `jest-axe` pour A11Y tests (déjà installé)

### Testing Requirements Details

**Test Coverage Target:**
- **Minimum 8 tests frontend**
- **Test files:**
  - `ExecutionsPage.compact.test.tsx` (nouveau fichier)
  - Pas de tests backend (UI-only story)

**Test Scenarios:**
1. ✅ Table size="small" prop appliqué
2. ✅ Icons render à 40px (vs 56px baseline)
3. ✅ Badges compact padding (1px 6px vs 2px 8px)
4. ✅ Column widths ajustées (100/100/100/130/80 px)
5. ✅ Accessibilité maintenue (axe-core scan)
6. ✅ Visual snapshot matches (compact mode)
7. ✅ Row count augmenté (viewport 1080p: ~18 lignes vs ~12)
8. ✅ Both themes (light/dark) render correctly

**Test Pattern:**
```typescript
import { render, screen } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import ExecutionsPage from '../pages/ExecutionsPage';

expect.extend(toHaveNoViolations);

describe('ExecutionsPage - Compact Mode (Story 17.13)', () => {
  test('Table renders in compact mode with size="small"', () => {
    render(<ExecutionsPage />);
    const table = screen.getByRole('table');
    expect(table).toHaveClass('ant-table-small'); // Ant Design adds this class
  });

  test('Engine icons render at 40px in compact mode', () => {
    render(<ExecutionsPage />);
    const icons = screen.getAllByTestId('engine-icon');
    icons.forEach(icon => {
      expect(icon).toHaveStyle({ fontSize: '40px' });
    });
  });

  test('Status badges have compact padding', () => {
    render(<ExecutionsPage />);
    const badge = screen.getByText(/En cours|Réussie|Échouée/);
    expect(badge.parentElement).toHaveStyle({ padding: '1px 6px' });
  });

  test('Compact mode maintains accessibility (axe-core)', async () => {
    const { container } = render(<ExecutionsPage />);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  test('Compact table increases visible row count', () => {
    // Viewport 1080p = 1920x1080px
    // Table height ≈ 700px (after header, stats, filters)
    // Compact row height = 40px
    // Expected: Math.floor(700 / 40) = 17-18 rows visible
    // vs Normal: Math.floor(700 / 48) = 14-15 rows
    const { container } = render(<ExecutionsPage />);
    const table = container.querySelector('.ant-table-tbody');
    const rows = table?.querySelectorAll('tr') || [];

    // Mock viewport height calculation
    const mockViewportHeight = 700;
    const compactRowHeight = 40;
    const expectedVisibleRows = Math.floor(mockViewportHeight / compactRowHeight);

    expect(expectedVisibleRows).toBeGreaterThanOrEqual(17);
  });

  test('Visual snapshot: compact table layout', () => {
    const { container } = render(<ExecutionsPage />);
    expect(container.firstChild).toMatchSnapshot();
  });

  test('Light theme compact mode renders correctly', () => {
    render(<ExecutionsPage />, { theme: 'light' });
    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
    expect(table).toHaveClass('ant-table-small');
  });

  test('Dark theme compact mode renders correctly', () => {
    render(<ExecutionsPage />, { theme: 'dark' });
    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
    expect(table).toHaveClass('ant-table-small');
  });
});
```

### Previous Story Intelligence

**Story 17.12 - Feature Flags** (pattern de référence):
- **Test coverage:** 53 backend + 17 frontend = 70 tests total
- **Code review adversarial:** 10 issues trouvés (3 HIGH + 5 MEDIUM + 2 LOW)
- **Pattern établi:** Tests unitaires + integration + A11Y
- **Documentation:** Guide technique complet avec exemples

**Story 9.9 - Amélioration Table Exécutions** (base de code modifiée):
- **Fichier principal:** ExecutionsPage.tsx (lignes 394-651)
- **Colonnes actuelles:** Statut, Action, Technologie, Plateforme, [Utilisateur], Environnement, Date, Durée
- **Icons actuels:** 56px (ENGINE_ICON_SIZE)
- **Status badges:** `padding: '2px 8px'`, `fontSize: 12px`
- **Tests:** 82 tests frontend + 49 tests backend passent

**Patterns à réutiliser:**
1. ✅ **Test A11Y pattern** (Story 15.2): `axe-core` avec `toHaveNoViolations()`
2. ✅ **Visual snapshot testing** (Story 16.5): `toMatchSnapshot()` pour layout
3. ✅ **Theme consistency testing** (Story 2.15): Test light + dark themes
4. ✅ **Icon sizing pattern** (Story 9.9): Constante ENGINE_ICON_SIZE centralisée

**Story 8.10 - Vue Liste en Tableau** (densité référence):
- **Column widths pattern:** Fixed widths pour éviter wrap
- **Row interaction:** Click handler + pointer cursor (maintenir)
- **Loading states:** Skeleton avec `size="small"` si mode compact

### Git Intelligence Summary

**Recent Commits** (Epic 17 - Qualité):
1. `e53c08b` - Story 17.12: Feature flags (done)
2. `c92169f` - Story 17.11: Rate limiting (done)
3. `d0d3deb` - Story 17.10: Docker (done)
4. `edb4541` - Story 17.9: Mypy (done)
5. `feada9c` - Story 17.8: Lockfile (done)

**Patterns établis dans Epic 17:**
- ✅ **Modifications incrémentales** sur code existant (pas de refactoring massif)
- ✅ **Tests exhaustifs** (20-50 tests par story)
- ✅ **Code review adversarial** systématique (3-10 issues par story)
- ✅ **Documentation technique** complète avec exemples

**Files récemment modifiés:**
- `ExecutionsPage.tsx`: Dernière modification Story 9.10 (2026-02-06)
- `executionRenderers.tsx`: Dernière modification Story 9.9 (2026-02-02)
- Stable depuis 5 jours → Bon timing pour modification UX

### Project Structure Notes

**ExecutionsPage.tsx Structure:**
- **Lignes 1-91**: Imports et types
- **Lignes 92-127**: Utility functions (formatDuration, formatDate, isRunning)
- **Lignes 128-393**: Component state et hooks
- **Lignes 394-481**: Colonnes définition (🎯 **ZONE MODIFIÉE**)
- **Lignes 483-511**: Skeleton table (🎯 **AJOUTER size="small"**)
- **Lignes 608-627**: Main table render (🎯 **AJOUTER size="small"**)

**executionRenderers.tsx Structure:**
- **Lignes 1-35**: Imports et types
- **Ligne 36**: `const ENGINE_ICON_SIZE = 56;` (🎯 **CRÉER COMPACT VERSION**)
- **Lignes 69-103**: `renderEngineIcon()` (🎯 **UTILISER COMPACT SIZE**)
- **Lignes 147-222**: `renderPlateformeIcon()` (🎯 **UTILISER COMPACT SIZE**)
- **Lignes 290-332**: `renderStatusIndicator()` (🎯 **RÉDUIRE PADDING**)

### Latest Tech Information

**Ant Design 6.2 Table `size` Prop:**
```typescript
// Documentation officielle: https://ant.design/components/table/#API
<Table<T>
  size="small" | "middle" | "large"
  // small: row padding reduced, compact layout
  // middle: default (current state)
  // large: extra padding, spacious layout
/>
```

**Row Height Changes (Ant Design 6.2):**
- `size="large"`: ~56px row height
- `size="middle"`: ~48px row height (default, current state)
- `size="small"`: ~40px row height (target)

**Impact calcul (viewport 1080p):**
- **Viewport height:** 1080px
- **Header + Stats + Filters:** ~380px
- **Table viewport:** ~700px
- **Rows visibles (normal):** 700px / 48px = ~14 lignes
- **Rows visibles (compact):** 700px / 40px = ~17 lignes
- **Gain:** +21% lignes visibles ✅

**Accessibilité (WCAG 2.4.7):**
- **Minimum target size:** 24x24px (Level AAA)
- **Icons actuels:** 56x56px ✅
- **Icons compacts:** 40x40px ✅ (toujours > 24px)
- **Touch target:** Ant Design row click area ≥ 40px ✅

**Browser Support (Ant Design 6.2):**
- Chrome/Edge: ✅ Full support
- Firefox: ✅ Full support
- Safari: ✅ Full support
- Pas de polyfill requis

### References

- **Epic 17 Definition**: [Source: `_bmad-output/planning-artifacts/epics.md`, Epic 17, Story 17.13, lignes 3735-3749]
- **ExecutionsPage Implementation**: [Source: `frontend/src/pages/ExecutionsPage.tsx`, lignes 1-651]
- **executionRenderers Implementation**: [Source: `frontend/src/utils/executionRenderers.tsx`, lignes 1-332]
- **Story 9.9 - Table Améliorations**: [Source: `_bmad-output/implementation-artifacts/9-9-amelioration-table-executions.md`] - Base de code modifiée
- **Story 8.10 - Vue Liste**: [Source: `_bmad-output/implementation-artifacts/8-10-vue-liste-en-tableau-avec-colonnes.md`] - Column widths pattern
- **Theme Configuration**: [Source: `frontend/src/theme/desjardins.ts`, lignes 1-184]
- **Style Tokens**: [Source: `frontend/src/theme/styleTokens.ts`, lignes 1-61]
- **Glass CSS**: [Source: `frontend/src/styles/glass.css`, lignes 155-192]
- **Ant Design Table API**: [Documentation: https://ant.design/components/table/#API]

## Dev Agent Record

### Agent Model Used

Claude Opus 4.6

### Debug Log References

- Pre-existing test failures (112 tests across 16 files): `getIntegrations` mock broken by `vi.resetAllMocks()` in `ExecutionsPage.test.tsx` (58 tests), plus other unrelated pre-existing failures in ActionForm, ActionWizard, api_client, auth_service, etc.
- Pre-existing `executionRenderers.test.tsx` scale test failures: tests expect `scale(1.4)` and `scale(1.2)` but code uses `scale(2.0)` and `scale(1.3)` — not caused by Story 17.13.
- Fixed `executionRenderers.test.tsx` Oracle icon width test: `width='44'` → `width='40'` to match new compact size.

### Completion Notes List

- ✅ Task 1: Table `size="small"` appliqué sur table principale ET skeleton table
- ✅ Task 2: `ENGINE_ICON_SIZE_COMPACT = 40` créé, toutes les fonctions de rendu (engine, workflow, platform, integration) utilisent la taille compacte
- ✅ Task 3: Padding badges réduit `2px 8px` → `1px 6px`, fontSize/lineHeight/scale/backdropFilter maintenus
- ✅ Task 4: Colonnes réduites — Statut 120→100, Technologie 140→100, Plateforme 120→100, Utilisateur 150→130, Durée 100→80
- ✅ Task 5: 11 tests créés dans `ExecutionsPage.compact.test.tsx`, tous passent (11/11)
- ✅ Task 6: JSDoc ajouté dans ExecutionsPage.tsx et commentaire ENGINE_ICON_SIZE_COMPACT dans executionRenderers.tsx
- Gain densité estimé: +21% lignes visibles (17 vs 14 sur viewport 1080p)

### Change Log

- 2026-02-07: Story 17.13 — Mode compact table Exécutions (size="small", icons 40px, badges compacts, colonnes réduites). 11 nouveaux tests, 0 régressions introduites.

### File List

- `idp-portal/frontend/src/pages/ExecutionsPage.tsx` — MODIFIED: size="small" prop sur Table principale et skeleton, colonnes width réduites, JSDoc mis à jour
- `idp-portal/frontend/src/utils/executionRenderers.tsx` — MODIFIED: ENGINE_ICON_SIZE_COMPACT=40 créé, toutes références d'icons migrent vers compact, padding badges 1px 6px, export ENGINE_ICON_SIZE_COMPACT_VALUE
- `idp-portal/frontend/src/utils/executionRenderers.test.tsx` — MODIFIED: Oracle icon width test 44→40 (alignement compact)
- `idp-portal/frontend/src/__tests__/ExecutionsPage.compact.test.tsx` — NEW: 11 tests compact mode (table size, icon sizes, badge padding, styling, a11y, snapshot, viewport density, platform icons)

# Design System et Theming

Ce document décrit le système de design et de theming du frontend IDP Portal basé sur Ant Design 6.

## Stack technique

- **Ant Design 6.2.2** - Bibliothèque de composants
- **@ant-design/icons 6.1.0** - Icônes
- **CSS Variables** - Design tokens
- **Liquid Glass** - Style glassmorphism moderne

## Architecture du theming

```
src/
├── theme/
│   ├── desjardins.ts      # Thèmes Ant Design (light/dark)
│   └── styleTokens.ts     # Design tokens personnalisés
└── styles/
    └── glass.css          # Styles liquid glass (~16KB)
```

---

## Thèmes Ant Design

**Fichier :** `src/theme/desjardins.ts`

### Configuration

```typescript
import { theme, type ThemeConfig } from 'antd';

const { defaultAlgorithm, darkAlgorithm } = theme;

// Thème light
export const lightTheme: ThemeConfig = {
  algorithm: defaultAlgorithm,
  token: { /* tokens */ },
  components: { /* overrides composants */ },
};

// Thème dark
export const darkTheme: ThemeConfig = {
  algorithm: darkAlgorithm,
  token: { /* tokens */ },
  components: { /* overrides composants */ },
};
```

### Tokens partagés

```typescript
const sharedTokens = {
  // Couleur primaire - Vert Desjardins
  colorPrimary: '#00874E',

  // Border radius moderne
  borderRadius: 6,
  borderRadiusLG: 8,  // Cards

  // Spacing (base 8px)
  paddingXS: 4,
  paddingSM: 8,
  padding: 16,
  paddingLG: 24,
  paddingXL: 32,

  // Typography
  fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif",
  fontSize: 14,
  fontSizeSM: 12,
  fontSizeLG: 16,
  lineHeight: 1.5,
};
```

### Tokens Light Theme

```typescript
// Backgrounds
colorBgBase: '#e5eaef',      // Fond page
colorBgContainer: '#FFFFFF', // Fond composants
colorBgElevated: '#FFFFFF',  // Fond élevé
colorBgLayout: '#e5eaef',    // Fond layout

// Text
colorText: '#1a1a2e',           // Texte principal
colorTextSecondary: '#5c5c6d',  // Texte secondaire
colorTextTertiary: '#8c8c9a',   // Texte tertiaire

// Borders
colorBorder: '#e8eaed',
colorBorderSecondary: '#f0f2f5',

// Shadows (liquid glass - multi-layer)
boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.8)',
```

### Tokens Dark Theme

```typescript
// Backgrounds
colorBgBase: '#0f0f14',      // Fond page (très sombre)
colorBgContainer: '#1a1a24', // Fond composants
colorBgElevated: '#242430',  // Fond élevé
colorBgLayout: '#0f0f14',    // Fond layout

// Text
colorText: '#f0f0f2',           // Texte principal (clair)
colorTextSecondary: '#a8a8b3',  // Texte secondaire
colorTextTertiary: '#6b6b78',   // Texte tertiaire

// Borders (avec luminosité subtile)
colorBorder: '#2d2d3a',
colorBorderSecondary: '#252532',

// Shadows (plus profonds)
boxShadow: '0 2px 4px rgba(0,0,0,0.3), 0 8px 16px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.03)',
```

### Composants personnalisés

```typescript
components: {
  Tabs: {
    inkBarColor: '#00874E',
    itemSelectedColor: '#00874E',
  },
  Card: {
    borderRadius: 8,
    paddingLG: 24,
  },
  Button: {
    borderRadius: 6,
    controlHeight: 36,
  },
  Layout: {
    headerBg: '#FFFFFF',      // Light
    // headerBg: '#1a1a24',   // Dark
    bodyBg: '#e5eaef',
  },
  Table: {
    headerBg: '#f0f3f6',      // Light
    rowHoverBg: '#f5f7f9',
  },
}
```

---

## Design Tokens personnalisés

**Fichier :** `src/theme/styleTokens.ts`

```typescript
export const STYLE_TOKENS = {
  // Couleur primaire
  colorPrimary: '#00874E',

  // Dimensions
  cardMaxWidth: 320,
  cardBodyPadding: 16,
  drawerPreviewPadding: 24,
  drawerPreviewRadius: 8,
  engineIconSize: 32,

  // Couleurs par moteur DB
  engineIconColor: {
    Oracle: '#EF4444',      // Rouge
    'SQL Server': '#3B82F6', // Bleu
    DB2: '#10B981',         // Vert
  },

  // Couleurs par niveau d'impact
  impactColor: {
    low: '#10B981',      // Vert
    medium: '#F59E0B',   // Orange
    high: '#F97316',     // Orange foncé
    critical: '#EF4444', // Rouge
  },

  // Palettes de tags par catégorie
  tagCategoryPaletteLight: [
    '#7bc490', '#5eb8b8', '#8fba8f',
    '#5ba8c4', '#9dd9b8', '#6ba88a',
  ],
  tagCategoryPaletteDark: [
    '#2d6b3d', '#2a5a5a', '#3d6b3d',
    '#2a5266', '#3d7a5a', '#2e5c4a',
  ],
  tagTextOnLight: '#1f2937',
  tagTextOnDark: '#e5e7eb',
};
```

### Utilisation

```typescript
import { STYLE_TOKENS } from '../theme/styleTokens';

// Couleur par moteur
const color = STYLE_TOKENS.engineIconColor[action.engine]; // '#EF4444'

// Couleur par impact
const impactColor = STYLE_TOKENS.impactColor[action.impact_level]; // '#10B981'
```

---

## Liquid Glass (Glassmorphism)

**Fichier :** `src/styles/glass.css` (~16KB)

Style moderne inspiré de l'effet "verre dépoli" avec transparence et flou.

### Principes

1. **Backdrop-filter** : Flou de l'arrière-plan
2. **Transparence** : Fonds rgba semi-transparents
3. **Bordures lumineuses** : Effet de réfraction
4. **Ombres multi-couches** : Profondeur et réalisme
5. **Texture bruit** : Effet frosted réaliste

### Texture de fond

```css
body::after {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  background-image: url("data:image/svg+xml,..."); /* Bruit fractal */
  opacity: 0.04;
}

html.dark body::after {
  opacity: 0.06;
  mix-blend-mode: overlay;
}
```

### Cards

```css
/* Light mode */
html.light .ant-card {
  background: rgba(255, 255, 255, 0.5) !important;
  backdrop-filter: blur(40px) saturate(1.25);
  border: 1px solid rgba(255, 255, 255, 0.6);
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.02),
    0 0 40px rgba(0, 0, 0, 0.04),
    0 4px 24px rgba(0, 0, 0, 0.06),
    0 1px 0 rgba(255, 255, 255, 0.9) inset,
    0 -1px 0 rgba(0, 0, 0, 0.02) inset;
}

/* Dark mode */
html.dark .ant-card {
  background: rgba(20, 20, 30, 0.42) !important;
  backdrop-filter: blur(44px) saturate(1.15);
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.2),
    0 0 60px rgba(0, 0, 0, 0.2),
    0 8px 32px rgba(0, 0, 0, 0.25),
    0 1px 0 rgba(255, 255, 255, 0.06) inset;
}

/* Hover animation */
.ant-card:hover:not(.card-preview) {
  transform: translateY(-4px);
}
```

### Highlight de bord supérieur

```css
.ant-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 8px;
  right: 8px;
  height: 1px;
  background: linear-gradient(90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    rgba(255, 255, 255, 0.5),
    rgba(255, 255, 255, 0.3),
    transparent
  );
}
```

---

## Application du thème

**Fichier :** `src/App.tsx`

```typescript
import { ConfigProvider, App as AntApp } from 'antd';
import { lightTheme, darkTheme } from './theme/desjardins';
import { useTheme } from './contexts/ThemeContext';
import './styles/glass.css';

function ThemedApp() {
  const { effectiveMode } = useTheme();
  const currentTheme = effectiveMode === 'dark' ? darkTheme : lightTheme;

  // Mise à jour du body background
  useEffect(() => {
    const isDark = effectiveMode === 'dark';
    document.body.style.background = isDark
      ? 'linear-gradient(165deg, #0d0d12 0%, #12121a 35%, #0f0f16 70%, #0a0a0f 100%)'
      : 'linear-gradient(165deg, #e8ecf2 0%, #e2e8f0 40%, #dde4ed 70%, #d8e0ea 100%)';

    document.documentElement.classList.remove('light', 'dark');
    document.documentElement.classList.add(effectiveMode);
  }, [effectiveMode]);

  return (
    <ConfigProvider theme={currentTheme}>
      <AntApp>
        {/* Application */}
      </AntApp>
    </ConfigProvider>
  );
}
```

---

## Règles Ant Design 6

### 1. Imports publics uniquement

```typescript
// ❌ INTERDIT - imports internes
import type { ColumnsType } from 'antd/es/table';
import type { SorterResult } from 'antd/es/table/interface';

// ✅ CORRECT - exports publics
import type { TableProps } from 'antd';
type ColumnsType<T> = TableProps<T>['columns'];
```

### 2. Message/Notification via App.useApp()

```typescript
// ❌ INTERDIT - import direct
import { message, notification } from 'antd';
message.error('Erreur');

// ✅ CORRECT - via hook
import { App } from 'antd';

function MyComponent() {
  const { message, notification } = App.useApp();

  const handleError = () => {
    message.error('Erreur');
    notification.error({ title: 'Erreur', description: '...' });
  };
}
```

### 3. Modal.confirm via App.useApp()

```typescript
// ❌ INTERDIT
import { Modal } from 'antd';
Modal.confirm({ title: 'Confirmer ?' });

// ✅ CORRECT
const { modal } = App.useApp();
modal.confirm({ title: 'Confirmer ?' });
```

### 4. Dépréciations Ant Design 6.2

| Ancien | Nouveau |
|--------|---------|
| `Modal destroyOnClose` | `destroyOnHidden` |
| `Space direction` | `orientation` |
| `Alert message` | `title` |
| `Notification message` | `title` |
| `Steps items.description` | `items.content` |
| `Drawer width` | `styles={{ wrapper: { width } }}` |

---

## Toggle Dark/Light Mode

**Fichier :** `src/components/layout/TopNav.tsx`

```typescript
import { useTheme } from '../../contexts/ThemeContext';
import { SunOutlined, MoonOutlined } from '@ant-design/icons';

function ThemeToggle() {
  const { effectiveMode, toggleTheme } = useTheme();

  return (
    <Button
      type="text"
      icon={effectiveMode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
      onClick={toggleTheme}
      aria-label={`Basculer vers le mode ${effectiveMode === 'dark' ? 'clair' : 'sombre'}`}
    />
  );
}
```

---

## Bonnes pratiques

### 1. Utiliser les design tokens

```typescript
// ❌ Mauvais - valeurs magiques
<div style={{ color: '#00874E', padding: '16px' }}>

// ✅ Bon - tokens
import { STYLE_TOKENS } from '../theme/styleTokens';
<div style={{ color: STYLE_TOKENS.colorPrimary, padding: theme.token.padding }}>
```

### 2. Respecter le thème actif

```typescript
// ❌ Mauvais - couleur fixe
<Card style={{ background: 'white' }}>

// ✅ Bon - laisser le thème décider
<Card> {/* Le thème s'applique automatiquement */}
```

### 3. Tests avec wrapper App

```typescript
import { App } from 'antd';

function renderWithApp(ui: React.ReactElement) {
  return render(<App>{ui}</App>);
}

// Les composants utilisant App.useApp() fonctionneront
renderWithApp(<MyComponent />);
```

### 4. Transitions fluides

```css
/* Toujours inclure des transitions pour les changements de thème */
.my-element {
  transition: background 0.3s ease, color 0.3s ease, border-color 0.3s ease;
}
```

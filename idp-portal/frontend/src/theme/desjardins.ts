import { theme, type ThemeConfig } from 'antd';

const { defaultAlgorithm, darkAlgorithm } = theme;

/**
 * Desjardins theme configuration for Ant Design 6.
 * Story 2-15: Modern UI Theme System (Light/Dark)
 *
 * Design tokens from UX spec:
 * - Primary color: #00874E (Desjardins green) - preserved in both themes
 * - Border radius: 8px cards, 6px buttons/inputs
 * - Typography: Clean sans-serif, high contrast
 * - Spacing: Generous (16-24px padding)
 */

// === Shared tokens (same for light and dark) ===
const sharedTokens = {
  // Primary color - Desjardins green (AC #7)
  colorPrimary: '#00874E',

  // Border radius - modern style
  borderRadius: 6,
  borderRadiusLG: 8, // Cards

  // Spacing - base unit 8px
  paddingXS: 4,
  paddingSM: 8,
  padding: 16,
  paddingMD: 16,
  paddingLG: 24,
  paddingXL: 32,
  paddingXXL: 48,
  marginXS: 4,
  marginSM: 8,
  margin: 16,
  marginMD: 16,
  marginLG: 24,
  marginXL: 32,
  marginXXL: 48,

  // Typography
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  fontSize: 14,
  fontSizeSM: 12,
  fontSizeLG: 16,
  fontSizeXL: 18,
  fontSizeHeading1: 24,
  lineHeight: 1.5,
  lineWidth: 1,
};

// === Shared component config ===
const sharedComponents = {
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
};

/**
 * Light theme configuration.
 * Clean, minimal design with high contrast and liquid glass feel.
 */
export const lightTheme: ThemeConfig = {
  algorithm: defaultAlgorithm,
  token: {
    ...sharedTokens,
    // Colors - Light mode (AC #4, #5)
    // Cooler, darker gray background for better contrast with white surfaces
    // Story 3-7: Enhanced contrast - fond plus grisé pour distinguer les cartes
    colorBgBase: '#e5eaef',
    colorBgContainer: '#FFFFFF',
    colorBgElevated: '#FFFFFF',
    colorBgLayout: '#e5eaef',
    colorText: '#1a1a2e',
    colorTextSecondary: '#5c5c6d',
    colorTextTertiary: '#8c8c9a',
    // Placeholder inputs/Select: gris lisible sur blanc (évite gris trop clair)
    colorTextPlaceholder: '#6b6b7a',
    colorBorder: '#e8eaed',
    colorBorderSecondary: '#f0f2f5',
    // Primary hover - darker for light mode
    colorPrimaryHover: '#006b3e',
    // Liquid glass shadows - soft, diffused, multi-layer with subtle highlight
    // Story 3-7: Enhanced shadow intensity for better depth perception
    boxShadow: '0 1px 3px rgba(0,0,0,0.08), 0 4px 12px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.8)',
    boxShadowSecondary: '0 2px 6px rgba(0,0,0,0.10), 0 8px 24px rgba(0,0,0,0.14), inset 0 1px 0 rgba(255,255,255,0.9)',
    boxShadowTertiary: '0 4px 10px rgba(0,0,0,0.12), 0 16px 40px rgba(0,0,0,0.18), inset 0 1px 0 rgba(255,255,255,1)',
  },
  components: {
    ...sharedComponents,
    Tabs: {
      ...sharedComponents.Tabs,
      itemColor: '#5c5c6d',
      itemHoverColor: '#1a1a2e',
    },
    Layout: {
      headerBg: '#FFFFFF',
      bodyBg: '#e5eaef',
      siderBg: '#FFFFFF',
    },
    Card: {
      ...sharedComponents.Card,
      colorBgContainer: '#FFFFFF',
    },
    Table: {
      headerBg: '#f0f3f6',
      rowHoverBg: '#f5f7f9',
    },
  },
};

/**
 * Dark theme configuration.
 * Same structure as light, only colors change.
 * Inspired by modern 2026 dark UI with liquid glass effects.
 * UX: Lighter base + elevated surfaces so cards/header are clearly distinct from background; brighter text for readability on all screens.
 */
export const darkTheme: ThemeConfig = {
  algorithm: darkAlgorithm,
  token: {
    ...sharedTokens,
    // Colors - Dark mode (AC #4, #5) — hierarchy: body < header/sider < cards
    colorBgBase: '#12121a',
    colorBgContainer: '#1e1e2a',
    colorBgElevated: '#262634',
    colorBgLayout: '#12121a',
    // Brighter text for readability (especially on low-contrast screens)
    colorText: '#f5f5f7',
    colorTextSecondary: '#b8b8c4',
    colorTextTertiary: '#9a9aa8',
    colorTextPlaceholder: '#9a9aa8',
    // More visible borders so cards and sections are clearly demarcated
    colorBorder: '#3a3a4c',
    colorBorderSecondary: '#2e2e3e',
    colorPrimaryHover: '#00b85e',
    boxShadow: '0 2px 4px rgba(0,0,0,0.3), 0 8px 16px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.04)',
    boxShadowSecondary: '0 4px 8px rgba(0,0,0,0.3), 0 12px 32px rgba(0,0,0,0.25), inset 0 1px 0 rgba(255,255,255,0.05)',
    boxShadowTertiary: '0 8px 16px rgba(0,0,0,0.35), 0 24px 48px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.06)',
  },
  components: {
    ...sharedComponents,
    Tabs: {
      ...sharedComponents.Tabs,
      itemColor: '#b8b8c4',
      itemHoverColor: '#f5f5f7',
    },
    Layout: {
      headerBg: '#1a1a28',
      bodyBg: '#12121a',
      siderBg: '#1a1a28',
    },
    Card: {
      ...sharedComponents.Card,
      colorBgContainer: '#1e1e2a',
      colorBorderSecondary: '#3a3a4c',
    },
    Table: {
      headerBg: '#1a1a28',
      rowHoverBg: '#252538',
      borderColor: '#3a3a4c',
    },
    Button: {
      ...sharedComponents.Button,
      defaultBg: '#262634',
      defaultBorderColor: '#3a3a4c',
    },
  },
};

/**
 * @deprecated Use lightTheme or darkTheme instead.
 * Kept for backwards compatibility during migration.
 */
export const desjardinsTheme = lightTheme;

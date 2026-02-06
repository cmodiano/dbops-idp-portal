/**
 * Style tokens for Story 2.5 components (architecture: avoid inline magic values).
 * Align with desjardins theme and UX spec.
 */

export const STYLE_TOKENS = {
  colorPrimary: '#00874E',
  cardMaxWidth: 320,
  cardBodyPadding: 16,
  drawerPreviewPadding: 24,
  drawerPreviewRadius: 8,
  drawerPreviewShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
  /** Engine icon size in ActionCard (px). */
  engineIconSize: 32,
  /** Engine icon colors (UX spec). */
  engineIconColor: {
    Oracle: '#EF4444',
    'SQL Server': '#3B82F6',
    DB2: '#10B981',
  } as const,
  /** Platform (execution) icon colors. */
  platformIconColor: {
    AAP: '#EE0000',
    'GitHub Actions': '#24292f',
    'Azure DevOps': '#0078D4',
    Terraform: '#7B42BC',
  } as const,
  /** Impact indicator colors (triple coding, UX spec). */
  impactColor: {
    low: '#10B981',
    medium: '#F59E0B',
    high: '#F97316',
    critical: '#EF4444',
  } as const,
  /**
   * Tag category palette (charte graphique).
   * Green/teal/blue family with distinct hue and lightness so tags are easy to tell apart.
   * Light mode: varied tints, dark text. Dark mode: darker tints, light text.
   */
  tagCategoryPaletteLight: [
    '#7bc490', // medium green
    '#5eb8b8', // teal
    '#8fba8f', // sage / yellow-green
    '#5ba8c4', // blue-teal
    '#9dd9b8', // light mint
    '#6ba88a', // green-teal
  ] as const,
  tagCategoryPaletteDark: [
    '#2d6b3d', // dark green
    '#2a5a5a', // dark teal
    '#3d6b3d', // dark sage
    '#2a5266', // dark blue-teal
    '#3d7a5a', // dark mint
    '#2e5c4a', // dark green-teal
  ] as const,
  /** Text on light tag backgrounds (light mode). */
  tagTextOnLight: '#1f2937',
  /** Text on dark tag backgrounds (dark mode). */
  tagTextOnDark: '#e5e7eb',
} as const;

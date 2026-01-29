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
  /** Impact indicator colors (triple coding, UX spec). */
  impactColor: {
    low: '#10B981',
    medium: '#F59E0B',
    high: '#F97316',
    critical: '#EF4444',
  } as const,
} as const;

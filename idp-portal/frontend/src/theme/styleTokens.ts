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
  /** Engine icon size in ActionCard (px) - larger for better visibility. */
  engineIconSize: 40,
  /** Workflow icon color (Story 18.2). */
  workflowColor: '#722ed1',
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
  /* Impact badge palette — Story 46.3 (Badges standardisation couleurs)
   * Progression chromatique : vert → jaune → orange → rouge
   * WCAG-friendly (texte teinté sur fond ~15% opacité via Ant Design <Tag color="#HEX">)
   * Écart de teinte (hue) entre niveaux adjacents : ~55° / ~21° / ~14° — tous perceptibles (seuil humain ~10°)
   */
  impactColor: {
    low:      '#10B981', // green-500  — Faible : aucun impact sur service            (hue ~160°)
    medium:   '#EAB308', // yellow-500 — Moyen  : impact possible sur perfs           (hue ~45°) — CHANGÉ #F59E0B (amber, trop proche de high)
    high:     '#F97316', // orange-500 — Élevé  : indisponibilité de service          (hue ~24°)
    critical: '#EF4444', // red-500    — Critique : indisponibilité + cas spéciaux   (hue ~0°)
  } as const,
  /* Environment badge palette — Story 46.3
   * Couleurs fixes par type d'environnement — sémantiquement distincts des badges d'impact
   * Note : production (#EF4444) et staging (#F97316) partagent intentionnellement les teintes
   * de critical/high pour renforcer la sémantique de gravité (production = critique).
   * Fallback sur gris pour environnements inconnus
   */
  environmentBadgeColor: {
    production:  '#EF4444', // red-500    — Production critique
    prod:        '#EF4444', // alias
    staging:     '#F97316', // orange-500 — Pré-production
    preprod:     '#F97316', // alias
    dev:         '#3B82F6', // blue-500   — Développement
    development: '#3B82F6', // alias
    test:        '#8B5CF6', // violet-500 — Environnement de test
    default:     '#6B7280', // gray-500   — Environnement inconnu
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
  /* Text contrast tokens — Story 46.4 (Accessibilité Contraste WCAG AA)
   * Toutes les couleurs ci-dessous sont calculées pour texte sur blanc (#FFFFFF) et fond clair (#FFFFFF).
   * Ratios vérifiés selon WCAG 2.1 §1.4.3 (texte normal ≥ 4.5:1) et §1.4.11 (non-texte ≥ 3:1).
   * NE PAS utiliser #52c41a ou #fa8c16 pour du texte visible — ils échouent (< 3:1).
   */
  textSuccess: '#166534', // green-800 Tailwind — ~6.8:1 sur blanc ✅ WCAG AA texte
  iconSuccess: '#16a34a', // green-600 Tailwind — ~3.15:1 sur blanc ✅ WCAG AA non-texte
  textWarning: '#92400e', // amber-800 Tailwind — ~7.2:1 sur blanc ✅ WCAG AA texte
  iconWarning: '#b45309', // amber-700 Tailwind — ~4.8:1 sur blanc ✅ WCAG AA texte+non-texte
  textError:   '#b91c1c', // red-700 Tailwind   — ~6.4:1 sur blanc ✅ WCAG AA texte
  iconError:   '#dc2626', // red-600 Tailwind   — ~4.7:1 sur blanc ✅ WCAG AA texte+non-texte (remplace #ff4d4f ~3.1:1)
  textMuted:   '#595959', // gray               — ~7.0:1 sur blanc ✅ WCAG AA texte (remplace #8c8c8c ~3.4:1)
} as const;

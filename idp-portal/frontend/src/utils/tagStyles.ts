/**
 * Shared tag styling: same category palette on catalog cards and filter TagCloud.
 * Charte graphique: single green/teal family, theme-aware text for contrast.
 * Hash by tag name so a given tag always gets the same color.
 */

import { STYLE_TOKENS } from '../theme/styleTokens';

export interface TagStyle {
  background: string;
  color: string;
  border?: string;
}

/**
 * Stable category color for a tag (by name hash). Theme-aware for light/dark mode.
 * @param tagName - Tag label (e.g. "oracle", "backup")
 * @param isDark - true when effective theme is dark (uses dark palette + light text)
 */
export function getTagStyle(tagName: string, isDark?: boolean): TagStyle {
  const palette = isDark
    ? STYLE_TOKENS.tagCategoryPaletteDark
    : STYLE_TOKENS.tagCategoryPaletteLight;
  const textColor = isDark ? STYLE_TOKENS.tagTextOnDark : STYLE_TOKENS.tagTextOnLight;
  let hash = 0;
  for (let i = 0; i < tagName.length; i++) hash = (hash << 5) - hash + tagName.charCodeAt(i);
  const idx = Math.abs(hash) % palette.length;
  return {
    background: palette[idx],
    color: textColor,
    border: 'none',
  };
}

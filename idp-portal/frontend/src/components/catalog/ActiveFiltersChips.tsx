/**
 * ActiveFiltersChips - Visual display of active filters with removal (Story 8.7, AC6).
 *
 * Features:
 * - Chips for category, tags, engines, impacts
 * - Individual removal via close button
 * - "Réinitialiser tous les filtres" button
 * - Desjardins green styling: Background #ECFDF5, text #00874E
 * - Story 18.4: Environment chips removed (environment = target property, not action)
 */

import { Space, Tag, Button } from 'antd';
import { CloseOutlined } from '@ant-design/icons';
import type { CategoryKey } from './CategoryTabs';
import { IMPACT_OPTIONS } from './HorizontalFilters';
import { useEngines } from '../../hooks/useEngines';
import { STYLE_TOKENS } from '../../theme/styleTokens';

export interface ActiveFiltersChipsProps {
  /** Active category (shown if not "tout"). */
  activeCategory: CategoryKey;
  /** Selected tags. */
  selectedTags: string[];
  /** Selected engines. */
  selectedEngines: string[];
  /** Selected impacts. */
  selectedImpacts: string[];
  /** Callback to reset category to "tout". */
  onRemoveCategory: () => void;
  /** Callback to remove a tag. */
  onRemoveTag: (tag: string) => void;
  /** Callback to remove an engine. */
  onRemoveEngine: (engine: string) => void;
  /** Callback to remove an impact. */
  onRemoveImpact: (impact: string) => void;
  /** Callback to clear all filters. */
  onClearAll: () => void;
}

/** Get display label for engine value. */
function getEngineLabel(value: string, engineOptions: { value: string; label: string }[]): string {
  return engineOptions.find((o) => o.value === value)?.label ?? value;
}

/** Get display label for impact value. */
function getImpactLabel(value: string): string {
  return IMPACT_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

/** Capitalize first letter. */
function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/**
 * Displays active filters as removable chips.
 * Returns null if no filters are active.
 */
export function ActiveFiltersChips({
  activeCategory,
  selectedTags,
  selectedEngines,
  selectedImpacts,
  onRemoveCategory,
  onRemoveTag,
  onRemoveEngine,
  onRemoveImpact,
  onClearAll,
}: ActiveFiltersChipsProps) {
  // Story 13.7: Load engines from REF_ENGINES table
  const { engineOptions } = useEngines();

  // Check if any filters are active (Story 8.7: exclude "mes-actions" from category filter)
  const hasFilters =
    (activeCategory !== 'tout' && activeCategory !== 'mes-actions') ||
    selectedTags.length > 0 ||
    selectedEngines.length > 0 ||
    selectedImpacts.length > 0;

  if (!hasFilters) {
    return null;
  }

  // Desjardins green styling for category chips
  const categoryChipStyle = {
    backgroundColor: '#ECFDF5',
    color: STYLE_TOKENS.colorPrimary,
    borderColor: STYLE_TOKENS.colorPrimary,
    minHeight: 44,
    display: 'inline-flex' as const,
    alignItems: 'center',
    padding: '10px 12px',
  };

  // Story 46.2 — zone tactile 44px pour tous les chips closables
  const chipStyle = {
    minHeight: 44,
    display: 'inline-flex' as const,
    alignItems: 'center',
    padding: '10px 12px',
  };

  // Story 46.2 — zone touchable élargie pour l'icône de suppression (≥ 44px : icône 16px + padding 14px × 2 = 44px)
  const closeIconStyle = { padding: 14, margin: -14 };

  return (
    <Space wrap style={{ marginBottom: 16 }} role="group" aria-label="Filtres actifs">
      {/* Category chip (only if not "tout" or "mes-actions") */}
      {activeCategory && activeCategory !== 'tout' && activeCategory !== 'mes-actions' && (
        <Tag
          closable
          onClose={onRemoveCategory}
          closeIcon={<span style={closeIconStyle} aria-label="Supprimer le filtre catégorie"><CloseOutlined aria-hidden="true" /></span>}
          style={categoryChipStyle}
        >
          Catégorie: {capitalize(activeCategory)}
        </Tag>
      )}

      {/* Tag chips */}
      {selectedTags.map((tag) => (
        <Tag
          key={`tag-${tag}`}
          closable
          onClose={() => onRemoveTag(tag)}
          color="blue"
          closeIcon={<span style={closeIconStyle} aria-label={`Supprimer le filtre tag ${tag}`}><CloseOutlined aria-hidden="true" /></span>}
          style={chipStyle}
        >
          Tag: {tag}
        </Tag>
      ))}

      {/* Engine chips */}
      {selectedEngines.map((engine) => (
        <Tag
          key={`engine-${engine}`}
          closable
          onClose={() => onRemoveEngine(engine)}
          closeIcon={<span style={closeIconStyle} aria-label={`Supprimer le filtre moteur ${engine}`}><CloseOutlined aria-hidden="true" /></span>}
          style={chipStyle}
        >
          Moteur: {getEngineLabel(engine, engineOptions)}
        </Tag>
      ))}

      {/* Impact chips */}
      {selectedImpacts.map((impact) => (
        <Tag
          key={`impact-${impact}`}
          closable
          onClose={() => onRemoveImpact(impact)}
          closeIcon={<span style={closeIconStyle} aria-label={`Supprimer le filtre impact ${impact}`}><CloseOutlined aria-hidden="true" /></span>}
          style={chipStyle}
        >
          Impact: {getImpactLabel(impact)}
        </Tag>
      ))}

      {/* Reset all button */}
      <Button type="link" size="middle" onClick={onClearAll}>
        Réinitialiser tous les filtres
      </Button>
    </Space>
  );
}

export default ActiveFiltersChips;

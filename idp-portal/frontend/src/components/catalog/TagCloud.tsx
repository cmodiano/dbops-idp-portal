/**
 * TagCloud - Clickable tag cloud for filtering catalog actions (Story 3.5).
 *
 * Features:
 * - Displays tags with action counts (AC1, AC12)
 * - Multi-select with AND logic (AC2, AC3)
 * - Toggle selection on click (AC4)
 * - Reset button when tags selected (AC5)
 * - Same pastel colors as catalog cards (AC6)
 * - Keyboard accessible (AC6)
 */

import { Tag, Button, Space } from 'antd';
import { CloseCircleOutlined } from '@ant-design/icons';
import type { CatalogTagWithCount } from '../../services/catalog_service';
import { useTheme } from '../../contexts/ThemeContext';
import { getTagStyle } from '../../utils/tagStyles';
import { STYLE_TOKENS } from '../../theme/styleTokens';

const { CheckableTag } = Tag;

export interface TagCloudProps {
  /** Available tags with counts. */
  tags: CatalogTagWithCount[];
  /** Currently selected tag names. */
  selectedTags: string[];
  /** Callback when selection changes. */
  onSelectionChange: (selectedTags: string[]) => void;
}

/**
 * Tag cloud component for visual multi-select filtering.
 * Each tag is clickable and toggles selection (AND logic for filtering).
 */
export function TagCloud({ tags, selectedTags, onSelectionChange }: TagCloudProps) {
  const { effectiveMode } = useTheme();
  const isDark = effectiveMode === 'dark';

  const handleTagToggle = (tagName: string, checked: boolean) => {
    if (checked) {
      onSelectionChange([...selectedTags, tagName]);
    } else {
      onSelectionChange(selectedTags.filter((t) => t !== tagName));
    }
  };

  const handleReset = () => {
    onSelectionChange([]);
  };

  const handleKeyDown = (tagName: string, event: React.KeyboardEvent) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      const isSelected = selectedTags.includes(tagName);
      handleTagToggle(tagName, !isSelected);
    }
  };

  if (tags.length === 0) {
    return null;
  }

  return (
    <Space
      wrap
      size={[8, 8]}
      style={{ marginBottom: 16 }}
      role="group"
      aria-label="Filtres par tags"
    >
      {tags.map((tag) => {
        const isSelected = selectedTags.includes(tag.name);
        const tagStyle = getTagStyle(tag.name, isDark);
        return (
          <CheckableTag
            key={tag.name}
            checked={isSelected}
            onChange={(checked) => handleTagToggle(tag.name, checked)}
            onKeyDown={(e) => handleKeyDown(tag.name, e)}
            tabIndex={0}
            style={{
              cursor: 'pointer',
              padding: '4px 12px',
              borderRadius: 16,
              fontSize: 13,
              ...tagStyle,
              border: isSelected ? `2px solid ${STYLE_TOKENS.colorPrimary}` : tagStyle.border,
            }}
          >
            {tag.name} ({tag.action_count})
          </CheckableTag>
        );
      })}
      {selectedTags.length > 0 && (
        <Button
          type="link"
          size="small"
          icon={<CloseCircleOutlined />}
          onClick={handleReset}
          aria-label="Réinitialiser les filtres par tags"
        >
          Réinitialiser
        </Button>
      )}
    </Space>
  );
}

export default TagCloud;

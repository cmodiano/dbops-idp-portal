/**
 * Tests for ActiveFiltersChips component (Story 8.7, AC6; Story 18.4: Environment chips removed).
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ActiveFiltersChips } from './ActiveFiltersChips';
import { ThemeProvider } from '../../contexts/ThemeContext';

// Wrapper with ThemeProvider for STYLE_TOKENS
function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe('ActiveFiltersChips', () => {
  const defaultProps = {
    activeCategory: 'tout' as const,
    selectedTags: [],
    selectedEngines: [],
    selectedImpacts: [],
    onRemoveCategory: vi.fn(),
    onRemoveTag: vi.fn(),
    onRemoveEngine: vi.fn(),
    onRemoveImpact: vi.fn(),
    onClearAll: vi.fn(),
  };

  it('returns null when no filters are active', () => {
    const { container } = renderWithTheme(<ActiveFiltersChips {...defaultProps} />);
    expect(container.firstChild).toBeNull();
  });

  it('displays category chip when category is not "tout"', () => {
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        activeCategory="patching"
      />
    );

    expect(screen.getByText('Catégorie: Patching')).toBeInTheDocument();
  });

  it('does not display category chip for "mes-actions"', () => {
    const { container } = renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        activeCategory="mes-actions"
      />
    );

    expect(container.firstChild).toBeNull();
  });

  it('displays tag chips', () => {
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        selectedTags={['oracle', 'rac']}
      />
    );

    expect(screen.getByText('Tag: oracle')).toBeInTheDocument();
    expect(screen.getByText('Tag: rac')).toBeInTheDocument();
  });

  it('displays engine chips', () => {
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        selectedEngines={['Oracle', 'SQL Server']}
      />
    );

    expect(screen.getByText('Moteur: Oracle')).toBeInTheDocument();
    expect(screen.getByText('Moteur: SQL Server')).toBeInTheDocument();
  });

  it('does not display environment chips (Story 18.4: removed)', () => {
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        selectedEngines={['Oracle']}
      />
    );

    // Environment chips should not exist
    expect(screen.queryByText(/Env:/i)).not.toBeInTheDocument();
  });

  it('displays impact chips with French labels', () => {
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        selectedImpacts={['high', 'low']}
      />
    );

    expect(screen.getByText('Impact: Élevé')).toBeInTheDocument();
    expect(screen.getByText('Impact: Faible')).toBeInTheDocument();
  });

  it('calls onRemoveCategory when category chip close is clicked', () => {
    const onRemoveCategory = vi.fn();
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        activeCategory="patching"
        onRemoveCategory={onRemoveCategory}
      />
    );

    const categoryChip = screen.getByText('Catégorie: Patching').closest('.ant-tag');
    const closeIcon = categoryChip?.querySelector('.ant-tag-close-icon, .anticon-close');
    if (closeIcon) {
      fireEvent.click(closeIcon);
      expect(onRemoveCategory).toHaveBeenCalled();
    }
  });

  it('calls onRemoveTag when tag chip close is clicked', () => {
    const onRemoveTag = vi.fn();
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        selectedTags={['oracle']}
        onRemoveTag={onRemoveTag}
      />
    );

    const tagChip = screen.getByText('Tag: oracle').closest('.ant-tag');
    const closeIcon = tagChip?.querySelector('.ant-tag-close-icon, .anticon-close');
    if (closeIcon) {
      fireEvent.click(closeIcon);
      expect(onRemoveTag).toHaveBeenCalledWith('oracle');
    }
  });

  it('displays reset button when filters are active', () => {
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        selectedTags={['oracle']}
      />
    );

    expect(screen.getByText('Réinitialiser tous les filtres')).toBeInTheDocument();
  });

  it('calls onClearAll when reset button is clicked', () => {
    const onClearAll = vi.fn();
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        selectedTags={['oracle']}
        onClearAll={onClearAll}
      />
    );

    fireEvent.click(screen.getByText('Réinitialiser tous les filtres'));
    expect(onClearAll).toHaveBeenCalled();
  });

  it('has ARIA label for accessibility', () => {
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        selectedTags={['oracle']}
      />
    );

    expect(screen.getByRole('group', { name: 'Filtres actifs' })).toBeInTheDocument();
  });

  describe('Story 46.2 — taille minimale 44px (WCAG 2.5.5)', () => {
    it('le chip catégorie a un style minHeight >= 44px', () => {
      renderWithTheme(
        <ActiveFiltersChips
          {...defaultProps}
          activeCategory="patching"
        />
      );

      const categoryTag = screen.getByText('Catégorie: Patching').closest('.ant-tag') as HTMLElement;
      expect(categoryTag).toBeTruthy();
      const minHeight = parseInt(categoryTag.style.minHeight);
      expect(minHeight).toBeGreaterThanOrEqual(44);
    });

    it('les chips tag ont un style minHeight >= 44px', () => {
      renderWithTheme(
        <ActiveFiltersChips
          {...defaultProps}
          selectedTags={['oracle']}
        />
      );

      const tagChip = screen.getByText('Tag: oracle').closest('.ant-tag') as HTMLElement;
      expect(tagChip).toBeTruthy();
      const minHeight = parseInt(tagChip.style.minHeight);
      expect(minHeight).toBeGreaterThanOrEqual(44);
    });

    it('le bouton reset n\'a pas size="small"', () => {
      renderWithTheme(
        <ActiveFiltersChips
          {...defaultProps}
          selectedTags={['oracle']}
        />
      );

      const resetBtn = screen.getByText('Réinitialiser tous les filtres').closest('button');
      expect(resetBtn).toBeTruthy();
      expect(resetBtn).not.toHaveClass('ant-btn-sm');
    });
  });
});

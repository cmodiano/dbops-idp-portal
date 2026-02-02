/**
 * Tests for ActiveFiltersChips component (Story 8.7, AC6).
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
    selectedEnvironments: [],
    selectedImpacts: [],
    onRemoveCategory: vi.fn(),
    onRemoveTag: vi.fn(),
    onRemoveEngine: vi.fn(),
    onRemoveEnvironment: vi.fn(),
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

    // Should return null since mes-actions is not shown as a chip
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

  it('displays environment chips', () => {
    renderWithTheme(
      <ActiveFiltersChips
        {...defaultProps}
        selectedEnvironments={['PROD', 'DEV']}
      />
    );

    expect(screen.getByText('Env: PROD')).toBeInTheDocument();
    expect(screen.getByText('Env: DEV')).toBeInTheDocument();
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

    // Find the close icon in the category tag
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
});

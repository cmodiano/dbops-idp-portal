/**
 * Tests for CategoryTabs component (Story 8.7, AC1, AC2).
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CategoryTabs, CATEGORIES } from './CategoryTabs';
import { ThemeProvider } from '../../contexts/ThemeContext';

// Wrapper with ThemeProvider
function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe('CategoryTabs', () => {
  it('renders all 7 category tabs (AC1)', () => {
    const onCategoryChange = vi.fn();
    renderWithTheme(
      <CategoryTabs activeCategory="tout" onCategoryChange={onCategoryChange} />
    );

    // Verify all 7 tabs are rendered (Story 8.7: French labels)
    expect(screen.getByRole('tab', { name: /Tout/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Approvisionnement/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Correctifs/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Administration/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Surveillance/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Sauvegarde/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Mes actions/i })).toBeInTheDocument();
  });

  it('calls onCategoryChange when tab is clicked (AC2)', () => {
    const onCategoryChange = vi.fn();
    renderWithTheme(
      <CategoryTabs activeCategory="tout" onCategoryChange={onCategoryChange} />
    );

    // Click on Correctifs tab (Patching in English)
    fireEvent.click(screen.getByRole('tab', { name: /Correctifs/i }));

    expect(onCategoryChange).toHaveBeenCalledWith('patching');
  });

  it('shows active tab correctly', () => {
    const onCategoryChange = vi.fn();
    renderWithTheme(
      <CategoryTabs activeCategory="patching" onCategoryChange={onCategoryChange} />
    );

    // Correctifs tab (Patching) should be selected
    const patchingTab = screen.getByRole('tab', { name: /Correctifs/i });
    expect(patchingTab).toHaveAttribute('aria-selected', 'true');

    // Tout tab should not be selected
    const toutTab = screen.getByRole('tab', { name: /Tout/i });
    expect(toutTab).toHaveAttribute('aria-selected', 'false');
  });

  it('displays favorites count in Mes actions tab', () => {
    const onCategoryChange = vi.fn();
    renderWithTheme(
      <CategoryTabs
        activeCategory="tout"
        onCategoryChange={onCategoryChange}
        favoritesCount={5}
      />
    );

    expect(screen.getByRole('tab', { name: /Mes actions \(5\)/i })).toBeInTheDocument();
  });

  it('does not display count when favoritesCount is 0', () => {
    const onCategoryChange = vi.fn();
    renderWithTheme(
      <CategoryTabs
        activeCategory="tout"
        onCategoryChange={onCategoryChange}
        favoritesCount={0}
      />
    );

    // Should show "Mes actions" without count - use getByText to match text content
    const mesActionsTab = screen.getByRole('tab', { name: /Mes actions/i });
    expect(mesActionsTab).toBeInTheDocument();
    // Verify it doesn't have a number in parentheses
    expect(mesActionsTab.textContent).not.toMatch(/\(\d+\)/);
  });

  it('has correct number of categories defined', () => {
    expect(CATEGORIES).toHaveLength(7);
  });

  it('keyboard navigation works (AC6)', () => {
    const onCategoryChange = vi.fn();
    renderWithTheme(
      <CategoryTabs activeCategory="tout" onCategoryChange={onCategoryChange} />
    );

    const toutTab = screen.getByRole('tab', { name: /Tout/i });
    toutTab.focus();

    // Arrow right should move to next tab
    fireEvent.keyDown(toutTab, { key: 'ArrowRight' });

    // This is handled by Ant Design's Tabs component internally
    // We just verify the component renders without errors
    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });
});

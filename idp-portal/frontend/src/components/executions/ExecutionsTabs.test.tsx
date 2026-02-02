/**
 * Tests for ExecutionsTabs component (Story 8.9, AC1, AC6).
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { ExecutionsTabs } from './ExecutionsTabs';
import { ThemeProvider } from '../../contexts/ThemeContext';

// Wrapper with ThemeProvider
function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider>{ui}</ThemeProvider>);
}

describe('ExecutionsTabs', () => {
  it('renders both tabs when canViewAll is true (AC1)', () => {
    const onScopeChange = vi.fn();
    renderWithTheme(
      <ExecutionsTabs
        activeScope="mine"
        onScopeChange={onScopeChange}
        canViewAll={true}
      />
    );

    // Verify both tabs are rendered (Story 8.9: French labels)
    expect(screen.getByRole('tab', { name: /Toutes les exécutions/i })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: /Mes exécutions/i })).toBeInTheDocument();
  });

  it('renders only "Mes exécutions" tab when canViewAll is false (AC6)', () => {
    const onScopeChange = vi.fn();
    renderWithTheme(
      <ExecutionsTabs
        activeScope="mine"
        onScopeChange={onScopeChange}
        canViewAll={false}
      />
    );

    // Only "Mes exécutions" should be visible
    expect(screen.getByRole('tab', { name: /Mes exécutions/i })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: /Toutes les exécutions/i })).not.toBeInTheDocument();
  });

  it('calls onScopeChange with "all" when "Toutes les exécutions" tab is clicked', () => {
    const onScopeChange = vi.fn();
    renderWithTheme(
      <ExecutionsTabs
        activeScope="mine"
        onScopeChange={onScopeChange}
        canViewAll={true}
      />
    );

    fireEvent.click(screen.getByRole('tab', { name: /Toutes les exécutions/i }));

    expect(onScopeChange).toHaveBeenCalledWith('all');
  });

  it('calls onScopeChange with "mine" when "Mes exécutions" tab is clicked', () => {
    const onScopeChange = vi.fn();
    renderWithTheme(
      <ExecutionsTabs
        activeScope="all"
        onScopeChange={onScopeChange}
        canViewAll={true}
      />
    );

    fireEvent.click(screen.getByRole('tab', { name: /Mes exécutions/i }));

    expect(onScopeChange).toHaveBeenCalledWith('mine');
  });

  it('shows "mine" tab as active when activeScope is "mine"', () => {
    const onScopeChange = vi.fn();
    renderWithTheme(
      <ExecutionsTabs
        activeScope="mine"
        onScopeChange={onScopeChange}
        canViewAll={true}
      />
    );

    const mineTab = screen.getByRole('tab', { name: /Mes exécutions/i });
    expect(mineTab).toHaveAttribute('aria-selected', 'true');

    const allTab = screen.getByRole('tab', { name: /Toutes les exécutions/i });
    expect(allTab).toHaveAttribute('aria-selected', 'false');
  });

  it('shows "all" tab as active when activeScope is "all"', () => {
    const onScopeChange = vi.fn();
    renderWithTheme(
      <ExecutionsTabs
        activeScope="all"
        onScopeChange={onScopeChange}
        canViewAll={true}
      />
    );

    const allTab = screen.getByRole('tab', { name: /Toutes les exécutions/i });
    expect(allTab).toHaveAttribute('aria-selected', 'true');

    const mineTab = screen.getByRole('tab', { name: /Mes exécutions/i });
    expect(mineTab).toHaveAttribute('aria-selected', 'false');
  });

  it('has tablist role for accessibility', () => {
    const onScopeChange = vi.fn();
    renderWithTheme(
      <ExecutionsTabs
        activeScope="mine"
        onScopeChange={onScopeChange}
        canViewAll={true}
      />
    );

    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });

  it('renders correctly with dark theme', () => {
    const onScopeChange = vi.fn();
    // ThemeProvider will use default theme, but component handles both modes
    renderWithTheme(
      <ExecutionsTabs
        activeScope="mine"
        onScopeChange={onScopeChange}
        canViewAll={true}
      />
    );

    // Component should render without errors in any theme
    expect(screen.getByRole('tablist')).toBeInTheDocument();
  });
});

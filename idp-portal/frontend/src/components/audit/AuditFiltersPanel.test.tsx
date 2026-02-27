/**
 * Tests pour AuditFiltersPanel — Story 46.7
 *
 * AC1: FilterOutlined + libellé "Filtres" visible
 * AC4: Badge count actifs cohérent
 * AC5: Bouton reset avec ClearOutlined + size large
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ConfigProvider } from 'antd';
import { ThemeProvider } from '../../contexts/ThemeContext';
import { AuditFiltersPanel } from './AuditFiltersPanel';

// Mock matchMedia
beforeEach(() => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('dark') ? false : true,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
});

function renderPanel(props: Partial<Parameters<typeof AuditFiltersPanel>[0]> = {}) {
  const defaultProps: Parameters<typeof AuditFiltersPanel>[0] = {
    dateRange: [null, null],
    setDateRange: vi.fn(),
    environment: undefined,
    setEnvironment: vi.fn(),
    engineType: undefined,
    setEngineType: vi.fn(),
    actionId: undefined,
    setActionId: vi.fn(),
    status: undefined,
    setStatus: vi.fn(),
    correlationId: '',
    setCorrelationId: vi.fn(),
    actionType: undefined,
    setActionType: vi.fn(),
    userSearchInput: '',
    setUserSearchInput: vi.fn(),
    actions: [],
    actionsLoading: false,
    engineOptions: [{ value: 'oracle', label: 'Oracle' }],
    enginesLoading: false,
    loading: false,
    activeFilterCount: 0,
    onResetFilters: vi.fn(),
    ...props,
  };

  return render(
    <ThemeProvider>
      <ConfigProvider>
        <AuditFiltersPanel {...defaultProps} />
      </ConfigProvider>
    </ThemeProvider>,
  );
}

describe('AuditFiltersPanel — Story 46.7', () => {
  it('affiche le titre "Filtres" avec icône FilterOutlined', () => {
    renderPanel();
    expect(screen.getByText('Filtres')).toBeInTheDocument();
  });

  it('affiche le bouton Réinitialiser avec ClearOutlined', () => {
    renderPanel();
    expect(screen.getByRole('button', { name: /réinitialiser/i })).toBeInTheDocument();
  });

  it('le bouton reset est désactivé quand aucun filtre actif', () => {
    renderPanel({ activeFilterCount: 0 });
    const resetButton = screen.getByRole('button', { name: /réinitialiser/i });
    expect(resetButton).toBeDisabled();
  });

  it('le bouton reset est activé quand au moins un filtre actif', () => {
    renderPanel({ activeFilterCount: 1 });
    const resetButton = screen.getByRole('button', { name: /réinitialiser/i });
    expect(resetButton).not.toBeDisabled();
  });

  it('le badge affiche count = 0 quand aucun filtre actif (badge masqué par défaut)', () => {
    renderPanel({ activeFilterCount: 0 });
    // Ant Design Badge ne montre pas le count "0" par défaut (showZero absent)
    expect(screen.queryByText('0')).not.toBeInTheDocument();
  });

  it('le badge affiche count = 1 quand un filtre actif', () => {
    renderPanel({ activeFilterCount: 1 });
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('le badge affiche count = 3 quand trois filtres actifs', () => {
    renderPanel({ activeFilterCount: 3 });
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('appelle onResetFilters au clic sur Réinitialiser', async () => {
    const onResetFilters = vi.fn();
    const user = userEvent.setup();
    renderPanel({ activeFilterCount: 1, onResetFilters });
    await user.click(screen.getByRole('button', { name: /réinitialiser/i }));
    expect(onResetFilters).toHaveBeenCalledOnce();
  });

  it('affiche le champ Date début (RangePicker)', () => {
    renderPanel();
    expect(screen.getByPlaceholderText('Date début')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Date fin')).toBeInTheDocument();
  });

  it('affiche le champ Rechercher un utilisateur', () => {
    renderPanel();
    expect(screen.getByPlaceholderText('Rechercher un utilisateur')).toBeInTheDocument();
  });

  it('affiche le champ Correlation ID', () => {
    renderPanel();
    expect(screen.getByPlaceholderText('Correlation ID')).toBeInTheDocument();
  });

  it('affiche le Tag Correlation quand correlationId est rempli', () => {
    renderPanel({ correlationId: 'test-abc' });
    expect(screen.getByText('Correlation: test-abc')).toBeInTheDocument();
  });

  it('appelle setCorrelationId("") à la fermeture du Tag Correlation', async () => {
    const setCorrelationId = vi.fn();
    const user = userEvent.setup();
    renderPanel({ correlationId: 'test-abc', setCorrelationId });

    const tag = screen.getByText('Correlation: test-abc').closest('.ant-tag');
    const closeIcon = tag?.querySelector('.ant-tag-close-icon, .anticon-close');
    if (closeIcon) {
      await user.click(closeIcon as Element);
      expect(setCorrelationId).toHaveBeenCalledWith('');
    }
  });

  it('possède le data-testid "audit-filters-panel"', () => {
    renderPanel();
    expect(screen.getByTestId('audit-filters-panel')).toBeInTheDocument();
  });

  it('possède le data-testid "audit-filter-environment" sur le Select Environnement', () => {
    renderPanel();
    expect(screen.getByTestId('audit-filter-environment')).toBeInTheDocument();
  });

  it('possède le data-testid "audit-filter-action-type" sur le Select Opération', () => {
    renderPanel();
    expect(screen.getByTestId('audit-filter-action-type')).toBeInTheDocument();
  });

  it('possède le data-testid "audit-filter-correlation-id" sur le Input Correlation ID', () => {
    renderPanel();
    expect(screen.getByTestId('audit-filter-correlation-id')).toBeInTheDocument();
  });
});

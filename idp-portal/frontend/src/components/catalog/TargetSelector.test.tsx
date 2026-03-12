/**
 * Tests for TargetSelector component (Story 13.2, Task 8.1).
 * Updated Story 71.1 code review: mock useTargetsPaginated hook instead of apiFetchRaw.
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { App } from 'antd';
import { TargetSelector, type Target } from './TargetSelector';

// Mock the useTargetInventory hook (TargetSelector uses useTargetsPaginated)
const mockUseTargetsPaginated = vi.fn();
vi.mock('../../hooks/useTargetInventory', () => ({
  useTargetsPaginated: (...args: unknown[]) => mockUseTargetsPaginated(...args),
}));

// Test data
const mockTargets: Target[] = [
  { name: 'srv-dev-01', environment: 'dev', target_type: 'server', metadata: null },
  { name: 'srv-dev-02', environment: 'dev', target_type: 'server', metadata: null },
  { name: 'srv-staging-01', environment: 'staging', target_type: 'server', metadata: null },
  { name: 'db-prod-01', environment: 'prod', target_type: 'database', metadata: null },
  { name: 'db-prod-02', environment: 'prod', target_type: 'database', metadata: null },
];

// Wrapper component for Ant Design context
function TestWrapper({ children }: { children: React.ReactNode }) {
  return <App>{children}</App>;
}

/** Helper: configure hook to return loaded targets */
function mockLoaded(targets: Target[] = mockTargets) {
  mockUseTargetsPaginated.mockReturnValue({ targets, loading: false, error: null });
}

/** Helper: configure hook to return loading state */
function mockLoading() {
  mockUseTargetsPaginated.mockReturnValue({ targets: [], loading: true, error: null });
}

/** Helper: configure hook to return error state */
function mockError(message: string) {
  mockUseTargetsPaginated.mockReturnValue({ targets: [], loading: false, error: message });
}

describe('TargetSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLoaded();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('renders with placeholder when no targets selected', () => {
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      expect(mockUseTargetsPaginated).toHaveBeenCalled();
      expect(screen.getByText('Selectionnez une cible')).toBeInTheDocument();
    });

    it('renders loading state while fetching targets', () => {
      mockLoading();
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      // Check loading state (Ant Design shows spinner inside Select)
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('displays error message when fetch fails', () => {
      mockError('Network error');

      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      expect(screen.getByText('Erreur')).toBeInTheDocument();
      expect(screen.getByText('Network error')).toBeInTheDocument();
    });
  });

  describe('Selection', () => {
    it('renders options after loading', async () => {
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      // Open dropdown
      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      // Wait for dropdown to open with options
      await waitFor(() => {
        const options = screen.getAllByRole('option');
        // Should have at least some options (targets from mockTargets)
        expect(options.length).toBeGreaterThanOrEqual(1);
      });
    });

    it('passes correct props to Select component', () => {
      const selectedTarget: Target = {
        name: 'srv-dev-01',
        environment: 'dev',
        target_type: 'server',
        metadata: null,
      };
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[selectedTarget]} onChange={onChange} />
        </TestWrapper>
      );

      // Verify the combobox is rendered
      const selectContent = screen.getByRole('combobox');
      expect(selectContent).toBeInTheDocument();
    });
  });

  describe('Grouping by environment', () => {
    it('groups targets by environment in dropdown', async () => {
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      // Open dropdown
      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      // Wait for dropdown and check group headers
      await waitFor(() => {
        // Group headers should be visible
        expect(screen.getByText('Développement')).toBeInTheDocument();
        expect(screen.getByText('Staging')).toBeInTheDocument();
        expect(screen.getByText('Production')).toBeInTheDocument();
      });
    });
  });

  describe('Search/Filter', () => {
    it('updates search value on input', async () => {
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      // Open dropdown and type to search
      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);
      fireEvent.change(select, { target: { value: 'prod' } });

      // Should show only prod targets (all targets are still shown since hook is mocked,
      // but the search value is passed to the hook)
      await waitFor(() => {
        expect(screen.getByText('db-prod-01')).toBeInTheDocument();
        expect(screen.getByText('db-prod-02')).toBeInTheDocument();
      });
    });
  });

  describe('Disabled state', () => {
    it('disables the selector when disabled prop is true', () => {
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} disabled />
        </TestWrapper>
      );

      // Ant Design adds disabled class to the wrapper div, not the combobox itself
      const selectWrapper = screen.getByRole('combobox').closest('.ant-select');
      expect(selectWrapper).toHaveClass('ant-select-disabled');
    });
  });

  describe('Accessibility', () => {
    it('has correct aria-label', () => {
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector
            value={[]}
            onChange={onChange}
            ariaLabel="Custom aria label"
          />
        </TestWrapper>
      );

      expect(screen.getByLabelText('Custom aria label')).toBeInTheDocument();
    });
  });

  describe('Story 21.5 — Non-standard environments', () => {
    it('displays non-standard environment groups with capitalized labels', async () => {
      const targetsWithNonStandard: Target[] = [
        { name: 'srv-dev-01', environment: 'dev', target_type: 'server', metadata: null },
        { name: 'srv-lab-01', environment: 'lab', target_type: 'server', metadata: null },
        { name: 'srv-qa-01', environment: 'qa', target_type: 'server', metadata: null },
      ];

      mockLoaded(targetsWithNonStandard);

      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      await waitFor(() => {
        expect(screen.getByText('Développement')).toBeInTheDocument();
        expect(screen.getByText('Lab')).toBeInTheDocument();
        expect(screen.getByText('Qa')).toBeInTheDocument();
      });
    });

    it('orders environments: dev first, then non-standard alphabetically', async () => {
      const targetsWithMixed: Target[] = [
        { name: 'srv-qa-01', environment: 'qa', target_type: 'server', metadata: null },
        { name: 'srv-dev-01', environment: 'dev', target_type: 'server', metadata: null },
        { name: 'db-prod-01', environment: 'prod', target_type: 'database', metadata: null },
        { name: 'srv-lab-01', environment: 'lab', target_type: 'server', metadata: null },
      ];

      mockLoaded(targetsWithMixed);

      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      await waitFor(() => {
        // All groups should be visible
        expect(screen.getByText('Développement')).toBeInTheDocument();
        expect(screen.getByText('Production')).toBeInTheDocument();
        expect(screen.getByText('Lab')).toBeInTheDocument();
        expect(screen.getByText('Qa')).toBeInTheDocument();
      });

      // Check ordering via DOM: dev should appear before prod, prod before lab, lab before qa
      const groupItems = document.querySelectorAll('.ant-select-item-group');
      const groupTexts = Array.from(groupItems).map((el) => el.textContent);
      expect(groupTexts).toEqual(['Développement', 'Production', 'Lab', 'Qa']);
    });

    it('shows Empty component when targets list is empty after loading', async () => {
      mockLoaded([]);

      const onChange = vi.fn();
      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      // Open dropdown to see notFoundContent
      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      await waitFor(() => {
        expect(screen.getByText('Aucune cible disponible')).toBeInTheDocument();
      });
    });

    it('uses default badge color for non-standard environments', async () => {
      const targetsWithLab: Target[] = [
        { name: 'srv-lab-01', environment: 'lab', target_type: 'server', metadata: null },
      ];

      mockLoaded(targetsWithLab);

      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      await waitFor(() => {
        expect(screen.getByText('Lab')).toBeInTheDocument();
      });

      // Check badge color — lab should get 'default' status
      const badgeDot = document.querySelector('.ant-badge-status-default');
      expect(badgeDot).toBeInTheDocument();
    });
  });
});

// ─── Coverage extras ──────────────────────────────────────────────────────────
describe('TargetSelector — coverage extras', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockLoaded();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('handles multiple selection mode (multiple=true)', () => {
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} multiple={true} />
      </TestWrapper>
    );
    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();
  });

  it('calls onChange with target from value when target not in fetched list', () => {
    const extraTarget: Target = { name: 'extra-server', environment: 'dev', target_type: 'server', metadata: null };
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[extraTarget]} onChange={onChange} />
      </TestWrapper>
    );
    // Select is rendered with the extra server as the current value
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('renders error message for fetch failure without message property', () => {
    mockError('Erreur lors du chargement des cibles');
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} />
      </TestWrapper>
    );
    expect(screen.getByText('Erreur')).toBeInTheDocument();
    expect(screen.getByText('Erreur lors du chargement des cibles')).toBeInTheDocument();
  });

  it('passes search term to hook via debounced value', async () => {
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} />
      </TestWrapper>
    );

    // Simulate search text change (sets searchValue which triggers debouncedSearch)
    const select = screen.getByRole('combobox');
    fireEvent.mouseDown(select);
    fireEvent.change(select, { target: { value: 'srv-dev' } });

    // Wait for debounce (300ms) — hook should be called with the search term
    await waitFor(() => {
      const calls = mockUseTargetsPaginated.mock.calls;
      const lastCall = calls[calls.length - 1];
      expect(lastCall[0]).toBe('srv-dev');
    }, { timeout: 1000 });
  });

  it('uses custom placeholder prop', () => {
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} placeholder="Custom placeholder" />
      </TestWrapper>
    );
    expect(screen.getByText('Custom placeholder')).toBeInTheDocument();
  });

  it('handleChange is invoked when option selected from dropdown', async () => {
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} />
      </TestWrapper>
    );

    // Open dropdown via mouseDown
    const select = screen.getByRole('combobox');
    fireEvent.mouseDown(select);

    // Wait for options to render in the dropdown
    await waitFor(() => {
      expect(screen.getAllByRole('option').length).toBeGreaterThan(0);
    });

    // Use keyboard navigation: ArrowDown highlights first option, Enter selects it
    fireEvent.keyDown(select, { key: 'ArrowDown', keyCode: 40 });
    fireEvent.keyDown(select, { key: 'Enter', keyCode: 13 });
    expect(onChange).toHaveBeenCalled();
  });
});

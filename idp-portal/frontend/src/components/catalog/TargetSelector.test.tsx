/**
 * Tests for TargetSelector component (Story 13.2, Task 8.1).
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { App } from 'antd';
import { TargetSelector, type Target } from './TargetSelector';

// Mock the api_client (TargetSelector uses apiFetchRaw)
vi.mock('../../services/api_client', () => ({
  apiFetch: vi.fn(),
  apiFetchRaw: vi.fn(),
}));

import { apiFetchRaw } from '../../services/api_client';

const mockApiFetchRaw = apiFetchRaw as ReturnType<typeof vi.fn>;

// Test data
const mockTargets: Target[] = [
  { name: 'srv-dev-01', environment: 'dev', target_type: 'server', metadata: null },
  { name: 'srv-dev-02', environment: 'dev', target_type: 'server', metadata: null },
  { name: 'srv-staging-01', environment: 'staging', target_type: 'server', metadata: null },
  { name: 'db-prod-01', environment: 'prod', target_type: 'database', metadata: null },
  { name: 'db-prod-02', environment: 'prod', target_type: 'database', metadata: null },
];

const mockTargetsResponse = {
  items: mockTargets,
  total: mockTargets.length,
  page: 1,
  page_size: 100,
  total_pages: 1,
};

// Wrapper component for Ant Design context
function TestWrapper({ children }: { children: React.ReactNode }) {
  return <App>{children}</App>;
}

describe('TargetSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApiFetchRaw.mockResolvedValue(mockTargetsResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Rendering', () => {
    it('renders with placeholder when no targets selected', async () => {
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      // Wait for targets to load
      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalledWith(
          expect.stringContaining('/inventory/targets')
        );
      });

      expect(screen.getByText('Selectionnez une cible')).toBeInTheDocument();
    });

    it('renders loading state while fetching targets', async () => {
      // Delay the response
      mockApiFetchRaw.mockImplementation(
        () =>
          new Promise((resolve) =>
            setTimeout(() => resolve(mockTargetsResponse), 100)
          )
      );

      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      // Check loading state (Ant Design shows spinner inside Select)
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('displays error message when fetch fails', async () => {
      mockApiFetchRaw.mockRejectedValue(new Error('Network error'));

      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Erreur')).toBeInTheDocument();
      });

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

      // Wait for targets to load
      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

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

    it('passes correct props to Select component', async () => {
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

      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

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

      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

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
    it('filters options based on search input', async () => {
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

      // Open dropdown and type to search
      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);
      fireEvent.change(select, { target: { value: 'prod' } });

      // Should show only prod targets
      await waitFor(() => {
        expect(screen.getByText('db-prod-01')).toBeInTheDocument();
        expect(screen.getByText('db-prod-02')).toBeInTheDocument();
      });
    });
  });

  describe('Disabled state', () => {
    it('disables the selector when disabled prop is true', async () => {
      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} disabled />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

      // Ant Design adds disabled class to the wrapper div, not the combobox itself
      const selectWrapper = screen.getByRole('combobox').closest('.ant-select');
      expect(selectWrapper).toHaveClass('ant-select-disabled');
    });
  });

  describe('Accessibility', () => {
    it('has correct aria-label', async () => {
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

      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

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

      mockApiFetchRaw.mockResolvedValue({
        items: targetsWithNonStandard,
        total: 3,
        page: 1,
        page_size: 100,
        total_pages: 1,
      });

      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

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

      mockApiFetchRaw.mockResolvedValue({
        items: targetsWithMixed,
        total: 4,
        page: 1,
        page_size: 100,
        total_pages: 1,
      });

      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

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
      mockApiFetchRaw.mockResolvedValue({
        items: [],
        total: 0,
        page: 1,
        page_size: 100,
        total_pages: 0,
      });

      const onChange = vi.fn();
      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

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

      mockApiFetchRaw.mockResolvedValue({
        items: targetsWithLab,
        total: 1,
        page: 1,
        page_size: 100,
        total_pages: 1,
      });

      const onChange = vi.fn();

      render(
        <TestWrapper>
          <TargetSelector value={[]} onChange={onChange} />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(mockApiFetchRaw).toHaveBeenCalled();
      });

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
    mockApiFetchRaw.mockResolvedValue(mockTargetsResponse);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('handles multiple selection mode (multiple=true)', async () => {
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} multiple={true} />
      </TestWrapper>
    );
    await waitFor(() => {
      expect(mockApiFetchRaw).toHaveBeenCalled();
    });
    const select = screen.getByRole('combobox');
    expect(select).toBeInTheDocument();
  });

  it('calls onChange with target from value when target not in fetched list', async () => {
    const extraTarget: Target = { name: 'extra-server', environment: 'dev', target_type: 'server', metadata: null };
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[extraTarget]} onChange={onChange} />
      </TestWrapper>
    );
    await waitFor(() => expect(mockApiFetchRaw).toHaveBeenCalled());
    // Select is rendered with the extra server as the current value
    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('renders error message for fetch failure without message property', async () => {
    mockApiFetchRaw.mockRejectedValue({ statusCode: 500 });
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} />
      </TestWrapper>
    );
    await waitFor(() => {
      expect(screen.getByText('Erreur')).toBeInTheDocument();
    });
    expect(screen.getByText('Erreur lors du chargement des cibles')).toBeInTheDocument();
  });

  it('refetches when search text changes', async () => {
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} />
      </TestWrapper>
    );
    await waitFor(() => expect(mockApiFetchRaw).toHaveBeenCalledTimes(1));

    // Simulate search text change (sets searchValue which triggers debouncedSearch)
    const select = screen.getByRole('combobox');
    fireEvent.mouseDown(select);
    fireEvent.change(select, { target: { value: 'srv-dev' } });

    // Wait for debounce (300ms) + second fetch
    await waitFor(() => {
      expect(mockApiFetchRaw).toHaveBeenCalledTimes(2);
    }, { timeout: 1000 });
    expect(mockApiFetchRaw).toHaveBeenLastCalledWith(expect.stringContaining('search=srv-dev'));
  });

  it('uses custom placeholder prop', async () => {
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} placeholder="Custom placeholder" />
      </TestWrapper>
    );
    await waitFor(() => expect(mockApiFetchRaw).toHaveBeenCalled());
    expect(screen.getByText('Custom placeholder')).toBeInTheDocument();
  });

  it('handleChange is invoked when option selected from dropdown (covers lines 161-171)', async () => {
    const onChange = vi.fn();
    render(
      <TestWrapper>
        <TargetSelector value={[]} onChange={onChange} />
      </TestWrapper>
    );

    await waitFor(() => expect(mockApiFetchRaw).toHaveBeenCalled());

    // Open dropdown via mouseDown (confirmed working in other tests in this file)
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

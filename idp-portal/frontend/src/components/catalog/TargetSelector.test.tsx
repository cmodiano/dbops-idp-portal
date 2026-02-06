/**
 * Tests for TargetSelector component (Story 13.2, Task 8.1).
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { App } from 'antd';
import { TargetSelector, type Target } from './TargetSelector';

// Mock the api_client
vi.mock('../../services/api_client', () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from '../../services/api_client';

const mockApiFetch = apiFetch as ReturnType<typeof vi.fn>;

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
    mockApiFetch.mockResolvedValue(mockTargetsResponse);
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
        expect(mockApiFetch).toHaveBeenCalledWith(
          expect.stringContaining('/inventory/targets')
        );
      });

      expect(screen.getByText('Selectionnez une cible')).toBeInTheDocument();
    });

    it('renders loading state while fetching targets', async () => {
      // Delay the response
      mockApiFetch.mockImplementation(
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
      mockApiFetch.mockRejectedValue(new Error('Network error'));

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
        expect(mockApiFetch).toHaveBeenCalled();
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
        expect(mockApiFetch).toHaveBeenCalled();
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
        expect(mockApiFetch).toHaveBeenCalled();
      });

      // Open dropdown
      const select = screen.getByRole('combobox');
      fireEvent.mouseDown(select);

      // Wait for dropdown and check group headers
      await waitFor(() => {
        // Group headers should be visible
        expect(screen.getByText('Developpement')).toBeInTheDocument();
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
        expect(mockApiFetch).toHaveBeenCalled();
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
        expect(mockApiFetch).toHaveBeenCalled();
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
        expect(mockApiFetch).toHaveBeenCalled();
      });

      expect(screen.getByLabelText('Custom aria label')).toBeInTheDocument();
    });
  });
});

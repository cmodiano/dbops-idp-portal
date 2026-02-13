/**
 * Tests for ProfileForm exclusion_patterns field.
 * Story 25.6 - Task 6: Frontend tests for exclusion patterns UI.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProfileForm } from './ProfileForm';
import type { ProfileResponse } from '../../types/api';
import * as profilesService from '../../services/profiles_service';
import * as adminService from '../../services/admin_service';
import { useEnvironments } from '../../hooks/useEnvironments';

vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: vi.fn(),
}));

const mockUseEnvironments = useEnvironments as ReturnType<typeof vi.fn>;

const mockOnSubmit = vi.fn().mockResolvedValue({ id: 1, name: 'Test', ad_group: 'GRP-X' } as ProfileResponse);
const mockOnCancel = vi.fn();
const mockOnSuccess = vi.fn();

const defaultProps = {
  open: true,
  onCancel: mockOnCancel,
  onSubmit: mockOnSubmit,
  loading: false,
  error: null,
  editProfile: null,
  onSuccess: mockOnSuccess,
};

describe('ProfileForm - exclusion_patterns field', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseEnvironments.mockReturnValue({
      environments: ['dev', 'staging', 'prod'],
      environmentOptions: [
        { value: 'dev', label: 'dev' },
        { value: 'staging', label: 'staging' },
        { value: 'prod', label: 'prod' },
      ],
      loading: false,
      error: null,
    });

    vi.spyOn(adminService, 'listActions').mockResolvedValue([]);
    vi.spyOn(adminService, 'getTags').mockResolvedValue([]);
    vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
      actions_type: 'all',
      action_ids: [],
      tag_patterns: [],
      environments: ['prod'],
    });
    vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      exclusion_patterns: [],
    });
  });

  it('exclusion_patterns field is displayed in form', async () => {
    const editProfile: ProfileResponse = {
      id: 1,
      name: 'Test DBA',
      description: 'Test profile',
      ad_group: 'test-dba-group',
      is_admin: false,
      is_auditor: false,
      created_at: '2026-02-10T00:00:00Z',
      updated_at: '2026-02-10T00:00:00Z',
    };
    render(<ProfileForm {...defaultProps} editProfile={editProfile} />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Patterns d'exclusion/i)).toBeInTheDocument();
    });
  });

  it('exclusion_patterns field has correct placeholder', async () => {
    const editProfile: ProfileResponse = {
      id: 1,
      name: 'Test DBA',
      description: 'Test profile',
      ad_group: 'test-dba-group',
      is_admin: false,
      is_auditor: false,
      created_at: '2026-02-10T00:00:00Z',
      updated_at: '2026-02-10T00:00:00Z',
    };
    render(<ProfileForm {...defaultProps} editProfile={editProfile} />);

    await waitFor(() => {
      // Ant Design Select renders placeholder as a span, not an HTML placeholder attribute
      expect(screen.getByText('ex: PROD-CRITICAL-*, DR-*')).toBeInTheDocument();
    });
  });

  it('editing profile loads existing exclusion_patterns', async () => {
    const editProfile: ProfileResponse = {
      id: 1,
      name: 'Test DBA',
      description: 'Test profile',
      ad_group: 'test-dba-group',
      is_admin: false,
      is_auditor: false,
      created_at: '2026-02-10T00:00:00Z',
      updated_at: '2026-02-10T00:00:00Z',
    };

    vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
      targets_type: 'all',
      target_names: [],
      target_patterns: [],
      exclusion_patterns: ['PROD-CRITICAL-*', 'DR-*'],
    });

    render(<ProfileForm {...defaultProps} editProfile={editProfile} />);

    await waitFor(() => {
      expect(profilesService.getProfileTargets).toHaveBeenCalledWith(1);
    });

    await waitFor(() => {
      expect(screen.getByText('PROD-CRITICAL-*')).toBeInTheDocument();
      expect(screen.getByText('DR-*')).toBeInTheDocument();
    });
  });

  it('user can add exclusion patterns as tags', async () => {
    const user = userEvent.setup();
    const editProfile: ProfileResponse = {
      id: 1,
      name: 'Test DBA',
      description: 'Test profile',
      ad_group: 'test-dba-group',
      is_admin: false,
      is_auditor: false,
      created_at: '2026-02-10T00:00:00Z',
      updated_at: '2026-02-10T00:00:00Z',
    };

    render(<ProfileForm {...defaultProps} editProfile={editProfile} />);

    await waitFor(() => {
      expect(screen.getByLabelText(/Patterns d'exclusion/i)).toBeInTheDocument();
    });

    // Ant Design Select tags mode: find the input by its id (Ant Design generates id from form field name)
    const input = screen.getByLabelText(/Patterns d'exclusion/i) as HTMLElement;
    // The label-linked element is the container; find the actual search input inside
    const searchInput = input.closest('.ant-select')?.querySelector('input.ant-select-selection-search-input') as HTMLInputElement
      ?? input.querySelector('input') as HTMLInputElement
      ?? input;
    await user.click(searchInput);
    await user.type(searchInput, 'PROD-CRITICAL-*{enter}');
    await user.type(searchInput, 'DR-*{enter}');

    await waitFor(() => {
      // Ant Design Select tags mode renders tags as selection items (plus dropdown options)
      expect(screen.getAllByText('PROD-CRITICAL-*').length).toBeGreaterThanOrEqual(1);
      expect(screen.getAllByText('DR-*').length).toBeGreaterThanOrEqual(1);
    });
  });
});

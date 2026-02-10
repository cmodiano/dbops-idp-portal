/**
 * Tests for ProfileForm (Story 2.9, AC #1, #2, #4).
 * Story 2.10: section Actions autorisées (AC1–AC4).
 * Story 2.11: section Targets autorisés (AC1–AC3).
 * Story 21.6: environment validation warning (AC6).
 * Story 23.7: filter_by_attribute Radio options (AC1–AC10).
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

const mockOnSubmit = vi.fn().mockResolvedValue({ id: 1, name: 'Assurance', ad_group: 'GRP-X' } as ProfileResponse);
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

const editProfile: ProfileResponse = {
  id: 1,
  name: 'Assurance',
  description: 'X',
  ad_group: 'GRP-X',
  is_admin: false,
  is_auditor: true,
  created_at: '2026-01-28T10:00:00Z',
  updated_at: '2026-01-28T10:00:00Z',
};

describe('ProfileForm', () => {
  beforeEach(() => {
    mockUseEnvironments.mockReturnValue({
      environments: ['dev', 'staging', 'prod'],
      environmentOptions: [
        { value: 'dev', label: 'Développement' },
        { value: 'staging', label: 'Staging' },
        { value: 'prod', label: 'Production' },
      ],
      loading: false,
      error: null,
    });
  });

  it('renders Nouveau profil when not editing', () => {
    render(<ProfileForm {...defaultProps} />);
    expect(screen.getByText('Nouveau profil')).toBeInTheDocument();
  });

  it('renders Modifier le profil when editing', () => {
    render(
      <ProfileForm
        {...defaultProps}
        editProfile={{
          id: 1,
          name: 'Assurance',
          description: 'X',
          ad_group: 'GRP-X',
          is_admin: false,
          is_auditor: true,
          created_at: '2026-01-28T10:00:00Z',
          updated_at: '2026-01-28T10:00:00Z',
        }}
      />
    );
    expect(screen.getByText('Modifier le profil')).toBeInTheDocument();
  });

  it('has name, description, ad_group, is_admin, is_auditor fields', () => {
    render(<ProfileForm {...defaultProps} />);
    expect(screen.getByLabelText(/^Nom/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Description/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Groupe AD/)).toBeInTheDocument();
    expect(screen.getByText('Administrateur')).toBeInTheDocument();
    expect(screen.getByText('Auditeur')).toBeInTheDocument();
  });

  it('shows error alert when error prop is set', () => {
    render(<ProfileForm {...defaultProps} error="Un profil avec ce nom existe déjà." />);
    expect(screen.getByText('Un profil avec ce nom existe déjà.')).toBeInTheDocument();
  });

  it('submits with name and ad_group (required)', async () => {
    const user = userEvent.setup();
    render(<ProfileForm {...defaultProps} />);
    await user.type(screen.getByLabelText(/^Nom/), 'Assurance');
    await user.type(screen.getByLabelText(/Groupe AD/), 'GRP-IDP-ASSURANCE');
    await user.click(screen.getByRole('button', { name: /Créer/i }));
    await vi.waitFor(() => expect(mockOnSubmit).toHaveBeenCalled());
    expect(mockOnSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Assurance',
        ad_group: 'GRP-IDP-ASSURANCE',
        is_admin: false,
        is_auditor: false,
      })
    );
  });

  it('calls onCancel when Annuler clicked', async () => {
    const user = userEvent.setup();
    render(<ProfileForm {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Annuler/i }));
    expect(mockOnCancel).toHaveBeenCalled();
  });

  describe('Story 2.10: Actions autorisées (edit only)', () => {
    beforeEach(() => {
      vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: [],
      });
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
      });
      vi.spyOn(adminService, 'listActions').mockResolvedValue([]);
      vi.spyOn(adminService, 'getTags').mockResolvedValue([]);
      vi.spyOn(profilesService, 'putProfileActions').mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: [],
      });
      vi.spyOn(profilesService, 'putProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
      });
    });

    it('shows section Actions autorisées when editing', async () => {
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Actions autorisées')).toBeInTheDocument();
      });
      expect(screen.getByText(/Liste d'actions/)).toBeInTheDocument();
      expect(screen.getByText('Pattern par tags')).toBeInTheDocument();
      expect(screen.getByText(/Toutes \(\*\)/)).toBeInTheDocument();
      expect(screen.getByText('Environnements autorisés')).toBeInTheDocument();
      expect(screen.getByText('Targets autorisés')).toBeInTheDocument();
      // Story 23.7: 5 radio options for targets
      expect(screen.getByText('Tous les serveurs')).toBeInTheDocument();
      expect(screen.getByText('Tous les serveurs Oracle')).toBeInTheDocument();
      expect(screen.getByText('Tous les serveurs SQL')).toBeInTheDocument();
      expect(screen.getByText('Liste de serveurs spécifiques')).toBeInTheDocument();
      expect(screen.getByText('Pattern de serveurs')).toBeInTheDocument();
    });

    it('calls putProfileActions and putProfileTargets on submit when editing', async () => {
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => expect(screen.getByText('Actions autorisées')).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled());
      await waitFor(() =>
        expect(profilesService.putProfileActions).toHaveBeenCalledWith(
          1,
          expect.objectContaining({
            actions_type: 'all',
            action_ids: [],
            tag_patterns: [],
            environments: [],
          })
        )
      );
      await waitFor(() =>
        expect(profilesService.putProfileTargets).toHaveBeenCalledWith(
          1,
          expect.objectContaining({
            targets_type: 'all',
            target_names: [],
            target_patterns: [],
          })
        )
      );
    });

    it('shows warning when putProfileActions fails but profile update succeeds', async () => {
      vi.spyOn(profilesService, 'putProfileActions').mockRejectedValue(new Error('Network error'));
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => expect(screen.getByText('Actions autorisées')).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => expect(mockOnSubmit).toHaveBeenCalled());
      await waitFor(() =>
        expect(screen.getByText(/Profil mis à jour, mais erreur/)).toBeInTheDocument()
      );
      expect(mockOnSuccess).toHaveBeenCalled();
    });

    it('loads and displays targets permissions when editing', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'pattern',
        target_names: [],
        target_patterns: ['assurance-*', 'infra-*'],
      });
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => expect(screen.getByText('Targets autorisés')).toBeInTheDocument());
      expect(profilesService.getProfileTargets).toHaveBeenCalledWith(1);
    });
  });

  describe('Story 21.6: Environment validation warning (AC6)', () => {
    beforeEach(() => {
      mockUseEnvironments.mockReturnValue({
        environments: ['dev', 'staging', 'prod'],
        environmentOptions: [
          { value: 'dev', label: 'Développement' },
          { value: 'staging', label: 'Staging' },
          { value: 'prod', label: 'Production' },
        ],
        loading: false,
        error: null,
      });
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
      });
      vi.spyOn(adminService, 'listActions').mockResolvedValue([]);
      vi.spyOn(adminService, 'getTags').mockResolvedValue([]);
      vi.spyOn(profilesService, 'putProfileActions').mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: [],
      });
      vi.spyOn(profilesService, 'putProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
      });
    });

    it('shows warning when profile has environments not in inventory (AC6)', async () => {
      // Profile loaded from backend has 'unknown_env' not in inventory
      vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: ['DEV', 'UNKNOWN_ENV'],
      });

      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);

      await waitFor(() => {
        expect(screen.getByText(/Attention : environnements non reconnus/)).toBeInTheDocument();
      });
      expect(screen.getAllByText(/UNKNOWN_ENV/).length).toBeGreaterThanOrEqual(1);
    });

    it('does not show warning when all environments are valid (AC6)', async () => {
      vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: ['DEV', 'PROD'],
      });

      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);

      await waitFor(() => {
        expect(screen.getByText('Environnements autorisés')).toBeInTheDocument();
      });
      expect(screen.queryByText(/Attention : environnements non reconnus/)).not.toBeInTheDocument();
    });

    it('does not show warning with empty environments (AC6)', async () => {
      vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: [],
      });

      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);

      await waitFor(() => {
        expect(screen.getByText('Environnements autorisés')).toBeInTheDocument();
      });
      expect(screen.queryByText(/Attention : environnements non reconnus/)).not.toBeInTheDocument();
    });

    it('submit button remains enabled despite warning (AC6)', async () => {
      vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: ['UNKNOWN_ENV'],
      });

      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);

      await waitFor(() => {
        expect(screen.getByText(/Attention : environnements non reconnus/)).toBeInTheDocument();
      });

      const submitButton = screen.getByRole('button', { name: /Enregistrer/i });
      expect(submitButton).not.toBeDisabled();
    });
  });

  describe('Story 23.7: filter_by_attribute targets options (AC1–AC10)', () => {
    beforeEach(() => {
      vi.spyOn(profilesService, 'getProfileActions').mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: [],
      });
      vi.spyOn(adminService, 'listActions').mockResolvedValue([]);
      vi.spyOn(adminService, 'getTags').mockResolvedValue([]);
      vi.spyOn(profilesService, 'putProfileActions').mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: [],
      });
      vi.spyOn(profilesService, 'putProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
    });

    it('renders 5 target radio options when editing (AC1)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Targets autorisés')).toBeInTheDocument();
      });
      expect(screen.getByText('Tous les serveurs')).toBeInTheDocument();
      expect(screen.getByText('Tous les serveurs Oracle')).toBeInTheDocument();
      expect(screen.getByText('Tous les serveurs SQL')).toBeInTheDocument();
      expect(screen.getByText('Liste de serveurs spécifiques')).toBeInTheDocument();
      expect(screen.getByText('Pattern de serveurs')).toBeInTheDocument();
    });

    it('shows info Alert for "Tous les serveurs" (AC4, AC7)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Targets autorisés')).toBeInTheDocument();
      });
      await waitFor(() => {
        expect(screen.getByText(/Accès complet à tous les serveurs/)).toBeInTheDocument();
      });
    });

    it('shows Oracle info Alert when selecting "Tous les serveurs Oracle" (AC2, AC7)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Tous les serveurs Oracle')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Tous les serveurs Oracle'));
      await waitFor(() => {
        expect(screen.getByText(/Accès à tous les serveurs Oracle/)).toBeInTheDocument();
      });
    });

    it('shows SQL info Alert when selecting "Tous les serveurs SQL" (AC3, AC7)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Tous les serveurs SQL')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Tous les serveurs SQL'));
      await waitFor(() => {
        expect(screen.getByText(/Accès à tous les serveurs SQL/)).toBeInTheDocument();
      });
    });

    it('pre-selects "Tous les serveurs Oracle" for Oracle profile (AC5)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: { engine_type: ['oracle'] },
      });
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText(/Accès à tous les serveurs Oracle/)).toBeInTheDocument();
      });
    });

    it('pre-selects "Tous les serveurs SQL" for SQL profile (AC5)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: { engine_type: ['sqlserver'] },
      });
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText(/Accès à tous les serveurs SQL/)).toBeInTheDocument();
      });
    });

    it('pre-selects "Tous les serveurs" for all without filter (AC5)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText(/Accès complet à tous les serveurs/)).toBeInTheDocument();
      });
    });

    it('shows Warning for advanced (unsupported) filter_by_attribute (AC8)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: { zone: ['prod'], engine_type: ['oracle'] },
      });
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText(/filtres avancés non supportés/)).toBeInTheDocument();
      });
    });

    it('shows Warning for multi-value engine_type (AC8)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: { engine_type: ['oracle', 'sqlserver'] },
      });
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText(/filtres avancés non supportés/)).toBeInTheDocument();
      });
    });

    it('submits Oracle payload with filter_by_attribute (AC2, AC9)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Tous les serveurs Oracle')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Tous les serveurs Oracle'));
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(profilesService.putProfileTargets).toHaveBeenCalledWith(1, {
          targets_type: 'all',
          target_names: [],
          target_patterns: [],
          filter_by_attribute: { engine_type: ['oracle'] },
        });
      });
    });

    it('submits SQL payload with filter_by_attribute (AC3, AC9)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Tous les serveurs SQL')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Tous les serveurs SQL'));
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(profilesService.putProfileTargets).toHaveBeenCalledWith(1, {
          targets_type: 'all',
          target_names: [],
          target_patterns: [],
          filter_by_attribute: { engine_type: ['sqlserver'] },
        });
      });
    });

    it('submits "Tous" payload with filter_by_attribute null (AC4)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Targets autorisés')).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(profilesService.putProfileTargets).toHaveBeenCalledWith(1, {
          targets_type: 'all',
          target_names: [],
          target_patterns: [],
          filter_by_attribute: null,
        });
      });
    });

    it('does not show info Alert for "Liste" or "Pattern" modes (AC7)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'list',
        target_names: ['srv-01'],
        target_patterns: [],
        filter_by_attribute: null,
      });
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Targets autorisés')).toBeInTheDocument();
      });
      // Wait for mode to be set
      await waitFor(() => {
        expect(screen.getByText('Targets')).toBeInTheDocument();
      });
      expect(screen.queryByText(/Accès complet à tous les serveurs/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Accès à tous les serveurs Oracle/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Accès à tous les serveurs SQL/)).not.toBeInTheDocument();
    });

    it('shows error when backend rejects filter_by_attribute (AC6, AC8)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: null,
      });
      vi.spyOn(profilesService, 'putProfileTargets').mockRejectedValue(new Error('Invalid filter'));
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Targets autorisés')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Tous les serveurs Oracle'));
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(screen.getByText(/Profil mis à jour, mais erreur/)).toBeInTheDocument();
      });
    });

    it('switch from Oracle to List mode hides Alert and shows target_names (AC7)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: { engine_type: ['oracle'] },
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText(/Accès à tous les serveurs Oracle/)).toBeInTheDocument();
      });
      await user.click(screen.getByText('Liste de serveurs spécifiques'));
      await waitFor(() => {
        expect(screen.queryByText(/Accès à tous les serveurs Oracle/)).not.toBeInTheDocument();
        expect(screen.getByText('Targets')).toBeInTheDocument();
      });
    });

    it('switch from List to Oracle mode hides target_names and shows Alert (AC7)', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'list',
        target_names: ['srv-01'],
        target_patterns: [],
        filter_by_attribute: null,
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Targets')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Tous les serveurs Oracle'));
      await waitFor(() => {
        expect(screen.getByText(/Accès à tous les serveurs Oracle/)).toBeInTheDocument();
        expect(screen.queryByText('Targets')).not.toBeInTheDocument();
      });
    });

    it('edit profile Oracle → change to SQL → submit correct payload', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: { engine_type: ['oracle'] },
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText(/Accès à tous les serveurs Oracle/)).toBeInTheDocument();
      });
      await user.click(screen.getByText('Tous les serveurs SQL'));
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(profilesService.putProfileTargets).toHaveBeenCalledWith(1, {
          targets_type: 'all',
          target_names: [],
          target_patterns: [],
          filter_by_attribute: { engine_type: ['sqlserver'] },
        });
      });
    });

    it('edit profile List → change to Oracle → submit correct payload', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'list',
        target_names: ['srv-01', 'srv-02'],
        target_patterns: [],
        filter_by_attribute: null,
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText('Targets autorisés')).toBeInTheDocument();
      });
      await user.click(screen.getByText('Tous les serveurs Oracle'));
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(profilesService.putProfileTargets).toHaveBeenCalledWith(1, {
          targets_type: 'all',
          target_names: [],
          target_patterns: [],
          filter_by_attribute: { engine_type: ['oracle'] },
        });
      });
    });

    it('edit profile advanced → change to Tous → submit filter_by_attribute null', async () => {
      vi.spyOn(profilesService, 'getProfileTargets').mockResolvedValue({
        targets_type: 'all',
        target_names: [],
        target_patterns: [],
        filter_by_attribute: { zone: ['prod'] },
      });
      const user = userEvent.setup();
      render(<ProfileForm {...defaultProps} editProfile={editProfile} />);
      await waitFor(() => {
        expect(screen.getByText(/filtres avancés non supportés/)).toBeInTheDocument();
      });
      await user.click(screen.getByText('Tous les serveurs'));
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));
      await waitFor(() => {
        expect(profilesService.putProfileTargets).toHaveBeenCalledWith(1, {
          targets_type: 'all',
          target_names: [],
          target_patterns: [],
          filter_by_attribute: null,
        });
      });
    });
  });
});

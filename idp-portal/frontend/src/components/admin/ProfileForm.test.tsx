/**
 * Tests for ProfileForm (Story 2.9, AC #1, #2, #4).
 * Story 2.10: section Actions autorisées (AC1–AC4).
 * Story 2.11: section Targets autorisés (AC1–AC3).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProfileForm } from './ProfileForm';
import type { ProfileResponse } from '../../types/api';
import * as profilesService from '../../services/profiles_service';
import * as adminService from '../../services/admin_service';

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
      expect(screen.getByText('Liste d\'actions')).toBeInTheDocument();
      expect(screen.getByText('Pattern par tags')).toBeInTheDocument();
      expect(screen.getByText(/Toutes \(\*\)/)).toBeInTheDocument();
      expect(screen.getByText('Environnements autorisés')).toBeInTheDocument();
      expect(screen.getByText('Targets autorisés')).toBeInTheDocument();
      expect(screen.getByText('Liste explicite')).toBeInTheDocument();
      expect(screen.getByText('Pattern')).toBeInTheDocument();
      expect(screen.getByText('Tous (*)')).toBeInTheDocument();
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
});

/**
 * ProfileWizard tests — Story 2.25 (AC #1–#7).
 *
 * Tests:
 * - 7.1: Wizard affiche 3 étapes ; navigation conserve les valeurs ; soumission à l'étape 3
 * - 7.2: Mode édition : champs pré-remplis depuis profil + permissions
 * - 7.3: Régression : création/édition via wizard produit le même résultat qu'via ProfileForm
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { ProfileWizard } from './ProfileWizard';

const renderWithApp = (ui: React.ReactElement) => render(<App>{ui}</App>);
import * as profilesService from '../../services/profiles_service';
import * as adminService from '../../services/admin_service';
import type { ProfileResponse, ProfileActionPermissionsResponse, ProfileTargetPermissionsResponse } from '../../types/api';

vi.mock('../../services/profiles_service');
vi.mock('../../services/admin_service');

import { useEnvironments } from '../../hooks/useEnvironments';
vi.mock('../../hooks/useEnvironments', () => ({
  useEnvironments: vi.fn(),
}));
const mockUseEnvironments = useEnvironments as ReturnType<typeof vi.fn>;

const mockProfilesService = vi.mocked(profilesService);
const mockAdminService = vi.mocked(adminService);

const mockProfile: ProfileResponse = {
  id: 1,
  name: 'Test Profile',
  description: 'A test profile',
  ad_group: 'GRP-TEST',
  is_admin: true,
  is_auditor: false,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-02T00:00:00Z',
};

const mockActionPermissions: ProfileActionPermissionsResponse = {
  actions_type: 'list',
  action_ids: [1, 2],
  tag_patterns: [],
  environments: ['DEV', 'STAGING'],
};

const mockTargetPermissions: ProfileTargetPermissionsResponse = {
  targets_type: 'pattern',
  target_names: [],
  target_patterns: ['assurance-*'],
};

const mockActions = [
  { id: 1, name: 'Action 1', status: 'published' as const, engine: 'Oracle' as const, created_at: '2026-01-01T00:00:00Z', execution_count: 0 },
  { id: 2, name: 'Action 2', status: 'published' as const, engine: 'Oracle' as const, created_at: '2026-01-01T00:00:00Z', execution_count: 0 },
];

const mockTags = [
  { id: 1, name: 'oracle', created_at: '2026-01-01T00:00:00Z' },
  { id: 2, name: 'provisioning', created_at: '2026-01-01T00:00:00Z' },
];

describe('ProfileWizard', () => {
  const defaultProps = {
    open: true,
    onCancel: vi.fn(),
    onSuccess: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
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
    mockAdminService.getAdminActions.mockResolvedValue({ data: mockActions, pagination: { page: 1, page_size: 10, total: mockActions.length, total_pages: 1 } });
    mockAdminService.getTags.mockResolvedValue(mockTags);
    mockProfilesService.createProfile.mockResolvedValue(mockProfile);
    mockProfilesService.updateProfile.mockResolvedValue(mockProfile);
    mockProfilesService.getProfileActions.mockResolvedValue(mockActionPermissions);
    mockProfilesService.getProfileTargets.mockResolvedValue(mockTargetPermissions);
    mockProfilesService.putProfileActions.mockResolvedValue(mockActionPermissions);
    mockProfilesService.putProfileTargets.mockResolvedValue(mockTargetPermissions);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Task 7.1 — Wizard 3 étapes, navigation, soumission', () => {
    it('affiche le wizard avec 3 étapes (AC1)', async () => {
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Steps should be visible
      expect(screen.getByText('Général')).toBeInTheDocument();
      expect(screen.getByText('Permissions Actions')).toBeInTheDocument();
      expect(screen.getByText('Permissions Targets')).toBeInTheDocument();
    });

    it('affiche l\'étape 1 Général par défaut (AC2)', async () => {
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Step 1 fields should be visible
      expect(screen.getByLabelText(/Nom du profil/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Description/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/Groupe AD/i)).toBeInTheDocument();
    });

    it('valide le nom requis avant de passer à l\'étape 2 (AC2)', async () => {
      const user = userEvent.setup();
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Try to go next without filling name
      const nextButton = screen.getByRole('button', { name: /Suivant/i });
      await user.click(nextButton);

      // Should show validation error
      await waitFor(() => {
        expect(screen.getByText(/Le nom est requis/i)).toBeInTheDocument();
      });
    });

    it('navigation Suivant/Précédent permet de naviguer entre les étapes (AC5)', async () => {
      const user = userEvent.setup();
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Fill step 1 (required for validation)
      await user.type(screen.getByLabelText(/Nom du profil/i), 'Mon Profil');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP-TEST');

      // Go to step 2 - Suivant button should work
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      // Wait for step 2 content to appear
      await waitFor(() => {
        expect(screen.getByLabelText(/Toutes les actions/i)).toBeInTheDocument();
      });

      // Précédent button should appear on step 2
      expect(screen.getByRole('button', { name: /Précédent/i })).toBeInTheDocument();

      // Go to step 3
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/Toutes les targets/i)).toBeInTheDocument();
      });

      // Enregistrer should appear on step 3
      expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument();
      // Suivant should not appear on step 3
      expect(screen.queryByRole('button', { name: /Suivant/i })).not.toBeInTheDocument();
    });

    it('soumission à l\'étape 3 appelle les bonnes APIs (AC6)', async () => {
      const user = userEvent.setup();
      const onSuccess = vi.fn();
      renderWithApp(<ProfileWizard {...defaultProps} onSuccess={onSuccess} />);

      // Step 1: Fill required fields
      await user.type(screen.getByLabelText(/Nom du profil/i), 'Nouveau Profil');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP-NEW');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      // Step 2: Keep default (all actions)
      await waitFor(() => {
        expect(screen.getByText(/Type de permission actions/i)).toBeInTheDocument();
      });
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      // Step 3: Keep default (all targets)
      await waitFor(() => {
        expect(screen.getByText(/Type de permission targets/i)).toBeInTheDocument();
      });

      // Submit
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(mockProfilesService.createProfile).toHaveBeenCalledWith({
          name: 'Nouveau Profil',
          description: null,
          ad_group: 'GRP-NEW',
          is_admin: false,
          is_auditor: false,
        });
        expect(mockProfilesService.putProfileActions).toHaveBeenCalledWith(1, {
          actions_type: 'all',
          action_ids: [],
          tag_patterns: [],
          environments: [],
        });
        expect(mockProfilesService.putProfileTargets).toHaveBeenCalledWith(1, {
          targets_type: 'all',
          target_names: [],
          target_patterns: [],
        });
        expect(onSuccess).toHaveBeenCalledWith(mockProfile);
      });
    });

    it('bouton Enregistrer visible uniquement à l\'étape 3 (AC6)', async () => {
      const user = userEvent.setup();
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Step 1: No Enregistrer button
      expect(screen.queryByRole('button', { name: /Enregistrer/i })).not.toBeInTheDocument();

      // Fill and go to step 2
      await user.type(screen.getByLabelText(/Nom du profil/i), 'Test');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByText(/Type de permission actions/i)).toBeInTheDocument();
      });

      // Step 2: No Enregistrer button
      expect(screen.queryByRole('button', { name: /Enregistrer/i })).not.toBeInTheDocument();

      // Go to step 3
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        // Step 3: Enregistrer button should be visible
        expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument();
      });
    });
  });

  describe('Task 7.2 — Mode édition : pré-remplissage', () => {
    it('charge et affiche les données du profil existant (AC7)', async () => {
      renderWithApp(<ProfileWizard {...defaultProps} editProfile={mockProfile} />);

      await waitFor(() => {
        expect(mockProfilesService.getProfileActions).toHaveBeenCalledWith(1);
        expect(mockProfilesService.getProfileTargets).toHaveBeenCalledWith(1);
      });

      // Check step 1 fields are pre-filled
      await waitFor(() => {
        expect(screen.getByLabelText(/Nom du profil/i)).toHaveValue('Test Profile');
        expect(screen.getByLabelText(/Description/i)).toHaveValue('A test profile');
        expect(screen.getByLabelText(/Groupe AD/i)).toHaveValue('GRP-TEST');
      });
    });

    it('en mode édition, appelle updateProfile au lieu de createProfile (AC7)', async () => {
      const user = userEvent.setup();
      const onSuccess = vi.fn();
      renderWithApp(<ProfileWizard {...defaultProps} editProfile={mockProfile} onSuccess={onSuccess} />);

      // Wait for all API calls to complete (profile data loading)
      await waitFor(() => {
        expect(mockProfilesService.getProfileActions).toHaveBeenCalledWith(1);
        expect(mockProfilesService.getProfileTargets).toHaveBeenCalledWith(1);
      });

      // Wait for form to be populated with profile values
      await waitFor(() => {
        expect(screen.getByLabelText(/Nom du profil/i)).toHaveValue('Test Profile');
      });

      // Navigate to step 2
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      // Wait for step 2 to render
      await waitFor(() => {
        expect(screen.getByLabelText(/Toutes les actions/i)).toBeInTheDocument();
      });

      // Navigate to step 3
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      // Wait for step 3 to render
      await waitFor(() => {
        expect(screen.getByLabelText(/Toutes les targets/i)).toBeInTheDocument();
      });

      // Submit
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      // Wait for API calls to complete
      await waitFor(() => {
        expect(mockProfilesService.updateProfile).toHaveBeenCalled();
      });

      // Verify correct APIs were called
      expect(mockProfilesService.createProfile).not.toHaveBeenCalled();
      expect(mockProfilesService.updateProfile).toHaveBeenCalledWith(1, expect.objectContaining({
        name: 'Test Profile',
      }));
    });

    it('affiche le titre "Modifier le profil" en mode édition (AC7)', async () => {
      renderWithApp(<ProfileWizard {...defaultProps} editProfile={mockProfile} />);

      await waitFor(() => {
        expect(screen.getByText(/Modifier le profil/i)).toBeInTheDocument();
      });
    });

    it('affiche le titre "Nouveau profil" en mode création', () => {
      renderWithApp(<ProfileWizard {...defaultProps} />);
      expect(screen.getByText(/Nouveau profil/i)).toBeInTheDocument();
    });
  });

  describe('Task 7.3 — Régression : mêmes payloads qu\'avec ProfileForm', () => {
    it('envoie le même payload ProfileCreate que ProfileForm', async () => {
      const user = userEvent.setup();
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Fill all fields like ProfileForm would
      await user.type(screen.getByLabelText(/Nom du profil/i), 'Test Profile');
      await user.type(screen.getByLabelText(/Description/i), 'Test description');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP-TEST');

      // Toggle admin switch
      const adminSwitch = screen.getByRole('switch', { name: /Admin/i });
      await user.click(adminSwitch);

      // Navigate through steps
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Type de permission actions/i)).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Type de permission targets/i)).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      // Verify ProfileCreate payload matches ProfileForm format
      await waitFor(() => {
        expect(mockProfilesService.createProfile).toHaveBeenCalledWith({
          name: 'Test Profile',
          description: 'Test description',
          ad_group: 'GRP-TEST',
          is_admin: true,
          is_auditor: false,
        });
      });
    });

    it('envoie le même payload ProfileActionPermissionsUpdate que ProfileForm', async () => {
      const user = userEvent.setup();
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Step 1
      await user.type(screen.getByLabelText(/Nom du profil/i), 'Test');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      // Step 2: verify default is "all" (don't change it)
      await waitFor(() => expect(screen.getByLabelText(/Toutes les actions/i)).toBeInTheDocument());
      expect(screen.getByLabelText(/Toutes les actions/i)).toBeChecked();

      // Go to step 3 and submit
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByLabelText(/Toutes les targets/i)).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      // Wait for API calls to complete
      await waitFor(() => {
        expect(mockProfilesService.createProfile).toHaveBeenCalled();
      });

      // Check putProfileActions was called with actions_type 'all' (default)
      expect(mockProfilesService.putProfileActions).toHaveBeenCalledWith(1, {
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: [],
      });
    });

    it('envoie le même payload ProfileTargetPermissionsUpdate que ProfileForm', async () => {
      const user = userEvent.setup();
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Navigate to step 3
      await user.type(screen.getByLabelText(/Nom du profil/i), 'Test');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Type de permission actions/i)).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      // Step 3: Select "Pattern"
      await waitFor(() => expect(screen.getByText(/Type de permission targets/i)).toBeInTheDocument());
      const patternRadio = screen.getByLabelText(/Pattern/i);
      await user.click(patternRadio);

      // Provide at least one pattern (required by validation)
      const patternsInput = screen.getByLabelText(/Target patterns/i);
      await user.type(patternsInput, 'assurance-*{enter}');

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(mockProfilesService.putProfileTargets).toHaveBeenCalledWith(1, {
          targets_type: 'pattern',
          target_names: [],
          target_patterns: ['assurance-*'],
        });
      });
    });
  });

  describe('AC3 — Étape 2 Permissions Actions', () => {
    it('affiche Radio.Group avec 3 options (all, list, pattern)', async () => {
      const user = userEvent.setup();
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Navigate to step 2
      await user.type(screen.getByLabelText(/Nom du profil/i), 'Test');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/Toutes les actions/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Liste d'actions/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Pattern de tags/i)).toBeInTheDocument();
      });
    });

    it('affiche multi-select environnements', async () => {
      const user = userEvent.setup();
      renderWithApp(<ProfileWizard {...defaultProps} />);

      await user.type(screen.getByLabelText(/Nom du profil/i), 'Test');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/Environnements autorisés/i)).toBeInTheDocument();
      });
    });
  });

  describe('AC4 — Étape 3 Permissions Targets', () => {
    it('affiche Radio.Group avec 3 options (all, list, pattern)', async () => {
      const user = userEvent.setup();
      renderWithApp(<ProfileWizard {...defaultProps} />);

      // Navigate to step 3
      await user.type(screen.getByLabelText(/Nom du profil/i), 'Test');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Type de permission actions/i)).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/Toutes les targets/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Liste de targets/i)).toBeInTheDocument();
        expect(screen.getByLabelText(/Pattern/i)).toBeInTheDocument();
      });
    });
  });

  describe('Error handling', () => {
    it('affiche une erreur si createProfile échoue', async () => {
      const user = userEvent.setup();
      mockProfilesService.createProfile.mockRejectedValue(new Error('Création échouée'));

      renderWithApp(<ProfileWizard {...defaultProps} />);

      await user.type(screen.getByLabelText(/Nom du profil/i), 'Test');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Type de permission actions/i)).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Type de permission targets/i)).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      await waitFor(() => {
        expect(screen.getByText(/Création échouée/i)).toBeInTheDocument();
      });
    });

    it('affiche un warning si permissions échouent mais profil créé', async () => {
      const user = userEvent.setup();
      mockProfilesService.putProfileActions.mockRejectedValue(new Error('Permissions actions échouées'));

      const onSuccess = vi.fn();
      renderWithApp(<ProfileWizard {...defaultProps} onSuccess={onSuccess} />);

      await user.type(screen.getByLabelText(/Nom du profil/i), 'Test');
      await user.type(screen.getByLabelText(/Groupe AD/i), 'GRP');
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Type de permission actions/i)).toBeInTheDocument());
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => expect(screen.getByText(/Type de permission targets/i)).toBeInTheDocument());

      await user.click(screen.getByRole('button', { name: /Enregistrer/i }));

      // onSuccess should still be called since profile was created
      await waitFor(() => {
        expect(onSuccess).toHaveBeenCalledWith(mockProfile);
      });
    });
  });

  describe('Modal behavior', () => {
    it('appelle onCancel quand on clique Annuler', async () => {
      const user = userEvent.setup();
      const onCancel = vi.fn();
      renderWithApp(<ProfileWizard {...defaultProps} onCancel={onCancel} />);

      await user.click(screen.getByRole('button', { name: /Annuler/i }));

      expect(onCancel).toHaveBeenCalled();
    });

    it('reset le state quand le modal se ferme', async () => {
      const { rerender } = renderWithApp(<ProfileWizard {...defaultProps} />);

      // Close modal
      rerender(<App><ProfileWizard {...defaultProps} open={false} /></App>);

      // Reopen
      rerender(<App><ProfileWizard {...defaultProps} open={true} /></App>);

      // Should be back to step 1 with empty fields (wait for Form to mount after reopen)
      await waitFor(() => {
        expect(screen.getByLabelText(/Nom du profil/i)).toHaveValue('');
      });
    });
  });

  describe('Story 21.6: Environment validation warning (AC6)', () => {
    it('shows warning when profile has environments not in inventory', async () => {
      const user = userEvent.setup();
      // Edit mode with environments including unknown one
      mockProfilesService.getProfileActions.mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: ['DEV', 'UNKNOWN_ENV'],
      });

      renderWithApp(<ProfileWizard {...defaultProps} editProfile={mockProfile} />);

      // Wait for data to load, then navigate to step 2
      await waitFor(() => {
        expect(screen.getByLabelText(/Nom du profil/i)).toHaveValue('Test Profile');
      });
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByText(/Attention : environnements non reconnus/)).toBeInTheDocument();
      });
      expect(screen.getAllByText(/UNKNOWN_ENV/).length).toBeGreaterThanOrEqual(1);
    });

    it('does not show warning when all environments are valid', async () => {
      const user = userEvent.setup();
      mockProfilesService.getProfileActions.mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: ['DEV', 'PROD'],
      });

      renderWithApp(<ProfileWizard {...defaultProps} editProfile={mockProfile} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Nom du profil/i)).toHaveValue('Test Profile');
      });
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/Environnements autorisés/i)).toBeInTheDocument();
      });
      expect(screen.queryByText(/Attention : environnements non reconnus/)).not.toBeInTheDocument();
    });

    it('does not show warning with empty environments', async () => {
      const user = userEvent.setup();
      mockProfilesService.getProfileActions.mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: [],
      });

      renderWithApp(<ProfileWizard {...defaultProps} editProfile={mockProfile} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Nom du profil/i)).toHaveValue('Test Profile');
      });
      await user.click(screen.getByRole('button', { name: /Suivant/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/Environnements autorisés/i)).toBeInTheDocument();
      });
      expect(screen.queryByText(/Attention : environnements non reconnus/)).not.toBeInTheDocument();
    });

    it('submit button remains enabled despite warning', async () => {
      const user = userEvent.setup();
      mockProfilesService.getProfileActions.mockResolvedValue({
        actions_type: 'all',
        action_ids: [],
        tag_patterns: [],
        environments: ['UNKNOWN_ENV'],
      });

      renderWithApp(<ProfileWizard {...defaultProps} editProfile={mockProfile} />);

      await waitFor(() => {
        expect(screen.getByLabelText(/Nom du profil/i)).toHaveValue('Test Profile');
      });

      // Navigate to step 2 to see warning
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => {
        expect(screen.getByText(/Attention : environnements non reconnus/)).toBeInTheDocument();
      });

      // Navigate to step 3 (Suivant should still work)
      await user.click(screen.getByRole('button', { name: /Suivant/i }));
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Enregistrer/i })).toBeInTheDocument();
      });

      // Submit button should not be disabled
      expect(screen.getByRole('button', { name: /Enregistrer/i })).not.toBeDisabled();
    });
  });
});

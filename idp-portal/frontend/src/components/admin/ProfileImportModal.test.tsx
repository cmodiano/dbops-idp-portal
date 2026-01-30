/**
 * Tests for ProfileImportModal (Story 2.26, Task 4).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { notification } from 'antd';
import { ProfileImportModal } from './ProfileImportModal';
import { PROFILE_YAML_TEMPLATE, PROFILE_YAML_TEMPLATE_FILENAME } from '../../utils/profileYamlTemplate';
import * as profilesService from '../../services/profiles_service';

vi.mock('../../services/profiles_service', () => ({
  importProfilesYaml: vi.fn(),
}));

const mockOnCancel = vi.fn();
const mockOnSuccess = vi.fn();

const defaultProps = {
  open: true,
  onCancel: mockOnCancel,
  onSuccess: mockOnSuccess,
};

describe('ProfileImportModal (Story 2.26)', () => {
  let createObjectURLMock: ReturnType<typeof vi.fn>;
  let revokeObjectURLMock: ReturnType<typeof vi.fn>;
  let clickMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    createObjectURLMock = vi.fn().mockReturnValue('blob:test-url');
    revokeObjectURLMock = vi.fn();
    clickMock = vi.fn();
    global.URL.createObjectURL = createObjectURLMock;
    global.URL.revokeObjectURL = revokeObjectURLMock;
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('Task 4.1 - Affichage du modal', () => {
    it('affiche le Collapse replie et le bouton "Telecharger template"', () => {
      render(<ProfileImportModal {...defaultProps} />);

      expect(screen.getByTestId('download-template-btn')).toBeInTheDocument();
      expect(screen.getByText('Telecharger template')).toBeInTheDocument();
      expect(screen.getByText('Voir le format YAML')).toBeInTheDocument();
      expect(screen.queryByTestId('yaml-example-content')).not.toBeInTheDocument();
    });

    it('affiche le champ de selection de fichier', () => {
      render(<ProfileImportModal {...defaultProps} />);

      expect(screen.getByTestId('file-input')).toBeInTheDocument();
      expect(screen.getByText(/Selectionnez un fichier/)).toBeInTheDocument();
    });

    it('affiche le bouton Importer', () => {
      render(<ProfileImportModal {...defaultProps} />);

      expect(screen.getByRole('button', { name: /Importer/i })).toBeInTheDocument();
    });
  });

  describe('Task 4.2 - Interaction Collapse', () => {
    it('deplie le bloc et affiche l\'exemple YAML au clic sur "Voir le format YAML"', async () => {
      const user = userEvent.setup();
      render(<ProfileImportModal {...defaultProps} />);

      expect(screen.queryByTestId('yaml-example-content')).not.toBeInTheDocument();

      await user.click(screen.getByText('Voir le format YAML'));

      await waitFor(() => {
        expect(screen.getByTestId('yaml-example-content')).toBeInTheDocument();
      });
      expect(screen.getByTestId('yaml-example-content').textContent).toContain('profiles:');
      expect(screen.getByTestId('yaml-example-content').textContent).toContain('name:');
      expect(screen.getByTestId('yaml-example-content').textContent).toContain('ad_group:');
    });

    it('l\'exemple contient les champs requis (AC3)', async () => {
      const user = userEvent.setup();
      render(<ProfileImportModal {...defaultProps} />);

      await user.click(screen.getByText('Voir le format YAML'));

      await waitFor(() => {
        expect(screen.getByTestId('yaml-example-content')).toBeInTheDocument();
      });

      const content = screen.getByTestId('yaml-example-content').textContent || '';
      expect(content).toContain('name:');
      expect(content).toContain('description:');
      expect(content).toContain('ad_group:');
      expect(content).toContain('is_admin:');
      expect(content).toContain('is_auditor:');
      expect(content).toContain('actions:');
      expect(content).toContain('type:');
      expect(content).toContain('patterns:');
      expect(content).toContain('targets:');
      expect(content).toContain('environments:');
    });
  });

  describe('Task 4.3 - Telechargement template', () => {
    it('declenche un telechargement avec le bon nom de fichier', async () => {
      const user = userEvent.setup();
      const mockAnchor = { href: '', download: '', click: clickMock };
      const originalCreateElement = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
        if (tagName === 'a') return mockAnchor as unknown as HTMLAnchorElement;
        return originalCreateElement(tagName);
      });

      render(<ProfileImportModal {...defaultProps} />);

      await user.click(screen.getByTestId('download-template-btn'));

      expect(createObjectURLMock).toHaveBeenCalled();
      expect(mockAnchor.download).toBe(PROFILE_YAML_TEMPLATE_FILENAME);
      expect(mockAnchor.download).toBe('profile-template.yaml');
      expect(clickMock).toHaveBeenCalled();
      expect(revokeObjectURLMock).toHaveBeenCalled();
    });

    it('le template telecharge contient le contenu YAML', async () => {
      const user = userEvent.setup();
      let capturedBlob: Blob | null = null;
      createObjectURLMock.mockImplementation((blob: Blob) => {
        capturedBlob = blob;
        return 'blob:test-url';
      });
      const mockAnchor = { href: '', download: '', click: clickMock };
      const originalCreateElement = document.createElement.bind(document);
      vi.spyOn(document, 'createElement').mockImplementation((tagName: string) => {
        if (tagName === 'a') return mockAnchor as unknown as HTMLAnchorElement;
        return originalCreateElement(tagName);
      });

      render(<ProfileImportModal {...defaultProps} />);

      await user.click(screen.getByTestId('download-template-btn'));

      expect(capturedBlob).not.toBeNull();
      const blobText = await capturedBlob!.text();
      expect(blobText).toBe(PROFILE_YAML_TEMPLATE);
      expect(blobText).toContain('profiles:');
    });
  });

  describe('Integration - Import flow', () => {
    it('affiche un warning si aucun fichier selectionne', async () => {
      const warningSpy = vi.spyOn(notification, 'warning').mockImplementation(() => {});

      const user = userEvent.setup();
      render(<ProfileImportModal {...defaultProps} />);

      await user.click(screen.getByRole('button', { name: /Importer/i }));

      expect(profilesService.importProfilesYaml).not.toHaveBeenCalled();
      expect(mockOnSuccess).not.toHaveBeenCalled();
      expect(warningSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: 'Fichier requis',
          description: 'Veuillez selectionner un fichier .yaml ou .yml',
        }),
      );

      warningSpy.mockRestore();
    });

    it('appelle importProfilesYaml avec le fichier selectionne', async () => {
      const user = userEvent.setup();
      vi.mocked(profilesService.importProfilesYaml).mockResolvedValue({ created: 1, updated: 2 });

      render(<ProfileImportModal {...defaultProps} />);

      const file = new File(['profiles: []'], 'test.yaml', { type: 'text/yaml' });
      const input = screen.getByTestId('file-input');
      await user.upload(input, file);

      await user.click(screen.getByRole('button', { name: /Importer/i }));

      await waitFor(() => {
        expect(profilesService.importProfilesYaml).toHaveBeenCalledWith(file);
      });
      expect(mockOnSuccess).toHaveBeenCalledWith(1, 2);
    });

  });
});

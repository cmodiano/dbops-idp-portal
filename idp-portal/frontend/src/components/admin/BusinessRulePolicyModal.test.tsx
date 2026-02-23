/**
 * Tests for BusinessRulePolicyModal (Story 34.14 — SOLID-FE-11).
 *
 * Modal de création/édition d'une règle métier prédéfinie (Story 28.4, AC#2).
 */

import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { App } from 'antd';
import { BusinessRulePolicyModal } from './BusinessRulePolicyModal';
import type { BusinessRulePolicyDetail, BusinessRulePolicyPayload } from '../../types/api';

const defaultProps = {
  open: true,
  onCancel: vi.fn(),
  onSave: vi.fn(),
  editPolicy: null as BusinessRulePolicyDetail | null,
  saving: false,
};

function renderModal(props: Partial<typeof defaultProps> = {}) {
  return render(
    <App>
      <BusinessRulePolicyModal {...defaultProps} {...props} />
    </App>,
  );
}

const mockEditPolicy: BusinessRulePolicyDetail = {
  id: 42,
  name: 'Règle Terraform SQL',
  description: 'Revue si sku_name modifié',
  is_active: true,
  policy_json: {
    on_step_output: [
      {
        when: { step_type: 'terraform_cloud', output_key: 'plan_output' },
        policy: {
          type: 'review_if_modified',
          require_review_if_modified: [
            { resource_type: 'azurerm_mssql_database', attribute_paths: ['sku_name'] },
          ],
          auto_approve_if_none_match: true,
        },
      },
    ],
  },
  created_at: '2026-02-20T10:00:00Z',
  updated_at: '2026-02-22T12:00:00Z',
};

const _validJson = JSON.stringify(
  {
    on_step_output: [
      {
        when: { step_type: 'aap' },
        policy: { type: 'review_if_modified', require_review_if_modified: [], auto_approve_if_none_match: true },
      },
    ],
  },
  null,
  2,
);

describe('BusinessRulePolicyModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendu modal ouverte/fermée', () => {
    it('ne rend pas le contenu quand open=false', () => {
      renderModal({ open: false });
      expect(screen.queryByText('Créer une règle métier')).not.toBeInTheDocument();
      expect(screen.queryByText('Modifier la règle métier')).not.toBeInTheDocument();
    });

    it('rend le contenu quand open=true', () => {
      renderModal({ open: true });
      expect(screen.getByText('Créer une règle métier')).toBeInTheDocument();
    });
  });

  describe('Titre création vs édition', () => {
    it("affiche 'Créer une règle métier' quand editPolicy=null", () => {
      renderModal({ editPolicy: null });
      expect(screen.getByText('Créer une règle métier')).toBeInTheDocument();
    });

    it("affiche 'Modifier la règle métier' quand editPolicy est défini", () => {
      renderModal({ editPolicy: mockEditPolicy });
      expect(screen.getByText('Modifier la règle métier')).toBeInTheDocument();
    });
  });

  describe('Population du formulaire depuis editPolicy', () => {
    it('pré-remplit le champ Nom depuis editPolicy', async () => {
      renderModal({ editPolicy: mockEditPolicy });
      await waitFor(() => {
        const nameInput = screen.getByPlaceholderText(/Revue Terraform SQL sku_name/i);
        expect(nameInput).toHaveValue('Règle Terraform SQL');
      });
    });

    it('pré-remplit la description depuis editPolicy', async () => {
      renderModal({ editPolicy: mockEditPolicy });
      await waitFor(() => {
        const descInput = screen.getByPlaceholderText(/Description de la règle/i);
        expect(descInput).toHaveValue('Revue si sku_name modifié');
      });
    });

    it('pré-remplit le JSON depuis editPolicy', async () => {
      renderModal({ editPolicy: mockEditPolicy });
      await waitFor(() => {
        const textarea = screen.getByPlaceholderText(/on_step_output/i);
        expect((textarea as HTMLTextAreaElement).value).toContain('on_step_output');
        expect((textarea as HTMLTextAreaElement).value).toContain('terraform_cloud');
      });
    });
  });

  describe("Boutons d'exemple JSON", () => {
    it("affiche les boutons d'exemple quand le textarea JSON est vide", () => {
      renderModal({ editPolicy: null });
      expect(screen.getByRole('button', { name: /insérer exemple terraform/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /insérer exemple aap/i })).toBeInTheDocument();
    });

    it("masque les boutons d'exemple quand editPolicy est défini (textarea non vide)", async () => {
      renderModal({ editPolicy: mockEditPolicy });
      await waitFor(() => {
        expect(
          screen.queryByRole('button', { name: /insérer exemple terraform/i }),
        ).not.toBeInTheDocument();
      });
    });

    it("insère le JSON Terraform au clic sur 'Insérer exemple Terraform'", async () => {
      const user = userEvent.setup();
      renderModal({ editPolicy: null });

      await user.click(screen.getByRole('button', { name: /insérer exemple terraform/i }));

      await waitFor(() => {
        const textarea = screen.getByPlaceholderText(/on_step_output/i);
        expect((textarea as HTMLTextAreaElement).value).toContain('terraform_cloud');
        expect((textarea as HTMLTextAreaElement).value).toContain('azurerm_mssql_database');
      });
    });

    it("insère le JSON AAP au clic sur 'Insérer exemple AAP'", async () => {
      const user = userEvent.setup();
      renderModal({ editPolicy: null });

      await user.click(screen.getByRole('button', { name: /insérer exemple aap/i }));

      await waitFor(() => {
        const textarea = screen.getByPlaceholderText(/on_step_output/i);
        expect((textarea as HTMLTextAreaElement).value).toContain('"step_type": "aap"');
      });
    });
  });

  describe("Validation JSON", () => {
    it("affiche une erreur quand le JSON est invalide", async () => {
      renderModal({ editPolicy: null });

      const textarea = screen.getByPlaceholderText(/on_step_output/i);
      // fireEvent.change évite les problèmes de caractères spéciaux de userEvent
      fireEvent.change(textarea, { target: { value: '{invalid json}' } });

      await waitFor(() => {
        expect(screen.getByText(/JSON invalide/i)).toBeInTheDocument();
      });
    });

    it("affiche une erreur quand 'on_step_output' est absent du JSON", async () => {
      renderModal({ editPolicy: null });

      const textarea = screen.getByPlaceholderText(/on_step_output/i);
      fireEvent.change(textarea, { target: { value: '{"other_key": []}' } });

      await waitFor(() => {
        expect(screen.getByText(/'on_step_output' doit être un tableau/i)).toBeInTheDocument();
      });
    });

    it("n'affiche pas d'erreur quand le JSON est valide", async () => {
      const user = userEvent.setup();
      renderModal({ editPolicy: null });

      // Saisir du JSON valide caractère par caractère prend du temps — simuler via click sur exemple
      await user.click(screen.getByRole('button', { name: /insérer exemple terraform/i }));

      await waitFor(() => {
        expect(screen.queryByText(/JSON invalide/i)).not.toBeInTheDocument();
        expect(screen.queryByText(/'on_step_output'/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Callback onCancel', () => {
    it("appelle onCancel au clic sur le bouton Annuler", async () => {
      const user = userEvent.setup();
      const onCancel = vi.fn();
      renderModal({ onCancel });
      await user.click(screen.getByRole('button', { name: /annuler/i }));
      expect(onCancel).toHaveBeenCalledTimes(1);
    });
  });

  describe('Callback onSave', () => {
    it("appelle onSave avec le bon payload lors de la création", async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);
      renderModal({ editPolicy: null, onSave });

      // Remplir le nom
      await user.type(
        screen.getByPlaceholderText(/Revue Terraform SQL sku_name/i),
        'Ma Nouvelle Règle',
      );

      // Insérer JSON valide via bouton exemple
      await user.click(screen.getByRole('button', { name: /insérer exemple terraform/i }));
      await waitFor(() => {
        const textarea = screen.getByPlaceholderText(/on_step_output/i);
        expect((textarea as HTMLTextAreaElement).value).toContain('on_step_output');
      });

      // Soumettre
      await user.click(screen.getByRole('button', { name: /créer/i }));

      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith(
          expect.objectContaining<Partial<BusinessRulePolicyPayload>>({
            name: 'Ma Nouvelle Règle',
            is_active: true,
          }),
        );
      });
    });

    it("appelle onSave avec le bon payload lors de l'édition", async () => {
      const user = userEvent.setup();
      const onSave = vi.fn().mockResolvedValue(undefined);
      renderModal({ editPolicy: mockEditPolicy, onSave });

      // Attendre le pré-remplissage
      await waitFor(() => {
        expect(
          (screen.getByPlaceholderText(/Revue Terraform SQL sku_name/i) as HTMLInputElement).value,
        ).toBe('Règle Terraform SQL');
      });

      // Soumettre directement
      await user.click(screen.getByRole('button', { name: /enregistrer/i }));

      await waitFor(() => {
        expect(onSave).toHaveBeenCalledWith(
          expect.objectContaining<Partial<BusinessRulePolicyPayload>>({
            name: 'Règle Terraform SQL',
            is_active: true,
          }),
        );
      });
    });
  });

  describe('État saving=true', () => {
    it('désactive le champ Nom quand saving=true', () => {
      renderModal({ saving: true });
      expect(screen.getByPlaceholderText(/Revue Terraform SQL sku_name/i)).toBeDisabled();
    });

    it('désactive le champ Description quand saving=true', () => {
      renderModal({ saving: true });
      expect(screen.getByPlaceholderText(/Description de la règle/i)).toBeDisabled();
    });

    it('désactive la TextArea JSON quand saving=true', () => {
      renderModal({ saving: true });
      expect(screen.getByPlaceholderText(/on_step_output/i)).toBeDisabled();
    });

    it('affiche le bouton principal en loading quand saving=true', () => {
      renderModal({ saving: true });
      const buttons = screen.getAllByRole('button');
      const saveButton = buttons.find(
        (b) => b.textContent?.includes('Créer') || b.textContent?.includes('Enregistrer'),
      );
      // Le bouton doit avoir la classe ant-btn-loading (Ant Design Button loading state)
      expect(saveButton).toHaveClass('ant-btn-loading');
    });
  });
});

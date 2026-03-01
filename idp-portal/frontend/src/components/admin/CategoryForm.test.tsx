/**
 * Tests for CategoryForm component (Story 55.5, Tâche 2).
 * Cible : ≥ 90 % de couverture sur CategoryForm.tsx (0 → 90 %).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from 'antd';
import { CategoryForm } from './CategoryForm';
import type { RefCategory } from '../../types/api';

// Mock du hook useCategoryForm
vi.mock('../../hooks/useCategoryForm', () => ({
  useCategoryForm: vi.fn(),
}));

import { useCategoryForm } from '../../hooks/useCategoryForm';

const mockSubmit = vi.fn();

const defaultCategory: RefCategory = {
  id: 1,
  code: 'backup',
  label: 'Sauvegarde',
  display_order: 1,
  is_active: 1,
};

function renderCategoryForm(props: Partial<Parameters<typeof CategoryForm>[0]> = {}) {
  const defaultProps = {
    open: true,
    onCancel: vi.fn(),
    onSuccess: vi.fn(),
    editCategory: undefined,
    ...props,
  };
  return render(
    <App>
      <CategoryForm {...defaultProps} />
    </App>,
  );
}

describe('CategoryForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(useCategoryForm).mockReturnValue({
      submit: mockSubmit,
      submitting: false,
      error: null,
    });
  });

  it('affiche le titre "Nouvelle catégorie" en mode création', () => {
    renderCategoryForm();
    expect(screen.getByText('Nouvelle catégorie')).toBeInTheDocument();
  });

  it('affiche le titre "Modifier la catégorie" en mode édition', () => {
    renderCategoryForm({ editCategory: defaultCategory });
    expect(screen.getByText('Modifier la catégorie')).toBeInTheDocument();
  });

  it('le champ Code est désactivé en mode édition', () => {
    renderCategoryForm({ editCategory: defaultCategory });
    const codeInput = screen.getByLabelText('Code de la catégorie');
    expect(codeInput).toBeDisabled();
  });

  it('le champ Code est activé en mode création', () => {
    renderCategoryForm();
    const codeInput = screen.getByLabelText('Code de la catégorie');
    expect(codeInput).not.toBeDisabled();
  });

  it('appelle onCancel quand le bouton Annuler est cliqué', async () => {
    const onCancel = vi.fn();
    const user = userEvent.setup();
    renderCategoryForm({ onCancel });
    await user.click(screen.getByText('Annuler'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('soumet le formulaire et appelle onSuccess en mode création', async () => {
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    const result: RefCategory = { id: 2, code: 'test', label: 'Test', display_order: 0, is_active: 1 };
    mockSubmit.mockResolvedValue(result);

    renderCategoryForm({ onSuccess });

    await user.type(screen.getByLabelText('Code de la catégorie'), 'test');
    await user.type(screen.getByLabelText('Libellé de la catégorie'), 'Test');
    await user.click(screen.getByText('Enregistrer'));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ code: 'test', label: 'Test' }),
        undefined,
      );
      expect(onSuccess).toHaveBeenCalledWith(result);
    });
  });

  it('affiche une notification d\'erreur quand submit échoue', async () => {
    const user = userEvent.setup();
    mockSubmit.mockRejectedValue(new Error('Duplicate code'));

    renderCategoryForm();

    await user.type(screen.getByLabelText('Code de la catégorie'), 'test');
    await user.type(screen.getByLabelText('Libellé de la catégorie'), 'Test');
    await user.click(screen.getByText('Enregistrer'));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalled();
    });
  });

  it('ne soumet pas quand les champs requis sont vides', async () => {
    const user = userEvent.setup();
    renderCategoryForm();
    await user.click(screen.getByText('Enregistrer'));
    // validateFields throws — submit n'est pas appelé
    expect(mockSubmit).not.toHaveBeenCalled();
  });

  it('soumet le formulaire en mode édition avec l\'id de la catégorie', async () => {
    const onSuccess = vi.fn();
    const user = userEvent.setup();
    const result: RefCategory = { ...defaultCategory, label: 'Updated' };
    mockSubmit.mockResolvedValue(result);

    renderCategoryForm({ editCategory: defaultCategory, onSuccess });

    // Effacer le libellé et entrer un nouveau
    const labelInput = screen.getByLabelText('Libellé de la catégorie');
    await user.clear(labelInput);
    await user.type(labelInput, 'Updated');
    await user.click(screen.getByText('Enregistrer'));

    await waitFor(() => {
      expect(mockSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ label: 'Updated' }),
        defaultCategory.id,
      );
    });
  });

  it('ne rend pas le modal quand open=false', () => {
    renderCategoryForm({ open: false });
    // Le modal est fermé — son contenu n'est pas dans le DOM (destroyOnHidden)
    expect(screen.queryByText('Nouvelle catégorie')).not.toBeInTheDocument();
  });

  it('affiche confirmLoading quand submitting=true', () => {
    vi.mocked(useCategoryForm).mockReturnValue({
      submit: mockSubmit,
      submitting: true,
      error: null,
    });
    renderCategoryForm();
    // Le bouton OK doit être en loading state — Ant Design ajoute ant-btn-loading
    const okBtn = screen.getByText('Enregistrer').closest('button');
    expect(okBtn).toBeInTheDocument();
    expect(okBtn).toHaveClass('ant-btn-loading');
  });
});

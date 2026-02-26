/**
 * ValidationReportPanel tests (Story 16.7, AC7).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ValidationReportPanel from './ValidationReportPanel';
import type { ValidationResult } from '../../utils/workflowValidation';
import { STYLE_TOKENS } from '../../theme/styleTokens';

describe('ValidationReportPanel', () => {
  const validResult: ValidationResult = {
    valid: true,
    errors: [],
  };

  const invalidResult: ValidationResult = {
    valid: false,
    errors: [
      { nodeId: 'a', type: 'error', message: 'Non atteignable depuis le début' },
      { nodeId: 'b', type: 'error', message: 'Boucle infinie détectée' },
      { nodeId: 'c', type: 'warning', message: 'Pas de chemin de sortie' },
    ],
  };

  it('renders nothing when validation is null', () => {
    const { container } = render(
      <ValidationReportPanel
        validation={null}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );
    expect(container.innerHTML).toBe('');
  });

  it('shows error and warning statistic titles', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Erreurs')).toBeInTheDocument();
  });

  it('shows error messages', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Non atteignable depuis le début')).toBeInTheDocument();
    expect(screen.getByText('Boucle infinie détectée')).toBeInTheDocument();
  });

  it('shows warning messages', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Pas de chemin de sortie')).toBeInTheDocument();
  });

  it('renders "Aller au nœud" buttons for each item with nodeId', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    const goToButtons = screen.getAllByText('Aller au nœud');
    expect(goToButtons.length).toBe(3); // 2 errors + 1 warning, all have nodeId
  });

  it('calls onGoToNode when "Aller au nœud" is clicked', async () => {
    const onGoToNode = vi.fn();
    const user = userEvent.setup();

    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={onGoToNode}
      />,
    );

    const goToButtons = screen.getAllByLabelText(/Aller au nœud/);
    await user.click(goToButtons[0]);

    expect(onGoToNode).toHaveBeenCalledWith('a');
  });

  it('shows success message when validation is valid', () => {
    render(
      <ValidationReportPanel
        validation={validResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Workflow valide')).toBeInTheDocument();
  });

  it('shows "Erreurs bloquantes" section divider', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Erreurs bloquantes')).toBeInTheDocument();
  });

  it('shows node IDs in error descriptions', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );

    expect(screen.getByText('Nœud : a')).toBeInTheDocument();
    expect(screen.getByText('Nœud : b')).toBeInTheDocument();
    expect(screen.getByText('Nœud : c')).toBeInTheDocument();
  });
});

describe('Story 46.4 — ValidationReportPanel contraste WCAG AA', () => {
  const validResult: ValidationResult = { valid: true, errors: [] };
  const invalidResult: ValidationResult = {
    valid: false,
    errors: [
      { nodeId: 'a', type: 'error', message: 'Erreur test' },
      { nodeId: 'b', type: 'warning', message: 'Avertissement test' },
    ],
  };

  it('success text uses STYLE_TOKENS.textSuccess (≥ 4.5:1 WCAG AA, not #52c41a)', () => {
    render(
      <ValidationReportPanel
        validation={validResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );
    const successText = screen.getByText('Workflow valide');
    // JSDOM serializes hex → rgb(): #166534 → rgb(22, 101, 52); #52c41a → rgb(82, 196, 26)
    const computedColor = window.getComputedStyle(successText).color;
    expect(computedColor).toBe('rgb(22, 101, 52)');     // STYLE_TOKENS.textSuccess
    expect(computedColor).not.toBe('rgb(82, 196, 26)'); // old inaccessible #52c41a
    // Also verify the token value itself is accessible
    expect(STYLE_TOKENS.textSuccess).toBe('#166534');
  });

  it('node ID text uses STYLE_TOKENS.textMuted (≥ 4.5:1, not #8c8c8c)', () => {
    render(
      <ValidationReportPanel
        validation={invalidResult}
        open={true}
        onClose={vi.fn()}
        onGoToNode={vi.fn()}
      />,
    );
    const nodeText = screen.getByText('Nœud : a');
    // JSDOM serializes hex → rgb(): #595959 → rgb(89, 89, 89); #8c8c8c → rgb(140, 140, 140)
    const computedColor = window.getComputedStyle(nodeText).color;
    expect(computedColor).toBe('rgb(89, 89, 89)');       // STYLE_TOKENS.textMuted
    expect(computedColor).not.toBe('rgb(140, 140, 140)'); // old inaccessible #8c8c8c
    expect(STYLE_TOKENS.textMuted).toBe('#595959');
  });

  it('STYLE_TOKENS.textSuccess is not #52c41a (WCAG AA compliance)', () => {
    expect(STYLE_TOKENS.textSuccess).not.toBe('#52c41a');
    expect(STYLE_TOKENS.textSuccess).toBe('#166534');
  });

  it('STYLE_TOKENS.textMuted is not #8c8c8c (WCAG AA compliance)', () => {
    expect(STYLE_TOKENS.textMuted).not.toBe('#8c8c8c');
    expect(STYLE_TOKENS.textMuted).toBe('#595959');
  });

  it('STYLE_TOKENS.iconWarning is not #fa8c16 (WCAG AA compliance ≥ 3:1)', () => {
    expect(STYLE_TOKENS.iconWarning).not.toBe('#fa8c16');
    expect(STYLE_TOKENS.iconWarning).toBe('#b45309');
  });

  it('STYLE_TOKENS.textError is not #ff4d4f for text (WCAG AA compliance)', () => {
    expect(STYLE_TOKENS.textError).not.toBe('#ff4d4f');
    expect(STYLE_TOKENS.textError).toBe('#b91c1c');
  });

  it('STYLE_TOKENS.iconError is not #ff4d4f (WCAG AA compliance ≥ 3:1)', () => {
    expect(STYLE_TOKENS.iconError).not.toBe('#ff4d4f');
    expect(STYLE_TOKENS.iconError).toBe('#dc2626');
  });
});

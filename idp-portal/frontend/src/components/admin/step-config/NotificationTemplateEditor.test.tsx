/**
 * Tests for NotificationTemplateEditor — Story 63.4 (AC3, AC6).
 *
 * Couvre :
 * - Rendu des champs send_email (recipient_email, subject, body)
 * - Rendu des champs send_teams (webhook_url, title, message, color)
 * - Clic sur un template prédéfini → pré-remplit les champs
 * - onChange appelé avec les bonnes valeurs sur modification
 * - VariablePicker présent sur subject/body et title/message
 * - Comportement disabled
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NotificationTemplateEditor } from './NotificationTemplateEditor';

vi.mock('../../../hooks/useOutputSchemas', () => ({
  useOutputSchemas: () => ({ availableVariables: [], loading: false, error: null }),
}));

const defaultEmailProps = {
  value: null,
  onChange: vi.fn(),
  operation: 'send_email' as const,
  currentStepId: 'notif-step',
  workflowId: 1,
};

const defaultTeamsProps = {
  value: null,
  onChange: vi.fn(),
  operation: 'send_teams' as const,
  currentStepId: 'notif-step',
  workflowId: 1,
};

describe('NotificationTemplateEditor — send_email (AC3)', () => {
  it('rend le champ recipient_email', () => {
    render(<NotificationTemplateEditor {...defaultEmailProps} />);
    expect(screen.getByPlaceholderText('dba@company.com')).toBeInTheDocument();
  });

  it('rend le champ subject', () => {
    render(<NotificationTemplateEditor {...defaultEmailProps} />);
    expect(screen.getByText('Sujet (subject)')).toBeInTheDocument();
  });

  it('rend le champ body (textarea)', () => {
    render(<NotificationTemplateEditor {...defaultEmailProps} />);
    expect(screen.getByText('Corps du message (body)')).toBeInTheDocument();
  });

  it('affiche le data-testid correct pour le rendu email', () => {
    const { container } = render(<NotificationTemplateEditor {...defaultEmailProps} />);
    expect(container.querySelector('[data-testid="notification-template-editor-email"]')).toBeInTheDocument();
  });

  it('appelle onChange avec les bonnes valeurs sur modification recipient_email', () => {
    const onChange = vi.fn();
    render(<NotificationTemplateEditor {...defaultEmailProps} onChange={onChange} />);
    const input = screen.getByPlaceholderText('dba@company.com');
    fireEvent.change(input, { target: { value: 'admin@company.com' } });
    expect(onChange).toHaveBeenCalledWith({ recipient_email: 'admin@company.com' });
  });

  it('pré-remplit subject et body au clic sur un template prédéfini Succès', () => {
    const onChange = vi.fn();
    render(<NotificationTemplateEditor {...defaultEmailProps} onChange={onChange} />);
    fireEvent.click(screen.getByText('✅ Succès'));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        subject: expect.stringContaining('action_name'),
        body: expect.stringContaining('execution_id'),
      }),
    );
  });

  it('pré-remplit subject et body au clic sur le template Échec', () => {
    const onChange = vi.fn();
    render(<NotificationTemplateEditor {...defaultEmailProps} onChange={onChange} />);
    fireEvent.click(screen.getByText('❌ Échec'));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        subject: expect.stringContaining('échoué'),
        body: expect.stringContaining('truncate'),
      }),
    );
  });

  it('rend le VariablePicker sur les champs recipient_email, cc, subject, body et attachments', () => {
    const { container } = render(
      <NotificationTemplateEditor {...defaultEmailProps} workflowId={1} />,
    );
    // recipient_email + cc + subject + body + attachments ont chacun un VariablePicker → au moins 5 (AC3, story 79.3)
    const pickers = container.querySelectorAll('[data-testid="variable-picker-trigger"]');
    expect(pickers.length).toBeGreaterThanOrEqual(5);
  });

  it('rend le VariablePicker sur le champ recipient_email (AC2, AC3 — story 79.1)', () => {
    const { container } = render(
      <NotificationTemplateEditor
        {...defaultEmailProps}
        workflowId={1}
        availableStepIds={['patch-step', 'check-step']}
      />,
    );
    // recipient_email + cc + subject + body + attachments ont chacun un VariablePicker → au moins 5
    const pickers = container.querySelectorAll('[data-testid="variable-picker-trigger"]');
    expect(pickers.length).toBeGreaterThanOrEqual(5);
  });

  it('rend le champ CC avec VariablePicker (AC3 — story 79.2)', () => {
    const { container } = render(
      <NotificationTemplateEditor {...defaultEmailProps} workflowId={1} />,
    );
    expect(screen.getByText('CC (optionnel, séparé par virgule)')).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/admin@company\.com/)).toBeInTheDocument();
    // Au moins 5 VariablePickers : recipient_email, cc, subject, body, attachments
    const pickers = container.querySelectorAll('[data-testid="variable-picker-trigger"]');
    expect(pickers.length).toBeGreaterThanOrEqual(5);
  });

  it('appelle onChange avec la valeur CC sur modification', () => {
    const onChange = vi.fn();
    render(<NotificationTemplateEditor {...defaultEmailProps} onChange={onChange} />);
    const ccInput = screen.getByPlaceholderText(/admin@company\.com/);
    fireEvent.change(ccInput, { target: { value: 'cc@company.com' } });
    expect(onChange).toHaveBeenCalledWith({ cc: 'cc@company.com' });
  });

  it('désactive les boutons de template quand disabled=true', () => {
    render(<NotificationTemplateEditor {...defaultEmailProps} disabled={true} />);
    expect(screen.getByText('✅ Succès').closest('button')).toBeDisabled();
    expect(screen.getByText('❌ Échec').closest('button')).toBeDisabled();
  });

  it('rend le champ attachments avec VariablePicker (AC5 — story 79.3)', () => {
    const { container } = render(
      <NotificationTemplateEditor {...defaultEmailProps} workflowId={1} />,
    );
    // Le champ attachments doit être présent
    expect(
      screen.getByPlaceholderText('{{ steps.patch.output.report_path }}'),
    ).toBeInTheDocument();
    // Au moins 5 VariablePickers : recipient_email, cc, subject, body, attachments
    const pickers = container.querySelectorAll('[data-testid="variable-picker-trigger"]');
    expect(pickers.length).toBeGreaterThanOrEqual(5);
  });

  it('appelle onChange avec la valeur attachments sur modification (story 79.3)', () => {
    const onChange = vi.fn();
    render(<NotificationTemplateEditor {...defaultEmailProps} onChange={onChange} />);
    const attachInput = screen.getByPlaceholderText('{{ steps.patch.output.report_path }}');
    fireEvent.change(attachInput, { target: { value: '/data/report.txt' } });
    expect(onChange).toHaveBeenCalledWith({ attachments: '/data/report.txt' });
  });

  it('désactive le champ attachments quand disabled=true (story 79.3)', () => {
    render(<NotificationTemplateEditor {...defaultEmailProps} disabled={true} />);
    const attachInput = screen.getByPlaceholderText('{{ steps.patch.output.report_path }}');
    expect(attachInput.closest('input')).toBeDisabled();
  });

  it('préserve la valeur CC lors du clic sur un template prédéfini (story 79.2)', () => {
    const onChange = vi.fn();
    render(
      <NotificationTemplateEditor
        {...defaultEmailProps}
        value={{ cc: 'admin@company.com', recipient_email: 'dba@company.com' }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByText('✅ Succès'));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        cc: 'admin@company.com',
        recipient_email: 'dba@company.com',
        subject: expect.stringContaining('action_name'),
        body: expect.stringContaining('execution_id'),
      }),
    );
  });
});

describe('NotificationTemplateEditor — send_teams (AC3)', () => {
  it('rend le champ webhook_url', () => {
    render(<NotificationTemplateEditor {...defaultTeamsProps} />);
    expect(screen.getByPlaceholderText('https://...')).toBeInTheDocument();
  });

  it('rend le champ title', () => {
    render(<NotificationTemplateEditor {...defaultTeamsProps} />);
    expect(screen.getByText('Titre (title)')).toBeInTheDocument();
  });

  it('rend le champ message (textarea)', () => {
    render(<NotificationTemplateEditor {...defaultTeamsProps} />);
    expect(screen.getByText('Message')).toBeInTheDocument();
  });

  it('affiche le data-testid correct pour le rendu Teams', () => {
    const { container } = render(<NotificationTemplateEditor {...defaultTeamsProps} />);
    expect(container.querySelector('[data-testid="notification-template-editor-teams"]')).toBeInTheDocument();
  });

  it('pré-remplit title et message au clic sur un template prédéfini Approbation', () => {
    const onChange = vi.fn();
    render(<NotificationTemplateEditor {...defaultTeamsProps} onChange={onChange} />);
    fireEvent.click(screen.getByText('🔔 Approbation'));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({
        title: expect.stringContaining('Approbation'),
        message: expect.stringContaining('approbation'),
      }),
    );
  });

  it('rend le VariablePicker sur les champs webhook_url, title et message', () => {
    const { container } = render(
      <NotificationTemplateEditor {...defaultTeamsProps} workflowId={1} />,
    );
    // webhook_url + title + message → au moins 3 VariablePickers pour send_teams (AC3, story 79.4)
    const pickers = container.querySelectorAll('[data-testid="variable-picker-trigger"]');
    expect(pickers.length).toBeGreaterThanOrEqual(3);
  });

  it('rend le champ color optionnel', () => {
    render(<NotificationTemplateEditor {...defaultTeamsProps} />);
    expect(screen.getByText('Couleur hex (color, optionnel)')).toBeInTheDocument();
  });

  it('appelle onChange avec les bonnes valeurs sur modification webhook_url', () => {
    const onChange = vi.fn();
    render(<NotificationTemplateEditor {...defaultTeamsProps} onChange={onChange} />);
    const input = screen.getByPlaceholderText('https://...');
    fireEvent.change(input, { target: { value: 'https://teams.example.com/webhook' } });
    expect(onChange).toHaveBeenCalledWith({ webhook_url: 'https://teams.example.com/webhook' });
  });

  it('désactive les champs quand disabled=true', () => {
    render(<NotificationTemplateEditor {...defaultTeamsProps} disabled={true} />);
    expect(screen.getByPlaceholderText('https://...').closest('input')).toBeDisabled();
  });

  it('rend le VariablePicker sur le champ webhook_url (AC3 — story 79.4)', () => {
    const { container } = render(
      <NotificationTemplateEditor {...defaultTeamsProps} workflowId={1} />,
    );
    // webhook_url + title + message → au moins 3 VariablePickers pour send_teams
    const pickers = container.querySelectorAll('[data-testid="variable-picker-trigger"]');
    expect(pickers.length).toBeGreaterThanOrEqual(3);
    // Vérifier que le champ webhook_url possède un picker adjacent (task 2.2 spec)
    const webhookLabel = screen.getByText('Webhook URL');
    expect(
      webhookLabel.parentElement?.querySelector('[data-testid="variable-picker-trigger"]'),
    ).toBeInTheDocument();
  });

  it('désactive le VariablePicker du champ webhook_url quand disabled=true (story 79.4)', () => {
    const { container } = render(
      <NotificationTemplateEditor {...defaultTeamsProps} disabled={true} workflowId={1} />,
    );
    const pickers = container.querySelectorAll('[data-testid="variable-picker-trigger"]');
    // Tous les pickers doivent afficher cursor: not-allowed (VariablePicker disabled = style visuel)
    pickers.forEach((picker) => {
      expect(picker).toHaveStyle({ cursor: 'not-allowed' });
    });
  });
});

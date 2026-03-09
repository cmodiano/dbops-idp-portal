/**
 * Tests for WorkflowBuilderToolbar — Story 26.5 AC8
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { App } from 'antd';
import { WorkflowBuilderToolbar, type WorkflowBuilderToolbarProps } from '../WorkflowBuilderToolbar';

const defaultProps: WorkflowBuilderToolbarProps = {
  disabled: false,
  exporting: false,
  validation: null,
  exportMenuItems: [
    { key: 'json', label: 'Exporter en JSON', icon: <span>J</span>, onClick: vi.fn() },
    { key: 'yaml', label: 'Exporter en YAML', icon: <span>Y</span>, onClick: vi.fn() },
    { key: 'image', label: "Exporter l'image", icon: <span>I</span>, onClick: vi.fn() },
  ],
  onImportClick: vi.fn(),
  onValidate: vi.fn(),
  onShowReport: vi.fn(),
  onClearValidation: vi.fn(),
};

const renderToolbar = (overrides: Partial<WorkflowBuilderToolbarProps> = {}) =>
  render(
    <App>
      <WorkflowBuilderToolbar {...defaultProps} {...overrides} />
    </App>
  );

describe('WorkflowBuilderToolbar', () => {
  it('renders all buttons (Importer, Exporter, Valider)', () => {
    renderToolbar();
    expect(screen.getByText('Importer')).toBeInTheDocument();
    expect(screen.getByText('Exporter')).toBeInTheDocument();
    expect(screen.getByText('Valider le workflow')).toBeInTheDocument();
  });

  it('renders helper text', () => {
    renderToolbar();
    expect(screen.getByText(/Glissez des actions/)).toBeInTheDocument();
  });

  it('disables Import button when disabled=true', () => {
    renderToolbar({ disabled: true });
    const importBtn = screen.getByRole('button', { name: 'Importer un workflow' });
    expect(importBtn).toBeDisabled();
  });

  it('disables Export button when disabled=true', () => {
    renderToolbar({ disabled: true });
    const exportBtn = screen.getByRole('button', { name: 'Exporter le workflow' });
    expect(exportBtn).toBeDisabled();
  });

  it('disables Export button when exporting=true', () => {
    renderToolbar({ exporting: true });
    const exportBtn = screen.getByRole('button', { name: 'Exporter le workflow' });
    expect(exportBtn).toBeDisabled();
  });

  it('calls onImportClick when Import button is clicked', () => {
    const onImportClick = vi.fn();
    renderToolbar({ onImportClick });
    fireEvent.click(screen.getByRole('button', { name: 'Importer un workflow' }));
    expect(onImportClick).toHaveBeenCalled();
  });

  it('calls onValidate when Validate button is clicked', () => {
    const onValidate = vi.fn();
    renderToolbar({ onValidate });
    fireEvent.click(screen.getByText('Valider le workflow'));
    expect(onValidate).toHaveBeenCalled();
  });

  it('does not show report/clear buttons when validation is null', () => {
    renderToolbar({ validation: null });
    expect(screen.queryByText('Voir le rapport')).not.toBeInTheDocument();
    expect(screen.queryByText('Effacer validation')).not.toBeInTheDocument();
  });

  it('shows report and clear buttons when validation is present', () => {
    renderToolbar({
      validation: { valid: true, errors: [] },
    });
    expect(screen.getByText('Voir le rapport')).toBeInTheDocument();
    expect(screen.getByText('Effacer validation')).toBeInTheDocument();
  });

  it('calls onShowReport when "Voir le rapport" button is clicked', () => {
    const onShowReport = vi.fn();
    renderToolbar({
      validation: { valid: true, errors: [] },
      onShowReport,
    });
    fireEvent.click(screen.getByText('Voir le rapport'));
    expect(onShowReport).toHaveBeenCalled();
  });

  it('calls onClearValidation when "Effacer validation" button is clicked', () => {
    const onClearValidation = vi.fn();
    renderToolbar({
      validation: { valid: true, errors: [] },
      onClearValidation,
    });
    fireEvent.click(screen.getByText('Effacer validation'));
    expect(onClearValidation).toHaveBeenCalled();
  });
});

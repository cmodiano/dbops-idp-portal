import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { AdminPreview } from './AdminPreview';
import type { ActionPreviewData } from '../../types/api';

const mockFormData: ActionPreviewData = {
  name: 'Creer PDB Oracle',
  description: 'Cree une nouvelle Pluggable Database Oracle.',
  engine: 'Oracle',
  platform: 'AAP',
  impact_level: 'medium',
  parameters_schema: {
    type: 'object',
    properties: {
      pdb_name: { type: 'string' },
    },
  },
  tags: ['oracle'],
};

describe('AdminPreview', () => {
  it('renders preview header with eye icon', () => {
    render(<AdminPreview formData={mockFormData} />);

    expect(screen.getByText('Preview')).toBeInTheDocument();
  });

  it('has aria-live="polite" for accessibility announcements', () => {
    const { container } = render(<AdminPreview formData={mockFormData} />);

    const liveRegion = container.querySelector('[aria-live="polite"]');
    expect(liveRegion).toBeInTheDocument();
  });

  it('renders ActionCard section with label', () => {
    render(<AdminPreview formData={mockFormData} />);

    expect(screen.getByText('Carte catalogue')).toBeInTheDocument();
  });

  it('renders ActionDrawerPreview section with label', () => {
    render(<AdminPreview formData={mockFormData} />);

    expect(screen.getByText('Fiche action (drawer)')).toBeInTheDocument();
  });

  it('renders ActionCard with action data', () => {
    render(<AdminPreview formData={mockFormData} />);

    const card = screen.getByRole('article');
    expect(card).toBeInTheDocument();
    expect(within(card).getByText('Creer PDB Oracle')).toBeInTheDocument();
  });

  it('renders ActionDrawerPreview with action data', () => {
    render(<AdminPreview formData={mockFormData} />);

    const region = screen.getByRole('region');
    expect(region).toBeInTheDocument();
    expect(within(region).getByText('Creer PDB Oracle')).toBeInTheDocument();
  });

  it('updates display when formData changes', () => {
    const { rerender } = render(<AdminPreview formData={mockFormData} />);

    expect(screen.getAllByText('Creer PDB Oracle').length).toBeGreaterThan(0);

    const updatedFormData: ActionPreviewData = {
      ...mockFormData,
      name: 'Updated Action Name',
    };

    rerender(<AdminPreview formData={updatedFormData} />);

    expect(screen.getAllByText('Updated Action Name').length).toBeGreaterThan(0);
    expect(screen.queryByText('Creer PDB Oracle')).not.toBeInTheDocument();
  });

  it('renders impact indicator from formData', () => {
    render(<AdminPreview formData={mockFormData} />);

    // Impact indicator appears in both ActionCard and ActionDrawerPreview
    const impactIndicators = screen.getAllByText('Moyen');
    expect(impactIndicators.length).toBeGreaterThanOrEqual(1);
  });

  it('renders enabled execute button in drawer preview (admin preview mode)', () => {
    render(<AdminPreview formData={mockFormData} />);

    // In admin preview mode, button is enabled to show what users with permission will see
    const button = screen.getByRole('button', { name: /Executer/i });
    expect(button).not.toBeDisabled();
  });
});

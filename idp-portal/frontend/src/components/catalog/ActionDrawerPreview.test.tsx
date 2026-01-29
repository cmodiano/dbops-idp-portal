import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ActionDrawerPreview } from './ActionDrawerPreview';
import type { ActionPreviewData } from '../../types/api';

const mockAction: ActionPreviewData = {
  name: 'Creer PDB Oracle',
  description: 'Cree une nouvelle Pluggable Database Oracle sur le serveur cible.',
  category: 'Provisioning',
  engine: 'Oracle',
  platform: 'AAP',
  impact_level: 'high',
  parameters_schema: {
    type: 'object',
    properties: {
      pdb_name: { type: 'string', description: 'Nom du PDB' },
      target_server: { type: 'string', description: 'Serveur cible' },
      size_gb: { type: 'number', description: 'Taille en GB' },
    },
  },
  tags: ['oracle', 'provisioning'],
};

describe('ActionDrawerPreview', () => {
  it('renders action name and description', () => {
    render(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('Creer PDB Oracle')).toBeInTheDocument();
    expect(screen.getByText(/Cree une nouvelle Pluggable Database/)).toBeInTheDocument();
  });

  it('renders with correct aria-label for accessibility', () => {
    render(<ActionDrawerPreview action={mockAction} />);

    const region = screen.getByRole('region');
    expect(region).toHaveAttribute('aria-label', 'Preview fiche action: Creer PDB Oracle');
  });

  it('renders impact indicator when impact_level is provided', () => {
    render(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('Eleve')).toBeInTheDocument();
  });

  it('renders engine, category, and platform metadata', () => {
    render(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('Oracle')).toBeInTheDocument();
    expect(screen.getByText('Provisioning')).toBeInTheDocument();
    expect(screen.getByText('AAP')).toBeInTheDocument();
  });

  it('renders parameters from parameters_schema', () => {
    render(<ActionDrawerPreview action={mockAction} />);

    expect(screen.getByText('pdb_name')).toBeInTheDocument();
    expect(screen.getByText('target_server')).toBeInTheDocument();
    expect(screen.getByText('size_gb')).toBeInTheDocument();
  });

  it('renders empty state when no parameters defined', () => {
    const actionWithoutParams = { ...mockAction, parameters_schema: null };
    render(<ActionDrawerPreview action={actionWithoutParams} />);

    expect(screen.getByText('Aucun parametre defini')).toBeInTheDocument();
  });

  it('renders disabled Execute button', () => {
    render(<ActionDrawerPreview action={mockAction} />);

    const button = screen.getByRole('button', { name: /Executer/i });
    expect(button).toBeInTheDocument();
    expect(button).toBeDisabled();
  });

  it('returns null when visible is false', () => {
    const { container } = render(<ActionDrawerPreview action={mockAction} visible={false} />);

    expect(container.firstChild).toBeNull();
  });

  it('renders placeholder text when name is empty', () => {
    const actionWithoutName = { ...mockAction, name: '' };
    render(<ActionDrawerPreview action={actionWithoutName} />);

    expect(screen.getByText('Sans nom')).toBeInTheDocument();
  });

  it('renders placeholder text when description is null', () => {
    const actionWithoutDesc = { ...mockAction, description: null };
    render(<ActionDrawerPreview action={actionWithoutDesc} />);

    expect(screen.getByText('Aucune description disponible.')).toBeInTheDocument();
  });

  it('has correct aria-label on disabled button', () => {
    render(<ActionDrawerPreview action={mockAction} />);

    const button = screen.getByRole('button', { name: /Executer/i });
    expect(button).toHaveAttribute('aria-label', 'Executer (desactive en mode preview)');
  });
});

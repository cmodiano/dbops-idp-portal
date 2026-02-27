import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ImpactIndicator } from './ImpactIndicator';
import { STYLE_TOKENS } from '../../theme/styleTokens';

describe('ImpactIndicator', () => {
  it('renders low impact with correct label and aria-label', () => {
    render(<ImpactIndicator level="low" />);

    expect(screen.getByText('Faible')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Impact: Faible');
  });

  it('renders medium impact with correct label and aria-label', () => {
    render(<ImpactIndicator level="medium" />);

    expect(screen.getByText('Moyen')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Impact: Moyen');
  });

  it('renders high impact with correct label and aria-label', () => {
    render(<ImpactIndicator level="high" />);

    expect(screen.getByText('Élevé')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Impact: Élevé');
  });

  it('renders critical impact with correct label and aria-label', () => {
    render(<ImpactIndicator level="critical" />);

    expect(screen.getByText('Critique')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', 'Impact: Critique');
  });

  it('renders small size variant with smaller styling', () => {
    render(<ImpactIndicator level="low" size="small" />);

    const tag = screen.getByText('Faible').closest('.ant-tag');
    expect(tag).toHaveStyle({ fontSize: '12px' });
  });

  it('renders default size without small styling override', () => {
    render(<ImpactIndicator level="low" size="default" />);

    // Just verify the tag renders correctly - default styling is managed by Ant Design
    expect(screen.getByText('Faible')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
  });
});

describe('Story 46.3 — Standardisation des couleurs de badges', () => {
  it('les 4 niveaux d\'impact ont des couleurs distinctes dans STYLE_TOKENS', () => {
    const { low, medium, high, critical } = STYLE_TOKENS.impactColor;

    // medium doit être #EAB308 (yellow-500) — CHANGÉ depuis #F59E0B (Story 46.3)
    expect(medium).toBe('#EAB308');

    // Chaque niveau doit avoir une couleur unique (non-régression)
    const colors = [low, medium, high, critical];
    const uniqueColors = new Set(colors);
    expect(uniqueColors.size).toBe(4);
  });

  it('la palette d\'environnement est définie et cohérente dans STYLE_TOKENS', () => {
    const { environmentBadgeColor } = STYLE_TOKENS;

    // Valeurs attendues (Story 46.3)
    expect(environmentBadgeColor.production).toBe('#EF4444');
    expect(environmentBadgeColor.prod).toBe('#EF4444');
    expect(environmentBadgeColor.staging).toBe('#F97316');
    expect(environmentBadgeColor.dev).toBe('#3B82F6');
    expect(environmentBadgeColor.test).toBe('#8B5CF6');
    expect(environmentBadgeColor.default).toBe('#6B7280');
  });
});

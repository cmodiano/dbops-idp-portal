/**
 * Tests for ProfilesTable (Story 2.9, AC #3).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProfilesTable } from './ProfilesTable';
import type { ProfileListItem } from '../../types/api';

const items: ProfileListItem[] = [
  {
    id: 1,
    name: 'Assurance',
    ad_group: 'GRP-IDP-ASSURANCE',
    permission_count: 0,
    created_at: '2026-01-28T10:00:00Z',
  },
];

const mockOnEdit = vi.fn();
const mockOnDelete = vi.fn().mockResolvedValue(undefined);
const mockOnNew = vi.fn();

const defaultProps = {
  dataSource: items,
  loading: false,
  onEdit: mockOnEdit,
  onDelete: mockOnDelete,
  onNew: mockOnNew,
};

describe('ProfilesTable', () => {
  it('renders table with columns Nom, Groupe AD, Permissions, Date de création', () => {
    render(<ProfilesTable {...defaultProps} />);
    expect(screen.getByText('Nom')).toBeInTheDocument();
    expect(screen.getByText('Groupe AD')).toBeInTheDocument();
    expect(screen.getByText('Permissions')).toBeInTheDocument();
    expect(screen.getByText('Date de création')).toBeInTheDocument();
  });

  it('renders profiles and Nouveau profil button', () => {
    render(<ProfilesTable {...defaultProps} />);
    expect(screen.getByText('Assurance')).toBeInTheDocument();
    expect(screen.getByText('GRP-IDP-ASSURANCE')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Nouveau profil/i })).toBeInTheDocument();
  });

  it('calls onNew when Nouveau profil clicked', async () => {
    const user = userEvent.setup();
    render(<ProfilesTable {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Nouveau profil/i }));
    expect(mockOnNew).toHaveBeenCalled();
  });

  it('calls onEdit when Modifier clicked', async () => {
    const user = userEvent.setup();
    render(<ProfilesTable {...defaultProps} />);
    await user.click(screen.getByRole('button', { name: /Modifier/i }));
    expect(mockOnEdit).toHaveBeenCalledWith(items[0]);
  });

  it('shows empty state when no profiles', () => {
    render(<ProfilesTable {...defaultProps} dataSource={[]} />);
    expect(screen.getByText('Aucun profil')).toBeInTheDocument();
  });
});

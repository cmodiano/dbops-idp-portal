import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App as AntApp } from 'antd';

import ApiKeysPage from './ApiKeysPage';
import { useApiKeys } from '../hooks/useApiKeys';

vi.mock('../hooks/useApiKeys', () => ({
  useApiKeys: vi.fn(),
}));

const mockUseApiKeys = useApiKeys as ReturnType<typeof vi.fn>;

describe('ApiKeysPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders keys list and warning for created raw key', () => {
    mockUseApiKeys.mockReturnValue({
      keys: [
        {
          id: 1,
          name: 'CI Key',
          scope: 'executions',
          created_at: '2026-02-26T10:00:00Z',
          expires_at: null,
          is_active: true,
          status: 'active',
        },
      ],
      loading: false,
      error: null,
      saving: false,
      lastCreatedRawKey: 'raw-key-only-once',
      create: vi.fn(),
      revoke: vi.fn(),
      clearRawKey: vi.fn(),
    });

    render(
      <AntApp>
        <ApiKeysPage />
      </AntApp>,
    );

    expect(screen.getByRole('heading', { name: /Mes clés API/i })).toBeInTheDocument();
    expect(screen.getByText('CI Key')).toBeInTheDocument();
    expect(screen.getByText(/Copiez maintenant, elle ne sera plus affichée/i)).toBeInTheDocument();
    expect(screen.getByText('raw-key-only-once')).toBeInTheDocument();
  });

  it('calls revoke action when clicking Révoquer', async () => {
    const user = userEvent.setup();
    const revoke = vi.fn().mockResolvedValue(undefined);

    mockUseApiKeys.mockReturnValue({
      keys: [
        {
          id: 11,
          name: 'Deploy Key',
          scope: 'catalog',
          created_at: '2026-02-26T10:00:00Z',
          expires_at: null,
          is_active: true,
          status: 'active',
        },
      ],
      loading: false,
      error: null,
      saving: false,
      lastCreatedRawKey: null,
      create: vi.fn(),
      revoke,
      clearRawKey: vi.fn(),
    });

    render(
      <AntApp>
        <ApiKeysPage />
      </AntApp>,
    );

    await user.click(screen.getByRole('button', { name: /^Révoquer$/i }));
    await user.click(screen.getAllByRole('button', { name: /^Révoquer$/i })[1]);
    expect(revoke).toHaveBeenCalledWith(11);
  });
});

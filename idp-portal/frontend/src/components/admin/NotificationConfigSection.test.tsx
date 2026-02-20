/**
 * Tests for NotificationConfigSection (Story 31.8).
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { NotificationConfigSection } from './NotificationConfigSection';
import type { NotificationConfig } from '../../types/api/catalog';

const emptyConfig: NotificationConfig = {
  channels: [
    { type: 'email', enabled: false, conditions: [], recipient: 'requester' },
    { type: 'teams', enabled: false, conditions: [], webhook_url_ref: '' },
    { type: 'page_dba', enabled: false, conditions: [], api_url: '' },
  ],
  page_individual_enabled: false,
};

describe('NotificationConfigSection', () => {
  it('renders all four channel headers', () => {
    render(<NotificationConfigSection value={null} onChange={vi.fn()} />);
    expect(screen.getByText('Email')).toBeInTheDocument();
    expect(screen.getByText('Teams (webhook)')).toBeInTheDocument();
    expect(screen.getByText('Page individuel')).toBeInTheDocument();
    expect(screen.getByText('Page DBA on-call')).toBeInTheDocument();
  });

  it('does not show email details when email is disabled', () => {
    render(<NotificationConfigSection value={emptyConfig} onChange={vi.fn()} />);
    expect(screen.queryByLabelText('Destinataire email')).not.toBeInTheDocument();
  });

  it('shows email details when email is enabled', () => {
    const config: NotificationConfig = {
      ...emptyConfig,
      channels: emptyConfig.channels.map((ch) =>
        ch.type === 'email' ? { ...ch, enabled: true } : ch,
      ),
    };
    render(<NotificationConfigSection value={config} onChange={vi.fn()} />);
    expect(screen.getByLabelText('Destinataire email')).toBeInTheDocument();
  });

  it('calls onChange when toggling email switch', () => {
    const onChange = vi.fn();
    render(<NotificationConfigSection value={emptyConfig} onChange={onChange} />);
    const emailSwitch = screen.getByLabelText('Activer les notifications email');
    fireEvent.click(emailSwitch);
    expect(onChange).toHaveBeenCalledTimes(1);
    const newConfig = onChange.mock.calls[0][0] as NotificationConfig;
    const emailChannel = newConfig.channels.find((ch) => ch.type === 'email');
    expect(emailChannel?.enabled).toBe(true);
  });

  it('calls onChange when toggling teams switch', () => {
    const onChange = vi.fn();
    render(<NotificationConfigSection value={emptyConfig} onChange={onChange} />);
    const teamsSwitch = screen.getByLabelText('Activer les notifications Teams');
    fireEvent.click(teamsSwitch);
    expect(onChange).toHaveBeenCalledTimes(1);
    const newConfig = onChange.mock.calls[0][0] as NotificationConfig;
    const teamsChannel = newConfig.channels.find((ch) => ch.type === 'teams');
    expect(teamsChannel?.enabled).toBe(true);
  });

  it('shows webhook URL input when teams is enabled', () => {
    const config: NotificationConfig = {
      ...emptyConfig,
      channels: emptyConfig.channels.map((ch) =>
        ch.type === 'teams' ? { ...ch, enabled: true } : ch,
      ),
    };
    render(<NotificationConfigSection value={config} onChange={vi.fn()} />);
    expect(screen.getByLabelText('URL webhook Teams')).toBeInTheDocument();
  });

  it('calls onChange when toggling page_individual', () => {
    const onChange = vi.fn();
    render(<NotificationConfigSection value={emptyConfig} onChange={onChange} />);
    const pageSwitch = screen.getByLabelText('Activer le page individuel');
    fireEvent.click(pageSwitch);
    expect(onChange).toHaveBeenCalledTimes(1);
    const newConfig = onChange.mock.calls[0][0] as NotificationConfig;
    expect(newConfig.page_individual_enabled).toBe(true);
  });

  it('calls onChange when toggling page_dba', () => {
    const onChange = vi.fn();
    render(<NotificationConfigSection value={emptyConfig} onChange={onChange} />);
    const dbaSwitch = screen.getByLabelText('Activer le page DBA');
    fireEvent.click(dbaSwitch);
    expect(onChange).toHaveBeenCalledTimes(1);
    const newConfig = onChange.mock.calls[0][0] as NotificationConfig;
    const dbaChannel = newConfig.channels.find((ch) => ch.type === 'page_dba');
    expect(dbaChannel?.enabled).toBe(true);
  });

  it('shows info alert when page_individual is enabled', () => {
    const config: NotificationConfig = {
      ...emptyConfig,
      page_individual_enabled: true,
    };
    render(<NotificationConfigSection value={config} onChange={vi.fn()} />);
    expect(screen.getByText(/prod.*critical/i)).toBeInTheDocument();
  });

  it('shows info alert when page_dba is enabled', () => {
    const config: NotificationConfig = {
      ...emptyConfig,
      channels: emptyConfig.channels.map((ch) =>
        ch.type === 'page_dba' ? { ...ch, enabled: true } : ch,
      ),
    };
    render(<NotificationConfigSection value={config} onChange={vi.fn()} />);
    expect(screen.getByText(/prod.*critical/i)).toBeInTheDocument();
  });

  it('does not show info alert when no page is enabled', () => {
    render(<NotificationConfigSection value={emptyConfig} onChange={vi.fn()} />);
    expect(screen.queryByText(/prod.*critical/i)).not.toBeInTheDocument();
  });

  it('renders with null value (uses defaults)', () => {
    render(<NotificationConfigSection value={null} onChange={vi.fn()} />);
    // All switches should be off (unchecked)
    expect(screen.getByLabelText('Activer les notifications email')).not.toBeChecked();
    expect(screen.getByLabelText('Activer les notifications Teams')).not.toBeChecked();
    expect(screen.getByLabelText('Activer le page individuel')).not.toBeChecked();
    expect(screen.getByLabelText('Activer le page DBA')).not.toBeChecked();
  });

  it('shows DBA API URL input when page_dba is enabled', () => {
    const config: NotificationConfig = {
      ...emptyConfig,
      channels: emptyConfig.channels.map((ch) =>
        ch.type === 'page_dba' ? { ...ch, enabled: true } : ch,
      ),
    };
    render(<NotificationConfigSection value={config} onChange={vi.fn()} />);
    expect(screen.getByLabelText('URL API page DBA')).toBeInTheDocument();
  });
});

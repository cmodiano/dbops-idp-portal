/**
 * Tests for executionRenderers utility functions (Story 9.9).
 *
 * Story 9.9:
 * AC1-AC3: renderStatusIndicator - Status indicator badges (pulsing vs fixed).
 * AC4: renderEngineIcon - Technology column with engine/workflow icons.
 * AC5: renderIntegrationIcon - Platform column with integration icons.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  renderStatusIndicator,
  renderEngineIcon,
  renderIntegrationIcon,
  STATUS_CONFIG,
  ENGINE_ICONS_CONFIG,
} from './executionRenderers';
import type { ExecutionStatusType, ActionEngine, ItemType } from '../types/api';

describe('executionRenderers', () => {
  describe('renderStatusIndicator (AC1-AC3)', () => {
    it('renders processing badge for RUNNING status', () => {
      const { container } = render(<>{renderStatusIndicator('RUNNING')}</>);
      const badge = container.querySelector('.ant-badge-status-processing');
      expect(badge).toBeInTheDocument();
    });

    it('renders processing badge for SUBMITTED status', () => {
      const { container } = render(<>{renderStatusIndicator('SUBMITTED')}</>);
      const badge = container.querySelector('.ant-badge-status-processing');
      expect(badge).toBeInTheDocument();
    });

    it('renders processing badge for PENDING_APPROVAL status', () => {
      const { container } = render(<>{renderStatusIndicator('PENDING_APPROVAL')}</>);
      const badge = container.querySelector('.ant-badge-status-processing');
      expect(badge).toBeInTheDocument();
    });

    it('renders success badge for COMPLETED status', () => {
      const { container } = render(<>{renderStatusIndicator('COMPLETED')}</>);
      const badge = container.querySelector('.ant-badge-status-success');
      expect(badge).toBeInTheDocument();
    });

    it('renders error badge for FAILED status', () => {
      const { container } = render(<>{renderStatusIndicator('FAILED')}</>);
      const badge = container.querySelector('.ant-badge-status-error');
      expect(badge).toBeInTheDocument();
    });

    it('renders default badge for CANCELLED status', () => {
      const { container } = render(<>{renderStatusIndicator('CANCELLED')}</>);
      const badge = container.querySelector('.ant-badge-status-default');
      expect(badge).toBeInTheDocument();
    });

    it('renders warning badge for REJECTED status', () => {
      const { container } = render(<>{renderStatusIndicator('REJECTED')}</>);
      const badge = container.querySelector('.ant-badge-status-warning');
      expect(badge).toBeInTheDocument();
    });

    it('applies larger scale transform for running statuses', () => {
      const { container } = render(<>{renderStatusIndicator('RUNNING')}</>);
      const badge = container.querySelector('.ant-badge');
      expect(badge).toHaveStyle({ transform: 'scale(1.4)' });
    });

    it('applies smaller scale transform for terminal statuses', () => {
      const { container } = render(<>{renderStatusIndicator('COMPLETED')}</>);
      const badge = container.querySelector('.ant-badge');
      expect(badge).toHaveStyle({ transform: 'scale(1.2)' });
    });
  });

  describe('renderEngineIcon (AC4)', () => {
    it('renders Oracle icon with red color', () => {
      const { container } = render(<>{renderEngineIcon('Oracle', 'action')}</>);
      const icon = container.querySelector('[class*="anticon-database"]');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveStyle({ color: '#EF4444' });
    });

    it('renders SQL Server icon with blue color', () => {
      const { container } = render(<>{renderEngineIcon('SQL Server', 'action')}</>);
      const icon = container.querySelector('[class*="anticon-cloud-server"]');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveStyle({ color: '#3B82F6' });
    });

    it('renders DB2 icon with green color', () => {
      const { container } = render(<>{renderEngineIcon('DB2', 'action')}</>);
      const icon = container.querySelector('[class*="anticon-hdd"]');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveStyle({ color: '#10B981' });
    });

    it('renders workflow icon with purple color when item_type is workflow', () => {
      const { container } = render(<>{renderEngineIcon('Oracle', 'workflow')}</>);
      const icon = container.querySelector('[class*="anticon-apartment"]');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveStyle({ color: '#722ed1' });
    });

    it('renders workflow icon even when engine is null', () => {
      const { container } = render(<>{renderEngineIcon(null, 'workflow')}</>);
      const icon = container.querySelector('[class*="anticon-apartment"]');
      expect(icon).toBeInTheDocument();
    });

    it('renders fallback dash when engine is null and item_type is action', () => {
      render(<>{renderEngineIcon(null, 'action')}</>);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('renders fallback dash when engine is undefined', () => {
      render(<>{renderEngineIcon(undefined, undefined)}</>);
      expect(screen.getByText('—')).toBeInTheDocument();
    });
  });

  describe('renderIntegrationIcon (AC5)', () => {
    it('renders Avatar with icon URL when integrationIcon is provided', () => {
      const { container } = render(
        <>{renderIntegrationIcon('AAP Production', '/icons/aap.png')}</>
      );
      const avatar = container.querySelector('.ant-avatar');
      expect(avatar).toBeInTheDocument();
      const img = container.querySelector('img');
      expect(img).toHaveAttribute('src', '/icons/aap.png');
    });

    it('renders Avatar with ApiOutlined fallback when integrationIcon is null', () => {
      const { container } = render(
        <>{renderIntegrationIcon('AAP Production', null)}</>
      );
      const avatar = container.querySelector('.ant-avatar');
      expect(avatar).toBeInTheDocument();
      const fallbackIcon = container.querySelector('[class*="anticon-api"]');
      expect(fallbackIcon).toBeInTheDocument();
    });

    it('renders fallback dash when integrationName is null', () => {
      render(<>{renderIntegrationIcon(null, null)}</>);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('renders fallback dash when integrationName is undefined', () => {
      render(<>{renderIntegrationIcon(undefined, undefined)}</>);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('renders square-shaped Avatar', () => {
      const { container } = render(
        <>{renderIntegrationIcon('Terraform Cloud', '/icons/tf.png')}</>
      );
      const avatar = container.querySelector('.ant-avatar-square');
      expect(avatar).toBeInTheDocument();
    });
  });

  describe('STATUS_CONFIG', () => {
    it('has all execution status types defined', () => {
      const statuses: ExecutionStatusType[] = [
        'SUBMITTED',
        'PENDING_APPROVAL',
        'RUNNING',
        'COMPLETED',
        'FAILED',
        'CANCELLED',
        'REJECTED',
      ];

      statuses.forEach((status) => {
        expect(STATUS_CONFIG).toHaveProperty(status);
        expect(STATUS_CONFIG[status]).toHaveProperty('label');
        expect(STATUS_CONFIG[status]).toHaveProperty('Icon');
        expect(STATUS_CONFIG[status]).toHaveProperty('color');
      });
    });

    it('has French labels for all statuses', () => {
      expect(STATUS_CONFIG.SUBMITTED.label).toBe('Soumise');
      expect(STATUS_CONFIG.PENDING_APPROVAL.label).toBe('En attente');
      expect(STATUS_CONFIG.RUNNING.label).toBe('En cours');
      expect(STATUS_CONFIG.COMPLETED.label).toBe('Terminée');
      expect(STATUS_CONFIG.FAILED.label).toBe('Échouée');
      expect(STATUS_CONFIG.CANCELLED.label).toBe('Annulée');
      expect(STATUS_CONFIG.REJECTED.label).toBe('Rejetée');
    });
  });

  describe('ENGINE_ICONS_CONFIG', () => {
    it('has all engine types defined', () => {
      const engines: ActionEngine[] = ['Oracle', 'SQL Server', 'DB2'];

      engines.forEach((engine) => {
        expect(ENGINE_ICONS_CONFIG).toHaveProperty(engine);
        expect(ENGINE_ICONS_CONFIG[engine]).toHaveProperty('Icon');
        expect(ENGINE_ICONS_CONFIG[engine]).toHaveProperty('color');
      });
    });
  });
});

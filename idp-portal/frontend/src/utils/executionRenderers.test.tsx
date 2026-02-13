/**
 * Tests for executionRenderers utility functions (Story 9.9).
 *
 * Story 9.9:
 * AC1-AC3: renderStatusIndicator - Status indicator badges (pulsing vs fixed).
 * AC4: renderEngineIcon - Technology column with engine/workflow icons.
 * AC5: renderPlatformIcon - Platform column with execution platform icons (action.platform).
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import {
  renderStatusIndicator,
  renderEngineIcon,
  renderPlatformIcon,
  renderPlateformeIcon,
  STATUS_CONFIG,
  ENGINE_ICONS_CONFIG,
  PLATFORM_ICONS_CONFIG,
} from './executionRenderers';
import type { ExecutionStatusType, ActionEngine, ActionPlatform } from '../types/api';

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

    it('renders error badge for INTEGRATION_ERROR status (Story 18.6)', () => {
      const { container } = render(<>{renderStatusIndicator('INTEGRATION_ERROR')}</>);
      const badge = container.querySelector('.ant-badge-status-error');
      expect(badge).toBeInTheDocument();
      expect(screen.getByText('Erreur intégration')).toBeInTheDocument();
    });

    it('INTEGRATION_ERROR and FAILED both use error badge (Story 18.6)', () => {
      const { container: c1 } = render(<>{renderStatusIndicator('INTEGRATION_ERROR')}</>);
      const { container: c2 } = render(<>{renderStatusIndicator('FAILED')}</>);
      expect(c1.querySelector('.ant-badge-status-error')).toBeInTheDocument();
      expect(c2.querySelector('.ant-badge-status-error')).toBeInTheDocument();
    });

    it('applies larger scale transform for running statuses', () => {
      const { container } = render(<>{renderStatusIndicator('RUNNING')}</>);
      const badge = container.querySelector('.ant-badge');
      expect(badge).toHaveStyle({ transform: 'scale(2.0)' });
    });

    it('applies smaller scale transform for terminal statuses', () => {
      const { container } = render(<>{renderStatusIndicator('COMPLETED')}</>);
      const badge = container.querySelector('.ant-badge');
      expect(badge).toHaveStyle({ transform: 'scale(1.3)' });
    });
  });

  describe('renderEngineIcon (AC4)', () => {
    it('renders Oracle icon (SVG)', () => {
      const { container } = render(<>{renderEngineIcon('Oracle', 'action')}</>);
      const img = container.querySelector('img[src*="oracle"]');
      expect(img).toBeInTheDocument();
      expect(img).toHaveAttribute('width', '40');
    });

    it('renders SQL Server icon (SVG)', () => {
      const { container } = render(<>{renderEngineIcon('SQL Server', 'action')}</>);
      const img = container.querySelector('img[src*="microsoft-sql-server"]');
      expect(img).toBeInTheDocument();
    });

    it('renders DB2 icon (SVG)', () => {
      const { container } = render(<>{renderEngineIcon('DB2', 'action')}</>);
      const img = container.querySelector('img[src*="db2"]');
      expect(img).toBeInTheDocument();
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

  describe('renderPlatformIcon (AC5)', () => {
    it('renders AAP icon with red color', () => {
      const { container } = render(<>{renderPlatformIcon('AAP')}</>);
      const icon = container.querySelector('[class*="anticon-rocket"]');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveStyle({ color: '#EE0000' });
    });

    it('renders GitHub Actions icon with dark color', () => {
      const { container } = render(<>{renderPlatformIcon('GitHub Actions')}</>);
      const icon = container.querySelector('[class*="anticon-thunderbolt"]');
      expect(icon).toBeInTheDocument();
    });

    it('renders Terraform icon with purple color', () => {
      const { container } = render(<>{renderPlatformIcon('Terraform')}</>);
      const icon = container.querySelector('[class*="anticon-apartment"]');
      expect(icon).toBeInTheDocument();
    });

    it('renders fallback dash when platform is null', () => {
      render(<>{renderPlatformIcon(null)}</>);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('renders fallback dash when platform is undefined', () => {
      render(<>{renderPlatformIcon(undefined)}</>);
      expect(screen.getByText('—')).toBeInTheDocument();
    });

    it('renders unknown platform as text', () => {
      render(<>{renderPlatformIcon('Custom Platform')}</>);
      expect(screen.getByText('Custom Platform')).toBeInTheDocument();
    });
  });

  describe('renderPlateformeIcon (AC5)', () => {
    it('prefers integration icon when integration has icon', () => {
      const { container } = render(
        <>{renderPlateformeIcon('AAP Prod', '/icons/custom.png', 'AAP')}</>
      );
      const avatar = container.querySelector('.ant-avatar');
      expect(avatar).toBeInTheDocument();
      const img = container.querySelector('img');
      expect(img).toHaveAttribute('src', expect.stringContaining('/icons/custom.png'));
    });

    it('falls back to platform icon when no integration', () => {
      const { container } = render(
        <>{renderPlateformeIcon(null, null, 'AAP')}</>
      );
      const icon = container.querySelector('[class*="anticon-rocket"]');
      expect(icon).toBeInTheDocument();
    });

    it('falls back to platform icon when integration has name but no icon', () => {
      const { container } = render(
        <>{renderPlateformeIcon('AAP Prod', null, 'AAP')}</>
      );
      // No integration_icon, no integrationIconsMap → platform icon (Rocket)
      const icon = container.querySelector('[class*="anticon-rocket"]');
      expect(icon).toBeInTheDocument();
    });

    it('uses integrationIconsMap fallback when integration has name but no icon', () => {
      const { container } = render(
        <>{
          renderPlateformeIcon(
            'AAP Prod',
            null,
            'AAP',
            { 'AAP Prod': '/icons/aap-custom.png' },
          )
        }</>
      );
      const avatar = container.querySelector('.ant-avatar');
      expect(avatar).toBeInTheDocument();
      const img = container.querySelector('img');
      expect(img).toHaveAttribute('src', expect.stringContaining('aap-custom.png'));
    });
  });

  describe('STATUS_CONFIG', () => {
    it('has all execution status types defined', () => {
      const statuses: ExecutionStatusType[] = [
        'SUBMITTED',
        'INTEGRATION_ERROR',
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
      expect(STATUS_CONFIG.INTEGRATION_ERROR.label).toBe('Erreur intégration');
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

  describe('PLATFORM_ICONS_CONFIG', () => {
    it('has all platform types defined', () => {
      const platforms: ActionPlatform[] = ['AAP', 'GitHub Actions', 'Azure DevOps', 'Terraform'];

      platforms.forEach((platform) => {
        expect(PLATFORM_ICONS_CONFIG).toHaveProperty(platform);
        expect(PLATFORM_ICONS_CONFIG[platform]).toHaveProperty('Icon');
        expect(PLATFORM_ICONS_CONFIG[platform]).toHaveProperty('color');
      });
    });
  });
});

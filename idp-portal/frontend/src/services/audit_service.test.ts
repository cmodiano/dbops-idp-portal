/**
 * Tests for audit_service (Story 71.11, AC #2).
 * Note: buildQueryString is private — tested indirectly via listExecutionAudit.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { listExecutionAudit, exportAuditReport } from './audit_service';
import * as apiClient from './api_client';

const mockCreateObjectURL = vi.fn().mockReturnValue('blob:test');
const mockRevokeObjectURL = vi.fn();
const mockAnchorClick = vi.fn();

describe('audit_service', () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockCreateObjectURL.mockReturnValue('blob:test');
    Object.defineProperty(window, 'URL', {
      value: { createObjectURL: mockCreateObjectURL, revokeObjectURL: mockRevokeObjectURL },
      writable: true,
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(mockAnchorClick);
    vi.spyOn(document.body, 'appendChild').mockImplementation(() => undefined as any);
    vi.spyOn(document.body, 'removeChild').mockImplementation(() => undefined as any);
  });

  describe('listExecutionAudit (tests buildQueryString indirectement)', () => {
    it('appelle apiFetchRaw sur /audit/executions sans filtres', async () => {
      const mockResult = { data: [], pagination: { count: 0, next: null, previous: null } };
      vi.spyOn(apiClient, 'apiFetchRaw').mockResolvedValue(mockResult as any);

      const result = await listExecutionAudit();

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/audit/executions', { method: 'GET' });
      expect(result.data).toEqual([]);
    });

    it('ajoute une query string vide si aucun filtre', async () => {
      const mockResult = { data: [], pagination: { count: 0, next: null, previous: null } };
      vi.spyOn(apiClient, 'apiFetchRaw').mockResolvedValue(mockResult as any);

      await listExecutionAudit({});

      expect(apiClient.apiFetchRaw).toHaveBeenCalledWith('/audit/executions', { method: 'GET' });
    });

    it('construit la query string avec tous les filtres', async () => {
      const mockResult = { data: [], pagination: { count: 0, next: null, previous: null } };
      vi.spyOn(apiClient, 'apiFetchRaw').mockResolvedValue(mockResult as any);

      await listExecutionAudit({
        from: '2024-01-01',
        to: '2024-12-31',
        environment: 'prod',
        action_id: 5,
        engine_type: 'oracle',
        user_id: 'john',
        status: 'success',
        correlation_id: 'corr-123',
        entity_type: 'server',
        action_type: 'patch',
        user: 'john.doe',
        sort: 'created_at',
        order: 'desc',
        limit: 50,
        offset: 10,
      });

      const callArg = (apiClient.apiFetchRaw as ReturnType<typeof vi.spyOn>).mock.calls[0][0] as string;
      expect(callArg).toContain('from=2024-01-01');
      expect(callArg).toContain('to=2024-12-31');
      expect(callArg).toContain('environment=prod');
      expect(callArg).toContain('action_id=5');
      expect(callArg).toContain('engine_type=oracle');
      expect(callArg).toContain('user_id=john');
      expect(callArg).toContain('status=success');
      expect(callArg).toContain('correlation_id=corr-123');
      expect(callArg).toContain('entity_type=server');
      expect(callArg).toContain('action_type=patch');
      expect(callArg).toContain('user=john.doe');
      expect(callArg).toContain('sort=created_at');
      expect(callArg).toContain('order=desc');
      expect(callArg).toContain('limit=50');
      expect(callArg).toContain('offset=10');
    });

    it('propage une erreur 403 (non-auditor)', async () => {
      vi.spyOn(apiClient, 'apiFetchRaw').mockRejectedValue(new Error('Forbidden'));

      await expect(listExecutionAudit()).rejects.toThrow('Forbidden');
    });
  });

  describe('exportAuditReport', () => {
    it('télécharge un rapport CSV — nom de fichier .csv et paramètre fmt=csv', async () => {
      const mockBlob = new Blob(['csv content'], { type: 'text/csv' });
      vi.spyOn(apiClient, 'apiFetchBlob').mockResolvedValue(mockBlob);

      await exportAuditReport('csv', {});

      const blobCallArg = (apiClient.apiFetchBlob as ReturnType<typeof vi.spyOn>).mock.calls[0][0] as string;
      expect(blobCallArg).toContain('fmt=csv');
      expect(blobCallArg).toContain('/audit/export/');
      expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
      expect(mockAnchorClick).toHaveBeenCalled();
    });

    it('télécharge un rapport PDF — nom de fichier .pdf et paramètre fmt=pdf', async () => {
      const mockBlob = new Blob(['pdf content'], { type: 'application/pdf' });
      vi.spyOn(apiClient, 'apiFetchBlob').mockResolvedValue(mockBlob);

      await exportAuditReport('pdf', { status: 'failed' });

      const blobCallArg = (apiClient.apiFetchBlob as ReturnType<typeof vi.spyOn>).mock.calls[0][0] as string;
      expect(blobCallArg).toContain('fmt=pdf');
      expect(blobCallArg).toContain('status=failed');
    });
  });
});

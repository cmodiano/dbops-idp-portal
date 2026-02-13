import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// We need to test with different import.meta.env.MODE values,
// so we dynamically import the module after mocking.

describe('Logger Service - Story 17.7', () => {
  let consoleLogSpy: ReturnType<typeof vi.spyOn>;
  let consoleWarnSpy: ReturnType<typeof vi.spyOn>;
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});
    consoleWarnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.resetModules();
  });

  describe('Development environment', () => {
    beforeEach(() => {
      vi.stubEnv('MODE', 'development');
    });

    afterEach(() => {
      vi.unstubAllEnvs();
    });

    it('should log debug messages in development', async () => {
      const { default: logger } = await import('./logger');
      logger.debug('test debug message', { key: 'value' });

      expect(consoleLogSpy).toHaveBeenCalledWith(
        '[DEBUG] test debug message',
        expect.objectContaining({
          level: 'debug',
          message: 'test debug message',
          key: 'value',
        })
      );
    });

    it('should log info messages in development', async () => {
      const { default: logger } = await import('./logger');
      logger.info('test info message', { action: 'test' });

      expect(consoleLogSpy).toHaveBeenCalledWith(
        '[INFO] test info message',
        expect.objectContaining({
          level: 'info',
          message: 'test info message',
          action: 'test',
        })
      );
    });

    it('should log warn messages in development', async () => {
      const { default: logger } = await import('./logger');
      logger.warn('test warn message', { retry: 2 });

      expect(consoleWarnSpy).toHaveBeenCalledWith(
        '[WARN] test warn message',
        expect.objectContaining({
          level: 'warn',
          message: 'test warn message',
          retry: 2,
        })
      );
    });

    it('should log error messages in development', async () => {
      const { default: logger } = await import('./logger');
      logger.error('test error message', { error: 'something failed' });

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        '[ERROR] test error message',
        expect.objectContaining({
          level: 'error',
          message: 'test error message',
          error: 'something failed',
        })
      );
    });

    it('should include ISO 8601 timestamp', async () => {
      const { default: logger } = await import('./logger');
      logger.info('timestamp test');

      expect(consoleLogSpy).toHaveBeenCalledWith(
        '[INFO] timestamp test',
        expect.objectContaining({
          timestamp: expect.stringMatching(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}Z$/),
        })
      );
    });

    it('should include structured data in log entries', async () => {
      const { default: logger } = await import('./logger');
      const data = { userId: 42, correlation_id: 'abc-123', action: 'fetch' };
      logger.error('structured test', data);

      expect(consoleErrorSpy).toHaveBeenCalledWith(
        '[ERROR] structured test',
        expect.objectContaining({
          level: 'error',
          message: 'structured test',
          userId: 42,
          correlation_id: 'abc-123',
          action: 'fetch',
        })
      );
    });
  });

  describe('Production environment', () => {
    beforeEach(() => {
      vi.stubEnv('MODE', 'production');
    });

    afterEach(() => {
      vi.unstubAllEnvs();
    });

    it('should NOT log debug messages in production', async () => {
      const { default: logger } = await import('./logger');
      logger.debug('should not appear');

      expect(consoleLogSpy).not.toHaveBeenCalled();
      expect(consoleWarnSpy).not.toHaveBeenCalled();
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });

    it('should NOT log info messages in production', async () => {
      const { default: logger } = await import('./logger');
      logger.info('should not appear');

      expect(consoleLogSpy).not.toHaveBeenCalled();
      expect(consoleWarnSpy).not.toHaveBeenCalled();
      expect(consoleErrorSpy).not.toHaveBeenCalled();
    });

    it('should log warn messages in production as JSON', async () => {
      const { default: logger } = await import('./logger');
      logger.warn('prod warning', { detail: 'test' });

      expect(consoleWarnSpy).toHaveBeenCalledTimes(1);
      const jsonArg = consoleWarnSpy.mock.calls[0][0] as string;
      const parsed = JSON.parse(jsonArg);
      expect(parsed).toMatchObject({
        level: 'warn',
        message: 'prod warning',
        detail: 'test',
      });
      expect(parsed.timestamp).toMatch(/^\d{4}-\d{2}-\d{2}T/);
    });

    it('should log error messages in production as JSON', async () => {
      const { default: logger } = await import('./logger');
      logger.error('prod error', { stack: 'Error: at foo()' });

      expect(consoleErrorSpy).toHaveBeenCalledTimes(1);
      const jsonArg = consoleErrorSpy.mock.calls[0][0] as string;
      const parsed = JSON.parse(jsonArg);
      expect(parsed).toMatchObject({
        level: 'error',
        message: 'prod error',
        stack: 'Error: at foo()',
      });
    });
  });

  describe('Edge cases', () => {
    beforeEach(() => {
      vi.stubEnv('MODE', 'development');
    });

    afterEach(() => {
      vi.unstubAllEnvs();
    });

    it('should work without optional data parameter', async () => {
      const { default: logger } = await import('./logger');
      logger.info('no data');

      expect(consoleLogSpy).toHaveBeenCalledWith(
        '[INFO] no data',
        expect.objectContaining({
          level: 'info',
          message: 'no data',
          timestamp: expect.any(String),
        })
      );
    });
  });
});

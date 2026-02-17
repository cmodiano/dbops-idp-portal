type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  [key: string]: unknown;
}

interface Logger {
  debug(message: string, data?: Record<string, unknown>): void;
  info(message: string, data?: Record<string, unknown>): void;
  warn(message: string, data?: Record<string, unknown>): void;
  error(message: string, data?: Record<string, unknown>): void;
}

const isDevelopment = import.meta.env.MODE === 'development';

function _output(level: LogLevel, entry: LogEntry): void {
  // eslint-disable-next-line no-console -- Logger internal implementation needs console access
  const consoleFn = level === 'error' ? console.error : level === 'warn' ? console.warn : console.log;

  if (isDevelopment) {
    consoleFn(`[${entry.level.toUpperCase()}] ${entry.message}`, entry);
  } else {
    // Production: structured JSON for warn/error only
    try {
      consoleFn(JSON.stringify(entry));
    } catch (stringifyError) {
      // Fallback if circular reference or stringify fails
      // eslint-disable-next-line no-console -- Fallback for logger failure
      console.error('[LOGGER STRINGIFY FAILED]', entry.level, entry.message, stringifyError);
    }
  }
}

const logger: Logger = {
  /**
   * Log debug message (development only).
   * @param message - Log message
   * @param data - Optional structured data (correlation_id, userId, etc.)
   */
  debug(message: string, data?: Record<string, unknown>): void {
    if (!isDevelopment) return;
    const entry: LogEntry = { timestamp: new Date().toISOString(), level: 'debug', message, ...data };
    _output('debug', entry);
  },

  /**
   * Log info message (development only).
   * @param message - Log message
   * @param data - Optional structured data
   */
  info(message: string, data?: Record<string, unknown>): void {
    if (!isDevelopment) return;
    const entry: LogEntry = { timestamp: new Date().toISOString(), level: 'info', message, ...data };
    _output('info', entry);
  },

  /**
   * Log warning message (all environments).
   * @param message - Log message
   * @param data - Optional structured data (error, retry count, etc.)
   */
  warn(message: string, data?: Record<string, unknown>): void {
    const entry: LogEntry = { timestamp: new Date().toISOString(), level: 'warn', message, ...data };
    _output('warn', entry);
  },

  /**
   * Log error message (all environments).
   * @param message - Log message
   * @param data - Optional structured data (error, stack, correlation_id, etc.)
   */
  error(message: string, data?: Record<string, unknown>): void {
    const entry: LogEntry = { timestamp: new Date().toISOString(), level: 'error', message, ...data };
    _output('error', entry);
  },
};

// TODO: Future hook for backend log forwarding (e.g., POST /api/v1/logs)

export default logger;

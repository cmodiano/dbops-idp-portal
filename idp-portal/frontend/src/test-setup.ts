import '@testing-library/jest-dom/vitest';

// Mock ResizeObserver for recharts components
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
global.ResizeObserver = ResizeObserverMock;

/**
 * Test setup for Vitest with React Testing Library.
 */

// Force UTC timezone for deterministic date rendering across environments
process.env.TZ = 'UTC';

import '@testing-library/jest-dom';

// Mock matchMedia for Ant Design components
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Mock ResizeObserver for Ant Design
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Suppress React "not wrapped in act(...)" warnings.
// These are caused by async effects (data fetching, Ant Design animations) that resolve
// after test assertions. They do not indicate bugs — just noise from concurrent state updates
// in components rendered during tests. See: https://github.com/testing-library/react-testing-library/issues/1061
const _originalConsoleError = console.error.bind(console);
console.error = (...args: Parameters<typeof console.error>) => {
  if (typeof args[0] === 'string' && args[0].includes('not wrapped in act(')) return;
  _originalConsoleError(...args);
};

// Suppress jsdom "Not implemented: Window's getComputedStyle() with pseudo-elements"
// jsdom does not implement pseudo-element style resolution; antd's CSS-in-JS triggers
// this on every render, producing noise in the test output.
const _originalGetComputedStyle = window.getComputedStyle.bind(window);
window.getComputedStyle = (elt: Element, pseudoElt?: string | null): CSSStyleDeclaration => {
  if (pseudoElt) {
    return {} as CSSStyleDeclaration;
  }
  return _originalGetComputedStyle(elt);
};

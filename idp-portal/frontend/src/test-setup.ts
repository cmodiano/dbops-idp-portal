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

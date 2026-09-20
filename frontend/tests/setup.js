require('@testing-library/jest-dom');
Object.defineProperty(globalThis.crypto, 'randomUUID', {
  value: () => require('node:crypto').randomUUID(), configurable: true,
});

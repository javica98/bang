const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './web/tests',
  use: {
    baseURL: 'http://localhost:5000',
    headless: true,
    viewport: { width: 1280, height: 900 },
  },
  outputDir: './web/tests/test-results',
});

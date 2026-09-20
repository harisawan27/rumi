// Run against the opt-in /dev/study-tracker synthetic fixture harness.
// Uses an externally installed Playwright; no browser runtime ships with Rumi.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');
const os = require('node:os');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    for (const [width, height] of [[1366,768], [1440,900], [1920,1080], [320,568], [375,667], [390,844], [430,932]]) {
      await page.setViewportSize({ width, height });
      await page.goto('http://127.0.0.1:3100/dev/study-tracker', { timeout: 120000 });
      await page.getByText('No study entries yet.').waitFor();
      await page.getByLabel('Minutes', { exact: true }).fill('60');
      await page.getByRole('button', { name: 'Add entry', exact: true }).click();
      await page.getByRole('button', { name: 'Remove Economics entry on 2026-09-14' }).waitFor();
      await page.getByRole('button', { name: 'Show graph', exact: true }).click();
      await page.getByRole('list', { name: 'Daily study graph' }).waitFor();
      assert.match(await page.getByRole('list', { name: 'Daily study graph' }).textContent(), /60 min/);
      await page.getByRole('button', { name: 'Simulate guest' }).click();
      assert.equal(await page.getByRole('region', { name: 'Study tracker' }).count(), 0);
      assert.equal(await page.getByText('Economics', { exact: true }).count(), 0);
      await page.getByRole('button', { name: 'Return owner' }).click();
      await page.getByRole('button', { name: 'Remove Economics entry on 2026-09-14' }).waitFor();
      if (width === 1366 || width === 320) {
        await page.getByRole('region', { name: 'Study tracker' }).evaluate(e => e.parentElement.scrollTo(0, 0));
        await page.screenshot({ path: path.join(os.tmpdir(), `rumi-tracker-${width}.png`), fullPage: true });
      }
      const overflow = await page.evaluate(() => ({
        page: document.documentElement.scrollWidth > innerWidth,
        tracker: [...document.querySelectorAll('.study-tracker, .study-tracker form')].some(e => e.scrollWidth > e.clientWidth + 1),
      }));
      assert.deepEqual(overflow, { page: false, tracker: false });
      const controls = await page.locator('.study-tracker input, .study-tracker select, .study-tracker button').evaluateAll(nodes => nodes.map(e => e.getBoundingClientRect().height));
      assert.ok(controls.every(h => h >= 44));
      await page.getByRole('button', { name: 'Remove Economics entry on 2026-09-14' }).click();
      await page.getByText('No study entries yet.').waitFor();
      console.log(`PASS ${width}x${height}: add, graph, guest teardown, reload, remove, overflow, touch targets`);
    }
    assert.deepEqual(errors, []);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });

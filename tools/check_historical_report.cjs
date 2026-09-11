// Local report only. NODE_PATH must point to the existing Playwright installation.
// Usage: node tools/check_historical_report.cjs /absolute/report.html /tmp/report-check
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const assert = require('assert/strict');
(async () => {
  const source = path.resolve(process.argv[2]);
  const output = path.resolve(process.argv[3] || '/tmp/neraium-report-check');
  fs.mkdirSync(output, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 1000 } });
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(pathToFileURL(source).href);
      assert.equal(await page.locator('h1').innerText(), 'Historical Evaluation');
      assert.equal(await page.locator('.brand').innerText(), 'NERAIUM');
      assert.deepEqual(await page.locator('section > h2').allTextContents(), [
        'Executive Summary', 'Key Findings', 'Measurable Consequence', 'Evidence', 'Limitations', 'Technical Appendix'
      ]);
      const main = await page.locator('section:not(.appendix)').allInnerTexts();
      assert(!/Internal operator|\/analysis_result|\/temporal_analysis|\/processing_trace|adapter_contract|energy_total_kwh|—/.test(main.join('\n')));
      assert.equal(await page.locator('pre').count(), 0);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      assert(await page.locator('.summary').evaluate(el => el.getBoundingClientRect().top < 900));
      assert.deepEqual(errors, []);
      await page.screenshot({ path: path.join(output, `report-${width}.png`), fullPage: true });
      if (width === 1440) {
        await page.emulateMedia({ media: 'print' });
        assert(await page.locator('.appendix').isVisible());
        await page.pdf({ path: path.join(output, 'report.pdf'), preferCSSPageSize: true, printBackground: true });
      }
      await page.close();
    }
    console.log('PASS: 1440px desktop, 390px mobile, no horizontal overflow, section order, no internal payloads, PDF generated.');
    console.log(output);
  } finally {
    await browser.close();
  }
})().catch(e => { console.error(e); process.exit(1); });

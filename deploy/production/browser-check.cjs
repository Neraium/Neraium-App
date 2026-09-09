// Run with NODE_PATH pointing to an installed playwright package. No mocked API.
const { chromium } = require('playwright');
const fs = require('fs');
const assert = require('assert/strict');
const crypto = require('crypto');
const config = require('./resources.json');
const token = fs.readFileSync(process.argv[2], 'utf8').trim();
const origin = 'https://' + config.cloudfront_hostname;
(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
  page.setDefaultTimeout(30000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const assertLanding = async () => {
    await page.getByRole('heading', {name: 'Historical Evaluation', exact: true}).waitFor();
    assert(!/Production Telemetry|Add data source|Add live data source|Connect a physical system/.test(await page.locator('body').innerText()));
  };
  async function click(name, path) {
    const response = page.waitForResponse(r => r.url().includes('/api/' + path) && r.request().method() === 'POST', {timeout: 150000});
    await page.getByRole('button', {name, exact: true}).click();
    const result = await response;
    assert(result.ok(), `${path}: ${result.status()} ${await result.text()}`);
    await page.getByRole('status').waitFor({state: 'hidden', timeout: 150000});
    assert.equal(await page.getByRole('alert').count(), 0);
    return result.json();
  }
  await page.goto(origin + '/');
  await assertLanding();
  await page.getByLabel('Internal workbench token').fill(token);
  await page.getByRole('button', {name: 'Open workbench', exact: true}).click();
  await page.getByRole('button', {name: 'New Evaluation', exact: true}).waitFor();
  assert((await page.locator('body').innerText()).includes(config.authority_commit.slice(0, 12)));
  await page.getByRole('button', {name: 'New Evaluation', exact: true}).click();
  for (const [label, value] of [['Customer','BROWSER DEPLOYMENT CHECK (synthetic)'],['Facility','App production verification'],['Physical system','Generated paired loop'],['Evaluation scope / question','64 generated rows per period; verify actual browser paired workflow.']]) {
    await page.getByLabel(label, {exact:true}).fill(value);
  }
  const evaluation = await click('Create historical evaluation', 'evaluations');
  assert.equal(evaluation.mode, 'paired');
  assert(await page.getByLabel('Upload comparison', {exact:true}).isDisabled());
  const hashes = {};
  for (const role of ['reference','comparison']) {
    let csv = 'time,flow,pressure,power\n';
    for (let i=0;i<64;i++) csv += `${(i+(role==='comparison'?129600:0))*60},${80+4*Math.sin(i/4)},${role==='reference'?40+2*Math.sin(i/4):55+2*Math.cos(i*2)},${role==='reference'?20+Math.sin(i/4):28+Math.sin(i/4)}\n`;
    const buffer = Buffer.from(csv);
    hashes[role] = crypto.createHash('sha256').update(buffer).digest('hex');
    const upload = page.waitForResponse(r => r.url().includes('/source?') && r.request().method()==='POST');
    await page.getByLabel('Upload ' + role, {exact:true}).setInputFiles({name:role+'.csv',mimeType:'text/csv',buffer});
    assert((await upload).ok());
    await page.getByRole('status').waitFor({state:'hidden'});
  }
  await page.getByRole('combobox', {name:/^Reference timestamp column/}).selectOption('time');
  await page.getByRole('combobox', {name:/^Reference timestamp format/}).selectOption('epoch_seconds');
  await click('Validate reference', 'evaluations/'+evaluation.id+'/validate');
  await page.getByRole('combobox', {name:/^Timestamp column/}).selectOption('time');
  await page.getByRole('combobox', {name:/^Timestamp format/}).selectOption('epoch_seconds');
  await click('Validate', 'evaluations/'+evaluation.id+'/validate');
  for (const signal of ['flow','pressure','power']) {
    await page.getByLabel('Include '+signal, {exact:true}).check();
    await page.getByLabel(signal+' meaning', {exact:true}).fill(signal);
    await page.getByLabel(signal+' unit', {exact:true}).fill('dimensionless');
  }
  await page.getByLabel('Supplied system context and known limitations').fill('Generated contract fixture; same synthetic system, no physical engineering claims.');
  await page.getByLabel(/^I verified both sources/).check();
  await click('Preview mappings','evaluations/'+evaluation.id+'/mapping-preview');
  await click('Confirm classifications, units, context and window policy','evaluations/'+evaluation.id+'/approve-mapping');
  const run = await click('Run authoritative SII','evaluations/'+evaluation.id+'/runs');
  await page.getByRole('heading', {name:'7. Review evidence',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Export report',exact:true}).count(),0);
  await page.getByLabel('Reviewer name',{exact:true}).fill('Browser deployment verification (synthetic)');
  await page.getByLabel(/^I reviewed this run's scope/).check();
  await click('Record review','runs/'+run.id+'/reviews');
  const evidenceDownload = page.waitForEvent('download');
  await page.getByRole('button',{name:'Download evidence JSON',exact:true}).click();
  const downloaded = await evidenceDownload;
  const evidence = JSON.parse(fs.readFileSync(await downloaded.path(),'utf8'));
  assert.equal(evidence.response.identity.commit, config.authority_commit);
  assert.equal(evidence.reference_source.sha256,hashes.reference);
  assert.equal(evidence.source.sha256,hashes.comparison);
  assert.equal(evidence.response.result.supplied_reference.reference.row_count,64);
  assert.equal(evidence.response.result.supplied_reference.comparison.row_count,64);
  assert.deepEqual(evidence.response.result.processing_trace.modules_failed,[]);
  const reportDownload = page.waitForEvent('download');
  await page.getByRole('button',{name:'Export report',exact:true}).click();
  const report = fs.readFileSync(await (await reportDownload).path(),'utf8');
  assert(report.includes('Reference period/data') && report.includes('Comparison period/data'));
  await assertLanding();
  await page.setViewportSize({width:390,height:844});
  await assertLanding();
  await page.reload();
  await assertLanding();
  await page.getByLabel('Internal workbench token').waitFor();
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({status:'passed',origin,commit:config.application_commit,authority_commit:config.authority_commit,evaluation_id:evaluation.id,run_id:run.id,desktop:true,mobile:true,report_export:true},null,2));
  await browser.close();
})().catch(error=>{console.error(error);process.exit(1);});

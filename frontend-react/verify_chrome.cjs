const puppeteer = require('puppeteer-core');
const path = require('path');

const CHROME_PATH = 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe';
const SCREENSHOT_DIR = 'C:\\Users\\hp\\.gemini\\antigravity\\brain\\98b64ba3-dbf5-4d37-9263-86ba9adfdbba\\screenshots';
const BASE_URL = 'http://127.0.0.1:5173';

async function run() {
  console.log('Launching Chrome from:', CHROME_PATH);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900']
  });

  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1440, height: 900 });

    page.on('console', msg => console.log('PAGE LOG:', msg.text()));
    page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

    // 1. Login Page
    console.log('Step 1: Navigating to', `${BASE_URL}/login`);
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle0' });
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_login_page.png') });
    console.log('  Captured: 01_login_page.png');

    // 2. Perform Login with deliberate input focus
    console.log('Step 2: Submitting credentials...');
    const testEmail = process.env.TEST_ADMIN_EMAIL || 'admin@opssage.internal';
    const testPassword = process.env.TEST_ADMIN_PASSWORD || 'AdminPass2026!';

    await page.waitForSelector('input[type="email"]');
    await page.click('input[type="email"]');
    await page.type('input[type="email"]', testEmail, { delay: 20 });
    await page.click('input[type="password"]');
    await page.type('input[type="password"]', testPassword, { delay: 20 });
    
    // Take a screenshot right before clicking submit
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01b_login_filled.png') });

    // Click submit button
    await page.click('button[type="submit"]');

    // Wait for URL to become root '/'
    console.log('Waiting for authentication navigation...');
    await page.waitForFunction(() => window.location.pathname === '/', { timeout: 15000 });
    await new Promise(r => setTimeout(r, 3000)); // allow dashboard telemetry API to load

    // 3. Dashboard Overview
    console.log('Step 3: Checking Dashboard Overview...');
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_dashboard_overview.png') });
    console.log('  Captured: 02_dashboard_overview.png');

    // 4. Incidents List
    console.log('Step 4: Navigating to Incidents...');
    await page.goto(`${BASE_URL}/incidents`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2500));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_incidents_page.png') });
    console.log('  Captured: 03_incidents_page.png');

    // 5. Incident Details
    console.log('Step 5: Inspecting incident details...');
    await page.goto(`${BASE_URL}/incidents/INC-20261122-33B83B`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2500));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_incident_detail.png') });
    console.log('  Captured: 04_incident_detail.png');

    // 6. AI Root-Cause Analysis
    console.log('Step 6: Checking AI RCA page...');
    await page.goto(`${BASE_URL}/analysis/INC-20261122-33B83B`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2500));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_ai_rca.png') });
    console.log('  Captured: 05_ai_rca.png');

    // 7. Precedents Retrieval / RAG
    console.log('Step 7: Checking Historical Precedents page...');
    await page.goto(`${BASE_URL}/precedents`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2500));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_precedents.png') });
    console.log('  Captured: 06_precedents.png');

    // 8. Knowledge Base
    console.log('Step 8: Checking Knowledge Base page...');
    await page.goto(`${BASE_URL}/knowledge`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2500));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '07_knowledge_base.png') });
    console.log('  Captured: 07_knowledge_base.png');

    // 9. DevOps Analytics
    console.log('Step 9: Checking DevOps Analytics page...');
    await page.goto(`${BASE_URL}/analytics`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2500));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '08_analytics.png') });
    console.log('  Captured: 08_analytics.png');

    // 10. Log Stream
    console.log('Step 10: Checking Log Stream page...');
    await page.goto(`${BASE_URL}/logs`, { waitUntil: 'networkidle0' });
    await new Promise(r => setTimeout(r, 2500));
    await page.screenshot({ path: path.join(SCREENSHOT_DIR, '09_logs_stream.png') });
    console.log('  Captured: 09_logs_stream.png');

    console.log('All Chrome checks and screenshots completed successfully!');
  } finally {
    await browser.close();
  }
}

run().catch(err => {
  console.error('Chrome Verification Error:', err);
  process.exit(1);
});

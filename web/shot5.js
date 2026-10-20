const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell' });
  const run = async (name, q, hash, fn) => {
    const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
    const errs = []; p.on('pageerror', e => errs.push('PAGEERROR ' + e.message));
    await p.goto('http://localhost:8765/index.html' + (hash || ''));
    await p.waitForFunction(() => document.getElementById('loading').hidden && document.getElementById('detail').hidden, null, { timeout: 60000 });
    await p.waitForTimeout(700);
    if (q) { await p.fill('#q', q); await p.waitForTimeout(300); await p.keyboard.press('Enter'); await p.waitForTimeout(1800); }
    if (fn) await fn(p);
    await p.mouse.move(1430, 300); await p.waitForTimeout(300);
    await p.screenshot({ path: `shots/${name}.png` }); console.log(name, errs); await p.close();
  };
  for (const a of process.argv.slice(2)) { const [n, q, h] = a.split('|'); await run(n, q, h); }
  await b.close();
})();

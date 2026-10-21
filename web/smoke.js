// Smoke test of the built site (web/test mirror, served on :8765). Usage: node smoke.js [outdir]
const { chromium, devices } = require('playwright');
const OUT = process.argv[2] || 'ux';
const EXE = '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell';
(async () => {
  const b = await chromium.launch({ executablePath: EXE });
  const fails = [];
  const ok = (cond, msg) => { if (!cond) fails.push(msg); console.log((cond ? '  ok  ' : '  FAIL ') + msg); };
  const ready = p => p.waitForFunction(() => document.getElementById('loading').hidden, null, { timeout: 90000 });
  // ---------------- desktop
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(e.message));
  const t0 = Date.now(); await p.goto('http://localhost:8765/index.html'); await ready(p); console.log('desktop first map', Date.now() - t0, 'ms');
  await p.waitForTimeout(1200); await p.screenshot({ path: `${OUT}/s_world.png` });
  const search = async term => { await p.fill('#q', term); await p.waitForTimeout(200); return p.$$eval('#results li', ls => ls.map(l => l.innerText.replace(/\n/g, ' | '))); };
  for (const [term, expect] of [['london', 'Greater London'], ['punjab', 'Punjab'], ['java', 'Java'], ['paris', 'Paris'], ['cape town', 'Cape Town'], ['türkiye', 'Turkey'], ['usa', 'United States'], ['uk', 'United Kingdom'], ['jawa', 'Java'], ['sao paulo', 'São Paulo'], ['dearborn', 'Detroit']]) {
    const r = await search(term); ok(r.length && r[0].toLowerCase().includes(expect.toLowerCase()), `search "${term}" → ${r[0]}`);
  }
  await p.fill('#q', 'Malappuram'); await p.waitForTimeout(200); await p.keyboard.press('Enter'); await p.waitForTimeout(1600);
  ok(!(await p.$eval('#panel', e => e.hidden)), 'search pins a panel');
  ok(/#@.*u\/IND\/Malappuram/.test(p.url()), 'URL holds view + selection: ' + p.url().split('#')[1]);
  await p.screenshot({ path: `${OUT}/s_malappuram.png` });
  await p.click('.chip[data-k="europe"]'); await p.waitForTimeout(1500);
  ok(p.url().endsWith('#europe'), 'view chip sets #europe');
  await p.goBack(); await p.waitForTimeout(1500);
  ok(/Malappuram/.test(p.url()) && !(await p.$eval('#panel', e => e.hidden)), 'Back restores the previous selection');
  await p.goto('http://localhost:8765/index.html#balkans'); await p.waitForTimeout(1500); await p.screenshot({ path: `${OUT}/s_balkans.png` });
  await p.evaluate(() => { location.hash = '#usa'; }); await p.waitForTimeout(1500); await p.screenshot({ path: `${OUT}/s_usa.png` });
  ok(await p.$eval('.chip[data-k="usa"]', e => e.classList.contains('on')), 'editing the hash moves the map (#usa)');
  // hover tooltip and pan with pinned panel
  await p.mouse.move(700, 450); await p.mouse.move(705, 452); await p.waitForTimeout(300);
  ok(!(await p.$eval('#tip', e => e.hidden)), 'hover shows a tooltip');
  await p.mouse.click(705, 452); await p.waitForTimeout(300);
  const pb = await p.$eval('#panel', e => e.getBoundingClientRect().toJSON());
  await p.mouse.move(600, 400); await p.mouse.down(); await p.mouse.move(400, 300, { steps: 6 }); await p.mouse.up(); await p.waitForTimeout(400);
  const pa = await p.$eval('#panel', e => e.getBoundingClientRect().toJSON());
  ok(pb.x === pa.x && pb.y === pa.y && pb.x > 1000, 'pinned panel stays docked top-right while panning');
  await p.screenshot({ path: `${OUT}/s_pinned.png` });
  // legend highlight + about + data-quality toggle
  await p.click('#lgMore'); await p.waitForTimeout(500);
  await p.hover('#scale rect.sw[data-k="9"]'); await p.waitForTimeout(400); await p.screenshot({ path: `${OUT}/s_highlight.png` });
  await p.click('#aboutBtn'); await p.waitForTimeout(400); ok(await p.$eval('#about', d => d.open), 'About dialog opens'); await p.screenshot({ path: `${OUT}/s_about.png` });
  await p.keyboard.press('Escape'); await p.waitForTimeout(200);
  // keyboard
  await p.focus('#map'); const k0 = p.url(); await p.keyboard.press('+'); await p.keyboard.press('ArrowLeft'); await p.waitForTimeout(900);
  ok(p.url() !== k0, 'keyboard zoom/pan changes the view');
  await p.keyboard.press('Enter'); await p.waitForTimeout(300); ok((await p.$eval('#live', e => e.textContent)).length > 0, 'Enter describes the place at the centre: ' + await p.$eval('#live', e => e.textContent));
  // dark mode
  await p.emulateMedia({ colorScheme: 'dark' }); await p.goto('http://localhost:8765/index.html#europe'); await ready(p); await p.waitForTimeout(1500); await p.screenshot({ path: `${OUT}/s_dark.png` });
  ok(errs.length === 0, 'no page errors on desktop: ' + errs.join(' | '));
  await ctx.close();
  // ---------------- phone
  const pc = await b.newContext({ ...devices['iPhone 13'] });
  const q = await pc.newPage(); const errs2 = []; q.on('pageerror', e => errs2.push(e.message));
  await q.goto('http://localhost:8765/index.html'); await ready(q); await q.waitForTimeout(1000); await q.screenshot({ path: `${OUT}/p_open.png` });
  const box = await q.locator('#map').boundingBox();
  await q.touchscreen.tap(box.x + box.width * 0.55, box.y + box.height * 0.35); await q.waitForTimeout(500); await q.screenshot({ path: `${OUT}/p_tap.png` });
  ok(!(await q.$eval('#panel', e => e.hidden)), 'tap opens the bottom sheet');
  await q.click('#panel .x'); await q.waitForTimeout(300);
  await q.click('#lgMore'); await q.waitForTimeout(300); await q.screenshot({ path: `${OUT}/p_legend.png` });
  ok(!(await q.$eval('#lgBody', e => e.hidden)), 'legend opens on phone after closing the sheet');
  await q.click('#lgMore');
  await q.click('#moreBtn'); await q.waitForTimeout(300); await q.screenshot({ path: `${OUT}/p_menu.png` });
  await q.click('#menu button[data-k="london"]'); await q.waitForTimeout(1800); await q.screenshot({ path: `${OUT}/p_london.png` });
  await q.setViewportSize({ width: 844, height: 390 }); await q.waitForTimeout(1200); await q.screenshot({ path: `${OUT}/p_landscape.png` });
  console.log('phone stage height in landscape:', await q.$eval('#stage', e => e.offsetHeight));
  ok(errs2.length === 0, 'no page errors on phone: ' + errs2.join(' | '));
  await b.close();
  console.log(fails.length ? `\n${fails.length} FAILED` : '\nall passed');
  process.exit(fails.length ? 1 : 0);
})();

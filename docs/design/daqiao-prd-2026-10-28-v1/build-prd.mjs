// Rebuild only this documentation bundle: screenshots, HTML and verification.
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';
import crypto from 'node:crypto';

const root = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '/Users/lanull/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const browserPath = process.env.CHROMIUM_PATH || '/Users/lanull/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const scenes = ['chat', 'account', 'tasks', 'task-detail', 'models', 'add-service', 'brief', 'dev', 'binding', 'account-rules'];
await fs.mkdir(path.join(root, 'assets'), { recursive: true });
const mime = {'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.png':'image/png','.md':'text/plain; charset=utf-8'};
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://localhost');
    const target = path.resolve(root, '.' + decodeURIComponent(url.pathname));
    if (!target.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
    const body = await fs.readFile(target);
    res.writeHead(200, {'Content-Type':mime[path.extname(target)] || 'application/octet-stream'}).end(body);
  } catch { res.writeHead(404).end(); }
});
await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
const base = `http://127.0.0.1:${server.address().port}`;
let browser;
const result = {document:'大乔 三谋个人 Agent PRD v1',date:'2026-10-28',scope:'documentation and static mockups only',screens:[],errors:[],links:[],report:{}};
try {
  browser = await chromium.launch({headless:true,executablePath:browserPath});
  const page = await browser.newPage({viewport:{width:1280,height:860},deviceScaleFactor:1});
  page.on('pageerror', e => result.errors.push(e.message));
  await page.route('**/*', route => route.request().url().startsWith(base) || route.request().url().startsWith('data:') ? route.continue() : route.abort());
  for (let i = 0; i < scenes.length; i++) {
    const scene = scenes[i];
    await page.goto(`${base}/mockups.html#${scene}`);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(120);
    const size = await page.evaluate(() => {
      const bounds=document.querySelector('.app').getBoundingClientRect();
      const clipped=[...document.querySelectorAll('.app *')].filter(el=>{
        const r=el.getBoundingClientRect();return r.width>0&&r.height>0&&(r.bottom>bounds.bottom+1||r.right>bounds.right+1||r.left<bounds.left-1);
      }).map(el=>({element:el.className,bottom:Math.round(el.getBoundingClientRect().bottom)}));
      return {width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,clipped,text:document.body.innerText.slice(0,160)};
    });
    const filename = `${String(i+1).padStart(2,'0')}-${scene}.png`;
    await page.screenshot({path:path.join(root,'assets',filename),fullPage:true});
    result.screens.push({scene,file:`assets/${filename}`,...size});
    if (size.width > 1280) result.errors.push(`${scene}: horizontal overflow ${size.width}`);
    if (size.clipped.length) result.errors.push(`${scene}: ${size.clipped.length} elements outside canvas`);
  }

  execFileSync(process.execPath, ['/Users/lanull/.codex/report-tools/render-md-report.mjs',path.join(root,'PRD.md'),path.join(root,'PRD.html'),'大乔 三谋个人 Agent PRD v1'], {stdio:'pipe'});
  let html = await fs.readFile(path.join(root,'PRD.html'),'utf8');
  const imageMatches = [...html.matchAll(/<img\s+[^>]*src="(assets\/[^"<>]+\.png)"[^>]*>/g)];
  for (const match of imageMatches) {
    const encoded = (await fs.readFile(path.join(root,match[1]))).toString('base64');
    const img = match[0].replace(`src="${match[1]}"`,`src="data:image/png;base64,${encoded}"`);
    html = html.replace(match[0], `<button class="prd-image" type="button" aria-label="放大设计样图">${img}</button>`);
  }
  html = html.replace('Report<br>HTML','大乔<br><small>产品需求文档</small>');
  html = html.replace('</head>', `<style>
    :root{--bg:#eff4f7;--paper:#fff;--ink:#30485b;--muted:#6a8090;--line:#dce6ed;--accent:#3f7295;--accent-2:#416d8b;--dark:#31516a}
    body{background:linear-gradient(145deg,#e8f0f6,#f6f3ed);font-family:"Avenir Next","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.85}
    .layout{grid-template-columns:250px minmax(0,1fr)}aside{background:#f8fbfd;color:#3c5c73;border-right:1px solid #dce6ed;padding:27px 19px}
    .mark{font-family:inherit;font-size:28px;line-height:1.2;letter-spacing:0}.mark small{font-size:13px;font-weight:400}.meta{color:#71899a;font-size:11px}
    .toc{color:#537187;font-size:12px;padding:6px 7px}.toc-3{color:#7b91a1;font-size:11px;padding-left:17px}.toc:hover{color:#345c7a;background:#e7eff5;border-radius:6px}
    main{padding:40px min(4vw,60px) 80px}article{max-width:1120px}h1,h2,h3{font-family:inherit;text-transform:none;letter-spacing:0;line-height:1.45}
    h1{font-size:36px;max-width:none;margin-bottom:18px}h2{font-size:25px;border-top:1px solid #d1dfe8;padding-top:25px;margin-top:42px}h3{font-size:18px}
    p,li{font-size:15px;max-width:950px}table{box-shadow:none;background:#fff;font-size:14px;border-radius:8px}th{font-family:inherit;letter-spacing:0;background:#e5eef5;color:#3b5f79}td,th{border:1px solid #dce6ed;padding:10px 12px;overflow-wrap:anywhere}
    code{background:#e9f0f5;border:0;color:#41617a}pre{background:#e5eef5;color:#36556b;border:0}
    .prd-image{display:block;background:#fff;padding:0;border:0;border-radius:12px;box-shadow:0 8px 28px #526f8014;width:100%;margin:21px 0;cursor:zoom-in;overflow:hidden}
    .prd-image img{display:block;width:100%;height:auto}dialog{border:0;border-radius:14px;padding:15px;background:#f7fafc;max-width:96vw;max-height:96vh}dialog::backdrop{background:#182e4399}
    dialog img{display:block;max-width:90vw;max-height:84vh;object-fit:contain}dialog button{font:14px inherit;border:0;background:#e3edf4;color:#365c79;padding:8px 18px;border-radius:8px;margin-bottom:10px;cursor:pointer}
    @media(max-width:860px){.layout{display:block}aside{height:auto;max-height:none;position:relative}aside nav{max-height:220px;overflow:auto}main{padding:26px 17px 60px}h1{font-size:28px}p,li{font-size:14px}table{display:block;overflow-x:auto}}
    @media print{aside{display:none}.layout{display:block}body{background:white}.prd-image{box-shadow:none;break-inside:avoid}h2,h3{break-after:avoid}}
  </style></head>`);
  html = html.replace('</body>', `<dialog id="image-preview"><button type="button">关闭</button><img alt="设计样图放大预览"></dialog><script>
    const dialog=document.getElementById('image-preview');
    document.querySelectorAll('.prd-image').forEach(button=>button.addEventListener('click',()=>{dialog.querySelector('img').src=button.querySelector('img').src;dialog.showModal();}));
    dialog.querySelector('button').addEventListener('click',()=>dialog.close());
    dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
  </script></body>`);
  await fs.writeFile(path.join(root,'PRD.html'),html);
  const md=await fs.readFile(path.join(root,'PRD.md'),'utf8');
  for(const match of md.matchAll(/!?\[[^\]]*\]\(([^)]+)\)/g)){
    const href=match[1];if(/^https?:|^#/.test(href))continue;
    const target=path.resolve(root,href.split('#')[0]);
    try{await fs.access(target);result.links.push({href,exists:true});}catch{result.links.push({href,exists:false});result.errors.push(`Missing link ${href}`);}
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.goto(`${base}/PRD.html`);
  result.report.desktop=await page.evaluate(()=>({headings:document.querySelectorAll('h2').length,tables:document.querySelectorAll('table').length,images:document.images.length-1,loadedImages:[...document.querySelectorAll('.prd-image img')].filter(img=>img.complete&&img.naturalWidth>0).length,overflow:document.documentElement.scrollWidth>innerWidth}));
  await page.screenshot({path:path.join(root,'assets','qa-prd-top.png')});
  await page.locator('.prd-image').first().click();
  result.report.imageZoom=await page.locator('dialog').evaluate(el=>el.open);
  await page.locator('dialog button').click();
  await page.setViewportSize({width:390,height:844});
  result.report.mobile=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,overflow:document.documentElement.scrollWidth>innerWidth}));
  if(result.report.desktop.overflow||result.report.mobile.overflow)result.errors.push('PRD horizontal overflow');
  if(result.report.desktop.loadedImages!==scenes.length)result.errors.push('PRD image load mismatch');
  result.report.embeddedImages=imageMatches.length;
  result.sourceHash=crypto.createHash('sha256').update(md).digest('hex');
  await fs.writeFile(path.join(root,'verification.json'),JSON.stringify(result,null,2)+'\n');
  console.log(JSON.stringify(result,null,2));
  if(result.errors.length)process.exitCode=1;
} finally {
  await browser?.close();
  await new Promise(resolve=>server.close(resolve));
}

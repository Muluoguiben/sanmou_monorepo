import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const root=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(import.meta.url);
const deps='/Users/lanull/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const {chromium}=require(path.join(deps,'playwright'));
const {tokens}=JSON.parse(await fs.readFile(path.join(root,'tokens.json'),'utf8'));
await fs.writeFile(path.join(root,'tokens.css'),'/* Generated from tokens.json. Do not edit separately. */\n:root {\n'+Object.entries(tokens).map(([key,value])=>`  --dq-${key}: ${value};`).join('\n')+'\n}\n');
await fs.copyFile(path.join(deps,'lucide/dist/umd/lucide.min.js'),path.join(root,'lucide.js'));
await fs.copyFile(path.join(deps,'lucide/LICENSE'),path.join(root,'LUCIDE-LICENSE.txt'));
await fs.mkdir(path.join(root,'assets'),{recursive:true});
const luminance=hex=>hex.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
const checks=[['text-primary','bg-start',4.5],['text-secondary','bg-start',4.5],['text-secondary','surface-soft',4.5],['text-muted','surface',4.5],['text-muted','surface-subtle',4.5],['on-primary','primary',4.5],['on-primary','primary-hover',4.5],['on-primary','primary-pressed',4.5],['success','success-bg',4.5],['warning','warning-bg',4.5],['danger','danger-bg',4.5],['border-control','bg-start',3],['border-control','surface-soft',3],['border-control','surface-subtle',3],['focus','bg-start',3]];
const result={date:'2026-10-28',scope:'design specification and component samples only',contrast:checks.map(([foreground,background,target])=>{const ratio=contrast(tokens[foreground],tokens[background]);return {foreground,background,ratio:Number(ratio.toFixed(3)),target,pass:ratio>=target};}),screens:[],interactions:{},errors:[]};
const css=await fs.readFile(path.join(root,'components.css'),'utf8');
const used=[...new Set([...css.matchAll(/var\(--dq-([a-z0-9-]+)\)/g)].map(m=>m[1]))];
result.tokens={used:used.length,missing:used.filter(k=>!(k in tokens))};
const server=http.createServer(async(req,res)=>{try{const p=path.resolve(root,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));if(!p.startsWith(root+path.sep)){res.writeHead(403).end();return;}const data=await fs.readFile(p);const ext=path.extname(p);res.writeHead(200,{'Content-Type':{'.html':'text/html;charset=utf-8','.css':'text/css','.js':'text/javascript','.png':'image/png'}[ext]||'text/plain'}).end(data);}catch{res.writeHead(404).end();}});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
const base=`http://127.0.0.1:${server.address().port}`;
let browser;
try{
  browser=await chromium.launch({headless:true,executablePath:'/Users/lanull/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'});
  const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1});
  page.on('pageerror',e=>result.errors.push(e.message));
  await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('data:')?r.continue():r.abort());
  const scenes=['foundations','controls','patterns'];
  for(let i=0;i<scenes.length;i++){
    await page.goto(`${base}/components.html#${scenes[i]}`);await page.evaluate(()=>document.fonts.ready);
    const metrics=await page.evaluate(()=>({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,icons:document.querySelectorAll('svg.lucide').length,unrenderedIcons:document.querySelectorAll('i[data-lucide]').length,overflow:document.documentElement.scrollWidth>innerWidth}));
    await page.screenshot({path:path.join(root,'assets',`${String(i+1).padStart(2,'0')}-${scenes[i]}.png`),fullPage:true});
    result.screens.push({scene:scenes[i],...metrics});
    if(metrics.overflow||metrics.unrenderedIcons)result.errors.push(`${scenes[i]} overflow or missing icons`);
    await page.setViewportSize({width:390,height:844});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    if(overflow)result.errors.push(`${scenes[i]} mobile overflow`);
    await page.setViewportSize({width:1280,height:900});
  }
  await page.goto(`${base}/components.html#controls`);
  await page.locator('[data-tab="tasks"]').click();result.interactions.tabs=(await page.locator('#tab-panel').innerText()).includes('任务');
  await page.locator('#dev-switch').check();result.interactions.dev=(await page.locator('[data-feedback]').innerText()).includes('Dev 开启');
  const before=await page.locator('[data-load]').boundingBox();await page.locator('[data-load]').click();const during=await page.locator('[data-load]').boundingBox();
  result.interactions.loading={disabled:await page.locator('[data-load]').isDisabled(),widthStable:before.width===during.width};
  await page.waitForFunction(()=>!document.querySelector('[data-load]').disabled);
  await page.goto(`${base}/components.html#patterns`);await page.locator('[data-remove]').click();
  result.interactions.attachmentRemoved=await page.locator('.attachment').count()===0;
  await page.locator('textarea').fill('示例消息');await page.locator('[data-send]').click();result.interactions.send=(await page.locator('textarea').inputValue())==='';
  result.interactions.statusAlignment=await page.locator('.task-head>span,.task-state').evaluateAll(els=>els.map(el=>{const r=el.getBoundingClientRect();return {x:r.x,width:r.width};}));
  execFileSync(process.execPath,['/Users/lanull/.codex/report-tools/render-md-report.mjs',path.join(root,'DESIGN-SYSTEM.md'),path.join(root,'DESIGN-SYSTEM.html'),'大乔界面设计规范 v1']);
  let html=await fs.readFile(path.join(root,'DESIGN-SYSTEM.html'),'utf8');
  for(const m of [...html.matchAll(/<img\s+[^>]*src="(assets\/[^"<>]+\.png)"[^>]*>/g)]){const data=(await fs.readFile(path.join(root,m[1]))).toString('base64');html=html.replace(m[0],`<button class="spec-image" type="button" aria-label="放大组件样板">${m[0].replace(`src="${m[1]}"`,`src="data:image/png;base64,${data}"`)}</button>`);}
  html=html.replace('Report<br>HTML','大乔<br><small>设计规范</small>');
  html=html.replace('</head>',`<style>
    :root{--bg:#EDF3F7;--paper:#fff;--ink:#31495B;--muted:#52697A;--line:#DCE6ED;--accent:#476D89;--accent-2:#3E617C;--dark:#31495B}
    body{background:linear-gradient(140deg,#DCE8F1,#EAF0F3 48%,#F4EEE7);font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.85}
    .layout{grid-template-columns:240px minmax(0,1fr)}aside{background:#F7FAFC;color:#31495B;border-right:1px solid #DCE6ED}.mark{font:28px/1.3 inherit;letter-spacing:0}.mark small{font-size:13px}.meta{color:#607487}
    .toc{color:#52697A;font-size:13px}.toc-3{color:#607487;font-size:12px}.toc:hover{color:#31495B;background:#E7F0F6}.mark,h1,h2,h3,th{font-family:inherit;text-transform:none;letter-spacing:0}
    h1{font-size:36px;line-height:1.4}h2{font-size:24px;line-height:1.5;border-top:1px solid #DCE6ED}h3{font-size:18px;line-height:1.5}p,li{font-size:15px;max-width:980px}main{padding:40px 4vw 80px}article{max-width:1120px}
    table{box-shadow:none;background:#fff;font-size:14px}th{background:#E7F0F6;color:#31495B}th,td{border:1px solid #DCE6ED;overflow-wrap:anywhere}code{background:#E7F0F6;color:#31495B;border:0}pre{background:#E7F0F6;color:#31495B;border:0}
    .spec-image{display:block;border:0;padding:0;width:100%;background:#fff;border-radius:16px;overflow:hidden;margin:22px 0;cursor:zoom-in}.spec-image img{display:block;width:100%;height:auto}
    dialog{max-width:96vw;max-height:96vh;border:0;border-radius:16px;padding:16px;background:white}dialog::backdrop{background:#1B2C3A99}dialog img{display:block;max-width:90vw;max-height:85vh;object-fit:contain}dialog button{background:#E7F0F6;border:0;color:#31495B;padding:8px 16px;border-radius:8px;margin-bottom:12px}
    @media(max-width:860px){.layout{display:block}aside{position:relative;max-height:none;height:auto}aside nav{max-height:200px;overflow:auto}main{padding:24px 16px}h1{font-size:28px}table{display:block;overflow-x:auto}}
  </style></head>`);
  html=html.replace('</body>',`<dialog><button type="button">关闭</button><img alt="组件样板放大预览"></dialog><script>const d=document.querySelector('dialog');document.querySelectorAll('.spec-image').forEach(b=>b.onclick=()=>{d.querySelector('img').src=b.querySelector('img').src;d.showModal();});d.querySelector('button').onclick=()=>d.close();d.onclick=e=>{if(e.target===d)d.close();};</script></body>`);
  await fs.writeFile(path.join(root,'DESIGN-SYSTEM.html'),html);
  await page.goto(`${base}/DESIGN-SYSTEM.html`);result.report=await page.evaluate(()=>({images:[...document.querySelectorAll('.spec-image img')].filter(i=>i.complete&&i.naturalWidth).length,overflow:document.documentElement.scrollWidth>innerWidth,headings:document.querySelectorAll('h2').length}));
  await page.screenshot({path:path.join(root,'assets','qa-report.png')});
  await page.locator('.spec-image').first().click();result.report.zoom=await page.locator('dialog').evaluate(d=>d.open);await page.locator('dialog button').click();
  await page.setViewportSize({width:390,height:844});result.report.mobileOverflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(result.contrast.some(c=>!c.pass))result.errors.push('contrast failure');if(result.tokens.missing.length)result.errors.push('missing token');
  if(result.report.images!==3||result.report.overflow||result.report.mobileOverflow)result.errors.push('report render failure');
  const md=await fs.readFile(path.join(root,'DESIGN-SYSTEM.md'),'utf8');result.links=[];
  for(const m of md.matchAll(/!?\[[^\]]*\]\(([^)]+)\)/g)){if(/^https?:|^#/.test(m[1]))continue;const p=path.resolve(root,m[1].split('#')[0]);try{await fs.access(p);result.links.push({href:m[1],exists:true});}catch{result.errors.push('missing link '+m[1]);}}
  await fs.writeFile(path.join(root,'verification.json'),JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify(result,null,2));if(result.errors.length)process.exitCode=1;
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

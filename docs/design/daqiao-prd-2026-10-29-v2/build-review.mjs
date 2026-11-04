// Design documentation renderer. No product API, model or game calls.
import fs from 'node:fs/promises';
import path from 'node:path';
import http from 'node:http';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import crypto from 'node:crypto';
const root=path.dirname(fileURLToPath(import.meta.url));
const ds=path.resolve(root,'../daqiao-design-system-2026-10-29-v2');
const designRoot=path.dirname(root);
const deps='/Users/lanull/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const require=createRequire(import.meta.url),{chromium}=require(path.join(deps,'playwright'));
const {tokens}=JSON.parse(await fs.readFile(path.join(ds,'tokens.json'),'utf8'));
const tokenCss='/* Generated from design-system v2 tokens.json. */\n:root {\n'+Object.entries(tokens).map(([k,v])=>`  --dq-${k}: ${v};`).join('\n')+'\n}\n';
for(const dir of [root,ds]){
  await fs.mkdir(path.join(dir,'assets'),{recursive:true});
  await fs.writeFile(path.join(dir,'tokens.css'),tokenCss);
  await fs.copyFile(path.join(deps,'lucide/dist/umd/lucide.min.js'),path.join(dir,'lucide.js'));
  await fs.copyFile(path.join(deps,'lucide/LICENSE'),path.join(dir,'LUCIDE-LICENSE.txt'));
}
const prdScenes=['chat','account','tasks','task-detail','models','add-service','brief','dev','binding','account-rules','scheduled','account-detail','developer','sync','sync-chat'];
const dsScenes=['foundations','controls','patterns','sync'];
const report={date:'2026-10-29',scope:'documents, design mockups and local simulated interactions only',screens:[],checks:{},errors:[]};
function assert(ok,message){if(!ok)report.errors.push(message);return ok;}
const luminance=h=>h.slice(1).match(/../g).map(v=>parseInt(v,16)/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((s,v,i)=>s+v*[.2126,.7152,.0722][i],0);
const contrast=(a,b)=>{const x=luminance(a),y=luminance(b);return(Math.max(x,y)+.05)/(Math.min(x,y)+.05);};
report.contrast=[['text-primary','bg-start',4.5],['text-secondary','bg-start',4.5],['on-primary','primary',4.5],['text-secondary','danger-bg',4.5],['primary-hover','surface-user',4.5],['border-control','bg-start',3]].map(([fg,bg,target])=>{const ratio=contrast(tokens[fg],tokens[bg]);assert(ratio>=target,`contrast ${fg}/${bg}`);return{fg,bg,ratio,target};});
for(const [dir,file] of [[root,'mockups.css'],[ds,'components.css']]){
  const css=await fs.readFile(path.join(dir,file),'utf8');
  const used=[...new Set([...css.matchAll(/var\(--dq-([a-z0-9-]+)/g)].map(m=>m[1]))];
  const missing=used.filter(k=>!(k in tokens));assert(missing.length===0,`Missing tokens in ${file}: ${missing.join(', ')}`);
  report.checks[file]={referencedTokens:used.length,missing};
}
const server=http.createServer(async(req,res)=>{try{
  const p=path.resolve(designRoot,'.'+decodeURIComponent(new URL(req.url,'http://localhost').pathname));
  if(![root,ds].some(dir=>p.startsWith(dir+path.sep))){res.writeHead(403).end();return;}
  const body=await fs.readFile(p),ext=path.extname(p);res.writeHead(200,{'Content-Type':{'.html':'text/html;charset=utf-8','.js':'text/javascript','.css':'text/css','.png':'image/png'}[ext]||'text/plain'}).end(body);
}catch{res.writeHead(404).end();}});
await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
const base=`http://127.0.0.1:${server.address().port}`;
let browser;
const url=(dir,file,hash='')=>`${base}/${path.basename(dir)}/${file}${hash?'#'+hash:''}`;
try{
  browser=await chromium.launch({headless:true,executablePath:'/Users/lanull/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'});
  const page=await browser.newPage({viewport:{width:1280,height:900},deviceScaleFactor:1});
  page.on('pageerror',e=>report.errors.push(e.message));
  await page.route('**/*',r=>r.request().url().startsWith(base)||r.request().url().startsWith('data:')?r.continue():r.abort());
  for(const [dir,file,scenes] of [[root,'mockups.html',prdScenes],[ds,'components.html',dsScenes]]){
    for(let i=0;i<scenes.length;i++){
      await page.setViewportSize({width:1280,height:900});await page.goto(url(dir,file,scenes[i]));await page.evaluate(()=>document.fonts.ready);await page.waitForTimeout(80);
      const state=await page.evaluate(()=>({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,icons:document.querySelectorAll('svg.lucide').length,unrenderedIcons:document.querySelectorAll('i[data-lucide]').length,title:document.body.innerText.slice(0,100)}));
      assert(state.width<=1280,`${file}#${scenes[i]} desktop overflow`);assert(state.unrenderedIcons===0,`${file}#${scenes[i]} missing icons`);
      await page.screenshot({path:path.join(dir,'assets',`${String(i+1).padStart(2,'0')}-${scenes[i]}.png`),fullPage:true});
      const widths=[];for(const width of [1024,768,390]){await page.setViewportSize({width,height:900});const sw=await page.evaluate(()=>document.documentElement.scrollWidth);widths.push({width,scrollWidth:sw});assert(sw<=width,`${file}#${scenes[i]} overflow at ${width}: ${sw}`);}
      report.screens.push({file,scene:scenes[i],...state,widths});
    }
  }
  await page.setViewportSize({width:1280,height:900});
  // Interaction checks are populated after inspecting the current mockup selectors.
  await runInteractions(page,url,root,ds,report,assert);
  const style=`
    :root{color-scheme:light;--ink:#31495B;--muted:#52697A;--line:#DCE6ED;--accent:#476D89;--accent-2:#3E617C}
    *{box-sizing:border-box}body{margin:0;color:var(--ink);background:linear-gradient(140deg,#DCE8F1,#EAF0F3 48%,#F4EEE7);font:15px/1.85 "Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
    .layout{display:grid;grid-template-columns:240px minmax(0,1fr);min-height:100vh}aside{position:sticky;top:0;height:100vh;overflow:auto;background:#F7FAFC;padding:28px 20px;border-right:1px solid var(--line)}.mark{font-size:28px;line-height:1.3;margin-bottom:16px}.mark small{font-size:13px}.meta{font-size:12px;color:var(--muted);margin-bottom:20px}
    .toc{display:block;font-size:13px;color:var(--muted);padding:6px 4px;text-decoration:none;border:0;line-height:1.5}.toc-3{padding-left:16px;font-size:12px}.toc:hover{background:#E7F0F6;color:var(--ink)}main{min-width:0;padding:40px 4vw 80px}article{max-width:1120px;margin:auto}h1{font-size:34px;line-height:1.4}h2{font-size:24px;line-height:1.5;margin-top:40px;padding-top:24px;border-top:1px solid var(--line);color:var(--accent)}h3{font-size:18px;line-height:1.5;margin-top:28px}p,li{max-width:980px}a{color:var(--accent-2);text-decoration:none;border-bottom:1px solid #A5BBCB}code{background:#E7F0F6;padding:2px 4px;border-radius:4px;font-family:Consolas,monospace;font-size:.9em}pre{background:#E7F0F6;padding:16px;border-radius:12px;overflow:auto}pre code{padding:0}
    table{width:100%;border-collapse:collapse;background:#fff;margin:20px 0;font-size:14px}td,th{border:1px solid var(--line);padding:10px 12px;vertical-align:top;text-align:left;overflow-wrap:anywhere}th{background:#E7F0F6}blockquote{border-left:3px solid var(--accent);padding-left:16px;color:var(--muted)}.doc-image{display:block;padding:0;border:0;border-radius:16px;overflow:hidden;width:100%;margin:24px 0;cursor:zoom-in;background:white}.doc-image img{display:block;width:100%;height:auto}
    dialog{border:0;border-radius:16px;max-width:96vw;max-height:96vh;padding:16px}dialog::backdrop{background:#1B2C3A99}dialog img{display:block;max-width:90vw;max-height:82vh;object-fit:contain}dialog button{font:14px inherit;color:var(--ink);background:#E7F0F6;border:0;border-radius:8px;padding:8px 16px;margin-bottom:12px}
    @media(max-width:860px){.layout{display:block}aside{position:relative;height:auto}aside nav{max-height:220px;overflow:auto}main{padding:24px 16px}h1{font-size:28px}table{display:block;overflow:auto}}@media print{aside{display:none}.layout{display:block}body{background:white}main{padding:0}.doc-image{break-inside:avoid}}
  `;
  report.documents=[];
  for(const [dir,stem,label] of [[root,'PRD','大乔 PRD v2'],[ds,'DESIGN-SYSTEM','大乔设计规范 v2']]){
    const mdPath=path.join(dir,stem+'.md'),htmlPath=path.join(dir,stem+'.html');
    execFileSync(process.execPath,['/Users/lanull/.codex/report-tools/render-md-report.mjs',mdPath,htmlPath,label]);
    let html=await fs.readFile(htmlPath,'utf8');
    html=html.replace(/<style>[\s\S]*?<\/style>/,`<style>${style}</style>`).replace('Report<br>HTML',`大乔<br><small>${stem==='PRD'?'产品需求 v2':'设计规范 v2'}</small>`);
    const images=[...html.matchAll(/<img\s+[^>]*src="(assets\/[^"<>]+\.png)"[^>]*>/g)];
    for(const m of images){const data=(await fs.readFile(path.join(dir,m[1]))).toString('base64');html=html.replace(m[0],`<button class="doc-image" type="button" aria-label="放大设计样图">${m[0].replace(`src="${m[1]}"`,`src="data:image/png;base64,${data}"`)}</button>`);}
    html=html.replace('</body>',`<dialog id="image-zoom"><button type="button">关闭</button><img alt="设计样图放大"></dialog><script>const d=document.getElementById('image-zoom');document.querySelectorAll('.doc-image').forEach(b=>b.onclick=()=>{d.querySelector('img').src=b.querySelector('img').src;d.showModal();});d.querySelector('button').onclick=()=>d.close();d.onclick=e=>{if(e.target===d)d.close();};</script></body>`);
    await fs.writeFile(htmlPath,html);
    const md=await fs.readFile(mdPath,'utf8'),links=[];
    for(const m of md.matchAll(/!?\[[^\]]*\]\(([^)]+)\)/g)){if(/^https?:|^#/.test(m[1]))continue;links.push(m[1]);(report.linkChecks??=[]).push({stem,href:m[1],target:path.resolve(dir,m[1].split('#')[0])});}
    await page.setViewportSize({width:1440,height:1000});await page.goto(url(dir,stem+'.html'));await page.evaluate(()=>document.fonts.ready);
    const metrics=await page.evaluate(()=>({headings:document.querySelectorAll('h2').length,images:[...document.querySelectorAll('.doc-image img')].filter(i=>i.complete&&i.naturalWidth>0).length,overflow:document.documentElement.scrollWidth>innerWidth}));
    assert(metrics.images===images.length,`${stem} images`);assert(!metrics.overflow,`${stem} desktop overflow`);
    await page.screenshot({path:path.join(dir,'assets','qa-reading.png')});
    if(images.length){await page.locator('.doc-image').first().click();assert(await page.locator('dialog').evaluate(d=>d.open),`${stem} image zoom`);await page.locator('dialog button').click();}
    await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${stem} mobile overflow`);
    report.documents.push({stem,...metrics,links,sourceHash:crypto.createHash('sha256').update(md).digest('hex')});
  }
  for(const check of report.linkChecks){try{await fs.access(check.target);check.exists=true;}catch{check.exists=false;report.errors.push(`${check.stem} missing link ${check.href}`);}}
  for(const dir of [root,ds])await fs.writeFile(path.join(dir,'verification.json'),JSON.stringify(report,null,2)+'\n');
  console.log(JSON.stringify({screens:report.screens.length,documents:report.documents.map(d=>({name:d.stem,images:d.images})),checks:report.checks,errors:report.errors},null,2));
  if(report.errors.length)process.exitCode=1;
}finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}

async function runInteractions(page,url,root,ds,report,assert){
  const checks={};report.checks.components=checks;
  await page.goto(url(ds,'components.html','controls'));
  const load=page.locator('[data-load]');await load.focus();const before=await load.boundingBox();await load.click();const during=await load.boundingBox();
  checks.loading=await load.evaluate(el=>({focused:document.activeElement===el,busy:el.getAttribute('aria-busy'),ariaDisabled:el.getAttribute('aria-disabled'),nativeDisabled:el.disabled,spinner:!!el.querySelector('svg')}));
  checks.loading.widthStable=before.width===during.width;
  assert(checks.loading.focused&&checks.loading.busy==='true'&&checks.loading.ariaDisabled==='true'&&!checks.loading.nativeDisabled&&checks.loading.spinner&&checks.loading.widthStable,'Loading focus/state/width');
  await page.waitForFunction(()=>document.querySelector('[data-load]').getAttribute('aria-busy')==='false');
  const first=page.locator('[data-tab]').first();await first.focus();await first.press('End');
  assert(await page.locator('[data-tab="models"]').getAttribute('aria-selected')==='true','Tab End');
  await page.locator('[data-tab="models"]').press('ArrowLeft');assert(await page.locator('[data-tab="evidence"]').getAttribute('aria-selected')==='true','Tab left direction');
  await page.locator('[data-tab="evidence"]').press('Home');assert(await first.getAttribute('aria-selected')==='true','Tab Home');
  checks.tabStops=await page.locator('[data-tab]').evaluateAll(els=>els.filter(el=>el.tabIndex===0).length);assert(checks.tabStops===1,'Roving tabindex');
  checks.readonly=await page.locator('[data-readonly]').evaluate(el=>({readOnly:el.readOnly,disabled:el.disabled}));assert(checks.readonly.readOnly&&!checks.readonly.disabled,'Readonly vs disabled');
  checks.buttonSizes=await page.locator('[data-size]').evaluateAll(els=>els.map(el=>({size:el.dataset.size,height:el.getBoundingClientRect().height})));assert(checks.buttonSizes.every(x=>x.height===({sm:32,md:36,lg:44}[x.size])),'Button sizes');
  await page.locator('#dev-switch').check();assert((await page.locator('[data-switch-label]').innerText())==='已开启','Switch visible state');
  const rgbHex=s=>'#'+s.match(/[\d.]+/g).slice(0,3).map(v=>Math.round(Number(v)).toString(16).padStart(2,'0')).join('');
  await page.locator('[data-ghost]').hover();
  const ghost=await page.locator('[data-ghost]').evaluate(el=>({fg:getComputedStyle(el).color,bg:getComputedStyle(el).backgroundColor}));
  await page.waitForTimeout(160);
  const ghostFinal=await page.locator('[data-ghost]').evaluate(el=>({fg:getComputedStyle(el).color,bg:getComputedStyle(el).backgroundColor}));
  const error=await page.locator('input.is-error').evaluate(el=>({fg:getComputedStyle(el,'::placeholder').color,bg:getComputedStyle(el).backgroundColor}));
  checks.actualContrast={ghost:contrast(rgbHex(ghostFinal.fg),rgbHex(ghostFinal.bg)),errorPlaceholder:contrast(rgbHex(error.fg),rgbHex(error.bg))};assert(checks.actualContrast.ghost>=4.5&&checks.actualContrast.errorPlaceholder>=4.5,'Actual hover/error contrast');
  await page.goto(url(ds,'components.html','patterns'));await page.locator('[data-remove]').click();assert(await page.locator('.attachment').count()===0,'Attachment remove');await page.locator('textarea').fill('示例');await page.locator('[data-send]').click();assert(await page.locator('textarea').inputValue()==='','Example send');
  checks.status=await page.locator('[data-task-group] .task-head>span,[data-task-group] .task-state').evaluateAll(els=>els.map(el=>({width:el.getBoundingClientRect().width,x:el.getBoundingClientRect().x,fontSize:getComputedStyle(el).fontSize})));
  assert(checks.status.every(x=>x.width===88&&x.x===checks.status[0].x&&x.fontSize==='14px'),'Status alignment/type');
  await page.locator('[data-wide-status]').click();assert(await page.locator('[data-task-group] .task-state').first().evaluate(el=>el.getBoundingClientRect().width)===132,'Wide status column');
  await page.goto(url(ds,'components.html','sync'));await page.locator('[data-sync-retry]').click();await page.waitForFunction(()=>document.querySelector('[data-sync-message-status]').textContent.includes('已同步'));checks.syncRetry=true;
  await page.locator('[data-sync-login]').click();assert((await page.locator('[data-sync-message-status]').innerText()).includes('需要登录'),'Expired sync session');
  const product={mockOnly:true};report.checks.product=product;
  let scenarioId=0;
  const go=hash=>page.goto(url(root,'mockups.html')+'?scenario='+(++scenarioId)+'#'+hash);
  const hash=async value=>{await page.evaluate(value=>{location.hash=value;},value);await page.waitForFunction(value=>document.querySelector('.app')?.dataset.screen===value,value);};
  await go('models');assert(await page.locator('[data-enable-model]').isDisabled(),'Unverified model enable blocked');assert(await page.locator('[data-action="set-primary"]').isDisabled(),'Unverified primary blocked');
  await page.locator('[data-action="test-model"]').click();assert(await page.locator('[data-action="test-model"]').evaluate(el=>document.activeElement===el),'Model test focus retained');await page.waitForFunction(()=>!document.querySelector('[data-enable-model]').disabled);await page.locator('[data-enable-model]').check();await page.locator('[data-action="set-primary"]').click();
  product.modelWorkflow=await page.locator('[data-primary]').inputValue()==='chat-fast';assert(product.modelWorkflow,'Model test-enable-primary flow');
  assert((await page.locator('[data-candidate]').innerText()).includes('尚未准入'),'Technical test does not grant action admission');
  await go('binding');await page.locator('[data-action="check-binding"]').click();product.duplicateBinding=(await page.locator('.content').innerText()).includes('不新建第二个');assert(product.duplicateBinding,'Duplicate role binding');
  await go('account');await page.locator('[data-action="toggle-viewer"]').first().click();assert(await page.locator('[data-viewer]').count()===0,'Viewer closes');await page.locator('[data-action="toggle-viewer"]').first().click();assert(await page.locator('[data-viewer]').count()===1,'Viewer reopens');
  await go('account-rules');await page.locator('[data-action="propose-rule"]').click();assert(await page.locator('[data-action="apply-rule"]').isDisabled(),'Unconfirmed rule apply blocked');await page.locator('[data-confirm-rule]').check();await page.locator('[data-action="apply-rule"]').click();product.ruleVersion=await page.evaluate(()=>state.ruleVersion);assert(product.ruleVersion===4,'Confirmed rule version');
  await go('task-detail');await page.locator('[data-action="cancel-task"]').click();product.cancelPending=await page.evaluate(()=>state.task==='cancelled'&&state.effectPending);assert(product.cancelPending,'Cancelled task keeps pending effect');await page.locator('[data-action="resolve-effect"]').click();assert(await page.evaluate(()=>state.task==='cancelled'&&!state.effectPending),'Reconciliation does not flip cancellation');
  await go('scheduled');await page.locator('[data-action="toggle-schedule"]').click();assert(await page.evaluate(()=>!state.scheduled),'Disable recurring plan');await page.locator('[data-action="toggle-schedule"]').click();await page.locator('[data-schedule-time]').fill('21:30');await page.locator('[data-action="save-schedule"]').click();assert(await page.evaluate(()=>state.time==='21:30'),'Edit schedule example');
  await go('developer');assert(await page.locator('.tabs a[href="#dev"]').count()===0,'Dev off hides tab');await page.locator('[data-dev]').check();assert(await page.locator('.tabs a[href="#dev"]').count()===1,'Dev on exposes tab');await page.locator('[data-dev]').uncheck();assert(await page.locator('.tabs a[href="#dev"]').count()===0,'Dev off restores navigation');
  await go('sync-chat');await page.locator('[data-compose]').fill('分析刚才的结果');await page.locator('[data-action="mac-send"]').click();assert(await page.evaluate(()=>state.macMessages.length===1&&state.task==='running'),'Mac reply has no game mutation');
  await hash('task-detail');product.macPersistent=await page.evaluate(()=>state.platform==='mac');assert(product.macPersistent,'Mac platform persists across navigation');assert(await page.locator('[data-action="cancel-task"]').isDisabled(),'Mac mutation UI blocked');
  await page.locator('[data-action="cancel-task"]').evaluate(el=>el.dispatchEvent(new MouseEvent('click',{bubbles:true})));assert(await page.evaluate(()=>state.task==='running'),'Mac mutation handler blocked');
  await hash('sync');await page.locator('[data-action="toggle-sync"]').click();await hash('sync-chat');await page.locator('[data-compose]').fill('离线消息示例');await page.locator('[data-action="mac-send"]').click();assert(await page.evaluate(()=>state.macMessages.at(-1).synced===false),'Offline message not delivered');
  await hash('sync');await page.locator('[data-action="toggle-sync"]').click();assert(await page.evaluate(()=>state.macMessages.length===2&&state.macMessages.every(m=>m.synced)),'Reconnect does not duplicate messages');await page.locator('[data-action="toggle-login"]').click();assert((await page.locator('.sync-mini').innerText()).includes('需要登录'),'Logged out header cannot claim synced');
  product.syncScope='simulated status and permissions only; no real transport tested';
}

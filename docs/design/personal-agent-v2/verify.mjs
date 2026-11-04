import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require=createRequire(import.meta.url);
const playwrightPath=process.env.PLAYWRIGHT_MODULE||'/Users/lanull/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright';
const {chromium}=require(playwrightPath);
const root=path.dirname(fileURLToPath(import.meta.url));
const output=path.join(root,'previews');fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||'/Users/lanull/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'});
const page=await browser.newPage({viewport:{width:1440,height:1050},deviceScaleFactor:1,reducedMotion:'reduce'});
const errors=[],checks=[],requests=[];
page.on('pageerror',e=>errors.push(e.message));
await page.route('**/*',route=>{const u=new URL(route.request().url());requests.push(u.hostname);return ['127.0.0.1','localhost'].includes(u.hostname)?route.continue():route.abort();});
const state=()=>page.evaluate(()=>window.DesignDemo.getState());
const click=(action,id)=>page.locator(`[data-action="${action}"]${id?`[data-id="${id}"]`:''}`).last().click();
const go=async route=>{await page.evaluate(route=>window.DesignDemo.navigate(route),route);};
const mark=s=>checks.push(s);
try {
  await page.goto(process.env.PREVIEW_URL||'http://127.0.0.1:8770/personal-agent-v2/');await page.evaluate(()=>window.DesignDemo.reset());
  assert.equal(await page.locator('.capability-card').count(),4);mark('对话首页明确列出四类能力');await click('context-panel');assert(await page.locator('#dialog-title').innerText()==='当前角色与安排');await page.keyboard.press('Escape');mark('顶部可查看当前角色与任务');
  for(const route of ['home','chat','tasks','roles','knowledge','battle','activity','settings']){
    await go(route);assert(await page.locator('h1').count()>0);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
    await page.screenshot({path:path.join(output,route+'.png'),animations:'disabled'});mark('页面可打开且无横向溢出：'+route);
  }
  await go('chat');await page.locator('#chat-input').fill('今晚先升级建筑，之后检查主力队伍');await click('send-chat');
  await click('new-task','今晚先升级建筑，之后检查主力队伍');assert.equal(await page.locator('#task-title').inputValue(),'今晚先升级建筑，之后检查主力队伍');mark('聊天目标保留到确认向导');
  await page.locator('#task-title').fill('');await click('wizard-next');assert(await page.locator('.field-error').isVisible());mark('空目标被拦截');
  await page.locator('#task-title').fill('演示：完成当前章节前置');await click('wizard-next');
  for(const c of await page.locator('[name="task-allow"]').all())await c.uncheck();await click('wizard-next');assert(await page.locator('.field-error').isVisible());mark('空操作范围被拦截');
  await page.locator('[name="task-allow"][value="观察状态"]').check();await click('wizard-next');await page.screenshot({path:path.join(output,'confirm-task.png'),animations:'disabled'});
  const count=(await state()).tasks.length;await click('wizard-create');const s=await state(),id=s.tasks[0].id;assert.equal(s.tasks.length,count+1);assert.equal(s.tasks.filter(t=>t.roleId==='wind'&&t.status==='running').length,1);mark('确认仅创建一个任务，同角色仅一个任务执行');
  await page.locator('#toast').evaluate(e=>e.classList.remove('visible'));await page.screenshot({path:path.join(output,'task-detail.png'),animations:'disabled'});
  await click('pause-task',id);const progress=(await state()).tasks.find(t=>t.id===id).progress;await click('advance-task',id);assert.equal((await state()).tasks.find(t=>t.id===id).progress,progress);mark('暂停后不能推进');
  await click('resume-task',id);await click('advance-task',id);assert.equal((await state()).tasks.find(t=>t.id===id).progress,20);mark('继续后从原进度推进');
  await click('takeover',id);await click('confirm-takeover');assert.equal((await state()).manual,true);assert.equal((await state()).tasks.find(t=>t.id===id).status,'manual');mark('人工接管暂停自动任务');
  await click('role-picker');await click('switch-role','north');assert.equal((await state()).manual,false);await click('role-picker');await click('switch-role','wind');assert.equal((await state()).manual,true);mark('接管状态按角色保存');
  await click('handback');assert.equal((await state()).tasks.find(t=>t.id===id).status,'paused');mark('交还后重新检查，不自动执行');
  await go('tasks');await click('task-detail',id);await click('resume-task',id);await page.keyboard.press('Escape');await go('settings');
  await click('connection-toggle');assert.equal((await state()).tasks.find(t=>t.id===id).status,'disconnected');await page.locator('#toast').evaluate(e=>e.classList.remove('visible'));await page.screenshot({path:path.join(output,'offline.png'),animations:'disabled'});await go('tasks');await click('task-detail',id);await click('resume-task',id);assert.equal((await state()).tasks.find(t=>t.id===id).status,'disconnected');mark('断连保留进度，不能假恢复');
  await page.keyboard.press('Escape');await click('connection-toggle');await go('tasks');await click('task-detail',id);assert.equal((await state()).tasks.find(t=>t.id===id).status,'paused');mark('重连后仍需确认继续');
  await click('cancel-task',id);await click('confirm-cancel',id);assert.equal((await state()).tasks.find(t=>t.id===id).status,'cancelled');assert.equal(await page.locator(`[data-action="resume-task"][data-id="${id}"]`).count(),0);mark('取消为终态，不可继续');await page.keyboard.press('Escape');
  await go('chat');await page.locator('#chat-input').fill('继续');await click('send-chat');assert.equal((await state()).tasks.filter(t=>t.roleId==='wind'&&t.status==='running').length,1);mark('聊天继续遵循同角色任务互斥');
  await click('role-picker');await click('switch-role','north');if(await page.locator('[data-action="confirm-role"]').count())await click('confirm-role','north');assert.equal((await state()).role.id,'north');assert.equal(await page.locator('[data-action="task-detail"][data-id="task-1"]').count(),0);mark('角色聊天与任务卡不混用');
  await go('settings');assert.equal(await page.locator('[name="resourceReserve"]').inputValue(),'1000');await page.locator('[name="resourceReserve"]').fill('1200');await click('save-settings');await page.reload();assert.equal((await state()).settings.resourceReserve,1200);mark('偏好按角色保存并可刷新恢复');
  await click('role-picker');await click('switch-role','wind');assert.equal((await state()).settings.resourceReserve,500);mark('角色偏好不串用');
  await go('knowledge');await click('import-knowledge');await page.locator('#kb-title').fill('测试攻略');await page.locator('#kb-url').fill('示例原文第3段');await click('create-kb');const kb=(await state()).knowledge[0];assert.equal(kb.status,'pending');await click('approve-kb',kb.id);assert.equal((await state()).knowledge[0].status,'reviewed');mark('资料导入→待审核→通过');
  await click('ask-kb',kb.id);assert.equal((await state()).route,'chat');assert((await state()).messages.some(m=>m.text.includes('测试攻略')));mark('资料可引用到聊天');
  await go('battle');await click('set-phase','pvp');assert.equal((await state()).role.phase,'pve');await page.locator('#toast').evaluate(e=>e.classList.remove('visible'));await page.screenshot({path:path.join(output,'pvp.png'),animations:'disabled'});mark('PVP预览不修改角色实际阶段');
  await page.evaluate(()=>window.DesignDemo.reset());await go('tasks');await click('task-detail','task-1');await click('advance-task','task-1');await click('advance-task','task-1');assert.equal((await state()).tasks.find(t=>t.id==='task-1').status,'completed');assert((await state()).messages.some(m=>m.text.includes('已完成')));mark('任务完成同步汇报');
  await page.keyboard.press('Escape');await page.setViewportSize({width:390,height:844});
  for(const route of ['home','chat','tasks','roles','knowledge','battle','activity','settings']){await go(route);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'手机宽度溢出 '+route);}
  await go('home');await page.locator('#toast').evaluate(e=>e.classList.remove('visible'));await page.screenshot({path:path.join(output,'mobile.png'),animations:'disabled'});await page.evaluate(()=>window.DesignDemo.reset());await go('chat');await page.screenshot({path:path.join(output,'mobile-chat.png'),animations:'disabled'});mark('390px下8页无横向溢出');
  await page.setViewportSize({width:1440,height:1050});await page.evaluate(()=>window.DesignDemo.reset());await go('home');await page.screenshot({path:path.join(output,'home.png'),animations:'disabled'});await click('connect');await page.screenshot({path:path.join(output,'connect.png'),animations:'disabled'});await page.keyboard.press('Escape');await go('knowledge');await click('review-kb','kb-4');await page.screenshot({path:path.join(output,'knowledge-review.png'),animations:'disabled'});
  assert.equal(errors.length,0,errors.join('\n'));mark('无浏览器脚本错误');
  const report={date:'2026-10-27',checks,passed:checks.length,browserErrors:errors,externalRequests:requests.filter(h=>!['127.0.0.1','localhost'].includes(h)),note:'只验证原型与示例状态，不调用模型或游戏'};
  fs.writeFileSync(path.join(root,'verification.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}

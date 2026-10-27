/* Standalone design preview. All displayed accounts, reports and knowledge are examples. */
(function () {
  'use strict';

  const sourceNames = { rule: '游戏基础知识', rea: '原包解析资料', guide: '玩家攻略' };
  const sourceIcons = { rule: 'book', rea: 'file', guide: 'video' };

  function heading(kicker, title, description, action) {
    return `<div class="page-heading"><div><div class="section-label">${kicker}</div><h1 class="page-title">${title}</h1><p class="page-description">${description}</p></div>${action || ''}</div>`;
  }

  function roles({ state, icon, badge, esc }) {
    const selected = state.role || { id: 'wind', name: '长风', connected: true };
    const roleList = [
      { id: 'wind', name: selected.id === 'wind' ? selected.name : '长风', server: 'S1 · 江山如画', phase: 'PVE 开荒', chapter: '第 8 章', caption: '稳步成长，先把基础打好。', seal: '风', color: 'jade', connected: selected.id === 'wind' ? selected.connected : true, stats: [['势力值', '2,840'], ['主力等级', '24'], ['当前目标', '推进章节']] },
      { id: 'north', name: selected.id === 'north' ? selected.name : '北望', server: 'S2 · 群雄逐鹿', phase: 'PVP 战斗', chapter: '赛季第 18 天', caption: '关注战况，准备下一场交锋。', seal: '北', color: 'clay', connected: selected.id === 'north' ? selected.connected : false, stats: [['势力值', '12,600'], ['主力等级', '42'], ['当前目标', '备战整队']] }
    ];
    return `${heading('ROLES & DEVICES', '角色与设备', '管理游戏角色、客户端连接，以及各角色的目标和偏好。', `<button class="button primary" data-action="connect">${icon('plus')}连接角色</button>`)}
      <div class="grid-2 role-grid">${roleList.map(role => {
        const active = role.id === selected.id;
        role.connected = (state.roles || []).find(item => item.id === role.id)?.connected ?? role.connected;
        const taskCount = (state.tasks || []).filter(task => task.roleId === role.id && !['done', 'completed', 'cancelled'].includes(task.status)).length;
        return `<article class="panel role-card ${active ? 'selected' : ''}">
          <div class="role-banner ${role.color}"><span class="role-seal" aria-hidden="true">${role.seal}</span><span class="pill role-phase">${role.phase}</span>${active ? '<span class="role-current">当前角色</span>' : ''}</div>
          <div class="role-card-body"><div class="split"><div><p class="small-text muted">${esc(role.server)}</p><h2>${esc(role.name)}</h2></div>${badge(role.connected ? 'running' : 'offline', role.connected ? '客户端在线' : '客户端离线')}</div>
            <p class="muted">${role.caption}</p>
            <div class="role-stats">${role.stats.map(([label, value]) => `<div><span class="small-text muted">${label}</span><strong>${value}</strong></div>`).join('')}</div>
            <div class="role-bottom"><span class="small-text muted">${role.chapter} · ${taskCount} 项进行中的安排</span><div class="row"><button class="button quiet small" data-action="edit-role" data-id="${role.id}" aria-label="编辑${esc(role.name)}的偏好">${icon('edit')}偏好</button><button class="button ${active ? 'quiet' : 'primary'} small" data-action="switch-role" data-id="${role.id}">${active ? '查看当前角色' : '切换角色'}${icon('arrow')}</button></div></div>
          </div>
        </article>`;
      }).join('')}</div>
      <section class="panel connection-panel"><div class="panel-head"><div><div class="section-label">CONNECTED COMPUTER</div><h2>执行设备</h2></div>${badge(selected.connected ? 'running' : 'offline', selected.connected ? '连接正常' : '等待连接')}</div>
        <div class="device-row"><div class="device-illustration">${icon('monitor', 36)}</div><div class="device-info"><h3>Lanull 的 Windows</h3><p class="muted">三谋客户端 · 每次只操作一个窗口</p><div class="row small-text"><span class="pill">1920 × 1080</span><span class="muted">${selected.connected ? '最近同步：刚刚' : '设备离线时，任务会保留等待'}</span></div></div><button class="button" data-action="connect">${icon('link')}管理连接</button></div>
      </section>
      <div class="quiet-note">${icon('shield')}切换角色时先处理正在执行的任务。操作授权与资源预算不会跨角色继承。</div>`;
  }

  function knowledge({ state, icon, badge, esc }) {
    const entries = state.knowledge || [];
    const filter = state.kFilter || 'all';
    const query = String(state.kQuery || '').trim().toLowerCase();
    const shown = entries.filter(item => (filter === 'all' || item.source === filter) && (!query || `${item.title} ${item.summary || ''}`.toLowerCase().includes(query)));
    const reviewed = entries.filter(item => item.status === 'reviewed').length;
    return `${heading('KNOWLEDGE LIBRARY', '知识库', '统一管理游戏基础知识、原包解析资料和玩家攻略。', `<button class="button primary" data-action="import-knowledge">${icon('plus')}添加资料</button>`)}
      <div class="knowledge-layout"><aside class="panel knowledge-sidebar"><div class="section-label">三类知识来源</div>
        <div class="knowledge-filters">${[['all', '全部资料', 'book'], ['rule', '游戏基础知识', 'book'], ['rea', '原包解析资料', 'file'], ['guide', '玩家攻略', 'video']].map(([key, title, symbol]) => `<button class="knowledge-filter ${filter === key ? 'active' : ''}" data-action="k-filter" data-id="${key}" aria-pressed="${filter === key}">${icon(symbol)}<span>${title}</span><span class="filter-count">${key === 'all' ? entries.length : entries.filter(item => item.source === key).length}</span></button>`).join('')}</div>
        <div class="knowledge-note"><div class="small-text muted">知识库状态</div><strong>${reviewed} 份已审核</strong><p class="small-text muted">待审资料可预览，审核通过后才供 Agent 使用。</p><div class="row">${icon('checkCircle')}<span class="small-text">保留来源与适用版本</span></div></div>
      </aside><section class="panel knowledge-main"><div class="library-toolbar"><label class="search-field">${icon('search')}<input class="input" data-input="knowledge-search" value="${esc(state.kQuery || '')}" placeholder="搜索规则、武将、攻略…" aria-label="搜索知识资料"></label><span class="small-text muted">${shown.length} 份资料</span></div>
        <div class="knowledge-table-head"><span>资料</span><span>来源</span><span>状态</span><span>操作</span></div>
        <div class="data-list knowledge-list">${shown.map((entry, index) => `<article class="knowledge-row">
          <button class="knowledge-title-button" data-action="kb-detail" data-id="${esc(entry.id)}"><span class="document-icon ${entry.source}">${icon(sourceIcons[entry.source] || 'file', 21)}</span><span><strong>${esc(entry.title)}</strong><span class="small-text muted">${esc(entry.summary || '查看内容、引用与适用范围')}</span></span></button>
          <span class="small-text knowledge-source">${sourceNames[entry.source] || '玩家攻略'}</span><span>${badge(entry.status === 'reviewed' ? 'done' : 'approval', entry.status === 'reviewed' ? '已审核' : '待审核')}</span>
          <button class="button quiet small" data-action="${entry.status === 'reviewed' ? 'ask-kb' : 'review-kb'}" data-id="${esc(entry.id)}">${entry.status === 'reviewed' ? '问问助手' : '去审核'}${icon('arrow', 15)}</button>
        </article>`).join('') || `<div class="empty-state">${icon('search', 32)}<h3>没有找到相关资料</h3><p class="muted">换一个关键词，或者添加一份新的攻略。</p><button class="button" data-action="import-knowledge">添加资料</button></div>`}</div>
      </section></div>
      <section class="knowledge-bottom"><div><span class="section-label">资料使用流程</span><h3>保留来源和适用范围</h3><p class="muted">助手会说明资料适用的赛季、条件和不同说法，再结合当前角色给建议。</p></div><div class="knowledge-steps"><span>添加资料</span>${icon('chevron')}<span>人工审核</span>${icon('chevron')}<span>用于任务</span></div></section>`;
  }

  function battle({ state, icon, badge, map, esc }) {
    const pvp = state.phase === 'pvp';
    const roleName = esc((state.role || {}).name || '长风');
    return `${heading('BATTLEFIELD', pvp ? 'PVP 战斗准备' : 'PVE 开荒态势', pvp ? '查看敌我情况、准备队伍和复盘战报。PVP 交互设计预览。' : '结合章节目标，查看队伍、资源和周边土地。', `<div class="segmented"><button data-action="set-phase" data-id="pve" class="${pvp ? '' : 'active'}" aria-pressed="${!pvp}">PVE 开荒</button><button data-action="set-phase" data-id="pvp" class="${pvp ? 'active' : ''}" aria-pressed="${pvp}">PVP 战斗</button></div>`)}
      <div class="battle-layout"><section class="panel field-map"><div class="panel-head"><div><h2>${pvp ? '前线态势' : '周边土地'}</h2><p class="small-text muted">${roleName} · 战场示意 · 非游戏截图</p></div><span class="pill">${pvp ? '备战阶段' : '主城周边'}</span></div>${map('large')}<div class="map-legend"><span><i class="legend-dot home"></i>己方</span><span><i class="legend-dot target"></i>${pvp ? '关注目标' : '待查看目标'}</span><span class="muted">点击目标查看详情</span></div></section>
        <aside class="stack battle-aside"><section class="panel"><div class="panel-head"><h2>助手建议</h2>${icon('command')}</div><div class="advice-title">${pvp ? '先整备，再决定是否出击' : '先完成章节前置，再扩大占地'}</div><p class="muted">${pvp ? '先检查队伍状态与最新战报。补齐敌方信息后，再比较进攻和防守方案。' : '当前章节需要完成建筑升级。资源恢复后继续升级，再检查主力队伍是否适合打地。'}</p><button class="button primary full-width" data-action="new-task">${icon(pvp ? 'swords' : 'target')}安排${pvp ? '备战' : '下一步'}</button></section>
          <section class="panel compact-panel"><div class="section-label">关注的目标</div><button class="target-row" data-action="land-detail" data-id="land-1"><span class="target-symbol">${icon('flag')}</span><span><strong>${pvp ? '北侧防守位置' : '五级木材地'}</strong><small class="muted">${pvp ? '需要补充最新情报' : '距离 3 格 · 待查看守军'}</small></span>${icon('chevron')}</button><button class="target-row" data-action="land-detail" data-id="land-2"><span class="target-symbol subtle">${icon('flag')}</span><span><strong>${pvp ? '友军集结位置' : '五级石料地'}</strong><small class="muted">${pvp ? '队伍整备后再确认' : '距离 5 格 · 后续备选'}</small></span>${icon('chevron')}</button></section>
        </aside></div>
      <div class="panel-head report-section-heading"><div><div class="section-label">BATTLE REPORTS</div><h2>战报复盘</h2></div><span class="small-text muted">示例战报 · 2 份</span></div>
      <div class="grid-2 report-grid">${[
        { id: 'battle-1', label: pvp ? '前线遭遇战' : '四级土地战斗', result: '获胜', status: 'done', time: '今天 09:18', main: '节奏稳定，注意下一战兵力', sub: '查看队伍表现、消耗与调整建议', type: 'swords' },
        { id: 'battle-2', label: pvp ? '防守战斗复盘' : '五级土地尝试', result: '待复盘', status: 'approval', time: '昨天 21:46', main: '先找出损失原因，再做调整', sub: '对比战法、队伍状态和战斗过程', type: 'file' }
      ].map(report => `<button class="panel report-card" data-action="battle-report" data-id="${report.id}"><div class="split"><span class="row">${icon(report.type)}<span>${report.label}</span></span>${badge(report.status, report.result)}</div><h3>${report.main}</h3><p class="muted small-text">${report.sub}</p><div class="split small-text"><span class="muted">${report.time}</span><span class="text-link">查看复盘 ${icon('arrow', 15)}</span></div></button>`).join('')}</div>`;
  }

  function activity({ state, icon, badge, esc }) {
    const filter = state.eventFilter || 'all';
    const all = state.events || [];
    const shown = all.filter(event => filter === 'all' || event.type === filter);
    const labels = { task: '任务', decision: '决策', system: '系统', approval: '确认' };
    const symbols = { task: 'checkCircle', decision: 'command', system: 'monitor', approval: 'shield' };
    return `${heading('ACTIVITY JOURNAL', '运行记录', '查看助手做了什么、使用了哪些资料，以及实际结果。', `<span class="pill">${icon('clock')}本次设计演示</span>`)}
      <div class="activity-layout"><section class="panel journal-panel"><div class="library-toolbar"><div class="segmented">${[['all', '全部记录'], ['task', '任务'], ['decision', '决策'], ['system', '系统']].map(([key, title]) => `<button class="${filter === key ? 'active' : ''}" data-action="event-filter" data-id="${key}" aria-pressed="${filter === key}">${title}</button>`).join('')}</div><span class="muted small-text">${shown.length} 条记录</span></div>
        <ol class="journal-timeline">${shown.map((event, index) => `<li class="journal-event"><span class="journal-marker ${esc(event.type || 'system')}">${icon(symbols[event.type] || 'activity', 16)}</span><div class="journal-content"><div class="split"><span class="section-label">${labels[event.type] || '运行'}</span><time class="small-text muted">${esc(event.time || '刚刚')}</time></div><button class="journal-title" data-action="trace-detail" data-id="${esc(event.id || String(all.indexOf(event)))}">${esc(event.title)}${icon('arrow', 14)}</button><p class="muted small-text">${esc(event.detail || '查看这一步的输入、依据与结果。')}</p></div></li>`).join('') || `<li class="empty-state">${icon('activity', 30)}<h3>暂时没有这类记录</h3><p class="muted">开始一个任务后，相关过程会显示在这里。</p></li>`}</ol>
      </section><aside class="stack journal-aside"><section class="panel"><div class="section-label">你关心的，不只是结果</div><h2>为什么这样做？</h2><p class="muted">点开任意一条记录，查看当时的角色状态、使用的资料，以及动作后的检查结果。</p><div class="journal-key"><span>${icon('book')}参考了什么</span><span>${icon('target')}准备完成什么</span><span>${icon('checkCircle')}实际完成了什么</span></div></section><section class="panel compact-panel"><div class="row">${icon('shield')}<h3>记录与授权分开</h3></div><p class="small-text muted">操作记录不会扩大权限。修改目标、额度和允许操作范围，都在任务确认时单独展示。</p></section></aside></div>`;
  }

  function settings({ state, icon, badge, esc }) {
    const settings = state.settings || {};
    const role = state.role || { name: '长风', connected: true };
    const reserve = Number.isFinite(Number(settings.resourceReserve)) ? Number(settings.resourceReserve) : 500;
    const checked = value => value ? ' checked' : '';
    return `${heading('PREFERENCES', '偏好与授权', '这些偏好只用于新任务，不会改变已经确认的任务预算。', `<button class="button primary" data-action="save-settings">${icon('check')}保存设置</button>`)}
      <div class="settings-layout"><div class="settings-form stack" id="preferences-form">
        <section class="panel"><div class="panel-head"><div><div class="section-label">PLAYER PREFERENCES</div><h2>开荒偏好</h2></div><span class="pill">${esc(role.name)}</span></div>
          <div class="setting-row"><div><h3>保留金铢</h3><p class="muted small-text">自动安排任务时，不使用这部分预留资源。</p></div><label class="number-field"><input class="input" type="number" name="resourceReserve" min="0" max="999999" step="100" value="${reserve}" aria-label="保留金铢数量"><span>金铢</span></label></div>
          <div class="setting-row"><div><h3>每天停止时间</h3><p class="muted small-text">到点后停止新增操作，保存进度。</p></div><input class="input time-input" type="time" name="stopTime" value="${esc(settings.stopTime || '23:00')}" aria-label="每日停止时间"></div>
          <div class="setting-row"><div><h3>等待条件满足后继续</h3><p class="muted small-text">重新检查状态后，继续已经授权的任务。</p></div><label class="toggle"><input type="checkbox" name="autoResume"${checked(settings.autoResume !== false)} aria-label="等待条件满足后继续"><span aria-hidden="true"></span></label></div>
        </section>
        <section class="panel"><div class="panel-head"><div><div class="section-label">NOTIFICATIONS</div><h2>通知与打扰</h2></div>${icon('bell')}</div>
          <div class="setting-row"><div><h3>只提醒重要变化</h3><p class="muted small-text">目标完成、需要你决定、无法继续时提醒。</p></div><label class="toggle"><input type="checkbox" name="notify"${checked(settings.notify !== false)} aria-label="只提醒重要变化"><span aria-hidden="true"></span></label></div>
          <div class="setting-row"><div><h3>安静模式</h3><p class="muted small-text">普通操作只写入记录，不发送逐条消息。</p></div><label class="toggle"><input type="checkbox" name="quiet"${checked(settings.quiet !== false)} aria-label="安静模式"><span aria-hidden="true"></span></label></div>
        </section>
        <section class="panel"><div class="panel-head"><div><div class="section-label">AUTHORIZATION</div><h2>执行前，明确范围</h2></div>${icon('shield')}</div><div class="permission-list"><div>${icon('checkCircle')}<span>新任务先展示目标、角色与资源预算</span></div><div>${icon('checkCircle')}<span>超出授权范围时，再征求你的决定</span></div><div>${icon('checkCircle')}<span>随时暂停或接管，不丢失任务进度</span></div></div><p class="small-text muted">具体允许操作在每次任务确认中设置，这里不会授予额外权限。</p></section>
      </div><aside class="stack settings-aside"><section class="panel"><div class="section-label">CONNECTION</div><div class="device-illustration small-device">${icon('monitor', 32)}</div><h2>Windows 客户端</h2><p class="muted small-text">${role.connected ? '当前连接正常，可接收已确认任务。' : '连接已中断。任务进度保留，恢复连接后再检查状态。'}</p>${badge(role.connected ? 'running' : 'offline', role.connected ? '在线' : '离线')}<button class="button full-width" data-action="connection-toggle">${icon(role.connected ? 'pause' : 'refresh')}${role.connected ? '模拟断开连接' : '模拟恢复连接'}</button></section>
        <section class="panel compact-panel"><div class="section-label">DESIGN PREVIEW</div><h3>自由探索，随时重来</h3><p class="muted small-text">这是可点击设计稿。任务、角色和操作结果均为示例，不会操作真实游戏。</p><button class="button quiet full-width" data-action="reset-demo">${icon('refresh')}重置演示数据</button></section></aside></div>`;
  }

  window.SecondaryViews = { roles, knowledge, battle, activity, settings };
})();

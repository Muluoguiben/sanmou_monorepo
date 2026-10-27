# 三谋 Personal Agent 设计原型 v1

2026-10-27。简洁白蓝工作台版，作为 [v2 温和渐变版](../personal-agent-v2/index.html)的对比版本保留。

直接用浏览器打开 [index.html](index.html)，无需安装依赖。

覆盖总览、对话、任务、角色、PVE／PVP战场、知识库、运行记录、偏好与授权；包含创建与确认任务、暂停／取消／接管、断连恢复、角色切换、资料审核等流程。

所有数据是设计示例，操作只更新浏览器本地存储；没有模型、游戏、麦克风或外网连接。

[verification.json](verification.json)记录30项自动检查通过；[previews/](previews/)保留真实浏览器渲染截图。测试入口是[verify.mjs](verify.mjs)，Playwright和Chromium路径可通过环境变量覆盖。

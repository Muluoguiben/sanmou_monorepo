---
name: Bridge Screenshot Architecture
description: WSL↔Windows 游戏截图桥接架构——dxcam + proxy 前台切换方案，解决 DX 游戏捕获难题
type: reference
---

## 架构

```
WSL Python (BridgeClient)
  → python.exe bridge_proxy.py (stdin/stdout JSON, 短命进程)
    → TCP localhost:9877
      → python.exe win_bridge_server.py (长驻后台)
        → dxcam (DXGI Desktop Duplication) → 游戏 PNG
```

## 关键文件

- `pioneer-agent/src/pioneer_agent/adapters/bridge_client.py` — WSL 侧客户端
- `pioneer-agent/src/pioneer_agent/adapters/bridge_proxy.py` — Windows python.exe 中转代理
- `pioneer-agent/src/pioneer_agent/adapters/win_bridge_server.py` — Windows 侧截图/点击服务
- `D:\win_bridge_server.py` — server 的 Windows 运行副本

## 踩过的坑

1. **mss/BitBlt 对 DirectX 窗口返回全黑** — 必须用 dxcam (DXGI Desktop Duplication)
2. **PrintWindow(PW_RENDERFULLCONTENT=2) 对游戏也无效** — 返回空白 PNG
3. **长驻 bridge server 无法 SetForegroundWindow** — Windows 限制后台进程切前台；解决方案：在 proxy（短命 python.exe 进程）里做前台切换
4. **多个旧 bridge server 堆积** — 重启前必须 `taskkill /F /IM python.exe` 杀干净
5. **游戏最小化时 GetWindowRect 返回 (-32000, -32000)** — 需要 `SendMessage(WM_SYSCOMMAND, SC_RESTORE)` 恢复

## 启动方式

```bash
# 杀旧进程 + 启动 server
cmd.exe /C "taskkill /F /IM python.exe >nul 2>&1"
sleep 2
cd /mnt/c && python.exe D:\\win_bridge_server.py &

# 测试
cd packages/pioneer-agent && PYTHONPATH=src python3 -c "
from pioneer_agent.adapters.bridge_client import BridgeClient
c = BridgeClient(); c.connect()
data = c.screenshot()
print(f'{len(data)} bytes')
c.close()
"
```

## Windows 侧依赖

```
pip install dxcam opencv-python-headless pyautogui pywin32 Pillow
```

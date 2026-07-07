# 析命师互动控制台 — 开发进度

> **当前版本**：v2.0 + M1 人格化重构（已落地，未 commit）
> **最后更新**：2026-07-07
> **相关文档**：[README.md](./README.md) · [USAGE.md](./USAGE.md) · [PLAN.md](./PLAN.md) · [VISION.md](./VISION.md)

---

## 📋 当前状态

v2.0 稳定版 + M3 拟人输入已 commit；**M1 人格化重构已落地（代码完成，待 commit / 端到端验证）**。
架构：单账号 / 静态知识库 + 拟人节奏 + 可选 LLM 决策。

```
config.json → 角色单选 → Playwright Chromium
                 ↑                  ↓
            rules.json          决策层（掷骰子 + LLM 决策）
            (13 字段)                ↓
                                拟人输入 (jieba + 节奏)
                                 ↓
                            React InputEvent 逐字注入 → 弹幕
```

**v3 里程碑进度**（详见 [PLAN.md](./PLAN.md)）：

| 里程碑 | 状态 |
|--------|:----:|
| M1 人格化重构 | ✅ 已落地（待 commit） |
| M2 冷启动知识采集 | ⏸ 暂缓 |
| M3 拟人输入 | ✅ 已 commit（b8ead87） |
| M4 实时听觉 | ⏸ 待 PoC |
| M5 决策融合 + 节流 | ⏸ 依赖 M4 |

## 📝 最近变更

### 2026-07-07 — M1 人格化重构（未 commit）
**后端**
- `rules.json` schema 升级：每个角色从 4 字段 → 13 字段（新增 crowd/device/vehicle/purchase_freq/region/marriage/customer_type/typing_style/response_tendency）。用 `migrate_rules.py` 一键迁移（22 个角色，幂等）。
- `llm_engine.py` 重写（56 → 197 行）：保留 load_personas API；新增 `think()` / `compose_system_prompt()` / `compose_user_prompt()` / `fallback_pick()` / `_parse_json_response()`。三层降级（异常→fallback→messages 随机）。
- `douyin_interact.py` 集成决策层：`response_tendency` 掷骰子 → `think()` → 失败降级；`llm_enabled=false` 完全走 v2 路径。
- `config.json` 新增 7 个 llm_* 字段（api_key/base_url/model/temperature/mode/timeout + enabled），删除 `rotate_interval`。
- `requirements.txt` 加 `openai>=1.0.0`（已装 2.24.0）。
- 新建 `migrate_rules.py`（一次性迁移脚本）。
- 新建 `personas/` 目录（角色 .md 高级覆盖用）。

**GUI**
- Tab 1 简化：删角色轮换 / 拟人输入下拉 / 多选 Listbox；加「弹幕策略」下拉（循环/随机）；角色改单选 Combobox。
- Tab 2 重做：拆三子标签 ⚙ 设定（10 字段选择器 + 回应率滑块）/ 💬 弹幕（保留增删改）/ 📄 提示词（personas/<name>.md 编辑）。预览拼接提示词弹窗。
- Tab 3 新增（🤖 LLM 配置）：Provider / 模型 / Base URL / API Key / 温度 / 超时 / 模式 / 测试连接按钮。
- 单账号模式：固定使用 personas[0]，无角色轮换。
- 弹幕策略：循环（顺序，不打乱）/ 随机（shuffle 后顺序消费）。

**Bug / 重构**
- `_refresh_account_personas` 改用 persona_combo（之前残留 role_list）。
- LLM 失败时 fallback_pick 从 messages 随机取（与 _get_next_msg 行为一致）。

### 2026-07-06 — M3 拟人输入（commit b8ead87）
- 新建 `humanized_input.py`：jieba 分词 + 词间随机 50~200ms + 标点后 30% 概率 0.5~1.5s 长停。
- `douyin_interact.py` L254 替换原固定 10ms/字循环。
- `requirements.txt` 加 `jieba>=0.42.1`。
- 实测 13 字句子从 ~130ms 拉到 ~2s（16x），节奏明显。

### 2026-07-06 — 文档重构
- 拆分 `DEVELOPMENT.md` (449 → 141 行) → 拆出 `PLAN.md` (182 行) / `VISION.md` (66 行)。
- 删 13 个死文件（详见清理记录）。

### 2026-07-06 — 清理死代码
- 删除 13 个旧文件（详见末尾清理记录）
- 决策：Cookie DPAPI 加密方向搁置

### 2026-07-05 — v2.0 发布
- 单账号重构 + 静态知识库 + PyInstaller 打包（commit 9e539ec）

### 2026-06 — v0.x 实验废弃
- 火山 ASR + DeepSeek/Ollama LLM 试验
- 代码已删除，配置 schema 留在 `.env.example`

## 🏗️ 架构要点

```
┌─ Tkinter GUI (ui.py) — 4 tabs ─────────────────────┐
│  🎥直播间互动 │ 💬角色管理 │ 🤖LLM配置 │ 📝弹幕采集 │
│  (启动/登录)   (设定/弹幕/   (Provider/API/  (采集)  │
│                .md 提示词)   测试连接)              │
└──────────────────┬──────────────────────────────────┘
                   │ subprocess.Popen (config.json IPC)
┌──────────────────┴──────────────────────────────────┐
│  douyin_interact.py (子进程)                          │
│                                                         │
│  launch_persistent_context → goto live room             │
│  → 查登录态 → 找输入框 → 主循环                        │
│                                                         │
│  每轮:                                                  │
│    1. llm_enabled=true:                                 │
│       掷骰子 response_tendency → 命中则                 │
│         think(persona, llm_config) → {respond,content} │
│       失败 → fallback_pick (messages 随机)               │
│    2. llm_enabled=false:                                │
│       _get_next_msg(persona) → shuffle 后顺序消费       │
│                                                         │
│    → 拟人输入 (jieba + 节奏) → React InputEvent 注入     │
│    → Enter 发送                                        │
└────────────────────────────────────────────────────────┘
```

### 弹幕发送细节（React contenteditable）

抖音输入框是 `zone-container`（React contenteditable div），**不能直接 `fill()`**：
1. 聚焦 → 清空 → Selection API 定位光标
2. 逐字 `createTextNode` + `range.insertNode` + `InputEvent('input')`
3. 在 `document` 上派发 `keydown`/`keypress`/`keyup` Enter（React 事件委托）
4. 每次发送前重新查询输入框（DOM 可能刷新）

> 完整使用说明见 [README.md](./README.md) · [USAGE.md](./USAGE.md)

## 📦 打包原理

```
launcher.py  ──PyInstaller──→  析命师互动控制台.exe
  ├── --mode login → do_login()
  ├── --mode run   → run(config)
  └── 无参数        → App().run() (GUI)

打包内容:
  ├── Python 3.11 + stdlib   (~80 MB)
  ├── Playwright Python 包   (~50 MB)
  └── Chromium 浏览器         (~412 MB)
                              ────────
                              ~547 MB
```

关键点：
- 入口是 `launcher.py`（多模式路由），不是 `ui.py`
- `sys.frozen` 检测打包环境，自动切换路径逻辑
- `sys.stdout` 在 `--windowed` 模式下为 `None`，所有 `reconfigure` 调用需加 `and sys.stdout` 保护
- 配置文件首次运行从 `_internal/` 复制到 exe 同级目录（可编辑）
- `PLAYWRIGHT_BROWSERS_PATH` 指向 `_internal/playwright_browsers/`

## 🔧 调试笔记

| 问题 | 原因 | 解决 |
|------|------|------|
| 浏览器不显示 | `pythonw` 子进程无窗口 | 用 `pythonw.exe` + 不加 `DETACHED_PROCESS` |
| 输入框找不到 | 未登录 / 直播间未开播 | 先扫码登录，检测 `sessionid` cookie |
| 打包后闪退 | `sys.stdout` 为 `None` | `and sys.stdout` 保护 |
| 子进程无反应 | `PROJECT_DIR` 未定义 | 统一用 `APP_DIR` + `sys.frozen` 适配 |
| UI 日志不刷新 | stdout 缓冲 | 子进程加 `-u` 参数禁用缓冲 |

### 版本历史

| 版本 | 日期 | 内容 |
|------|------|------|
| v0.1–v0.6 | 2026-06 | 早期版本（ASR/LLM 试验，已废弃） |
| v2.0 | 2026-07 | 单账号重构 + 静态知识库 + PyInstaller 打包 |

## 🧹 清理记录（2026-07-06）

「弹幕采集器」现有 4 个迭代版本，当前在用的是 `record_content.py`（v2），其余 3 个均为被取代的旧版 / 搁置实验，本次清理删除。

| 文件 | 类型 | 备注 |
|------|------|------|
| `record_content_ws.py` | 死代码 | WebSocket 直连实验版，撞抖音 2024 签名墙搁置 |
| `danmaku_collector.py` | 死代码 | 最早版采集器，输出到 `danmaku_data/` |
| `record_live.py` | 死代码 | 纯采集旧版，输出到 `record_data/` |
| `diag_cookies.py` | 调试脚本 | Cookie DPAPI 方向，搁置 |
| `diag_danmaku.py` | 调试脚本 | 2026-07-02 开发期排查 |
| `diag_dom.py` | 调试脚本 | 2026-07-02 开发期排查 |
| `diag_dpapi.py` | 调试脚本 | Cookie DPAPI 方向，搁置 |
| `debug_no_input.png` | 调试截图 | 早期调试产物（运行时按需重新生成） |
| `debug_room_load.png` | 调试截图 | 早期调试产物（运行时按需重新生成） |
| `diag_cookies_log.txt` | 调试日志 | 配套 `diag_cookies.py` |
| `diag_cookies_out.json` | 调试输出 | 配套 `diag_cookies.py` |
| `diag_dom_log.txt` | 调试日志 | 配套 `diag_dom.py` |
| `diag_out.json` | 调试输出 | 配套 `diag_dpapi.py` |
| `ws_log.txt` | 调试日志 | WebSocket 实验日志 |

### 同步更新
- `.codewhale/instructions.md`：移除 `danmaku_collector.py` / `record_live.py` 条目
- `DEVELOPMENT.md`：本章节由「待办」改为「已完成」记录

### 决策记录
- **Cookie DPAPI 加密方向**：搁置。`diag_dpapi.py` / `diag_cookies.py` 仅作诊断验证，未接入 `douyin_interact.py` 主流程。如未来重新推进，可从 git 历史恢复。
- **数据目录**：`danmaku_data/` 与 `record_data/` 保留（含历史采集数据，未删除）。如不再需要可手动清理。

---

## 📚 相关文档

- [README.md](./README.md) — 项目说明 / 快速启动 / FAQ
- [USAGE.md](./USAGE.md) — 独立运行指南
- [PLAN.md](./PLAN.md) — v3.0 拓展方案
- [VISION.md](./VISION.md) — v5 远期构想
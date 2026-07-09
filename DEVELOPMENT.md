# 析命师互动控制台 — 开发进度

> **当前版本**：v2.0 + M1 人格化重构（已 commit） + LLM 推理模型兼容（已 commit） + 节奏强化与字数控制（实测通过，commit 7337aed）
> **最后更新**：2026-07-09
> **相关文档**：[README.md](./README.md) · [USAGE.md](./USAGE.md) · [PLAN.md](./PLAN.md) · [VISION.md](./VISION.md)

---

## 📋 当前状态

v2.0 稳定版 + M3 拟人输入已 commit；**M1 人格化重构 + LLM 推理模型兼容已 commit 并端到端验证通过**。
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
| M1 人格化重构 | ✅ 已 commit（5530fa1） |
| M2 冷启动知识采集 | ⏸ 暂缓 |
| M3 拟人输入 | ✅ 已 commit（b8ead87） |
| M4 实时听觉 | ⏸ 待 PoC |
| M5 决策融合 + 节流 | ⏸ 依赖 M4 |

## 📝 最近变更

### 2026-07-08 — 节奏强化（A）+ 字数控制（B，待用户实测）

用户端到端测试时反馈两件事：
- A：M3 拟人输入仍有"整句黏贴闪电发送"的黏贴感（短句尤其明显，jieba 切完词间总耗时只 0.2-0.5s）
- B：LLM 输出普遍 7-10 字，不符合"真实直播间 1-5 字为主"的体感；且长度阈值是硬编码不可调

**A. 节奏强化（`humanized_input.py`）**
- 节奏区间拉宽：`normal` (50,200) → (80,280)；`slow` (120,280) → (180,400)；`fast` (20,80) → (40,130)
- 字内延迟由定值 5ms 改为区间 jitter (10, 25) ms
- 长停概率 30% → 45%；长停区间 (0.5, 1.5) → (0.6, 1.8) 秒
- 增加"剩余 token 衰减系数"：越打越顺手，单 token 停顿按 0.3 倍缩短
- 新增 `map_zh_style('慢/中/快' → 'slow/normal/fast')` 辅助函数

**A. 接线（`douyin_interact.py`）**
- 之前 `type_humanized` 一律用模块常量 `DEFAULT_TYPING_STYLE='normal'`，**忽略 persona 的 `typing_style` 字段**
- 改为 `map_zh_style(current_persona['typing_style'])`，实现真正的"按角色打字"

**B. 字数控制（`llm_engine.py` + `ui.py` + 可选 `config.json`）**
- 新增 `DEFAULT_LENGTH_CONTROL`：min_chars=1 / max_common=5 / max_occasional=9 / max_rare=11 / hard_cap=12
- 新增 `_normalize_length_control()`：单调性自校正（用户提供乱序数时自动夹紧）
- 新增 `_length_rules_text()`：动态生成 prompt 内的长度分布描述（70% / 25% / 5% 三档）
- 新增 `_enforce_length()`：超 `hard_cap` 强制截断 + 日志
- `compose_system_prompt(persona, length_control)` 接受配置，硬编码的「5~15 字」整段替换为动态文本
- `think()` 透传 `config['length_control']`，解析成功后做长度截断 + `[LLM] ⚠ 超长截断 (N→M 字)` 诊断日志
- **不重写用户的 `config.json`**（含真实 API key 且 gitignore），首次启动 GUI 后自动写入 `length_control` 块

**B. UI 暴露**
- Tab 3「🤖 LLM 配置」新增「📏 弹幕长度（字数）」段：5 个 Spinbox
  - 最短 / 70% 上限 / 25% 上限 / 5% 上限 / 硬截断
- `_load_config_to_form` 读、`_save_config_from_form` 写（`FocusOut` 触发）

**冒烟验证（已完成）**
- 4 文件 `python -m py_compile` 全部通过
- A：`map_zh_style` 映射、3 档区间、字内延迟、长停区间全部断言通过
- B：默认值、用户配置越界校正、长度规则文本、超长截断、prompt 注入全部断言通过

**待用户测试**
- 启动 GUI → Tab 3 看 5 个 Spinbox 默认值（1/5/9/11/12）
- 任意直播间运行，体感打字节奏是否变自然
- 调整上限 → 保存 → 重启看 config.json 里新增 `length_control` 字段
- 日志留意 `[LLM] ⚠ 超长截断 ...` 行——说明 prompt 没管住，程序兜住

### 2026-07-09 — 节奏强化 + 字数控制 实测通过

用户端到端测试反馈 OK，节奏体感自然、字数控制生效，无需再调。

**结论**
- v3 主干（M1 + M3 + 节奏强化 + 字数控制）全部进入"实测通过"状态
- 下一步可打包（`_pack_new.bat`）→ 用户拿去任意直播间验证
- C/D/E 待办章节保留，但优先级下降：v3 主干已可用，浏览器卡死和品类适配都可等下个版本再说

**同步到本仓库**
- `personas/桑蚕丝连衣裙.md`：精修后的高级提示词，覆盖 `rules.json[0]`
- `rules.json`：删 3 条 messages（"已拍加急"/"高一米六二..."/"这个外面不是要1000多吗？"），SX 占位移除
- `PLAN.md` / `VISION.md`：v4 路线 + 推迟决策的注记

### 2026-07-07 晚 — 版本划分决策:ASR 推迟到 v4

**决策**
- ASR（实时听觉）从 v3.0 里程碑推迟到 v4.0
- 理由：ASR 改造大（音频捕获 + 流式 + ASR 选型），v3 主干（M1+M3）已通，无需听觉也能跑
- 折中：v3.0 预留 ASR 数据源接口（`get_host_said()`），v4 接 ASR 时主程序零改动

**云端 ASR 候选**（M4 PoC 时评估）
- 国内：火山引擎（豆包/抖音同源）/ 阿里云 / 讯飞 / 百度 / 腾讯
- 国外：Azure Speech / Deepgram / AssemblyAI
- ⚠️ 不适合：OpenAI Whisper API（批处理非流式）/ Whisper 本地（慢无法实时）

**测试物料**
- `_test_v3.html`：V3 测试清单（9 场景 / ~34 检查点 / 浏览器交互 / localStorage 持久化 / 打印导出 PDF）

**明日计划**
- 用户手动测试 V3 各场景（预计 2 天）
- 测试通过后打包给用户测试
- 期间可并行：调研 M4 ASR 厂商定价（web search）

### 2026-07-07 — LLM 推理模型兼容（commit 27036fa1）+ 端到端验证

**问题（端到端测试时发现）**
- MINIMAX M3 / deepseek-reasoner 等推理模型会输出 `<think>...</think>` 推理块
- `_parse_json_response` 的 `\{.*?\}` 正则把 think 块内的 `{...}` 误抓为 JSON → 解析失败
- `max_tokens=64` 太小，think 阶段就把 token 用光，JSON 没机会输出
- 结果：LLM 调通但解析失败 → fallback 从 messages 池随机取 → 用户以为 LLM 没工作（22 分钟 16 条几乎全在池里）

**修法**
- `_parse_json_response` 增加预处理：剥离 `<think>...</think>` 和 markdown ```` ``` ```` 代码块
- `DEFAULT_MAX_TOKENS` 64 → 512（推理 + JSON 输出需要更大预算）
- `think()` 加 `[LLM] ✓/✗` 诊断日志，异常不再静默吞掉
- `_parse_json_response` 支持 `debug_log`，解析失败时打印原文便于诊断
- `.gitignore` 加 `_test_*.py` 模式，临时调试脚本不入库

**端到端验证（2026-07-07 晚）**
- 直播间：https://live.douyin.com/69742079457
- 角色：桑蚕丝连衣裙；模式：generate；Provider：MINIMAX M3（key / base_url / model 均正确）
- 22 分钟内 7 条 LLM 输出，全部池外自由发挥，符合桑蚕丝中产潜客画像
- 间隔 ~107s（推理模型慢于 `send_interval=40s`，符合预期，可接受）
- M1 + M3 主干链路确认通：**v3 决策层落地可交付**

### 2026-07-07 — M1 人格化重构（commit 5530fa1）
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

## 📌 待办（大工程，暂缓 / 用户实测后再决策）

> 2026-07-08 端到端测试发现 5 个问题，A/B 已实现。C/D/E 经讨论属于**大工程**（涉及架构 / prompt 重写 / 抓取层），暂不在本轮处理。先记录在此，避免遗忘。

### C. 浏览器 30 分钟卡死（止血方案）— **待做**

**症状**
- 浏览器在跑约 30 分钟后画面卡死，但仍有输出流；等一会儿画面又会动一下
- 锁定两个高概率方向：直播间弹幕列表 DOM 累积 / Chromium 持久化上下文的长时挂起

**快速止血方案**
- `douyin_interact.py` 加 watchdog：
  - 每 60s 截图一次，对比画面 hash，连续 2 次无变化判定卡死
  - 卡死 → `page.reload()` + 重新查找输入框（损失 ~5s，重启后稳定）
- 不抓弹幕（项目当前是发，不是抓），避免 MutationObserver 额外开销

**深度方案**
- 接 CDP `performance.memory.usedJSHeapSize` 每 5 分钟打一行 `[perf]`，定位堆涨点
- 每 25 分钟主动 `ctx.close()` + 重启上下文（牺牲少量复杂度换 24h 稳定）
- 排查 `--disable-gpu` 在持久化上下文下的长期兼容性

**预估改动**
- `douyin_interact.py` +60~120 行（watchdog loop + reload 恢复）
- 0 新依赖

**预估优先级**：C > D > E（影响可用性最大）

---

### D. persona 语义重写（人群 ≠ 妈妈身份）— **待做**

**症状**
- LLM 输出「适合妈妈的款吗」「带娃穿吗」「亲子款吗」这类**自我代入**的问句
- 问题：当前 `compose_system_prompt` 把 `marriage=已婚有娃` 当成**身份标签**注入，LLM 倾向显性表达

**修法方向**
- 重写 system prompt 的「人群画像」段落
  - 旧：「你是 {name}，来自 {region} 的{customer_type}顾客。八大人群：{crowd}。婚姻：{marriage}」
  - 新：去人称、去身份，只留**消费偏好**和**语言习惯**
    - 例：「关注的点：面料质感 / 起球 / 显瘦 / 价位」
    - 「语言习惯：短句、省略号、不主动暴露身份」
- 不写"我是妈妈"，让 LLM 从语言习惯自然推导出语气
- `rules.json` 中「桑蚕丝连衣裙」这类角色，把显式婚姻 / 亲子类 trait 清掉
- 后处理：content 含「妈妈/带娃/亲子/老公/婆婆/孩子」命中黑名单 → 标记但不强制替换（防御层）

**预估改动**
- `llm_engine.py` `compose_system_prompt` 重构 1 个段落（~20 行）
- `rules.json` 22 个角色逐个审视「人群」段（~30 分钟人工）
- `personas/<name>.md` 添加若干消费偏好段
- `_test_llm.py` 加新场景验证

**风险**
- prompt 大改后 LLM 输出风格会整体偏移，需要先在 `_test_llm.py` 跑一轮回归
- 不同 persona 影响不同，最好先在 1 个角色上试

---

### E. 直播间品类适配 — **待做**

**症状**
- 用户在「桑蚕丝连衣裙」这类女装直播间，LLM 输出「有亲子款吗」—— 童装直播间合适的提问，在女装直播间是离题
- 当前 prompt 没有任何结构化品类信息，全靠 LLM 自己脑补

**修法方向**
1. **抓取层** (`douyin_interact.py`)：启动时解析直播间
   - 抓房间标题 / 主播昵称 / 商品列表关键字
   - 简单分类：女装 / 童装亲子 / 男装 / 美妆 / 食品 / 珠宝饰品 / 其他
   - 输出 `category`, `banned_keywords`, `allowed_keywords`
2. **决策层** (`llm_engine.py`)：注入 system prompt
   - 新增「直播间语境」段：类别 + 禁用词 + 推荐关注点
3. **后处理**（防御）：命中 banned 直接拒发一次，避免 LLM 偶尔越界

**预估改动**
- `douyin_interact.py` 新增 `detect_room_category(page)`（~40 行）
- `llm_engine.py` `compose_system_prompt` 加一段，约 15 行
- 维护一份「品类 → 禁用词」查表（独立文件如 `room_categories.py`，~50 行）
- `_test_llm.py` 加多品类场景

**复杂度最高的项**：涉及多个层级联动 + 维护一份查表，且不同直播间风格迥异，建议作为最后做的项

---

### 决策记录
- **2026-07-08**：A/B 已落地，用户实测通过后再决定 C/D/E 哪些要做、哪些砍掉
- 评估准则：**用户感知明显度 × 实现复杂度**反向打分
  - C 影响最大（直接卡死）但实现复杂度最低（watchdog 30 行） → 优先
  - D 影响中等（被识别为机器人），但 prompt 大改需回归 → 中
  - E 影响最低（少数直播间踩坑），实现最复杂 → 最后

- [README.md](./README.md) — 项目说明 / 快速启动 / FAQ
- [USAGE.md](./USAGE.md) — 独立运行指南
- [PLAN.md](./PLAN.md) — v3.0 拓展方案
- [VISION.md](./VISION.md) — v5 远期构想
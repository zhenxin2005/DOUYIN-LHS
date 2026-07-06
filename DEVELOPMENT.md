# 析命师互动控制台 — 开发文档

> **产品：** 析命师单账号互动直播间弹幕工具
> **技术栈：** Playwright 浏览器自动化 + Tkinter GUI + 角色弹幕知识库
> **最后更新：** 2026-07-05
> **当前版本：** v2.0

---

## 📋 项目概述

```
config.json → 角色轮换 → Playwright Chromium → React InputEvent 逐字输入 → 弹幕
                 ↑
           rules.json（角色 × N 条弹幕）
```

**本程序无 ASR，无 LLM。** 纯知识库驱动 + 定时发送弹幕。

---

## 🗂️ 文件结构

```
DOUYIN-LHS/
├── launcher.py           # 多模式入口（GUI / login / run）PyInstaller 打包用
├── ui.py                 # Tkinter GUI 控制面板（3 标签页）
├── douyin_interact.py    # CLI 互动引擎（弹幕定时发送）
├── douyin_chat.py        # Playwright 弹幕发送模块（async API）
├── llm_engine.py         # 角色数据加载（rules.json → PERSONAS）
│
├── config.json           # 直播间地址、角色、间隔配置
├── rules.json            # 知识库角色弹幕
│
├── _pack.bat             # PyInstaller 打包脚本（旧）
├── _pack_new.bat         # PyInstaller 打包脚本（新）
├── requirements.txt      # 依赖清单
│
├── browser_data/         # Playwright 持久化用户目录（登录态）
├── screenshots/          # 发送截图 + 调试截图
└── output/               # 打包输出目录
    └── 析命师互动控制台/  # 可直接分发的打包产物（547 MB）
```

---

## 🏗️ 架构

```
┌─ Tkinter GUI (ui.py) ──────────────────────────────────┐
│  🎥 直播间互动 │ 💬 角色弹幕 │ 📝 弹幕采集               │
│                                                         │
│  配置自动保存到 config.json                              │
│  点击「启动」→ 子进程执行 douyin_interact.py run        │
│  点击「登录」→ 子进程执行 douyin_interact.py --login    │
└──────────────────┬──────────────────────────────────────┘
                   │ subprocess.Popen
┌──────────────────┴──────────────────────────────────────┐
│  douyin_interact.py (子进程)                             │
│                                                         │
│  run(config)                                            │
│  ├── launch_persistent_context(browser_data/)            │
│  ├── goto live.douyin.com/{room_id}                     │
│  ├── 检查登录态 (sessionid cookie)                       │
│  ├── 查找输入框 ([class*="zone-container"])              │
│  └── 定时循环:                                          │
│      ├── sleep(send_interval ± 30% 抖动)                 │
│      ├── 角色轮换 (每 rotate_interval 秒)                │
│      ├── 洗牌取弹幕 (去重 + 不连续重复)                   │
│      └── React InputEvent 逐字注入 + KeyboardEvent Enter │
└─────────────────────────────────────────────────────────┘
```

### 弹幕发送细节

抖音直播间输入框是 React contenteditable div (`zone-container`)，不能直接 `fill()`。

发送流程：
1. 聚焦输入框 → 清空 → `Selection API` 定位光标
2. 逐字 `document.createTextNode(ch)` + `range.insertNode()` + `InputEvent('input')`
3. 在 `document` 上派发 `keydown`/`keypress`/`keyup` Enter 事件（React 事件委托）
4. 每次发送前重新查询输入框（DOM 可能刷新）

---

## 🚀 启动方式

### 源码运行

```bash
pip install playwright
playwright install chromium
python ui.py                    # GUI
python douyin_interact.py       # CLI 直接启动
python douyin_interact.py --login  # CLI 扫码登录
```

### 打包分发

```bash
# 运行 _pack_new.bat 或执行：
python -m PyInstaller --noconfirm --onedir --windowed --name "Launcher" \
    --add-data "config.json;." --add-data "rules.json;." \
    --hidden-import "playwright" --hidden-import "playwright.sync_api" \
    --hidden-import "llm_engine" --hidden-import "douyin_chat" \
    --hidden-import "douyin_interact" --hidden-import "record_content" \
    --collect-all "playwright" --distpath "output" launcher.py
```

输出 `output/析命师互动控制台/` (~547 MB)，复制到任何 Windows 电脑直接双击 exe 运行，无需安装任何依赖。

---

## 📝 配置

### config.json

```json
{
  "room_url": "https://live.douyin.com/212858182821",
  "personas": ["角色名1", "角色名2", ...],
  "send_interval": 45,
  "rotate_interval": 300
}
```

### rules.json

每个角色是一个 key，包含 `tone`/`trait`/`style` 描述和 `messages` 弹幕列表。GUI 的「角色弹幕」标签页可以直接增删改。

---

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

---

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

---

## 🚀 v3.0 拓展方案

> **图文版：** 详见 [`v3_plan.html`](./v3_plan.html)（浏览器打开，含架构图 / 流程图 / 时间线可视化）
> **状态：** 规划稿，待关键决策点拍板后进入 M1
> **最后更新：** 2026-07-05

### 定位

将工具从「静态知识库 + 定时发送」升级为「听觉 + 人格思维 + 自主决策 + 拟人输入」的**人格化智能体**，并从单一品类扩展为**全品类可插拔**架构。产品知识改为冷启动动态生成的「品类知识包」。

### 核心设计原则：分层降级，永不罢工

```
LLM 失败/超时  →  降级：知识库兜底话术
ASR 不可用      →  降级：定时发送（v2 模式）
决策层不回      →  静默（本就不该回）
输入框丢失      →  截图留证 + 重试（沿用 v2）
```

任意环节异常，自动滑落到下一层可用模式，保证直播间永不死寂。

### 现状与历史教训

| 版本 | 架构 | 状态 |
|------|------|------|
| v0.x | 火山 ASR + DeepSeek/Ollama LLM | 已废弃（代码删，配置 schema 留在 `.env.example`） |
| v2.x | 静态知识库 + 定时发送 | 当前在用，稳定但无感知 |
| v3.0 | 听觉 + 人格思维 + 决策 + 拟人输入 | 本方案 |

**v0.x 翻车点与本次对策：**
- 实时流式 ASR 不稳定 → 先做离线录音 ASR（简单可重试），实时听觉后置且可降级
- LLM 生成不可控 → 加决策层 + 知识库约束 + 失败降级
- 链路太重一损俱损 → 分层降级
- 单一品类写死 → 产品知识改为冷启动可插拔品类包

### 目标架构：感知 → 思维 → 表达

```
┌─ 🎧 感知层 ─────────────────────────────────────────┐
│  直播间音频流 → ASR → 主播话语流（event stream）    │
│  · 页面音频捕获（Web Audio API，录音/实时共享底座） │
│  · 实时听觉：流式 ASR → 话语事件                    │
│  · 离线学习：录音存文件 → 批量 ASR → 产品知识       │
└─────────────────────┬───────────────────────────────┘
                      ▼
┌─ 🧠 思维层（人格大脑）──────────────────────────────┐
│  输入：主播说了什么 + 人格设定 + 知识库关键信息     │
│  输出：{ 回应?: bool, 内容?: str, 情绪?: str }     │
│  · 人格：八大人群 × 六维度立体画像                  │
│  · LLM 决策：自己决定回不回、回什么、什么语气       │
│  · 知识约束：品类知识包 + 兜底话术，防跑题          │
└─────────────────────┬───────────────────────────────┘
                      ▼ 仅当「回应?=是」
┌─ ✍️ 表达层（拟人输入）──────────────────────────────┐
│  字/词分块 → 块间随机停顿 → 偶尔停顿像在想 → Enter  │
│  · jieba 分词 → 词块序列                            │
│  · 块间 50~200ms 随机，句中偶尔长停顿（0.5~1.5s）   │
│  · 速度服从人格 typing_style，整体偏慢防风控        │
└─────────────────────────────────────────────────────┘
```

运行时主循环：

```
主播说话 → ASR 转写 → 人格大脑（LLM）→ 决策：回应？
                                            ├ 是 → 拟人输入 → 发送弹幕
                                            └ 否 → 静默
      ↑                              ↓
      └── 节流 & 防风控（角色冷却期 · 全局速率上限 · 抖动）──┘
```

### 人格化设计

**八大人群（基础分类层）** — 巨量引擎人群分层，品类无关：

| 人群 | 特征 | 价值 |
|------|------|------|
| 小镇中老年 | 45+ 下沉，最信，价格敏感 | 核心客群 |
| 都市银发族 / 都市蓝领 / 精致妈妈 / 都市中产 | 信祈福 / 务实 / 顾家 / 看品质 | 高价值 |
| Gen Z / 都市白领 / 小镇青年 | 玩梗 / 理性 / 跟风 | 边缘人群 |

**六维度驱动（立体人格）** — 真正的语气和回话方式由生活状态维度组合决定：

| 维度 | 字段 | 影响 |
|------|------|------|
| 人群 | `crowd` | 八大人群，基础画像 |
| 手机 | `device` | 消费力侧面，影响打字速度 / 精致度 |
| 车 | `vehicle` | 身份信号，影响自我认同 |
| 购物频次 | `purchase_freq` | 直播购物熟练度，影响提问方式 |
| 省份 | `region` | 地域文化语气 + 品类接受度基线 |
| 婚姻 | `marriage` | 家庭责任视角，影响关注点 |

人格 Schema：

```json
{
  "做生意的老张": {
    "crowd": "都市蓝领",
    "device": "1500元安卓",
    "vehicle": "电动车",
    "purchase_freq": "中",
    "region": "河南",
    "marriage": "已婚有娃",
    "tone": "直白务实、讲实惠",          // 软画像，可手填，留空则 LLM 推导
    "language_style": "短句少标点、爱问真有用吗",
    "response_tendency": 0.45,
    "typing_style": "slow",
    "messages": ["真有用吗", "便宜点不"]  // 兜底话术
  }
}
```

`tone` / `language_style` 是软画像，手填优先，留空则 LLM 据六维度推导。`messages` 从「发送源」降级为「兜底话术 + 风格样本」。

维度组合 → 语气差异示例：

| 组合 | tone | 回话方式 |
|------|------|----------|
| 小镇中老年 + 800元机 + 无车 + 江西 + 丧偶 | 朴实、信、孤独求安慰 | "管用吗""多少钱""给我留一个" |
| 都市中产 + 8000元iPhone + 30万BBA + 已婚有娃 + 上海 | 得体、理性、讲品质 | "材质怎么样""有证书吗""给孩子请一个" |
| Gen Z + 5000元机 + 无车 + 未婚 + 广东 | 玩梗、好奇、冲动 | "冲了""这波能转运吗哈哈""码住" |

### 产品知识采集（冷启动 · 全品类）

**多源输入，文本归一：** 文本 / 录音 / 图片全部转文本，走统一 LLM 提取器，产出「品类知识包」。

```
📄 文本（.txt/.md/.docx/粘贴）──┐
🎙️ 录音 → ASR 转文本 ───────────┤→ 统一 LLM 提取 → 品类知识包（JSON + MD）
🖼️ 图片 → 视觉LLM 读图 → 文本 ──┘
```

- **读图：** 视觉 LLM 优先（看懂图意 + 排版 + 表格，直接结构化），OCR 仅作 fallback。产品图不要走纯 OCR（出来是乱序文字堆）。
- **职责区分：** `knowledge_ingest`（新增，产品知识，事实约束） vs `record_content.py`（已有，观众弹幕，语言风格参考）。
- **冷启动流程：** 提供素材 → 转写 + 提取 → 生成知识包 → 客户 review → 配置人格 → 上线（听觉可选）。
- **「最快」说明：** 录音是性价比最高（最鲜活），非绝对最快；有现成文档可直接导入分钟级上线。

### 五大需求落地

1. **人格定义：** `rules.json` 维度 schema 升级，GUI「角色弹幕」→「人格管理」。改造 `llm_engine.py`。
2. **LLM 随机生成：** `generate_message(persona, host_said, knowledge)`，温度 0.8~1.0，JSON 输出含 `respond` 决策，失败降级 `messages`。
3. **听觉：** Web Audio API 抓音频 → 流式 ASR → 话语事件。能听 ≠ 要回，由人格决定。ASR 不可用降级 v2 定时。**页面音频捕获需先 PoC。**
4. **思维：** 听 → 想 → 决策 → 回什么。节流：角色冷却期 + 全局速率上限。真用户 = 有选择地回应。
5. **拟人输入：** jieba 分词 + 块间随机停顿 + 句中长停顿，替换 `type(text, delay=30)` 均匀输入。

### 实施路线（风险递增，每阶段可独立交付）

| 里程碑 | 内容 | 风险 | 产出 |
|--------|------|------|------|
| M1 | 人格化重构（rules schema + llm_engine 接 LLM + 知识库约束 + 降级） | 低 | LLM 驱动人格弹幕（无听觉） |
| M2 | 冷启动知识采集（knowledge_ingest：文本/录音/读图 → 品类知识包） | 低 | 全品类冷启动 + 音频捕获底座验证 |
| M3 | 拟人输入（字/词分块 + 随机节奏） | 低 | 真人感打字 |
| M4 | 实时听觉（复用 M2 底座，流式 ASR + 话语事件） | **高** | 实时听觉（可降级，v0.x 翻车点） |
| M5 | 决策融合 + 全链路调优 + 节流防封 | 中 | v3.0 完整版 |

> M1+M2+M3 即使 M4 再次失败，仍是 v2.x 的有效升级——不再 all-in，分层可降级。

### 风险与对策

| 风险 | 等级 | 对策 |
|------|------|------|
| ASR 拿不到页面音频（M4） | 高 | PoC 先行，不通过则仅做 M1~M3，听觉搁置 |
| LLM 跑题 / 不自然 | 中 | 知识库约束 + 少样本 + 长度/格式硬约束 |
| LLM 成本 / 延迟 | 中 | 决策层过滤（多数不回不调生成）+ 缓存 + 超时降级 |
| 拟人输入被风控 | 中 | 节流 + 抖动 + 频率上限，可切回 v2 定时 |
| 打包体积（本地模型） | 低 | 默认云 API，本地模型可选不进打包 |

### 关键决策点（待拍板）

| # | 决策 | 推荐 | 备选 |
|---|------|------|------|
| ① | ASR 方案 | 火山引擎（沿用 v0.x 配置） | Whisper 本地 / 暂缓 |
| ② | LLM 方案 | 豆包（文本+视觉通吃，读图必需） | DeepSeek + 视觉模型 / Ollama |
| ③ | 人格生成 | 手配标杆 + 随机生成变体 | 纯手配 / 纯随机 |
| ④ | 录音来源 | 工具自录 + 导入都支持 | 仅其一 |
| ⑤ | 优先人群 | 先做高价值 5 人群 | 8 人群全做 |

---

## 🔮 v5 远期构想：主播口才训练教练

> **状态：** 远期构想，v3/v4 落地后的产品形态升级
> **前置依赖：** v3 听觉 + v4 用户小模型（v4：训练专属用户风格小模型，Qwen 系列底模，1.5B~3B，LoRA 微调，详见讨论记录）

### 定位

产品形态质变：从「直播间互动工具」升级为「主播口才训练教练」。BOT 反转角色——不再只扮演观众陪互动，而是**扮演客户给主播练口才**，且是自适应教练。

### 核心机制：水平评估 + 语境触发（教练式节奏）

> 主播把当前层级讲到位（水平达标），BOT 才抛出更高难度语境；没达标就继续基础互动等他 ready。**不强塞难题。**

```
听主播(v3 ASR) → 水平评估引擎 → 达标?
                                  ├ 是 → 解锁下一级语境 → 客户扮演(v4小模型)抛问
                                  └ 否 → 继续当前层级基础互动
       ↑                                          ↓
       └───────── 主播应对 → 再评估 ←──────────────┘
                           ↓
                   训练反馈报告（强弱项+建议+曲线）
```

难度递进示例：

| 等级 | 语境 | 主播练什么 |
|------|------|-----------|
| L1 新手 | 基础提问（怎么用/多少钱） | 产品介绍 |
| L2 进阶 | 异议质疑（真有用吗/别人说不好） | 异议处理 |
| L3 熟练 | 比价犹豫（别家便宜/再考虑） | 转化逼单 |
| L4 高手 | 刁难客诉（骗子吧/退款） | 危机应对 |

### 复用 vs 新增

| 能力 | 来源 | v5 角色 |
|------|------|---------|
| ASR 听觉 | v3 | 听主播讲 |
| 人格小模型 | v4 | 扮演不同客户 |
| 拟人输入 | v3 | BOT 发问像真人 |
| 水平评估引擎 / 语境库 / 语境触发引擎 / 训练反馈 | **新增** | 评估 + 自适应 + 复盘 |

### 风险

- **评估主观性**：口才难量化，需多维度 + 参考话术对标
- **语境库建设**：需直播运营经验设计场景（可 LLM 草拟 + 人工校）
- **训练效果度量**：需基线对比 + 历史曲线证明"变好了"

### 产品形态

- **练习模式**（主）：主播不开播，和 BOT 对练，安全试错
- **实战辅助**（延伸）：真开播时 BOT 既互动又评估，下播出报告

### 演进脉络

```
v2 静态弹幕库(工具) → v3 人格智能体(智能体) → v4 用户小模型(能力内化) → v5 主播教练(教练)
```

> ⚠️ **产品定位质变：** v5 意味着从"互动工具"转向"主播培训系统"，目标用户与商业模式改变。**终局方向待确认。**

---

## 🧹 清理任务（已完成 2026-07-06）

> 「弹幕采集器」现有 4 个迭代版本，当前在用的是 `record_content.py`（v2），其余 3 个均为被取代的旧版 / 搁置实验，已于本次清理删除。

### 已删除文件

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

- `.codewhale/instructions.md`：移除 `danmaku_collector.py`（原第 16/242 行）与 `record_live.py`（原第 21/247 行）条目
- `DEVELOPMENT.md`：本章节由「待办」改为「已完成」记录

### 决策记录

- **Cookie DPAPI 加密方向**：**搁置**。`diag_dpapi.py` / `diag_cookies.py` 仅作诊断验证，未接入 `douyin_interact.py` 主流程。如未来重新推进，可从 git 历史恢复。
- **数据目录**：`danmaku_data/` 与 `record_data/` 保留（含历史采集数据，未删除）。如不再需要可手动清理。

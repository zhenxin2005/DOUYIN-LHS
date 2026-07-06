# 抖音直播间定时互动工具

**Playwright 浏览器自动化 + 角色弹幕知识库 + 定时发送**

```
知识库 rules.json → 定时器 → 角色轮换 → Playwright 自动弹幕
```

---

## 快速启动

```powershell
cd C:\Users\zhenx\Desktop\DOUYIN-LHS
pip install -r requirements.txt
python douyin_interact.py https://live.douyin.com/房间号
```

把链接换成你要进的直播间，按 **`Ctrl+C`** 停止。

---

## 核心能力

### 1️⃣ 角色弹幕知识库
预置多种消费者角色，从 `rules.json` 读取各角色的弹幕内容。支持在 GUI 中直接编辑角色和弹幕。

### 2️⃣ 角色轮换
每 N 秒自动切换一种角色（可配置），话术风格丰富不重样。

### 3️⃣ 弹幕自动发送
Playwright Chromium 浏览器自动化，加载 cookies 登录态后自动在直播间输入框发送弹幕。发送成功自动截图留证。

### 4️⃣ 定时发送 + 抖动
每次发送间隔带 ±30% 随机抖动，避免规律被识别。

### 5️⃣ 自动重连 + 退出保护

| 故障场景 | 行为 |
|---------|------|
| 输入框找不到 | 截图留证，继续重试 |
| 未知错误 | 等待后重试 |
| **连续失败** | **程序自动退出** |

---

## 文件结构

```
DOUYIN-LHS/
├── launcher.py           ← 多模式入口（GUI / login / run）PyInstaller 打包用
├── ui.py                 ← Tkinter GUI 控制面板
├── douyin_interact.py    ← CLI 互动引擎（弹幕定时发送）
├── douyin_chat.py        ← Playwright 弹幕发送模块
├── llm_engine.py         ← 角色数据加载（rules.json → PERSONAS）
├── config.json           ← 直播间、角色、间隔配置
├── rules.json            ← 角色弹幕知识库
├── requirements.txt      ← Python 依赖
├── README.md             ← 本文件
├── USAGE.md              ← 详细使用指南
├── DEVELOPMENT.md        ← 开发文档
└── screenshots/          ← 弹幕发送截图存档
```

---

## 配置说明

编辑 `config.json`：

```json
{
  "room_url": "https://live.douyin.com/房间号",
  "personas": ["角色名1", "角色名2"],
  "send_interval": 45,
  "rotate_interval": 300
}
```

**参数说明：**

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `room_url` | 直播间链接 | — |
| `personas` | 启用的角色列表 | 全部角色 |
| `send_interval` | 发送间隔（秒） | 45 |
| `rotate_interval` | 角色切换间隔（秒） | 300 |

编辑 `rules.json` 可以添加/修改角色和弹幕内容。

---

## 使用技巧

**首次运行：**
1. 运行 `python douyin_interact.py --login` 扫码登录抖音
2. 运行 `python douyin_interact.py` 或 `python ui.py` 启动互动

**换直播间：** Ctrl+C 停掉，修改 `config.json` 中的 `room_url`，重新运行即可。

---

## 常见问题

**Q: 提示 "未检测到登录态"**
运行 `python douyin_interact.py --login` 扫码登录。

**Q: 弹幕发不出去**
检查直播间是否开播，或重新登录更新登录态。

**Q: 想调整发送速度**
修改 `config.json` 中的 `send_interval`（秒）。

---

## 架构

```
rules.json 知识库 → 定时器(±30%抖动) → 角色轮换 → Playwright 逐字 InputEvent 注入 → 弹幕
```

## 许可证

仅供学习研究使用。

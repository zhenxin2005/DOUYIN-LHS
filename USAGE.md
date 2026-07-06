# 抖音直播互动系统 — 独立运行指南

## 概述

定时从知识库读取弹幕，通过 Playwright 浏览器自动化自动发送到抖音直播间。

```
rules.json 知识库 → 定时器 → 角色轮换 → Playwright 自动弹幕
```

## 环境要求

| 依赖 | 版本 |
|------|------|
| Python | 3.11+ |
| playwright | 1.60+ |

```powershell
pip install -r requirements.txt
playwright install chromium
```

## 文件结构

```
C:\Users\zhenx\Desktop\DOUYIN-LHS\
├── douyin_interact.py    ← 主程序（定时弹幕发送）
├── douyin_chat.py        ← Playwright 弹幕发送模块
├── llm_engine.py         ← 角色数据加载
├── config.json           ← 直播间、角色、间隔配置
├── rules.json            ← 角色弹幕知识库
├── requirements.txt      ← Python 依赖
├── screenshots/          ← 弹幕发送截图存档
└── browser_data/         ← 登录态持久化目录
```

## 快速启动

```powershell
# 1. 扫码登录（首次）
python douyin_interact.py --login

# 2. 启动互动
python douyin_interact.py
```

或使用 GUI：

```powershell
python ui.py
```

## 配置说明

### config.json

```json
{
  "room_url": "https://live.douyin.com/房间号",
  "personas": ["角色名1", "角色名2"],
  "send_interval": 45,
  "rotate_interval": 300
}
```

### rules.json

每个角色是一个 key，包含 `messages` 弹幕列表：

```json
{
  "角色名": {
    "tone": "语气描述",
    "trait": "性格特征",
    "style": "说话风格",
    "messages": ["弹幕1", "弹幕2", "弹幕3"]
  }
}
```

---

## 停止运行

按 **`Ctrl + C`** 即可停止。程序会自动关闭浏览器。

---

## 常见问题

### Q: 提示 "未检测到登录态"

运行 `python douyin_interact.py --login` 用抖音 APP 扫码登录。

### Q: 弹幕发不出去

1. 检查直播间是否开播
2. 重新运行 `--login` 更新登录态
3. 检查 `rules.json` 是否有对应角色的弹幕

### Q: 想换直播间

修改 `config.json` 中的 `room_url`，重新运行即可。

### Q: 想调整发送速度

修改 `config.json` 中的 `send_interval`（单位：秒）。

---

> 代码会自动重连，跑上就不用管了。想换直播间就 Ctrl+C 停掉重开。

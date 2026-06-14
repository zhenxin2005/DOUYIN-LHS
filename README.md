# 抖音直播间实时互动工具 (PoC)

**火山引擎（豆包语音）大模型实时语音识别 + 抖音直播流**

## 功能

实时监听抖音直播间主播口播语音，转成文字，自动匹配关键词，触发多账号互动。

```
主播说 → 火山引擎 ASR → 实时文字 → 关键词匹配 → 多账号自动互动
```

## 当前状态

| 模块 | 状态 |
|------|------|
| 直播流获取 | ✅ 支持 `live.douyin.com` 和 `douyin.com` |
| 音频采集 | ✅ ffmpeg 提取 PCM 16kHz 单声道 |
| 实时语音识别 | ✅ 火山引擎 BigModel ASR |
| 关键词匹配 | ✅ 命中后打印提醒 |
| 多账号互动发送 | 🔜 待实现 |

## 环境要求

- Python 3.11+
- ffmpeg

## 安装

```bash
pip install -r requirements.txt
```

## 配置

```bash
cp .env.example .env
```

编辑 `.env` 填入火山引擎凭据：

```ini
# 火山引擎语音应用凭据
VOLC_APP_ID=你的APP_ID
VOLC_ACCESS_TOKEN=你的Access_Token
VOLC_RESOURCE_ID=volc.seedasr.sauc.duration

# 互动关键词（逗号分隔）
KEYWORDS=扣1,扣个1,打1,点点赞,关注,打想要
```

### 获取火山引擎凭据

1. 注册并登录 [火山引擎控制台](https://console.volcengine.com/)
2. 进入 **语音技术** → **大模型语音识别** → 开通服务
3. 在应用详情页获取：
   - **APP ID** → 填到 `VOLC_APP_ID`
   - **Access Token** → 填到 `VOLC_ACCESS_TOKEN`

## 使用

```bash
python douyin_interact.py <抖音直播间URL>
```

示例：

```bash
# live.douyin.com 直链
python douyin_interact.py https://live.douyin.com/123456789

# douyin.com 链接
python douyin_interact.py https://www.douyin.com/follow/live/123456789

# 直接房间号
python douyin_interact.py 123456789
```

## 运行效果

```
==================================================
  抖音互动 PoC — 火山(豆包) ASR
==================================================

  主播: 某某直播间  |  流: http://pull-flv-l26.douyincdn.com/...
  ✅ 音频就绪
  ✅ 火山 ASR 已连接
  ✅ 服务器就绪

🔊 开始 (Ctrl+C 停止)...

  🎤 百分之二十多，实打实靠的是品质，大家都是懂货都识货
  🎤 开播到现在二十来分钟，已经是卖了好几百件
  🎯 命中: 关注, 点点赞 → 触发互动(TODO)
```

## 架构

```
┌──────────────────────┐      ┌─────────────────┐
│  抖音直播间           │      │  火山引擎        │
│  FLV 视频流           │      │  BigModel ASR   │
└──────────┬───────────┘      └────────▲────────┘
           │ ffmpeg PCM               │ WebSocket
           ▼                           │
┌──────────────────────┐      ┌───────┴─────────┐
│  ffmpeg 子进程        │─────▶│  asyncio 主循环   │
│  16kHz 16bit mono    │ PCM  │  发送音频帧       │
│  stdout pipe          │      │  接收识别结果     │
└──────────────────────┘      └───────┬─────────┘
                                      │ 文本
                                      ▼
                             ┌───────────────┐
                             │  关键词匹配     │
                             │  互动策略引擎   │
                             └───────────────┘
```

## 许可证

仅供学习研究使用。

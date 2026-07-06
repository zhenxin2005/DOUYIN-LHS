# -*- coding: utf-8 -*-
"""
弹幕采集器 — 后台静默模式 (Headless + 不登录)

用法:
    # 默认:完全后台静默,不弹窗口,不需要登录态
    python record_content.py <直播间URL> <时长分钟>

    # 调试:打开可见浏览器(也仍然不登录,只是能看到渲染)
    python record_content.py <直播间URL> <时长分钟> --show

    # 走已有登录态(完整模式,会弹浏览器)
    python record_content.py <直播间URL> <时长分钟> --login

输出: record_data/danmaku_房间号_时间.json
{
  "room_id": "...",
  "time": "...",
  "count": N,
  "items": [{"user": "用户A", "text": "你好"}, ...]
}
"""

import json
import re
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
sys.path.insert(0, str(PROJECT_DIR))

if sys.platform == "win32" and sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

OUTPUT_DIR = PROJECT_DIR / "record_data"
OUTPUT_DIR.mkdir(exist_ok=True)

_NOISE = ["来了", "欢迎", "抖音严禁", "违法", "理性消费", "隐私", "下载抖音",
          "充钻石", "进入全屏", "本场点赞", "京ICP", "已结束", "猜你喜欢"]


def _is_noise(text):
    t = text.strip()
    if not t or len(t) <= 2:
        return True
    for kw in _NOISE:
        if kw in t:
            return True
    return False


def emit(typ, text, **extra):
    """输出 JSON 事件到 stdout
    typ: danmaku | status | done
    extra: 额外字段(如 user)
    """
    now = datetime.now().strftime("%H:%M:%S")
    obj = {"type": typ, "time": now, "text": text}
    obj.update(extra)
    print(json.dumps(obj, ensure_ascii=False), flush=True)


# ── 在浏览器里跑 JS，一次性提取 {user, text} 结构 ──
# 抖音直播间真实结构(2024-2026):
#   <div class="webcast-chatroom___item">           ← 弹幕项(三个下划线!)
#     <span class="v8LY0gZF">用户昵称：</span>     ← 用户名(哈希类,会变)
#     <span class="webcast-chatroom___content-with-emoji-text">弹幕</span>
_EXTRACT_JS = r"""
() => {
    const items = [];
    // 真实弹幕项类名: webcast-chatroom___item (三个下划线)
    const itemSelectors = [
        '.webcast-chatroom___item',
        '[class*="webcast-chatroom___item"]',
        '[class*="webcast-chat"] [class*="___item"]',
    ];
    // 弹幕内容类名: webcast-chatroom___content-with-emoji-text (稳定)
    const contentSelectors = [
        '.webcast-chatroom___content-with-emoji-text',
        '[class*="content-with-emoji-text"]',
    ];

    let chatItems = [];
    for (const sel of itemSelectors) {
        const found = document.querySelectorAll(sel);
        if (found.length > 0) { chatItems = found; break; }
    }
    if (chatItems.length === 0) return items;

    chatItems.forEach(item => {
        // 找内容 span(用稳定类名)
        let textEl = null;
        for (const sel of contentSelectors) {
            const el = item.querySelector(sel);
            if (el) { textEl = el; break; }
        }
        const text = textEl ? textEl.innerText.trim() : '';

        // 用户名:从整个 item 的 innerText 里扣掉 text 部分
        // 抖音 item.innerText 格式: "用户昵称：弹幕内容"
        // (主播回复时会是 "主播昵称：@被回复人 弹幕内容")
        let user = '';
        const full = (item.innerText || '').trim();
        if (text) {
            const idx = full.lastIndexOf(text);
            if (idx > 0) {
                let prefix = full.substring(0, idx).trim();
                // 去掉尾部冒号
                prefix = prefix.replace(/[:：]\s*$/, '').trim();
                // 只取第一行(避免主播回复时带上 @xxx)
                const newlineIdx = prefix.search(/[\r\n]/);
                if (newlineIdx > 0) {
                    prefix = prefix.substring(0, newlineIdx).trim();
                }
                user = prefix;
            }
        }
        if (!user) {
            // 兜底:用第一个冒号切
            const colonIdx = full.search(/[：:]/);
            if (colonIdx > 0) {
                user = full.substring(0, colonIdx).trim();
            }
        }

        if (user && text) {
            items.push({user: user, text: text});
        }
    });

    return items;
}
"""


def extract_room_id(url: str) -> str:
    """从 URL 提取房间号"""
    for p in [r"live\.douyin\.com/(\d+)", r"/live/(\d+)"]:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return "unknown"


def run_silent(url: str, mins: int) -> int:
    """静默采集:headless + 不登录。返回采集条数。"""
    room_id = extract_room_id(url)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    end_t = time.time() + mins * 60

    emit("status", f"开始采集(静默模式) {mins} 分钟 [房间:{room_id}]")

    user_data_dir = str(PROJECT_DIR / "browser_data")
    items = []
    seen = set()

    with sync_playwright() as p:
        # 关键:用 launch_persistent_context 复用 browser_data/ 里的 cookies
        # headless=True 不弹窗口(后台静默)
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,    # 后台静默,不弹窗口
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36",
            locale="zh-CN",
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        emit("status", "页面加载完成,等待弹幕组件渲染...")
        time.sleep(8)  # headless 渲染稍慢,多等一会

        # 诊断:看页面上有没有弹幕组件
        try:
            diag = page.evaluate("""
                () => {
                    const out = {
                        title: document.title,
                        bodyHasLoginPrompt: (document.body?.innerText || '').includes('需先登录'),
                        chatBoxCount: document.querySelectorAll('[class*="webcast-chat"]').length,
                        chatItemCount: document.querySelectorAll('[class*="chat-item"]').length,
                    };
                    return out;
                }
            """)
            emit("status", f"页面诊断: chat-box={diag['chatBoxCount']}, "
                           f"chat-item={diag['chatItemCount']}, "
                           f"需登录={diag['bodyHasLoginPrompt']}")
            if diag['bodyHasLoginPrompt']:
                emit("status", "⚠️ 检测到登录墙,browser_data/ 登录态可能已过期")
                emit("status", "   解决:用 --show 模式重新跑一次扫码登录")
        except Exception as e:
            emit("status", f"页面诊断失败: {e}")

        empty_rounds = 0
        while time.time() < end_t:
            try:
                batch = page.evaluate(_EXTRACT_JS)
                if not batch:
                    empty_rounds += 1
                else:
                    empty_rounds = 0

                for obj in batch:
                    user = obj.get("user", "").strip()
                    text = obj.get("text", "").strip()
                    if not user or not text:
                        continue
                    if _is_noise(text):
                        continue
                    key = f"{user}\x1e{text}"
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append({"user": user, "text": text})
                    emit("danmaku", text, user=user)

                if empty_rounds == 5:
                    emit("status", "⚠️ 连续 10 秒未采集到弹幕")
                elif empty_rounds == 30:
                    emit("status", "⚠️ 连续 1 分钟无弹幕,检查直播间状态")
            except Exception as e:
                emit("status", f"采集轮询异常: {e}")
            time.sleep(2)

        browser.close()

    emit("status", f"采集完成: {len(items)} 条")

    path = OUTPUT_DIR / f"danmaku_{room_id}_{ts}.json"
    path.write_text(
        json.dumps(
            {"room_id": room_id, "time": ts, "count": len(items), "items": items},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    emit("status", f"保存: {path}")
    emit("done", json.dumps({"file": str(path), "count": len(items), "items": items}))
    return len(items)


def run_visible_with_login(url: str, mins: int) -> int:
    """可见模式 + 登录态(原行为,保留兼容)"""
    room_id = extract_room_id(url)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    end_t = time.time() + mins * 60
    user_data_dir = str(PROJECT_DIR / "browser_data")

    emit("status", f"开始采集(可见+登录) {mins} 分钟 [房间:{room_id}]")

    items = []
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-gpu"],
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        )
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        while time.time() < end_t:
            try:
                batch = page.evaluate(_EXTRACT_JS)
                for obj in batch:
                    user = obj.get("user", "").strip()
                    text = obj.get("text", "").strip()
                    if not user or not text:
                        continue
                    if _is_noise(text):
                        continue
                    key = f"{user}\x1e{text}"
                    if key in seen:
                        continue
                    seen.add(key)
                    items.append({"user": user, "text": text})
                    emit("danmaku", text, user=user)
            except Exception as e:
                emit("status", f"采集轮询异常: {e}")
            time.sleep(2)

        browser.close()

    emit("status", f"采集完成: {len(items)} 条")
    path = OUTPUT_DIR / f"danmaku_{room_id}_{ts}.json"
    path.write_text(
        json.dumps(
            {"room_id": room_id, "time": ts, "count": len(items), "items": items},
            ensure_ascii=False, indent=2,
        ),
        encoding="utf-8",
    )
    emit("status", f"保存: {path}")
    emit("done", json.dumps({"file": str(path), "count": len(items), "items": items}))
    return len(items)


def main():
    parser = argparse.ArgumentParser(
        description="抖音直播间弹幕采集器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s https://live.douyin.com/123456 10          # 静默 10 分钟
  %(prog)s https://live.douyin.com/123456 10 --show   # 显示浏览器但不登录
  %(prog)s https://live.douyin.com/123456 10 --login  # 显示浏览器+登录态
        """,
    )
    parser.add_argument("url", nargs="?",
                        default="https://live.douyin.com/212858182821",
                        help="直播间 URL")
    parser.add_argument("minutes", nargs="?", type=int, default=10,
                        help="采集时长(分钟),默认 10")
    parser.add_argument("--show", action="store_true",
                        help="显示浏览器窗口(headless=False,仍走 browser_data/)")
    parser.add_argument("--login", action="store_true",
                        help="(兼容旧名,等同于 --show)")

    args = parser.parse_args()

    try:
        if args.show or args.login:
            # 可见模式:headless=False,仍走 browser_data/ 登录态
            count = run_visible_with_login(args.url, args.minutes)
        else:
            # 默认:headless=True 静默 + browser_data/ 登录态
            count = run_silent(args.url, args.minutes)
        sys.exit(0 if count > 0 else 2)
    except KeyboardInterrupt:
        emit("status", "用户中断")
        sys.exit(130)


if __name__ == "__main__":
    main()
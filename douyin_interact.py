#!/usr/bin/env python3
"""
析命师单账号互动亲朋好友静态语义版 · 抖音直播间定时互动系统
纯知识库驱动 + 定时发送弹幕（无 ASR / 无 LLM）

用法:
  python douyin_interact.py               # 启动互动（默认有头浏览器）
  python douyin_interact.py --headless    # 无头模式
  python douyin_interact.py --login       # 扫码登录

配置:
  config.json  — 直播间、角色、间隔
  rules.json   — 知识库角色弹幕
"""

import argparse
import json
import random
import re
import sys
import time
from pathlib import Path

# PyInstaller 打包后用运行目录，开发时用脚本目录
if getattr(sys, 'frozen', False):
    PROJECT_DIR = Path(sys.executable).parent
    # 首次运行复制默认配置
    import shutil as _shutil
    _bundle = Path(sys._MEIPASS)
    for _f in ["config.json", "rules.json"]:
        _dst = PROJECT_DIR / _f
        if not _dst.exists():
            _src = _bundle / _f
            if _src.exists():
                _shutil.copy2(_src, _dst)
else:
    PROJECT_DIR = Path(__file__).parent

if sys.platform == "win32" and sys.stdout:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from llm_engine import PERSONAS
except ImportError:
    PERSONAS = [{"name": "默认用户", "tone": "", "trait": "", "style": "", "messages": []}]

from humanized_input import type_humanized, DEFAULT_TYPING_STYLE  # M3 拟人输入


# ══════════════════════════════════════════════
#  配置加载
# ══════════════════════════════════════════════

def load_config() -> dict:
    path = PROJECT_DIR / "config.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_persona_messages() -> dict[str, list[str]]:
    path = PROJECT_DIR / "rules.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                result = {}
                for name, val in data.items():
                    if isinstance(val, dict):
                        result[name] = val.get("messages", [])
                    elif isinstance(val, list):
                        result[name] = val
                return result
        except Exception:
            pass
    return {p["name"]: list(p.get("messages", [])) for p in PERSONAS}


def extract_room_id(s: str) -> str:
    for p in [r"live\.douyin\.com/(\d+)", r"/live/(\d+)"]:
        m = re.search(p, s)
        if m:
            return m.group(1)
    if s.strip().isdigit():
        return s.strip()
    raise ValueError(f"无法解析: {s}")


# ══════════════════════════════════════════════
#  主运行器
# ══════════════════════════════════════════════

def run(config: dict, headless: bool = False):
    """角色弹幕定时发送（同步 Playwright API）"""
    from playwright.sync_api import sync_playwright

    room_url = config.get("room_url", "")
    if not room_url:
        print("❌ 未配置 room_url，请检查 config.json")
        return

    send_interval = config.get("send_interval", 45)
    persona_interval = config.get("rotate_interval", 300)
    active_personas = config.get("personas", [])

    personas = [p for p in PERSONAS if p["name"] in (active_personas or [])]
    if not personas:
        personas = PERSONAS

    persona_messages = load_persona_messages()
    total_msgs = sum(len(v) for v in persona_messages.values())

    print(f"\n{'=' * 50}")
    print(f"  析命师单账号互动亲朋好友静态语义版 · 角色弹幕")
    print(f"{'=' * 50}")
    print(f"  📺 直播间: {room_url}")
    print(f"  🎭 角色: {', '.join(p['name'] for p in personas)}")
    print(f"  💬 弹幕总数: {total_msgs} 条  |  ⏰ 间隔: {send_interval}s")
    print(f"  👤 模式: {'无头(headless)' if headless else '有头(可见)'}")

    user_data_dir = str(PROJECT_DIR / "browser_data")
    # 命令行 --user-data-dir 覆盖
    _cli_udd = config.get("_user_data_dir") if 'config' in dir() else None
    if _cli_udd:
        user_data_dir = _cli_udd

    # 停止标记文件：GUI 写入此文件 → 主循环检测到后优雅退出 → finally 关浏览器
    # 定义在 with 之前，确保所有 return 路径也能清理残留标记
    stop_flag = PROJECT_DIR / ".stop_flag"
    stop_flag.unlink(missing_ok=True)  # 启动时清掉残留标记

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-gpu"],
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        room_id = extract_room_id(room_url)
        page.goto(f"https://live.douyin.com/{room_id}", wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)

        # 检查登录态
        cookies = ctx.cookies()
        if not any(c["name"] == "sessionid" for c in cookies):
            print("  ⚠️ 未检测到登录态 (sessionid)，请先扫码登录！")
            print("  💡 执行: python douyin_interact.py --login")
            try:
                (PROJECT_DIR / "screenshots").mkdir(exist_ok=True)
                page.screenshot(path=str(PROJECT_DIR / "screenshots" / "debug_no_login.png"))
                print("  📸 截图已保存: screenshots/debug_no_login.png")
            except Exception:
                pass
            ctx.close()
            stop_flag.unlink(missing_ok=True)
            return
        print("  🔑 登录态有效")

        # 找输入框
        input_elem = page.query_selector('[class*="zone-container"]')
        if not input_elem:
            input_elem = page.query_selector('[class*="editor-kit"]')
        if not input_elem:
            input_elem = page.query_selector("div[contenteditable='true']")

        if not input_elem:
            print("  ⚠️ 未找到输入框（可能直播间未开播或页面结构变化）")
            try:
                (PROJECT_DIR / "screenshots").mkdir(exist_ok=True)
                page.screenshot(path=str(PROJECT_DIR / "screenshots" / "debug_no_input.png"))
                print("  📸 截图已保存: screenshots/debug_no_input.png")
            except Exception:
                pass
            ctx.close()
            stop_flag.unlink(missing_ok=True)
            return

        print("  ✅ 弹幕模块已就绪")

        persona_idx = 0
        persona_switched_at = time.time()
        last_reply = ""
        msg_index: dict[str, int] = {}  # 每个角色独立的游标，避免切换角色时跳过弹幕
        shuffled_msgs: dict[str, list[str]] = {}

        def _get_next_msg(persona_name: str) -> str:
            nonlocal last_reply
            msgs = persona_messages.get(persona_name, [])
            if not msgs:
                return ""
            idx = msg_index.get(persona_name, 0)
            if persona_name not in shuffled_msgs or idx >= len(shuffled_msgs[persona_name]):
                shuffled = list(msgs)
                random.shuffle(shuffled)
                if len(shuffled) > 1 and shuffled[0] == last_reply:
                    shuffled[0], shuffled[1] = shuffled[1], shuffled[0]
                shuffled_msgs[persona_name] = shuffled
                idx = 0
            reply = shuffled_msgs[persona_name][idx]
            msg_index[persona_name] = idx + 1
            last_reply = reply
            return reply

        print(f"\n🔊 开始定时发送 (Ctrl+C 停止)...\n")

        try:
            while True:
                jitter = send_interval * random.uniform(-0.3, 0.3)
                actual_wait = max(5, send_interval + jitter)
                # 分段睡眠，以便及时响应停止标记
                slept = 0.0
                while slept < actual_wait:
                    if stop_flag.exists():
                        break
                    time.sleep(min(0.5, actual_wait - slept))
                    slept += 0.5
                if stop_flag.exists():
                    print("  ⏹ 收到停止信号")
                    break

                now = time.time()

                # 角色轮换
                if now - persona_switched_at >= persona_interval:
                    persona_idx = (persona_idx + 1) % len(personas)
                    persona_switched_at = now
                    print(f"  🔄 角色 → {personas[persona_idx]['name']}")

                current_persona = personas[persona_idx]
                reply = _get_next_msg(current_persona["name"])
                if not reply:
                    continue

                print(f"  ⏰ [{personas[persona_idx]['name']}] → {reply}")

                try:
                    el = page.query_selector('[class*="zone-container"]')
                    if not el:
                        el = page.query_selector('[class*="editor-kit"]')
                    if not el:
                        el = page.query_selector("div[contenteditable='true']")
                    if not el:
                        print("  ⚠️ 未找到输入框")
                        continue
                    el.click()
                    time.sleep(0.2)
                    el.evaluate("el2 => { el2.textContent = ''; el2.innerHTML = ''; el2.focus(); }")
                    time.sleep(0.1)
                    # M3 拟人输入：jieba 分词 + 词间随机 + 标点长停
                    type_humanized(el, reply, typing_style=DEFAULT_TYPING_STYLE)
                    time.sleep(0.3)
                    page.evaluate("""() => {
                        ['keydown','keypress','keyup'].forEach(type => {
                            document.dispatchEvent(new KeyboardEvent(type, {
                                key:'Enter', code:'Enter', keyCode:13, which:13,
                                bubbles:true, cancelable:true, composed:true,
                            }));
                        });
                    }""")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  ⚠️ 发送异常: {e}")

        except KeyboardInterrupt:
            print("\n  ⏹ 用户停止")
        finally:
            ctx.close()
            stop_flag.unlink(missing_ok=True)
            print("  🛑 已停止")


# ══════════════════════════════════════════════
#  扫码登录
# ══════════════════════════════════════════════

def do_login(udd: str | None = None):
    """有头浏览器扫码登录
    udd: 账号浏览器数据目录(多账号时传 accounts/<name>/)
    """
    from playwright.sync_api import sync_playwright

    print(f"\n{'=' * 50}")
    print(f"  🔑 扫码登录")
    print(f"{'=' * 50}")
    print(f"  🌐 打开有头浏览器...")
    print(f"  📱 请用抖音 APP 扫一扫登录")
    print(f"  ✅ 登录成功后自动关闭\n")

    user_data_dir = str(PROJECT_DIR / "browser_data")
    if udd and Path(udd).exists():
        user_data_dir = udd
    print(f"  📂 登录态保存到: {user_data_dir}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-gpu"],
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://www.douyin.com/", wait_until="domcontentloaded")

        print("\n" + "=" * 60)
        print("  📱 请在浏览器窗口中扫码登录抖音")
        print("  👀 登录成功后能看到右上角有你的头像")
        print("  ⏳ 检测到登录成功后自动关闭...")
        print("=" * 60 + "\n")

        for i in range(180):
            time.sleep(1)
            cookies = ctx.cookies()
            if any(c["name"] == "sessionid" for c in cookies):
                print("\n  ✅ 登录成功！")
                break
            if i % 15 == 0 and i > 0:
                print(f"  ⏳ 等待登录... {i}秒")

        ctx.close()

    print(f"\n  ✅ 登录态已保存到 browser_data/")
    print(f"  💡 现在可以启动互动: python douyin_interact.py\n")


# ══════════════════════════════════════════════
#  主入口
# ══════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="析命师单账号互动亲朋好友静态语义版 · 抖音直播间定时互动系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python douyin_interact.py              # 启动互动
  python douyin_interact.py --headless   # 无头模式启动
  python douyin_interact.py --login      # 扫码登录
        """,
    )
    parser.add_argument("--login", action="store_true", help="有头浏览器扫码登录")
    parser.add_argument("--headless", action="store_true", help="无头模式")
    parser.add_argument("--user-data-dir", type=str, default=None,
                        help="账号浏览器数据目录(默认 browser_data/,多账号时用 accounts/<name>/)")

    args = parser.parse_args()

    if args.login:
        do_login(args.user_data_dir)
        return

    config = load_config()
    # 命令行 --user-data-dir 覆盖 config 里的 account
    if args.user_data_dir:
        config["_user_data_dir"] = args.user_data_dir
    run(config, headless=args.headless)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
多模式入口 — PyInstaller 打包用
  - 无参数 → 启动 GUI
  - --mode login → 扫码登录
  - --mode run  → 启动互动
"""

import os, sys

# PyInstaller 打包后，告诉 Playwright 浏览器在哪
if getattr(sys, 'frozen', False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = os.path.join(sys._MEIPASS, "playwright_browsers")

def _arg_value(name: str) -> str | None:
    """从 sys.argv 里取出 --name value 形式的下个参数"""
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


if len(sys.argv) >= 2 and sys.argv[1] == "--mode":
    mode = sys.argv[2] if len(sys.argv) > 2 else ""
    # 打包模式下也要尊重 --user-data-dir,否则多账号全挤在 browser_data/
    udd = _arg_value("--user-data-dir")
    if mode == "login":
        from douyin_interact import do_login
        do_login(udd)
    elif mode == "run":
        from douyin_interact import load_config, run
        config = load_config()
        if udd:
            config["_user_data_dir"] = udd
        run(config)
    elif mode == "record":
        url = sys.argv[3] if len(sys.argv) > 3 else "https://live.douyin.com/212858182821"
        mins = int(sys.argv[4]) if len(sys.argv) > 4 else 10
        from record_content import main as record_main
        sys.argv = ["record_content.py", url, str(mins)]
        record_main()
    else:
        print(f"Unknown mode: {mode}")
else:
    from ui import App
    App().run()

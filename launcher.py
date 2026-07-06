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

if len(sys.argv) >= 2 and sys.argv[1] == "--mode":
    mode = sys.argv[2] if len(sys.argv) > 2 else ""
    if mode == "login":
        from douyin_interact import do_login
        do_login()
    elif mode == "run":
        from douyin_interact import load_config, run
        config = load_config()
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

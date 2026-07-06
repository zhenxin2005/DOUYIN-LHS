@echo off
cd /d "%~dp0"
echo ======================================
echo   打包中... 请等待 2-3 分钟
echo ======================================
echo.
python -c "import py_compile; [py_compile.compile(f, doraise=True) for f in ['launcher.py','ui.py','douyin_interact.py','llm_engine.py','douyin_chat.py']]; print('Verify OK')"
if errorlevel 1 goto :error

rmdir /s /q build output 2>nul

python -m PyInstaller --noconfirm --onedir --windowed --name "Launcher" --add-data "config.json;." --add-data "rules.json;." --hidden-import "playwright" --hidden-import "playwright.sync_api" --hidden-import "llm_engine" --hidden-import "douyin_chat" --hidden-import "douyin_interact" --hidden-import "record_content" --collect-all "playwright" --distpath "output" launcher.py
if errorlevel 1 goto :error

python -c "import shutil; from pathlib import Path; from playwright.sync_api import sync_playwright; p=sync_playwright().start(); chrome_dir=Path(p.chromium.executable_path).parent; p.stop(); dst=Path('output/Launcher/_internal/playwright_browsers/chromium'); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copytree(str(chrome_dir), str(dst), dirs_exist_ok=True); src=Path('output/Launcher'); tgt=Path('output/析命师互动控制台'); src.rename(tgt); (tgt/'Launcher.exe').rename(tgt/'析命师互动控制台.exe'); print(f'Done! {(sum(f.stat().st_size for f in tgt.rglob(\"*\") if f.is_file())/1024/1024):.0f} MB')"

echo.
echo ======================================
echo   完成！文件在 output\析命师互动控制台\
echo ======================================
pause
goto :eof

:error
echo.
echo ======================================
echo   打包失败！请检查错误信息
echo ======================================
pause

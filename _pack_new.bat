@echo off
cd /d "%~dp0"
echo ======================================
echo   打包中... 请等待 2-3 分钟
echo ======================================
echo.

:: 清理旧输出
rmdir /s /q output 2>nul
rmdir /s /q build 2>nul

:: PyInstaller 打包
python -m PyInstaller ^
    --noconfirm ^
    --onedir ^
    --windowed ^
    --name "Launcher" ^
    --add-data "config.json;." ^
    --add-data "rules.json;." ^
    --hidden-import "playwright" ^
    --hidden-import "playwright.sync_api" ^
    --hidden-import "llm_engine" ^
    --hidden-import "douyin_chat" ^
    --hidden-import "douyin_interact" ^
    --hidden-import "record_content" ^
    --collect-all "playwright" ^
    --distpath "output" ^
    launcher.py

if errorlevel 1 (
    echo.
    echo ======================================
    echo   打包失败！请检查错误信息
    echo ======================================
    pause
    goto :eof
)

:: 复制 Chromium 浏览器(动态查路径,不依赖版本号)
python -c "
import shutil, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

try:
    with sync_playwright() as p:
        chrome_exe = Path(p.chromium.executable_path)
        chrome_dir = chrome_exe.parent
        # build_id 目录(如 chromium-1223),launcher.py 通过 PLAYWRIGHT_BROWSERS_PATH 自动找到
        build_dir = chrome_dir.parent
        build_name = build_dir.name
        # 目标: output/Launcher/_internal/playwright_browsers/<build_name>/
        dst = Path('output/Launcher/_internal/playwright_browsers') / build_name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(build_dir), str(dst), dirs_exist_ok=True)
        print(f'Chromium OK: {build_name} -> {dst}')
except Exception as e:
    print(f'Chromium 复制失败: {e}')
    print('请先运行: playwright install chromium')
    sys.exit(1)
"
if errorlevel 1 (
    echo.
    echo ======================================
    echo   打包失败！Chromium 没复制成功
    echo ======================================
    pause
    goto :eof
)

:: 重命名为中文文件夹名
python -c "
import shutil
from pathlib import Path
src = Path('output/Launcher')
tgt = Path('output/析命师互动控制台')
src.rename(tgt)
exe = tgt / 'Launcher.exe'
if exe.exists():
    exe.rename(tgt / '析命师互动控制台.exe')
size = sum(f.stat().st_size for f in tgt.rglob('*') if f.is_file()) / 1024 / 1024
print(f'Done! {size:.0f} MB')
"

echo.
echo ======================================
echo   完成！文件在 output\析命师互动控制台\
echo ======================================
pause

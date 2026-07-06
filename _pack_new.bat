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

:: 复制 Chromium 浏览器
python -c "
import shutil
from pathlib import Path

chrome_src = Path(r'C:\Users\zhenx\AppData\Local\ms-playwright\chromium-1223\chrome-win64')
dst = Path('output/Launcher/_internal/playwright_browsers/chromium')
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copytree(str(chrome_src), str(dst), dirs_exist_ok=True)
print('Chromium OK')
"

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

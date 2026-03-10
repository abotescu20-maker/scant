@echo off
REM ============================================================
REM Alex Local Agent — Windows Build Script
REM ============================================================
REM Run this on a Windows machine to build AlexAgent.exe
REM
REM Prerequisites:
REM   pip install pyinstaller pystray pillow
REM   pip install -r requirements.txt
REM   playwright install chromium
REM ============================================================

echo.
echo ==========================================
echo  Alex Local Agent - Windows Build
echo ==========================================
echo.

REM Install build dependencies
echo [1/4] Installing build dependencies...
pip install --quiet pyinstaller pystray pillow
if errorlevel 1 (
    echo ERROR: pip install failed
    pause
    exit /b 1
)

REM Clean previous builds
echo [2/4] Cleaning previous builds...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist __pycache__ rmdir /s /q __pycache__

REM Generate icon if missing
echo [3/4] Checking icon...
if not exist alex_icon.ico (
    echo Generating icon...
    python -c "from PIL import Image; img = Image.open('alex_icon.png') if __import__('os').path.exists('alex_icon.png') else __import__('PIL.ImageDraw', fromlist=['ImageDraw']); exec(open('_gen_icon.py').read()) if __import__('os').path.exists('_gen_icon.py') else None"
    python -c "
from PIL import Image, ImageDraw
size = 256
img = Image.new('RGBA', (size, size), (0,0,0,0))
draw = ImageDraw.Draw(img)
draw.ellipse([4,4,size-4,size-4], fill='#22c55e')
cx, cy = size//2, size//2
pts = [(cx, cy-72), (cx-56, cy+56), (cx+56, cy+56)]
draw.polygon(pts, fill='white')
draw.polygon([(cx-24, cy+16),(cx+24, cy+16),(cx+18, cy+56),(cx-18, cy+56)], fill='#22c55e')
img.save('alex_icon.ico', format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
print('Created alex_icon.ico')
"
)

REM Build
echo [4/4] Building AlexAgent.exe...
pyinstaller alex_agent_win.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

if exist dist\AlexAgent.exe (
    echo.
    echo ==========================================
    echo  SUCCESS! Build complete.
    echo ==========================================
    echo.
    echo Output: dist\AlexAgent.exe
    echo.
    echo Distribution:
    echo   1. Copy dist\AlexAgent.exe to employee's computer
    echo   2. Double-click to run
    echo   3. On first run, config file opens in Notepad
    echo   4. Fill in API key and save
    echo   5. Agent starts automatically in system tray
    echo.

    REM Create zip for distribution
    powershell -command "Compress-Archive -Path 'dist\AlexAgent.exe' -DestinationPath 'dist\AlexAgent-1.0.0-win.zip' -Force"
    if exist dist\AlexAgent-1.0.0-win.zip (
        echo Distribution zip: dist\AlexAgent-1.0.0-win.zip
    )
) else (
    echo.
    echo ERROR: dist\AlexAgent.exe not found after build
)

echo.
pause

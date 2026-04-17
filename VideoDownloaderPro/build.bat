@echo off
chcp 65001 >nul
echo ========================================
echo   Video Downloader Pro - Build Script
echo ========================================
echo.

:: Очистка предыдущей сборки
echo [1/4] Cleaning previous build...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "VideoDownloaderPro.spec" del "VideoDownloaderPro.spec"
echo       Done!
echo.

:: Проверка наличия иконки
echo [2/4] Checking icon files...
if exist "assets\icon.ico" (
    echo       Found: assets\icon.ico
    set ICON_PARAM=--icon=assets/icon.ico
) else (
    echo       WARNING: assets\icon.ico not found!
    echo       EXE will have default icon.
    set ICON_PARAM=
)

if exist "assets\icon.png" (
    echo       Found: assets\icon.png
    set DATA_PARAM=--add-data "assets/icon.png;assets"
) else (
    echo       WARNING: assets\icon.png not found!
    echo       Window icon may not appear.
    set DATA_PARAM=
)
echo.

:: Сборка
echo [3/4] Building executable...
echo       This may take 1-3 minutes...
echo.

pyinstaller --onefile --windowed %ICON_PARAM% %DATA_PARAM% --name VideoDownloaderPro main_gui.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [4/4] Build complete!
echo.
echo ========================================
echo   SUCCESS!
echo   Output: dist\VideoDownloaderPro.exe
echo ========================================
echo.

:: Открыть папку dist
explorer dist

pause

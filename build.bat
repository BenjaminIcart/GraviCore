@echo off
echo ============================================
echo   Build GraviCore.exe (single file)
echo ============================================
echo.

:: Ensure PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

:: Clean previous build
if exist dist\GraviCore.exe del /f dist\GraviCore.exe
if exist build\GraviCore rmdir /s /q build\GraviCore

echo.
echo [BUILD] Building with PyInstaller...
echo.

pyinstaller GraviCore.spec --noconfirm

echo.
if exist dist\GraviCore.exe (
    echo ============================================
    echo   BUILD OK!
    echo   dist\GraviCore.exe
    echo ============================================
    for %%I in (dist\GraviCore.exe) do echo   Size: %%~zI bytes
) else (
    echo [ERROR] Build failed. Check errors above.
)

echo.
pause

@echo off
echo ============================================
echo   Build CentredeMasse.exe (single file)
echo ============================================
echo.

:: Ensure PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing PyInstaller...
    pip install pyinstaller
)

:: Clean previous build
if exist dist\CentredeMasse.exe del /f dist\CentredeMasse.exe
if exist build\CentredeMasse rmdir /s /q build\CentredeMasse

echo.
echo [BUILD] Building with PyInstaller...
echo.

pyinstaller CentredeMasse.spec --noconfirm

echo.
if exist dist\CentredeMasse.exe (
    echo ============================================
    echo   BUILD OK!
    echo   dist\CentredeMasse.exe
    echo ============================================
    for %%I in (dist\CentredeMasse.exe) do echo   Size: %%~zI bytes
) else (
    echo [ERROR] Build failed. Check errors above.
)

echo.
pause

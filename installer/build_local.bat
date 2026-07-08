@echo off
REM =====================================================================
REM  Build local del installer .exe para POS Print Proxy v2.0
REM
REM  Requiere: Python 3.11+, deps de requirements-dev.txt, Inno Setup 6.
REM
REM  Salida: dist_installer\POSPrintProxySetup-2.0.0.exe
REM =====================================================================

setlocal
set VERSION=2.0.0
cd /d "%~dp0.."

echo === Paso 1/3: instalar dependencias ===
pip install -r requirements-dev.txt || goto :error

echo.
echo === Paso 2/3: bundle con PyInstaller ===
python installer\build_exe.py --clean || goto :error

echo.
echo === Paso 3/3: instalador con Inno Setup ===
where iscc >nul 2>&1
if errorlevel 1 (
    echo ERROR: Inno Setup ^(iscc.exe^) no esta en el PATH.
    echo Descargalo desde https://jrsoftware.org/isdl.php
    goto :error
)
iscc /DAppVersion=%VERSION% installer\setup.iss || goto :error

echo.
echo === Listo ===
echo Installer generado: dist_installer\POSPrintProxySetup-%VERSION%.exe
goto :end

:error
echo.
echo Build FALLO
exit /b 1

:end
endlocal

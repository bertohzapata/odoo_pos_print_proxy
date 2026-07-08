@echo off
REM ======================================================================
REM  POS Print Proxy v2.0 - launcher de desarrollo
REM
REM  Este BAT es para correr desde el repo clonado (sin installer). El
REM  usuario final NO lo ve: instala el .exe y arranca la app desde el
REM  menu inicio o desde el system tray si tiene auto-start.
REM ======================================================================

title POS Print Proxy - Dev
echo ============================================
echo   POS Print Proxy v2.0 - Dev launcher
echo ============================================
echo.

cd /d "%~dp0"

REM Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta en el PATH.
    echo Instala Python 3.11+ desde https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Deps
python -c "import PySide6, fastapi" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias por primera vez...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: pip fallo.
        pause
        exit /b 1
    )
    echo.
)

REM Lanzar la GUI. Si se pasa "--daemon" arranca solo el daemon (retrocompat v1.4)
python -m posprintproxy %*

if errorlevel 1 pause

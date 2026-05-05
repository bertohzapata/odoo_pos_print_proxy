@echo off
title POS Print Proxy
echo ============================================
echo   POS Print Proxy - Iniciando...
echo ============================================
echo.

cd /d "%~dp0"

REM Verificar que Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no esta instalado o no esta en el PATH.
    echo Descarga Python 3.11+ desde https://www.python.org/downloads/
    echo Asegurate de marcar "Add Python to PATH" durante la instalacion.
    pause
    exit /b 1
)

REM Verificar dependencias
python -c "import fastapi" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias por primera vez...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: No se pudieron instalar las dependencias.
        pause
        exit /b 1
    )
    echo.
)

REM Verificar certificados HTTPS
if not exist localhost.pem (
    echo.
    echo ============================================
    echo   ATENCION: No hay certificados HTTPS
    echo ============================================
    echo.
    echo Si tu Odoo esta en HTTPS, el navegador bloqueara las peticiones
    echo a este proxy por "Mixed Content".
    echo.
    echo Para activar HTTPS local, EJECUTAR UNA VEZ:
    echo   1. Cerrar esta ventana
    echo   2. Click derecho en setup_https.bat
    echo   3. Seleccionar "Ejecutar como administrador"
    echo.
    echo Si quieres continuar igual en modo HTTP por ahora, presiona una tecla.
    echo Si quieres cancelar y configurar HTTPS, cerrar esta ventana ahora.
    echo.
    pause
)

REM Iniciar el proxy
echo Iniciando proxy... (Ctrl+C para detener)
echo.
python main.py

pause

@echo off
title POS Print Proxy - Setup HTTPS local
echo ============================================
echo   Setup HTTPS para POS Print Proxy
echo ============================================
echo.
echo Este script:
echo   1. Descarga mkcert (si no lo tiene)
echo   2. Instala una CA local en el almacen de certificados de Windows
echo   3. Genera un certificado HTTPS valido para localhost
echo.
echo IMPORTANTE: Este script DEBE ejecutarse como administrador.
echo (Click derecho en setup_https.bat ^> Ejecutar como administrador)
echo.

REM Verificar permisos de administrador
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Este script requiere permisos de administrador.
    echo.
    echo SOLUCION:
    echo   1. Cerrar esta ventana
    echo   2. Click derecho en setup_https.bat
    echo   3. Seleccionar "Ejecutar como administrador"
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"

REM Descargar mkcert si no existe
if not exist mkcert.exe (
    echo Descargando mkcert v1.4.4 desde GitHub...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-windows-amd64.exe' -OutFile 'mkcert.exe' -UseBasicParsing"
    if errorlevel 1 (
        echo.
        echo ERROR: No se pudo descargar mkcert.
        echo.
        echo Posibles causas:
        echo   - Sin conexion a internet
        echo   - Firewall corporativo bloqueando GitHub
        echo.
        echo Alternativa manual:
        echo   1. En otra PC con internet, descargar mkcert.exe desde:
        echo      https://github.com/FiloSottile/mkcert/releases/latest
        echo   2. Renombrar el archivo a mkcert.exe
        echo   3. Copiarlo a esta carpeta y volver a ejecutar este script
        echo.
        pause
        exit /b 1
    )
    echo OK: mkcert descargado.
    echo.
)

REM Paso 1: Instalar la CA en el almacen de certificados de Windows
echo Paso 1/2: Instalando CA local en Windows...
echo (Puede aparecer una ventana de Windows pidiendo confirmacion - aceptar)
echo.
mkcert.exe -install
if errorlevel 1 (
    echo.
    echo ERROR: No se pudo instalar la CA local.
    pause
    exit /b 1
)
echo OK: CA instalada.
echo.

REM Paso 2: Generar certificado para localhost
echo Paso 2/2: Generando certificado HTTPS para localhost...
mkcert.exe -cert-file localhost.pem -key-file localhost-key.pem localhost 127.0.0.1
if errorlevel 1 (
    echo.
    echo ERROR: No se pudo generar el certificado.
    pause
    exit /b 1
)
echo OK: Certificado generado.
echo.

echo ============================================
echo   Setup HTTPS completado con exito
echo ============================================
echo.
echo Archivos generados en esta carpeta:
echo   - localhost.pem       (certificado publico)
echo   - localhost-key.pem   (clave privada - NO compartir)
echo.
echo Estos archivos los lee automaticamente el proxy al iniciar.
echo.
echo PROXIMO PASO:
echo   Cerrar esta ventana y ejecutar start_proxy.bat
echo   El proxy debe arrancar en modo HTTPS.
echo.
pause

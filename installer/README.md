# Installer — POS Print Proxy v2.0

Este directorio contiene los scripts para producir el instalador `.exe`
que las tiendas descargan y ejecutan con doble click.

## Requisitos

- **Windows 10/11 x64** (el bundle requiere Windows para compilar con PyInstaller)
- **Python 3.11+**
- **Inno Setup 6** (https://jrsoftware.org/isdl.php) - instala `iscc.exe`

## Build local

Desde la raiz del repo:

```cmd
installer\build_local.bat
```

Salida: `dist_installer\POSPrintProxySetup-2.0.0.exe`

## Build via CI

Cada push de tag `v2.*` a la rama principal dispara
`.github/workflows/release.yml`, que:

1. Instala Python 3.12 y las deps
2. Ejecuta PyInstaller
3. Ejecuta Inno Setup (via `innosetup-action`)
4. Sube el `.exe` a GitHub Releases como asset del tag

El auto-updater de la app consulta el endpoint
`https://api.github.com/repos/bertohzapata/odoo_pos_print_proxy/releases/latest`
y avisa via tray cuando hay una version nueva.

## Contenido del installer

- `POSPrintProxy.exe` + runtime PyInstaller (Python + Qt + FastAPI + deps)
- `bin\mkcert.exe` (para generar/renovar certificados HTTPS)
- `config.yaml.default` (plantilla que se copia a %APPDATA% en primera ejecucion)
- Todo el codigo del paquete `posprintproxy` empaquetado

## Comportamiento del installer

- **Idioma**: Espanol e Ingles (Inno Setup detecta automaticamente)
- **Requisitos**: no requiere admin salvo que instale en Program Files
- **Deteccion de version previa**: si detecta un install anterior, ofrece
  desinstalarlo automaticamente antes de continuar (silencioso)
- **Preserva datos del usuario**: los archivos en `%APPDATA%\POSPrintProxy\`
  (config, certs, logs) NO se borran al desinstalar
- **Auto-inicio opcional**: checkbox en el wizard escribe la clave `HKCU\Run`

## Estructura del bundle

```
POSPrintProxy\               (en Program Files o carpeta elegida)
├── POSPrintProxy.exe
├── bin\
│   └── mkcert.exe
├── config.yaml.default
├── posprintproxy\           (theme.qss embebido aqui)
├── _internal\               (runtime PyInstaller)
└── ...

%APPDATA%\POSPrintProxy\     (datos del usuario)
├── config.yaml              (creado en primera ejecucion, copia de default)
├── certs\
│   ├── localhost.pem
│   ├── localhost-key.pem
│   └── mkcert.exe           (copia local, si el usuario renovo desde la GUI)
└── logs\
    └── proxy.log
```

## Iconos

Este directorio deberia tener `app.ico` para el .exe y accesos directos.
Si no existe, el build cae al icono default de Windows.

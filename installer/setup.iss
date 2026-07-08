; ============================================================================
; POS Print Proxy - Inno Setup script
;
; Instala la aplicacion en Program Files, crea acceso directo, ofrece
; auto-inicio, y (opcionalmente) desinstala versiones previas antes.
;
; Compilar en Windows con Inno Setup Compiler (ISCC.exe):
;   iscc installer/setup.iss
;
; O desde Inno Setup Compiler.exe > Open > setup.iss > Compile
; ============================================================================

#define AppName "POS Print Proxy"
#define AppExeName "POSPrintProxy.exe"
#define AppPublisher "Humberto Zapata"
#define AppURL "https://github.com/bertohzapata/odoo_pos_print_proxy"
#define AppId "{{9F4D8A3B-1D2E-4C1E-B9F2-8B0A5D3F5E12}"

; Version se pasa como parametro desde CI o build_local.bat:
;   iscc /DAppVersion=2.0.0 installer/setup.iss
#ifndef AppVersion
#define AppVersion "2.0.0"
#endif


[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
DefaultDirName={autopf}\POSPrintProxy
DefaultGroupName=POS Print Proxy
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
OutputDir=..\dist_installer
OutputBaseFilename=POSPrintProxySetup-{#AppVersion}
; No requerimos admin: si el usuario elige Program Files, Windows escalara;
; si elige AppData, no hara falta.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible


[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"


[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Iconos adicionales:"; Flags: unchecked
Name: "autostart"; Description: "Iniciar POS Print Proxy al iniciar sesion (minimizado a la bandeja)"; GroupDescription: "Auto-inicio:"; Flags: unchecked


[Files]
Source: "..\dist\POSPrintProxy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\config.yaml.default"; DestDir: "{app}"; Flags: ignoreversion


[Dirs]
; Carpetas de datos del usuario (persisten en desinstalacion normal)
Name: "{userappdata}\POSPrintProxy"; Permissions: users-full
Name: "{userappdata}\POSPrintProxy\logs"
Name: "{userappdata}\POSPrintProxy\certs"


[Icons]
Name: "{group}\POS Print Proxy"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar POS Print Proxy"; Filename: "{uninstallexe}"
Name: "{autodesktop}\POS Print Proxy"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon


[Registry]
; Auto-inicio opcional (HKCU\Run)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "POSPrintProxy"; ValueData: """{app}\{#AppExeName}"" --minimized"; Flags: uninsdeletevalue; Tasks: autostart


[Run]
Filename: "{app}\{#AppExeName}"; Description: "Iniciar POS Print Proxy ahora"; Flags: nowait postinstall skipifsilent runasoriginaluser


[UninstallDelete]
; Al desinstalar, la carpeta de datos del usuario (%APPDATA%\POSPrintProxy)
; NO se borra automaticamente (queda para conservar el cert). El usuario
; puede borrarla manualmente si quiere una limpieza total.


[Code]

function RemoveQuotes(S: String): String;
begin
  if (Length(S) > 1) and (S[1] = '"') and (S[Length(S)] = '"') then
    Result := Copy(S, 2, Length(S) - 2)
  else
    Result := S;
end;

// Detectar version instalada previa (por AppId) y desinstalarla silenciosamente.
// Se declara despues de RemoveQuotes para no depender de forward declaration.
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
  UninstallString: String;
  CRLF: String;
  Prompt: String;
begin
  Result := True;
  CRLF := Chr(13) + Chr(10);

  if RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppId}_is1',
    'UninstallString', UninstallString) or
     RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppId}_is1',
    'UninstallString', UninstallString) then
  begin
    UninstallString := RemoveQuotes(UninstallString);

    Prompt := 'Ya hay una version de POS Print Proxy instalada. ' +
              'Se desinstalara automaticamente antes de continuar. ' +
              'Los certificados HTTPS y la configuracion se conservaran.' +
              CRLF + CRLF +
              'Continuar?';

    if MsgBox(Prompt, mbConfirmation, MB_YESNO) = IDYES then
    begin
      Exec(UninstallString, '/VERYSILENT /SUPPRESSMSGBOXES /NORESTART',
           '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    end
    else
    begin
      Result := False;
    end;
  end;
end;

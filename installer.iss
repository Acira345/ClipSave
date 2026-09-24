; =====================================================================
;  Script de Inno Setup para ClipSave.
;
;  Requiere tener instalado Inno Setup (gratis):
;  https://jrsoftware.org/isdl.php
;
;  Como usarlo:
;    1) Primero compila la app normal con build.bat (modo --onedir),
;       para que exista la carpeta dist\ClipSave con ClipSave.exe adentro.
;    2) Abre este archivo (installer.iss) con Inno Setup Compiler,
;       o corre build_installer.bat (usa ISCC.exe por linea de comandos).
;    3) El instalador final queda en Output\ClipSave-Setup.exe
;       Ese es el archivo que le mandas a la gente en vez del .exe suelto.
; =====================================================================

#define MyAppName "ClipSave"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Diyel"
#define MyAppExeName "ClipSave.exe"

[Setup]
AppId={{8F2B6E1A-4C3D-4A9B-9E7F-CLIPSAVE0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=ClipSave-Setup
Compression=lzma2
SolidCompression=yes
SetupIconFile=icono.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
; No pide permisos de administrador: instala solo para el usuario actual,
; asi cualquiera lo puede instalar sin pedirle contraseña a un admin.
PrivilegesRequired=lowest

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un acceso directo en el Escritorio"; GroupDescription: "Accesos directos:"

[Files]
; Copia TODO el contenido de la carpeta que genera build.bat (dist\ClipSave)
Source: "dist\ClipSave\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent

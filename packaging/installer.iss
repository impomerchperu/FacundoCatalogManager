; Facundo Catalog Manager - Windows installer
; Build the PyInstaller bundle first with scripts/build_windows.ps1.

#define MyAppName "Facundo Catalog Manager"
#ifndef FCM_VERSION
#define FCM_VERSION "0.1.0"
#endif
#define MyAppVersion FCM_VERSION
#define MyAppPublisher "Importaciones Facundo"
#define MyAppExeName "FacundoCatalogManager.exe"

[Setup]
AppId={{4A3D9E16-8E3A-4F83-B3E8-4F3B76C3A4C1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\FacundoCatalogManager
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
CloseApplications=yes
OutputDir=..\dist\Windows
OutputBaseFilename=FacundoCatalogManager-{#MyAppVersion}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=..\resources\facundo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\Windows\FacundoCatalogManager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el Escritorio"; GroupDescription: "Accesos directos:";

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent

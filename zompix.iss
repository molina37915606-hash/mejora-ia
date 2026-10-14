#define AppName "Zompix"
#define AppVersion "1.4.0"
[Setup]
AppId={{A8C59E68-5F01-4CBF-8C76-0E104548623D}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Zompix
DefaultDirName={localappdata}\Programs\Zompix
DefaultGroupName=Zompix
OutputDir=dist
OutputBaseFilename=Zompix-Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
SetupIconFile=zompix.ico
UninstallDisplayIcon={app}\Zompix.exe
CloseApplications=yes
RestartApplications=no
[Files]
Source: "dist\Zompix.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{autoprograms}\Zompix"; Filename: "{app}\Zompix.exe"
Name: "{autodesktop}\Zompix"; Filename: "{app}\Zompix.exe"; Tasks: desktopicon
[Tasks]
Name: desktopicon; Description: "Crear acceso directo en el escritorio"; Flags: checkedonce
[Run]
Filename: "{app}\Zompix.exe"; Description: "Abrir Zompix"; Flags: nowait postinstall skipifsilent

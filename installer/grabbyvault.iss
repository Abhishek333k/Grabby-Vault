; Inno Setup script — compile with Inno Setup 6 after build.bat
; Does not code-sign; add SignTool when you have a certificate.

#define MyAppName "GrabbyVault"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "SilenVault"
#define MyAppURL "https://store.silenvault.com"
#define MyAppExeName "GrabbyVault.exe"

[Setup]
AppId={{A3C8B2E1-7D4F-4A9B-9C1E-GrabbyVault01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\dist\installer
OutputBaseFilename=GrabbyVault-Setup
SetupIconFile=..\assets\grabbyvault.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
; After: build.bat produces dist\GrabbyVault\
Source: "..\dist\GrabbyVault\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch GrabbyVault"; Flags: nowait postinstall skipifsilent

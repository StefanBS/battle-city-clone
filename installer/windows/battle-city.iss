; Requires Inno Setup 6+

#define MyAppName "Battle City"
#define MyAppVersion "1.0.3"
#define MyAppPublisher "Battle City Clone"
#define MyAppExeName "BattleCity.exe"

[Setup]
AppId={{1EE01768-3762-4299-A5D0-BFCAF23FE9C5}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=..\..\dist
OutputBaseFilename=BattleCitySetup-{#MyAppVersion}
SetupIconFile=..\..\assets\icons\battle-city.ico
Compression=lzma2/max
LZMANumBlockThreads=2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\BattleCity\*"; DestDir: "{app}"; Excludes: "*.pdb,*.pyc,__pycache__\*"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\assets\icons\battle-city.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\_internal\assets\icons\battle-city.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

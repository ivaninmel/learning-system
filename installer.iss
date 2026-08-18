#define AppName "学习小助手"
#define AppVersion "1.0.0"
#define AppPublisher "学习小助手"
#define AppExeName "学习小助手.exe"

[Setup]
AppId={{4EA0CEBF-C4C7-44E7-ABD5-AC42C4CA38DC}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=installer
OutputBaseFilename=学习小助手安装程序
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName={#AppName}

[Files]
Source: "dist\学习小助手\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 {#AppName}"; Flags: nowait postinstall skipifsilent

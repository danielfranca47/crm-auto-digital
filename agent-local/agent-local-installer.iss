; Script Inno Setup do instalador do agent-local (Gerador de Leads — Digital Pro).
;
; Gera um Setup.exe que instala por-usuário (sem pedir senha de administrador),
; cria atalho no Menu Iniciar sempre e na Área de Trabalho por padrão (opcional),
; e regista desinstalador em "Adicionar/Remover Programas".
;
; Pré-requisito: dist\agent-local.exe já gerado (ver build.bat).
; Uso: ver build-installer.bat.

#define MyAppName "Gerador de Leads — Digital Pro"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Digital Pro"
#define MyAppExeName "agent-local.exe"

[Setup]
AppId={{B6F52F8F-CDE5-4F8A-BDED-6AFF5C7C4EE3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\DigitalPro\GeradorDeLeads
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=installer_output
OutputBaseFilename=DigitalPro-GeradorDeLeads-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"; Flags: checkedonce

[Files]
Source: "dist\agent-local.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent

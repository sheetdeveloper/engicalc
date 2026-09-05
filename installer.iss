; Inno Setup script for EngiCalc.
;
; Prerequisites (one-time, on Windows):
;   1. Run build_exe.bat first (creates dist\EngiCalc.exe)
;   2. Install Inno Setup (free): https://jrsoftware.org/isdl.php
;
; Then either:
;   - Right-click this file -> "Compile", or
;   - Run build_installer.bat, which does it from the command line.
;
; Output: Output\EngiCalc_Setup.exe -- hand this single file to anyone;
; running it installs the app with a Start Menu entry, an optional
; desktop icon, and a proper uninstaller.

#define MyAppName "EngiCalc"
; Stamped automatically from engicalc/__init__.py by
; stamp_installer_version.py, which build_exe.bat and
; build_installer.bat both run before compiling. Don't bump this by
; hand -- edit engicalc/__init__.py instead.
#define MyAppVersion "1.2.0"
; Must match the code signing certificate subject exactly once one is
; bought, or the installer and the signature name different publishers.
#define MyAppPublisher "Sam Jury"
#define MyAppExeName "EngiCalc.exe"

[Setup]
AppId={{3D9E7A21-5C48-4F6B-8E12-A7C4B9D3F016}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=EngiCalc_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
; The app is per-user data only (~\.engicalc), so it does not need
; administrator rights to be useful. lowest lets someone install it on
; a locked-down work machine without raising a ticket.
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "dist\EngiCalc.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

; Saved calculations and any formulas the user added live in
; %USERPROFILE%\.engicalc and are deliberately left alone on uninstall.
; Someone removing the app to install a newer build should not lose their
; work; someone who really wants it gone can delete that folder.
[UninstallDelete]
Type: dirifempty; Name: "{app}"

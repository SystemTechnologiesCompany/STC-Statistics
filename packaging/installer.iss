#ifndef StageDir
  #error StageDir must point to the prepared installer payload
#endif
#if VER < EncodeVer(7, 0, 0)
  #error Inno Setup 7+ is required for long runtime file paths
#endif
#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif

[Setup]
AppId={{BC1A5A15-7C6D-4828-9185-530C0119B9D1}
AppName=STC Statistics
AppVersion={#AppVersion}
AppPublisher=System Technologies Company
AppPublisherURL=https://stc-official.netlify.app
AppSupportURL=https://www.linkedin.com/company/system-technologies-company-stc/
AppUpdatesURL=https://github.com/SystemTechnologiesCompany/STC-Statistics/releases
DefaultDirName={localappdata}\Programs\STC Statistics
DefaultGroupName=STC Statistics
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.17763
WizardStyle=modern dark includetitlebar
WizardBackColor=#0A0F0D
WizardImageBackColor=#0A0F0D
WizardSmallImageBackColor=#0A0F0D
WizardImageFile={#StageDir}\wizard-large.bmp
WizardSmallImageFile={#StageDir}\wizard-small.bmp
SetupIconFile={#StageDir}\stc-statistics-desktop.ico
UninstallDisplayIcon={app}\stc-statistics-desktop.ico
OutputDir={#OutputDir}
OutputBaseFilename=STC_Statistics_{#AppVersion}_Setup
Compression=lzma2/fast
SolidCompression=yes
LZMANumBlockThreads=2
LZMABlockSize=32768
DiskSpanning=no
DisableWelcomePage=no
DisableProgramGroupPage=yes
DisableDirPage=no
AllowNoIcons=yes
AppMutex=STCStatisticsInstalled
SetupMutex=STCStatisticsSetup
CloseApplications=yes
RestartApplications=no
Uninstallable=yes
; CI can install/uninstall entirely inside its workspace without registering or
; creating shortcuts in the user's Windows profile. Customer default is normal.
CreateUninstallRegKey=not IsolatedTest
UninstallDisplayName=STC Statistics
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany=System Technologies Company
VersionInfoDescription=STC Statistics Setup
VersionInfoProductName=STC Statistics
InfoBeforeFile={#StageDir}\setup-info-en.txt

[Languages]
Name: english; MessagesFile: compiler:Default.isl; InfoBeforeFile: "{#StageDir}\setup-info-en.txt"
Name: french; MessagesFile: compiler:Languages\French.isl; InfoBeforeFile: "{#StageDir}\setup-info-fr.txt"

[CustomMessages]
english.DesktopShortcut=Create a desktop shortcut
french.DesktopShortcut=Créer un raccourci sur le Bureau
english.LaunchApp=Open STC Statistics
french.LaunchApp=Ouvrir STC Statistics
english.NewerVersion=A newer STC Statistics version is already installed. Use the app's Updates page, or download a newer setup.
french.NewerVersion=Une version plus récente de STC Statistics est déjà installée. Utilisez la page Mises à jour ou téléchargez une installation plus récente.
english.UpdateBusy=An STC Statistics update is in progress. Let it finish before installing or uninstalling.
french.UpdateBusy=Une mise à jour de STC Statistics est en cours. Attendez sa fin avant d'installer ou de désinstaller.

[Tasks]
Name: desktopicon; Description: "{cm:DesktopShortcut}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#StageDir}\STC Statistics.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\stc-statistics-desktop.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\installation.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\THIRD_PARTY_NOTICES.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#StageDir}\runtime\*"; DestDir: "{app}\runtime"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\STC Statistics"; Filename: "{app}\STC Statistics.exe"; IconFilename: "{app}\stc-statistics-desktop.ico"; AppUserModelID: "STC.Statistics"
Name: "{autodesktop}\STC Statistics"; Filename: "{app}\STC Statistics.exe"; IconFilename: "{app}\stc-statistics-desktop.ico"; Tasks: desktopicon; AppUserModelID: "STC.Statistics"
Name: "{group}\Uninstall STC Statistics"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\STC Statistics.exe"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; These are generated application/runtime files, never the user's project folder.
Type: filesandordirs; Name: "{app}\runtime"
; Do not delete licensing/, updates/ recovery checkpoints or user projects.

[Code]
function IsolatedTest(): Boolean;
begin
  Result := ExpandConstant('{param:STCISOLATED|0}') = '1';
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  VersionFile, LocalVersion: String;
  VersionText: AnsiString;
  Candidate, Existing: Int64;
  StartPos, EndPos: Integer;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\updates\install.lock')) then begin
    Result := CustomMessage('UpdateBusy');
    Exit;
  end;
  { The app version can advance through patches without changing launcher metadata. }
  VersionFile := ExpandConstant('{app}\runtime\app\stc_statistics\version.py');
  if LoadStringFromFile(VersionFile, VersionText) then begin
    StartPos := Pos('''', VersionText);
    if StartPos = 0 then StartPos := Pos('"', VersionText);
    if StartPos > 0 then begin
      LocalVersion := Copy(VersionText, StartPos + 1, Length(VersionText));
      EndPos := Pos('''', LocalVersion);
      if EndPos = 0 then EndPos := Pos('"', LocalVersion);
      if EndPos > 0 then begin
        LocalVersion := Copy(LocalVersion, 1, EndPos - 1);
        if StrToVersion(LocalVersion, Existing) and StrToVersion('{#AppVersion}', Candidate) then
          if ComparePackedVersion(Existing, Candidate) > 0 then Result := CustomMessage('NewerVersion');
      end;
    end;
  end;
end;

function InitializeUninstall(): Boolean;
begin
  Result := not FileExists(ExpandConstant('{app}\updates\install.lock'));
  if not Result then MsgBox(CustomMessage('UpdateBusy'), mbInformation, MB_OK);
end;

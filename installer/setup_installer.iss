; Inno Setup Script for Enterprise Monitoring Agent v2.0.0
; FIXED: Added top-level Start Menu shortcut for Windows Search visibility

#define MyAppName "Enterprise Monitoring Agent"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Skillers Zone LTD"
#define MyAppURL "https://www.skillerszone.com"
#define MyAppExeName "Agent.exe"

[Setup]
AppId={{8F2A3B4C-5D6E-7F8G-9H0I-1J2K3L4M5N6O}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Enterprise Monitoring Agent
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=EnterpriseMonitoring_v{#MyAppVersion}_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\Agent.exe


[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Executables
Source: "..\dist\Watchdog.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\Agent.exe"; DestDir: "{app}"; Flags: ignoreversion

; NSSM Service Manager
Source: "..\tools\nssm.exe"; DestDir: "{app}\tools"; Flags: ignoreversion

; Documentation
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\BUILD_GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion

; Icon file
Source: "..\resources\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; FIXED: Top-level Start Menu shortcut for Windows Search visibility
; This puts "Enterprise Monitoring Agent" at the root of Start Menu
; Windows Indexing picks this up immediately, making it searchable
Name: "{commonprograms}\Enterprise Monitoring Agent"; Filename: "{app}\Agent.exe"; Comment: "Enterprise Monitoring User Agent"; IconFilename: "{app}\icon.ico"

; Desktop icon (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

; Additional shortcuts in program group folder (for traditional Start Menu navigation)
Name: "{group}\Enterprise Monitoring Agent"; Filename: "{app}\Agent.exe"; Comment: "User Monitoring Agent"; IconFilename: "{app}\icon.ico"
Name: "{group}\Service Manager"; Filename: "{sys}\sc.exe"; Parameters: "query EnterpriseWatchdog"; Comment: "Check Service Status"
Name: "{group}\View Logs"; Filename: "explorer.exe"; Parameters: "C:\ProgramData\EnterpriseMonitoring\logs"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Dirs]
; Create data directories
Name: "C:\ProgramData\EnterpriseMonitoring"; Permissions: users-modify
Name: "C:\ProgramData\EnterpriseMonitoring\data"; Permissions: users-modify
Name: "C:\ProgramData\EnterpriseMonitoring\data\screenshots"; Permissions: users-modify
Name: "C:\ProgramData\EnterpriseMonitoring\logs"; Permissions: users-modify
Name: "C:\ProgramData\EnterpriseMonitoring\config"; Permissions: users-modify
Name: "C:\ProgramData\EnterpriseMonitoring\exports"; Permissions: users-modify

[Run]
; Install Service using NSSM
Filename: "{app}\tools\nssm.exe"; Parameters: "install EnterpriseWatchdog ""{app}\Watchdog.exe"""; StatusMsg: "Installing Watchdog Service..."; Flags: runhidden

; Configure Service
Filename: "{app}\tools\nssm.exe"; Parameters: "set EnterpriseWatchdog AppDirectory ""{app}"""; Flags: runhidden
Filename: "{app}\tools\nssm.exe"; Parameters: "set EnterpriseWatchdog DisplayName ""Enterprise Monitoring Watchdog"""; Flags: runhidden
Filename: "{app}\tools\nssm.exe"; Parameters: "set EnterpriseWatchdog Description ""Central monitoring service for Enterprise Monitoring Agent"""; Flags: runhidden
Filename: "{app}\tools\nssm.exe"; Parameters: "set EnterpriseWatchdog Start SERVICE_AUTO_START"; Flags: runhidden
Filename: "{app}\tools\nssm.exe"; Parameters: "set EnterpriseWatchdog ObjectName LocalSystem"; Flags: runhidden

; Configure Service logging
Filename: "{app}\tools\nssm.exe"; Parameters: "set EnterpriseWatchdog AppStdout ""C:\ProgramData\EnterpriseMonitoring\logs\watchdog_stdout.log"""; Flags: runhidden
Filename: "{app}\tools\nssm.exe"; Parameters: "set EnterpriseWatchdog AppStderr ""C:\ProgramData\EnterpriseMonitoring\logs\watchdog_stderr.log"""; Flags: runhidden

; Start Service
Filename: "{app}\tools\nssm.exe"; Parameters: "start EnterpriseWatchdog"; StatusMsg: "Starting Watchdog Service..."; Flags: runhidden

; Add User Agent to startup (runs on user login)
Filename: "reg"; Parameters: "add HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v EnterpriseMonitoringAgent /t REG_SZ /d ""{app}\Agent.exe"" /f"; StatusMsg: "Adding User Agent to startup..."; Flags: runhidden

[UninstallRun]
; Stop and remove service
Filename: "{app}\tools\nssm.exe"; Parameters: "stop EnterpriseWatchdog"; Flags: runhidden
Filename: "{app}\tools\nssm.exe"; Parameters: "remove EnterpriseWatchdog confirm"; Flags: runhidden

; Remove from startup
Filename: "reg"; Parameters: "delete HKCU\Software\Microsoft\Windows\CurrentVersion\Run /v EnterpriseMonitoringAgent /f"; Flags: runhidden

; Stop running Agent
Filename: "taskkill"; Parameters: "/F /IM Agent.exe"; Flags: runhidden

[UninstallDelete]
; Optional: Delete data files (ask user)
Type: filesandordirs; Name: "C:\ProgramData\EnterpriseMonitoring\data"
Type: filesandordirs; Name: "C:\ProgramData\EnterpriseMonitoring\logs"

[Code]
function InitializeSetup(): Boolean;
var
  ResultCode: Integer;
begin
  Result := True;
  
  // Check if service already exists
  if Exec('sc', 'query EnterpriseWatchdog', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      // Service exists, ask to uninstall first
      if MsgBox('Enterprise Monitoring Agent is already installed. Do you want to uninstall the existing version first?', 
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        // Stop service
        Exec('nssm', 'stop EnterpriseWatchdog', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
        Sleep(2000);
        // Remove service
        Exec('nssm', 'remove EnterpriseWatchdog confirm', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
        Sleep(1000);
      end
      else
      begin
        Result := False;
      end;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Give service time to start
    Sleep(3000);
  end;
end;

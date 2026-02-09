; Inno Setup Script for Enterprise Monitoring Agent
; Split-Brain Architecture: Service Watchdog (SYSTEM) + User Agent (User)

#define MyAppName "Enterprise Monitoring Agent"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Skillers Zone LTD"
#define MyAppURL "https://www.skillerszone.com"
#define MyWatchdogServiceName "EnterpriseWatchdog"

[Setup]
AppId={{F1B2C3D4-E5F6-7G8H-9I0J-K1L2M3N4O5P6}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={commonpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=EnterpriseMonitoring_v{#MyAppVersion}_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\Agent.exe
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Service Watchdog (SYSTEM process)
Source: "..\dist\Watchdog.exe"; DestDir: "{app}"; Flags: ignoreversion

; User Agent (User process)
Source: "..\dist\Agent.exe"; DestDir: "{app}"; Flags: ignoreversion

; NSSM for service management
Source: "..\tools\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion

; Optional: Documentation
; Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion
; Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Create ProgramData directories
Name: "C:\ProgramData\EnterpriseMonitoring"; Permissions: users-modify
Name: "C:\ProgramData\EnterpriseMonitoring\data"; Permissions: users-modify
Name: "C:\ProgramData\EnterpriseMonitoring\data\screenshots"; Permissions: users-modify
Name: "C:\ProgramData\EnterpriseMonitoring\logs"; Permissions: users-modify
Name: "C:\ProgramData\EnterpriseMonitoring\config"; Permissions: users-modify

[Registry]
; Register User Agent to start on login
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "EnterpriseAgent"; \
    ValueData: """{app}\Agent.exe"""; \
    Flags: uninsdeletevalue

[Run]
; === INSTALL SERVICE WATCHDOG ===

; Stop service if already exists (will fail silently if doesn't exist)
Filename: "{app}\nssm.exe"; \
    Parameters: "stop ""{#MyWatchdogServiceName}"""; \
    Flags: runhidden; StatusMsg: "Stopping existing service..."

; Wait a moment for service to stop
Filename: "{cmd}"; Parameters: "/C timeout /T 2 /NOBREAK"; \
    Flags: runhidden

; Remove old service if exists (will fail silently if doesn't exist)
Filename: "{app}\nssm.exe"; \
    Parameters: "remove ""{#MyWatchdogServiceName}"" confirm"; \
    Flags: runhidden

; Install new service
Filename: "{app}\nssm.exe"; \
    Parameters: "install ""{#MyWatchdogServiceName}"" ""{app}\Watchdog.exe"""; \
    Flags: runhidden; StatusMsg: "Installing Watchdog Service..."

; Configure service display name
Filename: "{app}\nssm.exe"; \
    Parameters: "set ""{#MyWatchdogServiceName}"" DisplayName ""Enterprise Monitoring Watchdog"""; \
    Flags: runhidden

; Configure service description
Filename: "{app}\nssm.exe"; \
    Parameters: "set ""{#MyWatchdogServiceName}"" Description ""Central database manager and IPC server for Enterprise Monitoring"""; \
    Flags: runhidden

; Set service to start automatically
Filename: "{app}\nssm.exe"; \
    Parameters: "set ""{#MyWatchdogServiceName}"" Start SERVICE_AUTO_START"; \
    Flags: runhidden

; Configure stdout logging
Filename: "{app}\nssm.exe"; \
    Parameters: "set ""{#MyWatchdogServiceName}"" AppStdout ""C:\ProgramData\EnterpriseMonitoring\logs\watchdog_stdout.log"""; \
    Flags: runhidden

; Configure stderr logging
Filename: "{app}\nssm.exe"; \
    Parameters: "set ""{#MyWatchdogServiceName}"" AppStderr ""C:\ProgramData\EnterpriseMonitoring\logs\watchdog_stderr.log"""; \
    Flags: runhidden

; Configure restart on failure
Filename: "{app}\nssm.exe"; \
    Parameters: "set ""{#MyWatchdogServiceName}"" AppExit Default Restart"; \
    Flags: runhidden

; Set restart delay (10 seconds)
Filename: "{app}\nssm.exe"; \
    Parameters: "set ""{#MyWatchdogServiceName}"" AppRestartDelay 10000"; \
    Flags: runhidden

; Start service
Filename: "{app}\nssm.exe"; \
    Parameters: "start ""{#MyWatchdogServiceName}"""; \
    Flags: runhidden; StatusMsg: "Starting Watchdog Service..."

; === LAUNCH USER AGENT ===

; Start User Agent immediately (will also start on login via Registry)
Filename: "{app}\Agent.exe"; \
    Description: "Launch Enterprise Monitoring Agent"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; Stop User Agent (best effort - may not be running)
Filename: "taskkill"; Parameters: "/F /IM Agent.exe"; \
    Flags: runhidden; RunOnceId: "StopAgent"

; Stop Watchdog Service
Filename: "{app}\nssm.exe"; \
    Parameters: "stop ""{#MyWatchdogServiceName}"""; \
    Flags: runhidden; RunOnceId: "StopService"

; Remove Watchdog Service
Filename: "{app}\nssm.exe"; \
    Parameters: "remove ""{#MyWatchdogServiceName}"" confirm"; \
    Flags: runhidden; RunOnceId: "RemoveService"

[Code]
// ===== ADMIN PRIVILEGE CHECK =====
function InitializeSetup(): Boolean;
begin
  Result := True;
  
  if not IsAdminLoggedOn() then
  begin
    MsgBox('This installer requires administrator privileges to install a Windows service.' + #13#10 + 
           'Please run the installer as administrator.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  
  if not IsAdminInstallMode() then
  begin
    MsgBox('This installer must be run with elevated privileges.' + #13#10 +
           'Please right-click the installer and select "Run as administrator".', mbError, MB_OK);
    Result := False;
    Exit;
  end;
end;

// ===== STOP EXISTING PROCESSES BEFORE INSTALL =====
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Result := '';
  
  // Try to stop User Agent if running
  Exec('taskkill', '/F /IM Agent.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(1000);
  
  // Check if Watchdog service exists and try to stop it
  if Exec('sc', 'query "{#MyWatchdogServiceName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    if ResultCode = 0 then
    begin
      Log('Watchdog service exists, attempting to stop...');
      Exec('sc', 'stop "{#MyWatchdogServiceName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
      Sleep(3000); // Wait for service to stop
    end;
  end;
end;

// ===== POST-INSTALL VERIFICATION =====
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    // Verify Watchdog service installation
    if Exec(ExpandConstant('{app}\nssm.exe'), 'status "{#MyWatchdogServiceName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      if ResultCode = 0 then
      begin
        Log('Watchdog service installed and started successfully');
      end
      else
      begin
        MsgBox('Warning: Watchdog service installation may have encountered issues. ' +
               'Please check the logs at C:\ProgramData\EnterpriseMonitoring\logs\', 
               mbInformation, MB_OK);
      end;
    end;
  end;
end;

// ===== UNINSTALL CLEANUP =====
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ResultCode: Integer;
begin
  if CurUninstallStep = usUninstall then
  begin
    // Stop User Agent
    Exec('taskkill', '/F /IM Agent.exe', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000);
    
    // Stop and remove Watchdog service
    Exec(ExpandConstant('{app}\nssm.exe'), 'stop "{#MyWatchdogServiceName}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(2000);
    Exec(ExpandConstant('{app}\nssm.exe'), 'remove "{#MyWatchdogServiceName}" confirm', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000);
  end;
  
  if CurUninstallStep = usPostUninstall then
  begin
    // Ask if user wants to keep monitoring data
    if MsgBox('Do you want to remove all monitoring data and logs from C:\ProgramData\EnterpriseMonitoring?' + #13#10 + #13#10 +
              'This includes screenshots, clipboard history, and database files.', 
              mbConfirmation, MB_YESNO) = IDYES then
    begin
      DelTree('C:\ProgramData\EnterpriseMonitoring', True, True, True);
    end;
  end;
end;

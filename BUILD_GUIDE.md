# Enterprise Monitoring Agent - Build Guide
## Split-Brain Architecture (Service + Agent)

---

## Overview

This guide walks you through building and deploying the Enterprise Monitoring Agent with the split-brain architecture:

- **Watchdog.exe** - SYSTEM service (Session 0) that manages the database and receives data via IPC
- **Agent.exe** - User process (Interactive Session) that captures screen, clipboard, and app usage

---

## Prerequisites

### Required Software

1. **Python 3.9+** (https://www.python.org/downloads/)
2. **PyInstaller** (installed via pip)
3. **Inno Setup 6** (https://jrsoftware.org/isinfo.php)
4. **NSSM** (https://nssm.cc/download) - Get the 64-bit version

### System Requirements

- Windows 10/11 (64-bit)
- Administrator privileges
- Internet connection for dependencies

---

## Step 1: Environment Setup

### 1.1 Create Project Directory

```bash
mkdir EnterpriseMonitoring
cd EnterpriseMonitoring
```

### 1.2 Install Python Dependencies

```bash
# Install all required packages
pip install -r requirements.txt

# Verify installation
pip list | findstr "mss pyperclip pystray cryptography psutil pyinstaller"
```

Expected output:
```
cryptography          41.0.7
mss                   9.0.1
psutil                5.9.6
pyinstaller           6.3.0
pyperclip             1.8.2
pystray               0.19.5
```

---

## Step 2: Download NSSM

### 2.1 Download and Extract

1. Download NSSM from: https://nssm.cc/download
2. Extract the ZIP file
3. Copy `nssm-2.24\win64\nssm.exe` to your project

### 2.2 Create Tools Directory

```bash
mkdir tools
copy path\to\nssm.exe tools\nssm.exe
```

Verify:
```bash
dir tools\nssm.exe
```

---

## Step 3: Build Executables

### 3.1 Build Service Watchdog

```bash
# Build Watchdog.exe
pyinstaller --clean --noconfirm build_watchdog.spec
```

Expected output:
```
Building EXE from EXE-00.toc completed successfully.
```

Verify:
```bash
dir dist\Watchdog.exe
```

### 3.2 Build User Agent

```bash
# Build Agent.exe
pyinstaller --clean --noconfirm build_agent.spec
```

Expected output:
```
Building EXE from EXE-00.toc completed successfully.
```

Verify:
```bash
dir dist\Agent.exe
```

### 3.3 Verify Build Outputs

Your `dist\` folder should contain:
```
dist\
├── Watchdog.exe  (~15-20 MB)
└── Agent.exe     (~25-30 MB)
```

---

## Step 4: Compile Installer

### 4.1 Open Inno Setup

1. Launch Inno Setup Compiler
2. File → Open → Select `installer\setup_installer.iss`

### 4.2 Compile

1. Build → Compile
2. Wait for compilation to complete

Expected output:
```
Successful compile (0 errors, 0 warnings)
Output: installer_output\EnterpriseMonitoring_v2.0.0_Setup.exe
```

### 4.3 Verify Installer

```bash
dir installer_output\EnterpriseMonitoring_v2.0.0_Setup.exe
```

Expected size: ~40-50 MB

---

## Step 5: Test Installation (Development)

### 5.1 Manual Testing

**Test Watchdog Service:**
```bash
# Navigate to dist folder
cd dist

# Test Watchdog manually
Watchdog.exe
```

Expected output:
```
[INFO] SERVICE WATCHDOG INITIALIZING
[INFO] Version: 2.0.0
[INFO] Database initialized at C:\ProgramData\EnterpriseMonitoring\data\monitoring.db
[INFO] IPC Server listening on 127.0.0.1:51234
[INFO] Service Watchdog started successfully
```

Press Ctrl+C to stop.

**Test User Agent:**
```bash
# Test Agent manually
Agent.exe
```

Expected output:
```
[INFO] USER AGENT INITIALIZING
[INFO] Version: 2.0.0
[INFO] Connecting to Service Watchdog...
[INFO] Connected to IPC server at 127.0.0.1:51234
[INFO] User Agent started successfully
```

You should see the green tray icon appear.

### 5.2 Test IPC Communication

1. Start Watchdog.exe in one terminal
2. Start Agent.exe in another terminal
3. Check Watchdog logs for incoming messages:

```bash
type C:\ProgramData\EnterpriseMonitoring\logs\watchdog.log
```

Expected:
```
[INFO] Client connected from ('127.0.0.1', 51235)
[DEBUG] Received screenshot: C:\ProgramData\...\screenshot_20240208_143022_000001.jpg
[DEBUG] Received clipboard: text
[DEBUG] Received app usage: chrome.exe
```

---

## Step 6: Full Installation Test

### 6.1 Run Installer

```bash
# Right-click and "Run as administrator"
installer_output\EnterpriseMonitoring_v2.0.0_Setup.exe
```

### 6.2 Verify Service Installation

```bash
# Check service status
nssm status EnterpriseWatchdog
```

Expected output:
```
SERVICE_RUNNING
```

Alternative check:
```bash
sc query EnterpriseWatchdog
```

### 6.3 Verify User Agent Auto-Start

1. Log out and log back in
2. Check for Agent.exe in Task Manager
3. Look for green tray icon

### 6.4 Verify Data Collection

**Check screenshots:**
```bash
dir C:\ProgramData\EnterpriseMonitoring\data\screenshots
```

**Check database:**
```bash
dir C:\ProgramData\EnterpriseMonitoring\data\monitoring.db
```

**Check logs:**
```bash
type C:\ProgramData\EnterpriseMonitoring\logs\watchdog.log
type C:\ProgramData\EnterpriseMonitoring\logs\agent.log
```

---

## Step 7: Deployment

### 7.1 Distribution

The installer is self-contained:
```
EnterpriseMonitoring_v2.0.0_Setup.exe
```

### 7.2 Silent Installation

For enterprise deployment:
```bash
# Silent install
EnterpriseMonitoring_v2.0.0_Setup.exe /VERYSILENT /NORESTART

# Silent uninstall
"C:\Program Files\Enterprise Monitoring Agent\unins000.exe" /VERYSILENT
```

### 7.3 Group Policy Deployment

1. Copy installer to network share: `\\server\share\software\`
2. Create GPO: Computer Configuration → Policies → Software Settings → Software Installation
3. Add New Package → Select installer
4. Configure: Assigned / Published
5. Apply to target OUs

---

## Service Management Commands

### Check Status
```bash
nssm status EnterpriseWatchdog
sc query EnterpriseWatchdog
```

### Start Service
```bash
nssm start EnterpriseWatchdog
net start EnterpriseWatchdog
```

### Stop Service
```bash
nssm stop EnterpriseWatchdog
net stop EnterpriseWatchdog
```

### Restart Service
```bash
nssm restart EnterpriseWatchdog
```

### View Service Logs
```bash
type C:\ProgramData\EnterpriseMonitoring\logs\watchdog_stdout.log
type C:\ProgramData\EnterpriseMonitoring\logs\watchdog_stderr.log
```

---

## User Agent Management

### Check if Running
```bash
tasklist | findstr Agent.exe
```

### Manually Start
```bash
"C:\Program Files\Enterprise Monitoring Agent\Agent.exe"
```

### Kill Agent
```bash
taskkill /F /IM Agent.exe
```

---

## Troubleshooting

### Issue: Service Won't Start

**Check logs:**
```bash
type C:\ProgramData\EnterpriseMonitoring\logs\watchdog_stderr.log
```

**Common causes:**
1. Port 51234 already in use
2. Database locked
3. Permissions issue on C:\ProgramData

**Solution:**
```bash
# Check port usage
netstat -ano | findstr :51234

# Reset permissions
icacls "C:\ProgramData\EnterpriseMonitoring" /grant Users:(OI)(CI)F /T
```

### Issue: Agent Can't Connect to Service

**Check service is running:**
```bash
nssm status EnterpriseWatchdog
```

**Check firewall:**
```bash
# Add firewall rule (if needed)
netsh advfirewall firewall add rule name="Enterprise Watchdog" dir=in action=allow protocol=TCP localport=51234
```

**Check logs:**
```bash
type C:\ProgramData\EnterpriseMonitoring\logs\agent.log
```

### Issue: Screenshots Not Being Captured

**Check Agent process:**
```bash
tasklist | findstr Agent.exe
```

**Check screenshot directory:**
```bash
dir C:\ProgramData\EnterpriseMonitoring\data\screenshots
```

**Restart Agent:**
```bash
taskkill /F /IM Agent.exe
"C:\Program Files\Enterprise Monitoring Agent\Agent.exe"
```

### Issue: High CPU/Memory Usage

**Check monitor thread status:**
- Screenshots: 1 per second = ~3.6K files/hour
- Reduce SCREENSHOT_INTERVAL in config.py if needed

**Optimize settings:**
Edit `C:\ProgramData\EnterpriseMonitoring\config\settings.json`:
```json
{
  "screenshot_interval": 2.0,
  "screenshot_quality": 30,
  "screenshot_scale": 0.3
}
```

---

## Uninstallation

### Standard Uninstall
1. Settings → Apps → Enterprise Monitoring Agent → Uninstall
2. Choose to keep or remove data

### Silent Uninstall
```bash
"C:\Program Files\Enterprise Monitoring Agent\unins000.exe" /VERYSILENT
```

### Manual Cleanup (if needed)
```bash
# Stop processes
taskkill /F /IM Agent.exe
nssm stop EnterpriseWatchdog
nssm remove EnterpriseWatchdog confirm

# Remove files
rmdir /S /Q "C:\Program Files\Enterprise Monitoring Agent"
rmdir /S /Q "C:\ProgramData\EnterpriseMonitoring"

# Remove registry entries
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v EnterpriseAgent /f
```

---

## Database Access

### Query Database Directly

```bash
# Open database with SQLite
sqlite3 C:\ProgramData\EnterpriseMonitoring\data\monitoring.db

# Example queries
.tables
SELECT COUNT(*) FROM screenshots;
SELECT COUNT(*) FROM clipboard_events;
SELECT COUNT(*) FROM app_usage;

# Export to CSV
.mode csv
.output screenshots.csv
SELECT * FROM screenshots ORDER BY timestamp DESC LIMIT 100;
.quit
```

---

## Production Deployment Checklist

- [ ] Build tested on clean VM
- [ ] Installer tested on Windows 10 and 11
- [ ] Service starts automatically after reboot
- [ ] Agent starts on user login
- [ ] Data collection verified (screenshots, clipboard, apps)
- [ ] Database retention tested
- [ ] Logs rotating correctly
- [ ] Uninstaller tested
- [ ] Silent install/uninstall tested
- [ ] Documentation updated
- [ ] Code signed (optional but recommended)

---

## Security Considerations

### Encryption

All sensitive clipboard data is encrypted using Fernet (AES-128) before storage.

Key location: `C:\ProgramData\EnterpriseMonitoring\config\.encryption_key`

**Backup encryption key** for data recovery:
```bash
copy C:\ProgramData\EnterpriseMonitoring\config\.encryption_key backup_location\
```

### Permissions

- Service runs as SYSTEM (full access)
- Data directory has user modify permissions
- Encryption key is hidden (HIDDEN + SYSTEM attributes)

### Network Security

- IPC uses localhost only (127.0.0.1)
- No external network access required
- Authentication token validates messages

---

## Support

For issues or questions:
1. Check logs in `C:\ProgramData\EnterpriseMonitoring\logs\`
2. Review this guide's troubleshooting section
3. Contact: support@skillerszone.com

---

## Version History

**v2.0.0** - Initial split-brain architecture release
- Service Watchdog (SYSTEM) + User Agent (User) separation
- Socket-based IPC communication
- Time-lapse screenshots (1 fps)
- Clipboard monitoring with encryption
- Application usage tracking
- System tray icon

---

**Build completed successfully!** 🎉

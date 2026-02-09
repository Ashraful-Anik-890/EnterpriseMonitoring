# Enterprise Monitoring Agent
## Split-Brain Architecture - Solving the Session 0 Isolation Problem

---

## 🎯 Problem Statement

Windows Services run in **Session 0** (isolated from user desktop), which prevents:
- ❌ Screen capture (all screenshots are black)
- ❌ Clipboard access (empty clipboard)
- ❌ User window detection (no active windows visible)

**Previous solutions** tried to run everything as a service = **Failed**.

---

## ✅ Solution: Split-Brain Architecture

We solve this by separating the application into **two cooperating processes**:

### 1. **Service Watchdog** (SYSTEM - Session 0)
- Runs as Windows Service via NSSM
- Manages central SQLite database
- Receives data via IPC (Socket)
- Enforces retention policies
- Monitors Agent health

**Can't access:** User desktop, clipboard, windows  
**Can access:** All files, system resources, network

### 2. **User Agent** (USER - Interactive Session)
- Runs as logged-in user
- Captures screenshots (mss library)
- Monitors clipboard (pyperclip library)
- Tracks application usage
- Sends data to Watchdog via IPC

**Can access:** User desktop, clipboard, windows  
**Can't access:** SYSTEM-level operations

---

## 🏗️ Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                 WINDOWS SYSTEM                       │
├─────────────────────────────────────────────────────┤
│                                                       │
│  SESSION 0 (SYSTEM)          │  SESSION 1 (User)    │
│  ┌──────────────────┐        │  ┌───────────────┐   │
│  │ Service Watchdog │◄───────┼──┤  User Agent   │   │
│  │  (Watchdog.exe)  │  IPC   │  │  (Agent.exe)  │   │
│  └──────────────────┘ Socket │  └───────────────┘   │
│         │                     │         │            │
│         ▼                     │         ▼            │
│  ┌──────────────┐            │  ┌─────────────────┐ │
│  │   Database   │            │  │ • Screenshots   │ │
│  │  (SQLite)    │            │  │ • Clipboard     │ │
│  │              │            │  │ • App Tracking  │ │
│  └──────────────┘            │  │ • Tray Icon     │ │
│                               │  └─────────────────┘ │
└───────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
EnterpriseMonitoring/
├── src/
│   ├── __init__.py
│   ├── config.py                 # Shared configuration
│   ├── crypto_manager.py         # Encryption utilities
│   ├── db_manager.py             # Database operations
│   ├── ipc_manager.py            # Socket communication
│   ├── service_watchdog.py       # SYSTEM service
│   └── user_agent.py             # User process
├── installer/
│   └── setup_installer.iss       # Inno Setup script
├── tools/
│   └── nssm.exe                  # Service manager
├── build_watchdog.spec           # PyInstaller for Watchdog
├── build_agent.spec              # PyInstaller for Agent
├── requirements.txt
├── BUILD_GUIDE.md
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Windows 10/11 (64-bit)
- Administrator privileges

### Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Download NSSM
# Place nssm.exe in tools/ folder

# 3. Build executables
pyinstaller --clean build_watchdog.spec
pyinstaller --clean build_agent.spec

# 4. Compile installer
# Open installer/setup_installer.iss in Inno Setup and compile

# 5. Run installer
installer_output\EnterpriseMonitoring_v2.0.0_Setup.exe
```

See **[BUILD_GUIDE.md](BUILD_GUIDE.md)** for detailed instructions.

---

## 🔧 Components

### Service Watchdog
- **Language:** Python 3.9+
- **Libraries:** Standard library + cryptography + psutil
- **Location:** `C:\Program Files\Enterprise Monitoring Agent\Watchdog.exe`
- **Runs as:** SYSTEM
- **Startup:** Automatic (via NSSM)

### User Agent
- **Language:** Python 3.9+
- **Libraries:** mss, pyperclip, pystray, Pillow, cryptography
- **Location:** `C:\Program Files\Enterprise Monitoring Agent\Agent.exe`
- **Runs as:** Current user
- **Startup:** Registry Run Key (HKCU\...\Run)

### IPC Protocol
- **Transport:** TCP Socket (localhost only)
- **Port:** 51234
- **Authentication:** Shared secret token
- **Message Format:** Length-prefixed JSON

---

## 📊 Data Collection

### Screenshots
- **Frequency:** 1 per second (time-lapse)
- **Format:** JPEG (configurable quality)
- **Resolution:** Scaled to 50% (configurable)
- **Storage:** `C:\ProgramData\EnterpriseMonitoring\data\screenshots\`
- **Retention:** 7 days (configurable)

### Clipboard
- **Frequency:** Polled every 0.5 seconds
- **Data:** Text only (encrypted)
- **Preview:** First 200 characters
- **Storage:** SQLite database (encrypted)
- **Retention:** 30 days (configurable)

### Application Usage
- **Frequency:** Polled every 1 second
- **Data:** Window title, process name, duration
- **Storage:** SQLite database
- **Retention:** 90 days (configurable)

---

## 🗄️ Database Schema

Located at: `C:\ProgramData\EnterpriseMonitoring\data\monitoring.db`

### Tables

**screenshots**
- timestamp, filepath, file_size_bytes, resolution
- active_window, active_app

**clipboard_events**
- timestamp, content_type, content_preview
- encrypted_content, content_hash, source_app

**app_usage**
- timestamp, app_name, window_title, duration_seconds

**system_events**
- timestamp, event_type, severity, message, details

---

## 🔒 Security

### Encryption
- **Algorithm:** Fernet (AES-128 CBC + HMAC)
- **Key Storage:** `C:\ProgramData\EnterpriseMonitoring\config\.encryption_key`
- **Encrypted Data:** Clipboard content, sensitive metadata

### Access Control
- Service: Runs as SYSTEM (full access)
- Agent: Runs as user (limited access)
- Database: Write-only by service
- Config: User modify permissions

### Network
- **IPC:** Localhost only (127.0.0.1)
- **No external network:** All data stored locally
- **Authentication:** Token-based message validation

---

## 📈 Performance

### Resource Usage (Typical)
- **Service Watchdog:** ~20 MB RAM, <1% CPU
- **User Agent:** ~50 MB RAM, 2-5% CPU
- **Disk Usage:** ~500 MB/day (screenshots)

### Optimization
- Screenshots: 1 fps (not video encoding)
- Database: WAL mode for concurrency
- Cleanup: Automatic old data deletion
- UPX: Executable compression

---

## 🛠️ Configuration

Edit: `C:\ProgramData\EnterpriseMonitoring\config\settings.json`

```json
{
  "screenshot_interval": 1.0,
  "screenshot_quality": 50,
  "screenshot_scale": 0.5,
  "clipboard_poll_interval": 0.5,
  "app_usage_poll_interval": 1.0,
  "retention_days": 30,
  "max_screenshot_age_days": 7,
  "encryption_enabled": true
}
```

Changes take effect after restarting Agent and Service.

---

## 🔍 Monitoring & Logs

### Service Logs
```
C:\ProgramData\EnterpriseMonitoring\logs\
├── watchdog.log          # Service application log
├── watchdog_stdout.log   # Service stdout (NSSM)
├── watchdog_stderr.log   # Service errors (NSSM)
└── agent.log             # User Agent log
```

### Check Status

```bash
# Service status
nssm status EnterpriseWatchdog

# Agent status
tasklist | findstr Agent.exe

# View logs
type C:\ProgramData\EnterpriseMonitoring\logs\watchdog.log
type C:\ProgramData\EnterpriseMonitoring\logs\agent.log
```

---

## 🔄 Service Management

### Start/Stop Service

```bash
# Start
nssm start EnterpriseWatchdog
net start EnterpriseWatchdog

# Stop
nssm stop EnterpriseWatchdog
net stop EnterpriseWatchdog

# Restart
nssm restart EnterpriseWatchdog

# Status
nssm status EnterpriseWatchdog
```

### Start/Stop Agent

```bash
# Start (manually)
"C:\Program Files\Enterprise Monitoring Agent\Agent.exe"

# Stop
taskkill /F /IM Agent.exe
```

---

## 🗑️ Uninstallation

### Standard Uninstall
1. Settings → Apps → Enterprise Monitoring Agent
2. Uninstall
3. Choose to keep or remove data

### Silent Uninstall
```bash
"C:\Program Files\Enterprise Monitoring Agent\unins000.exe" /VERYSILENT
```

### Manual Cleanup
```bash
# Stop everything
taskkill /F /IM Agent.exe
nssm stop EnterpriseWatchdog
nssm remove EnterpriseWatchdog confirm

# Remove files
rmdir /S /Q "C:\Program Files\Enterprise Monitoring Agent"
rmdir /S /Q "C:\ProgramData\EnterpriseMonitoring"
```

---

## 🐛 Troubleshooting

### Service Won't Start
1. Check logs: `C:\ProgramData\EnterpriseMonitoring\logs\watchdog_stderr.log`
2. Verify port 51234 is available: `netstat -ano | findstr :51234`
3. Check permissions on C:\ProgramData

### Agent Can't Connect
1. Verify service is running: `nssm status EnterpriseWatchdog`
2. Check firewall settings
3. Review agent.log for errors

### No Screenshots
1. Verify Agent is running: `tasklist | findstr Agent.exe`
2. Check screenshot directory: `dir C:\ProgramData\EnterpriseMonitoring\data\screenshots`
3. Restart Agent

See **[BUILD_GUIDE.md](BUILD_GUIDE.md)** for more troubleshooting.

---

## 📚 Technical Details

### Why Two Processes?

**Windows Session Isolation:**
- Session 0: Services (SYSTEM) - No desktop access
- Session 1+: User sessions - Desktop access

**Our Solution:**
- Watchdog in Session 0: Database + IPC server
- Agent in Session 1: Monitoring + IPC client

**Communication:**
- Socket-based IPC on localhost
- Length-prefixed JSON messages
- Authentication tokens
- Automatic reconnection

### Why Not Named Pipes?

- **Sockets** are simpler and more portable
- No permission issues with SYSTEM ↔ User
- Better error handling
- Easier to implement reconnection

### Why NSSM Instead of Win32ServiceUtil?

- **NSSM** runs standard Python scripts
- No complex service lifecycle code
- Easier debugging (stdout/stderr logging)
- Better restart policies

---

## 🎓 Learning Resources

- [Windows Session Isolation](https://docs.microsoft.com/en-us/windows/win32/services/interactive-services)
- [Socket Programming in Python](https://docs.python.org/3/library/socket.html)
- [mss Screenshot Library](https://python-mss.readthedocs.io/)
- [NSSM Documentation](https://nssm.cc/usage)

---

## 📄 License

Proprietary - Skillers Zone LTD  
All rights reserved.

---

## 🤝 Support

For technical support or questions:
- **Email:** support@skillerszone.com
- **Documentation:** [BUILD_GUIDE.md](BUILD_GUIDE.md)
- **Logs:** `C:\ProgramData\EnterpriseMonitoring\logs\`

---

## ✅ Production Checklist

Before deploying to production:

- [ ] Build tested on clean Windows 10/11 VM
- [ ] Service starts automatically after reboot
- [ ] Agent starts on user login
- [ ] Screenshots being captured (1 fps)
- [ ] Clipboard events being logged
- [ ] App usage tracking works
- [ ] Database retention tested (30 days)
- [ ] Logs rotating correctly
- [ ] Installer tested (install + uninstall)
- [ ] Silent install/uninstall tested
- [ ] Encryption key backed up
- [ ] Documentation updated

---

**Version:** 2.0.0  
**Last Updated:** February 2026  
**Architecture:** Split-Brain IPC  

**🎉 Session 0 isolation problem = SOLVED!**

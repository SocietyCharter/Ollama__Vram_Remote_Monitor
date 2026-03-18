# Ollama Monitor — Setup Guide

A lightweight desktop widget that polls a remote Ollama server and displays GPU stats, loaded models, and server health. No installer. No dependencies beyond Python itself.

---

## Prerequisites

### Python 3.10+ for Windows
- Download from https://www.python.org/downloads/
- During setup, **check "Add Python to PATH"** — the launcher needs it
- No third-party packages required; the widget uses stdlib only (tkinter, urllib, subprocess, threading)

### Configuration
The widget reads its settings from environment variables or a config file — there are **no hardcoded values to edit in source code**.

**Option A — config.yml (recommended, requires PyYAML):**
```
pip install pyyaml
```
Copy `config.example.yml` to `config.yml` and fill in your values:
```yaml
host: 192.168.1.100      # ← your server's IP or hostname
ssh_user: yourname       # ← your SSH username
port: 11434              # ← Ollama port (default is fine)
```

**Option B — .env file / environment variables:**
Copy `.env.example` to `.env` and fill in your values:
```
OLLAMA_HOST=192.168.1.100
OLLAMA_SSH_USER=yourname
```
Load it before running (Linux/macOS: `export $(grep -v '^#' .env | xargs)`).

**Option C — config.ini (stdlib, no extra packages):**
Create `config.ini` next to `monitor.py`:
```ini
[ollama]
host = 192.168.1.100
ssh_user = yourname
```

If required values (`host`, `ssh_user`) are missing from all sources, the widget will display an error on startup explaining what to set.

### SSH Key Auth to the Ollama Server
- The widget SSHs into your configured server to fetch GPU stats via `nvidia-smi`
- **Recommended:** Set up passwordless SSH key auth so the widget runs silently
  ```
  # On Windows (PowerShell):
  ssh-keygen -t ed25519 -C "ollama-monitor"
  # Then copy your public key to the server:
  ssh-copy-id YOUR_SSH_USER@YOUR_SERVER_IP
  ```
- **If you skip this:** SSH will prompt for a password the first time a GPU poll runs. The prompt appears in a hidden subprocess — the GPU fields will show `N/A` until key auth is configured. HTTP metrics (version, models) still work without SSH.
- **First connection note:** The launcher uses `StrictHostKeyChecking=no`. On the very first connection, SSH will auto-accept and store the server's host key. Subsequent connections verify against the stored key.

---

## File Setup

You need exactly **two files** in the **same folder**:

```
C:\Users\YourName\OllamaMonitor\
    monitor.py
    launch.bat
```

Any folder works. They just have to be together — `launch.bat` finds `monitor.py` by its own location, not by the desktop shortcut's location.

---

## Creating the Desktop Shortcut

1. Open File Explorer and navigate to the folder containing both files
2. **Right-click** `launch.bat`
3. Select **Send To → Desktop (create shortcut)**
4. (Optional) Rename the shortcut on your desktop to "Ollama Monitor"

> **Why a shortcut instead of moving the file?**
> The `.bat` locates `monitor.py` relative to itself. If you move the `.bat` without `monitor.py`, it won't work. The shortcut keeps both files in their folder while giving you a desktop launch point.

---

## Launching

Double-click the desktop shortcut. The monitor window appears immediately (no terminal window).

- The widget is **always-on-top** by default
- It polls every 5 seconds
- Close the window normally to exit

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Python not found" popup | Install Python 3.10+ and check "Add to PATH" |
| GPU fields show `N/A` | Set up SSH key auth; verify `ssh YOUR_SSH_USER@YOUR_SERVER_IP nvidia-smi` works from PowerShell |
| "monitor.py not found" popup | Both files must be in the same folder |
| Window doesn't appear | Check Task Manager for `pythonw.exe`; may be blocked by antivirus |
| Wrong server | Edit `host` / `ssh_user` / `port` in `config.yml` (or set `OLLAMA_HOST` / `OLLAMA_SSH_USER` env vars) |

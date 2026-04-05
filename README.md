# Ollama Monitor
<img width="981" height="418" alt="image" src="https://github.com/user-attachments/assets/5446749a-6d28-47e9-8929-e8e22af1b3aa" />



A lightweight, always-on-top desktop widget that polls a remote [Ollama](https://ollama.com) server and displays real-time GPU stats, loaded models, and server health — no browser required.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue) ![Platform: Windows](https://img.shields.io/badge/platform-Windows-lightgrey) ![stdlib only](https://img.shields.io/badge/deps-stdlib%20only-green) ![Tested with Ollama 0.20.2](https://img.shields.io/badge/ollama-0.20.2%20tested-brightgreen)

---

## What It Does

- **Server health** — shows online/offline status and Ollama version
- **GPU stats** — name, temperature, utilisation, and VRAM usage bar (via SSH + `nvidia-smi`)
- **Active models** — which models are currently loaded in VRAM
- **Installed models** — scrollable list of every model on the server
- Polls every 5 seconds (configurable); colour-coded indicators for heat/load

---

## Getting Started

### Requirements

| Requirement | Notes |
|---|---|
| Python 3.10+ | Must be on PATH. Download from [python.org](https://www.python.org/downloads/) |
| tkinter | Included with standard Python for Windows |
| SSH access to your Ollama server | Passwordless key auth strongly recommended |
| `nvidia-smi` on the server | Required for GPU stats; HTTP metrics work without it |
| Ollama server | Tested with **0.20.2**; any 0.x release with `/api/tags`, `/api/ps`, and `/api/version` endpoints should work |
| PyYAML *(optional)* | Only needed if you use `config.yml` for configuration |

### Installation

1. **Download** (or clone) this repository to any local folder:
   ```
   git clone https://github.com/YOUR_USERNAME/ollama-monitor.git
   cd ollama-monitor
   ```

2. **Install the optional YAML dependency** if you plan to use `config.yml`:
   ```
   pip install pyyaml
   ```
   Skip this step if you prefer environment variables or `config.ini`.

3. **Configure** the widget — see the [Configuration](#configuration) section below.

4. **Set up SSH key auth** to your Ollama server so GPU polling runs silently:
   ```bash
   # Generate a key (skip if you already have one)
   ssh-keygen -t ed25519 -C "ollama-monitor"

   # Copy your public key to the server
   ssh-copy-id YOUR_SSH_USER@YOUR_SERVER_IP
   ```
   GPU fields will show `N/A` if SSH auth fails. HTTP metrics (version, models) still work without it.

5. **Run** the monitor:
   - **Windows (no terminal window):** double-click `launch.bat`
   - **Any OS (with terminal):** `python monitor.py`

### Creating a Desktop Shortcut (Windows)

1. Right-click `launch.bat` → **Send To → Desktop (create shortcut)**
2. Optionally rename the shortcut to "Ollama Monitor"
3. Double-click the shortcut to launch — no terminal window appears

> **Important:** `monitor.py` and `launch.bat` must remain in the **same folder**. The launcher locates the script relative to itself, not the shortcut.

---

## Configuration

The widget requires two values at startup: the server's IP/hostname and your SSH username. There are no hardcoded values to edit in source code.

### Option A — `config.yml` *(recommended)*

```bash
# Requires PyYAML:
pip install pyyaml

# Copy the example and fill in your values:
cp config.example.yml config.yml
```

```yaml
# config.yml
host: 192.168.1.100      # IP address or hostname of your Ollama server
ssh_user: yourname       # SSH username on that server
port: 11434              # Ollama HTTP port (default: 11434)
poll_interval: 5         # Seconds between polls (default: 5)
http_timeout: 4          # HTTP request timeout in seconds (default: 4)
ssh_timeout: 5           # SSH subprocess timeout in seconds (default: 5)
```

### Option B — Environment Variables

Set variables in your shell or load them from a `.env` file:

```bash
# Copy the example:
cp .env.example .env
# Edit .env with your values, then load it:

# Linux / macOS:
export $(grep -v '^#' .env | xargs)

# Windows PowerShell:
Get-Content .env | ForEach-Object { $name,$val=$_.split('=',2); [System.Environment]::SetEnvironmentVariable($name,$val) }
```

| Variable | Required | Default | Description |
|---|---|---|---|
| `OLLAMA_HOST` | ✅ | — | Server IP or hostname |
| `OLLAMA_SSH_USER` | ✅ | — | SSH username |
| `OLLAMA_PORT` | ✗ | `11434` | Ollama HTTP port |
| `OLLAMA_POLL_INTERVAL` | ✗ | `5` | Seconds between polls |
| `OLLAMA_HTTP_TIMEOUT` | ✗ | `4` | HTTP request timeout (s) |
| `OLLAMA_SSH_TIMEOUT` | ✗ | `5` | SSH subprocess timeout (s) |

### Option C — `config.ini`

No extra packages needed — uses Python's built-in `configparser`:

```ini
; config.ini (place next to monitor.py)
[ollama]
host = 192.168.1.100
ssh_user = yourname
port = 11434
poll_interval = 5
```

### Priority Order

Environment variables override everything. Full priority chain:

```
Environment variables > config.yml > config.ini > built-in defaults
```

If `host` or `ssh_user` are missing from all sources, the widget exits immediately with an error message explaining what to set.

---

## Usage

### Basic Launch

```bash
# Run with terminal (any OS):
python monitor.py

# Run silently on Windows (no terminal window):
pythonw.exe monitor.py
# or just double-click launch.bat
```

### The Widget

Once running, the widget appears as a compact, always-on-top window:

```
● 192.168.1.100:11434  ONLINE          v0.6.2
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GPU
  Name    NVIDIA GeForce RTX 4090
  Temp    62°C
  Util    43%
  VRAM    12345 / 24576 MiB (50%)
  [████████████░░░░░░░░░░░░]

ACTIVE MODELS
  qwen3:30b

INSTALLED MODELS
  qwen3:30b
  qwen2.5-coder:32b
  llama3:8b
  ...

Last updated: 14:23:07
```

Colour indicators:
- **Green** — healthy (temp < 70°C, util < 60%, VRAM < 75%)
- **Yellow** — elevated (temp 70–84°C, util 60–89%, VRAM 75–89%)
- **Red** — critical / offline (temp ≥ 85°C, util ≥ 90%, VRAM ≥ 90%, or server down)

### Adjusting Poll Rate

Set `OLLAMA_POLL_INTERVAL` (seconds) in your config. The minimum effective value is `1`; the default is `5`.

```yaml
# config.yml
poll_interval: 2   # more frequent updates
```

### Pointing at a Different Server

Update `host` (and `ssh_user` if needed) in your config file, or change the environment variables, and restart the widget.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Python not found" popup | Install Python 3.10+ and check "Add to PATH" during setup |
| GPU fields show `N/A` | Set up SSH key auth; verify `ssh YOUR_SSH_USER@YOUR_SERVER_IP nvidia-smi` works from your shell |
| Widget won't start — missing config error | Set `OLLAMA_HOST` + `OLLAMA_SSH_USER` as env vars, or create `config.yml` from `config.example.yml` |
| "monitor.py not found" popup | Both `monitor.py` and `launch.bat` must be in the same folder |
| Window doesn't appear after double-click | Check Task Manager for `pythonw.exe`; may be blocked by antivirus |
| HTTP metrics missing but SSH works | Verify Ollama is running on the server and the port matches (`11434` by default) |

---

## File Structure

```
ollama-monitor/
├── monitor.py          # Main application
├── launch.bat          # Silent Windows launcher
├── config.example.yml  # Configuration template (YAML)
├── .env.example        # Configuration template (env vars)
├── SETUP.md            # Detailed setup guide (Windows focus)
└── README.md           # This file
```

> **Note:** `config.yml`, `.env`, and `config.ini` are intentionally excluded from version control. Never commit files containing your real server address or credentials.

---

## Contributing

Pull requests welcome. Keep stdlib-only for core functionality; optional dependencies (like PyYAML) must remain truly optional with graceful fallback.

---

## License

MIT

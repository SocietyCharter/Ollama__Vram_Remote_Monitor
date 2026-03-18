"""
monitor.py — Ollama Desktop Widget
Polls a remote Ollama server and displays GPU stats, loaded models, and server health.
Stdlib only (tkinter, urllib, subprocess, threading, json, datetime, os).

Configuration is loaded from environment variables, with fallback to a local
config.yml file (if PyYAML is installed) or config.ini (via configparser).
See config.example.yml for all available settings.
"""

import json
import os
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from urllib.request import urlopen
from urllib.error import URLError

# ─── CONFIG — loaded from environment variables ────────────────────────────────
# Set these in your shell, a .env file (loaded by your launcher), or edit
# config.example.yml and copy it to config.yml.
#
# Required:
#   OLLAMA_HOST      — IP or hostname of your Ollama server
#   OLLAMA_SSH_USER  — SSH username on that server
#
# Optional (defaults shown):
#   OLLAMA_PORT          — Ollama HTTP port          (default: 11434)
#   OLLAMA_POLL_INTERVAL — seconds between polls     (default: 5)
#   OLLAMA_HTTP_TIMEOUT  — HTTP request timeout (s)  (default: 4)
#   OLLAMA_SSH_TIMEOUT   — SSH subprocess timeout (s) (default: 5)
# ──────────────────────────────────────────────────────────────────────────────

def _load_config():
    """
    Load configuration with the following priority (highest first):
      1. Environment variables
      2. config.yml (if present and PyYAML installed)
      3. config.ini (if present, via configparser)
      4. Hardcoded defaults for non-sensitive settings only
    """
    cfg = {}

    # --- Try config.ini (stdlib, always available) ---
    try:
        import configparser
        ini = configparser.ConfigParser()
        ini_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        if ini.read(ini_path):
            section = 'ollama' if 'ollama' in ini else (ini.sections()[0] if ini.sections() else None)
            if section:
                for key in ('host', 'ssh_user', 'port', 'poll_interval', 'http_timeout', 'ssh_timeout'):
                    val = ini[section].get(key)
                    if val:
                        cfg[key.upper()] = val
    except Exception:
        pass

    # --- Try config.yml (optional dependency: PyYAML) ---
    try:
        import yaml
        yml_path = os.path.join(os.path.dirname(__file__), 'config.yml')
        if os.path.exists(yml_path):
            with open(yml_path) as f:
                data = yaml.safe_load(f) or {}
            mapping = {
                'host': 'HOST', 'ssh_user': 'SSH_USER', 'port': 'PORT',
                'poll_interval': 'POLL_INTERVAL', 'http_timeout': 'HTTP_TIMEOUT',
                'ssh_timeout': 'SSH_TIMEOUT',
            }
            for yml_key, cfg_key in mapping.items():
                if yml_key in data:
                    cfg[cfg_key] = str(data[yml_key])
    except Exception:
        pass

    # --- Environment variables override everything ---
    env_map = {
        'OLLAMA_HOST':          'HOST',
        'OLLAMA_SSH_USER':      'SSH_USER',
        'OLLAMA_PORT':          'PORT',
        'OLLAMA_POLL_INTERVAL': 'POLL_INTERVAL',
        'OLLAMA_HTTP_TIMEOUT':  'HTTP_TIMEOUT',
        'OLLAMA_SSH_TIMEOUT':   'SSH_TIMEOUT',
    }
    for env_key, cfg_key in env_map.items():
        val = os.environ.get(env_key)
        if val:
            cfg[cfg_key] = val

    # --- Validate required fields ---
    missing = [k for k in ('HOST', 'SSH_USER') if not cfg.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing required configuration: {', '.join(missing)}\n"
            "Set OLLAMA_HOST and OLLAMA_SSH_USER as environment variables,\n"
            "or copy config.example.yml to config.yml and fill in your values."
        )

    return cfg


_cfg = _load_config()

HOST          = _cfg['HOST']
SSH_USER      = _cfg['SSH_USER']
PORT          = int(_cfg.get('PORT', 11434))
POLL_INTERVAL = int(_cfg.get('POLL_INTERVAL', 5))
HTTP_TIMEOUT  = int(_cfg.get('HTTP_TIMEOUT', 4))
SSH_TIMEOUT   = int(_cfg.get('SSH_TIMEOUT', 5))

# ─── COLORS ───────────────────────────────────────────────────────────────────
BG      = '#1e1e1e'
ACCENT  = '#00ff88'
RED     = '#ff4444'
YELLOW  = '#ffcc00'
WHITE   = '#ffffff'
DIMGRAY = '#888888'
PANEL   = '#2a2a2a'
BAR_BG  = '#3a3a3a'
# ──────────────────────────────────────────────────────────────────────────────


def fetch_ollama(path):
    """GET http://HOST:PORT/<path>, return parsed JSON or None."""
    url = f'http://{HOST}:{PORT}{path}'
    try:
        with urlopen(url, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None


def fetch_gpu_stats():
    """
    SSH into the model server, run nvidia-smi, parse CSV.
    Returns dict with keys: name, temp, util, mem_used, mem_total
    or all 'N/A' on failure.
    """
    na = {'name': 'N/A', 'temp': 'N/A', 'util': 'N/A',
          'mem_used': 'N/A', 'mem_total': 'N/A'}
    cmd = [
        'ssh',
        '-o', 'BatchMode=yes',
        '-o', 'ConnectTimeout=4',
        '-o', 'StrictHostKeyChecking=no',
        '-o', 'LogLevel=ERROR',
        f'{SSH_USER}@{HOST}',
        'nvidia-smi',
        '--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total',
        '--format=csv,noheader,nounits',
    ]
    # CREATE_NO_WINDOW suppresses the cmd flash on Windows; harmless on other OS
    _no_window = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=SSH_TIMEOUT,
            creationflags=_no_window,
        )
        if result.returncode != 0:
            return na
        line = result.stdout.strip().splitlines()[0]
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 5:
            return na
        return {
            'name':     parts[0],
            'temp':     parts[1],
            'util':     parts[2],
            'mem_used': parts[3],
            'mem_total': parts[4],
        }
    except Exception:
        return na


class OllamaMonitor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Ollama Monitor')
        self.configure(bg=BG)
        self.resizable(False, False)
        self.attributes('-topmost', True)

        # Shared state — written by poller thread, read by UI thread
        self._lock = threading.Lock()
        self._state = {
            'online':       False,
            'version':      '',
            'gpu':          {'name': '—', 'temp': '—', 'util': '—',
                             'mem_used': '—', 'mem_total': '—'},
            'active':       [],
            'installed':    [],
            'last_updated': '—',
        }

        self._dirty = threading.Event()   # poller sets this when new data is ready
        self._build_ui()
        self._start_poller()
        self.after(200, self._check_dirty)

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        W = 320
        PAD = 10

        # ── Header ────────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG, pady=6)
        hdr.pack(fill='x', padx=PAD)

        self._dot = tk.Label(hdr, text='●', font=('Consolas', 14), bg=BG, fg=RED)
        self._dot.pack(side='left')

        self._hdr_label = tk.Label(
            hdr, text=f'  {HOST}:{PORT}  OFFLINE',
            font=('Consolas', 11, 'bold'), bg=BG, fg=WHITE
        )
        self._hdr_label.pack(side='left')

        self._ver_label = tk.Label(
            hdr, text='', font=('Consolas', 9), bg=BG, fg=DIMGRAY
        )
        self._ver_label.pack(side='right')

        tk.Frame(self, bg=DIMGRAY, height=1).pack(fill='x', padx=PAD)

        # ── GPU Panel ─────────────────────────────────────────────────────────
        self._gpu_panel = self._section('GPU', W, PAD)

        self._gpu_name = self._kv_row(self._gpu_panel, 'Name', '—')
        self._gpu_temp = self._kv_row(self._gpu_panel, 'Temp', '—')
        self._gpu_util = self._kv_row(self._gpu_panel, 'Util', '—')

        vram_frame = tk.Frame(self._gpu_panel, bg=PANEL)
        vram_frame.pack(fill='x', pady=(2, 0))
        tk.Label(vram_frame, text='VRAM', width=8, anchor='w',
                 font=('Consolas', 9), bg=PANEL, fg=DIMGRAY).pack(side='left')
        self._vram_text = tk.Label(
            vram_frame, text='—', font=('Consolas', 9), bg=PANEL, fg=WHITE
        )
        self._vram_text.pack(side='right')

        bar_outer = tk.Frame(self._gpu_panel, bg=BAR_BG, height=8)
        bar_outer.pack(fill='x', pady=(3, 4))
        bar_outer.pack_propagate(False)
        self._vram_bar = tk.Frame(bar_outer, bg=ACCENT, height=8, width=0)
        self._vram_bar.place(x=0, y=0, relheight=1.0, width=0)
        self._bar_outer = bar_outer

        tk.Frame(self, bg=DIMGRAY, height=1).pack(fill='x', padx=PAD)

        # ── Active Models Panel ───────────────────────────────────────────────
        active_panel = self._section('Active Models', W, PAD)
        self._active_list = tk.Label(
            active_panel, text='None', font=('Consolas', 9),
            bg=PANEL, fg=WHITE, anchor='w', justify='left', wraplength=W - 40
        )
        self._active_list.pack(fill='x', pady=(0, 4))

        tk.Frame(self, bg=DIMGRAY, height=1).pack(fill='x', padx=PAD)

        # ── Installed Models Panel ────────────────────────────────────────────
        inst_panel = self._section('Installed Models', W, PAD)
        self._inst_count = tk.Label(
            inst_panel, text='0 models', font=('Consolas', 9),
            bg=PANEL, fg=DIMGRAY, anchor='w'
        )
        self._inst_count.pack(fill='x')

        scroll_frame = tk.Frame(inst_panel, bg=PANEL)
        scroll_frame.pack(fill='x', pady=(2, 4))

        scrollbar = tk.Scrollbar(scroll_frame, orient='vertical', width=10)
        self._inst_listbox = tk.Listbox(
            scroll_frame, font=('Consolas', 9), bg='#252525', fg=WHITE,
            selectbackground=ACCENT, selectforeground=BG,
            yscrollcommand=scrollbar.set, height=6,
            borderwidth=0, highlightthickness=0,
            activestyle='none',
        )
        scrollbar.config(command=self._inst_listbox.yview)
        self._inst_listbox.pack(side='left', fill='x', expand=True)
        scrollbar.pack(side='right', fill='y')

        tk.Frame(self, bg=DIMGRAY, height=1).pack(fill='x', padx=PAD)

        # ── Footer ────────────────────────────────────────────────────────────
        ftr = tk.Frame(self, bg=BG, pady=4)
        ftr.pack(fill='x', padx=PAD)
        self._footer = tk.Label(
            ftr, text='Last updated: —', font=('Consolas', 8),
            bg=BG, fg=DIMGRAY
        )
        self._footer.pack(side='left')

    def _section(self, title, width, pad):
        """Create a titled panel section, return inner frame."""
        outer = tk.Frame(self, bg=BG, pady=4)
        outer.pack(fill='x', padx=pad)
        tk.Label(outer, text=title.upper(), font=('Consolas', 8, 'bold'),
                 bg=BG, fg=ACCENT).pack(anchor='w')
        inner = tk.Frame(outer, bg=PANEL, padx=6, pady=4)
        inner.pack(fill='x')
        return inner

    def _kv_row(self, parent, key, value):
        """Single key: value row inside a panel. Returns value Label."""
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill='x', pady=1)
        tk.Label(row, text=key, width=8, anchor='w',
                 font=('Consolas', 9), bg=PANEL, fg=DIMGRAY).pack(side='left')
        val = tk.Label(row, text=value, font=('Consolas', 9), bg=PANEL, fg=WHITE,
                       anchor='w')
        val.pack(side='left', fill='x', expand=True)
        return val

    # ── Polling Thread ─────────────────────────────────────────────────────────

    def _start_poller(self):
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()

    def _check_dirty(self):
        """Called on the tkinter main thread every 500ms. Redraws only when poller has new data."""
        if self._dirty.is_set():
            self._dirty.clear()
            self._refresh_ui()
        self.after(500, self._check_dirty)

    def _poll_loop(self):
        while True:
            version_data = fetch_ollama('/api/version')
            online = version_data is not None
            version_str = version_data.get('version', '') if online else ''

            ps_data = fetch_ollama('/api/ps') if online else None
            tags_data = fetch_ollama('/api/tags') if online else None

            # Active models: models currently loaded in VRAM
            active = []
            if ps_data and 'models' in ps_data:
                active = [m.get('name', '?') for m in ps_data['models']]

            # Installed models: all models known to the server
            installed = []
            if tags_data and 'models' in tags_data:
                installed = [m.get('name', '?') for m in tags_data['models']]

            gpu = fetch_gpu_stats()
            ts = datetime.now().strftime('%H:%M:%S')

            with self._lock:
                self._state.update({
                    'online':       online,
                    'version':      version_str,
                    'gpu':          gpu,
                    'active':       active,
                    'installed':    installed,
                    'last_updated': ts,
                })
            self._dirty.set()   # signal UI thread to redraw

            # Sleep in small increments so the thread exits quickly on destroy
            import time
            for _ in range(POLL_INTERVAL * 10):
                time.sleep(0.1)

    # ── UI Refresh ────────────────────────────────────────────────────────────

    def _refresh_ui(self):
        with self._lock:
            s = dict(self._state)
            gpu = dict(self._state['gpu'])
            active = list(self._state['active'])
            installed = list(self._state['installed'])

        # Header
        if s['online']:
            self._dot.config(fg=ACCENT)
            ver = f" v{s['version']}" if s['version'] else ''
            self._hdr_label.config(
                text=f"  {HOST}:{PORT}  ONLINE", fg=ACCENT
            )
            self._ver_label.config(text=ver)
        else:
            self._dot.config(fg=RED)
            self._hdr_label.config(
                text=f"  {HOST}:{PORT}  OFFLINE", fg=RED
            )
            self._ver_label.config(text='')

        # GPU
        self._gpu_name.config(text=gpu['name'])

        temp = gpu['temp']
        temp_color = WHITE
        if temp not in ('N/A', '—', ''):
            try:
                t = int(temp)
                temp_color = ACCENT if t < 70 else (YELLOW if t < 85 else RED)
            except ValueError:
                pass
        self._gpu_temp.config(text=f"{temp}°C" if temp not in ('N/A', '—') else temp,
                              fg=temp_color)

        util = gpu['util']
        util_color = WHITE
        if util not in ('N/A', '—', ''):
            try:
                u = int(util)
                util_color = ACCENT if u < 60 else (YELLOW if u < 90 else RED)
            except ValueError:
                pass
        self._gpu_util.config(
            text=f"{util}%" if util not in ('N/A', '—') else util,
            fg=util_color
        )

        # VRAM bar
        mem_used  = gpu['mem_used']
        mem_total = gpu['mem_total']
        if mem_used not in ('N/A', '—') and mem_total not in ('N/A', '—'):
            try:
                used_mib  = int(mem_used)
                total_mib = int(mem_total)
                ratio = used_mib / total_mib if total_mib > 0 else 0
                self._vram_text.config(
                    text=f"{used_mib} / {total_mib} MiB ({ratio*100:.0f}%)"
                )
                bar_color = ACCENT if ratio < 0.75 else (YELLOW if ratio < 0.90 else RED)
                self._vram_bar.config(bg=bar_color)
                # Update bar width after geometry is settled
                self.update_idletasks()
                outer_w = self._bar_outer.winfo_width()
                bar_w = max(1, int(outer_w * ratio))
                self._vram_bar.place_configure(width=bar_w)
            except (ValueError, ZeroDivisionError):
                self._vram_text.config(text='N/A')
                self._vram_bar.place_configure(width=0)
        else:
            self._vram_text.config(text='N/A')
            self._vram_bar.place_configure(width=0)

        # Active Models
        if active:
            self._active_list.config(text='\n'.join(active), fg=WHITE)
        else:
            self._active_list.config(text='None', fg=DIMGRAY)

        # Installed Models
        self._inst_count.config(
            text=f"{len(installed)} model{'s' if len(installed) != 1 else ''}"
        )
        self._inst_listbox.delete(0, 'end')
        for name in installed:
            self._inst_listbox.insert('end', name)

        # Footer
        self._footer.config(text=f"Last updated: {s['last_updated']}")


if __name__ == '__main__':
    app = OllamaMonitor()
    app.mainloop()

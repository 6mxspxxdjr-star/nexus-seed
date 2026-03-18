#!/usr/bin/env python3
"""
nexus_ui.py — Animated ASCII startup and chat interface for Nexus.

Single-file, minimal dependencies (stdlib + optional PIL for image input).
All animation parameters, colors, and behaviors are stored in an editable
JSON config file that Nexus agents can modify at runtime.

Usage:
    python nexus_ui.py                            # Built-in logo
    python nexus_ui.py logo.png                   # Convert image to ASCII
    python nexus_ui.py --config path/to/conf.json # Custom config
    python nexus_ui.py --no-chat                  # Animation only, no chat
    python nexus_ui.py --duration 5               # Shorten animation
"""

import argparse
import json
import math
import os
import shutil
import signal
import sys
import textwrap
import time
import urllib.request
import urllib.error
from pathlib import Path

# Fix stdout encoding for Unicode block characters on all platforms
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Enable ANSI escape codes on Windows
if sys.platform == "win32":
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION — self-modifiable by Nexus agents via JSON
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "ascii_ramp": " .·:;+=*o0#@",
    "animation": {
        "boot_duration": 3.0,
        "materialize_duration": 2.0,
        "pulse_cycles": 2,
        "pulse_period": 2.8,
        "pulse_amplitude": 0.22,
        "flow_speed": 3.0,
        "heartbeat_speed": 2.5,
        "settle_duration": 1.0,
        "fps": 18,
        "materialize_style": "radial",
    },
    "colors": {
        "warm":   [255, 170, 50],
        "cool":   [60, 210, 190],
        "glow":   [140, 255, 200],
        "text":   [185, 190, 200],
        "dim":    [50, 55, 65],
        "prompt": [90, 210, 170],
        "user":   [220, 220, 230],
        "bg":     [15, 16, 20],
    },
    "prompt_text": "Nexus. Ask me anything.",
    "boot_steps": [
        "Initializing core systems",
        "Loading semantic memory",
        "Connecting agents",
        "Calibrating simulation engine",
        "Syncing knowledge graph",
        "Ready",
    ],
    "logo_width_ratio": 0.55,
    "chat": {
        "model": "qwen2.5:14b",
        "ollama_url": "http://localhost:11434",
        "system_prompt": (
            "You are Nexus, an autonomous intelligence system. "
            "Be concise, direct, and helpful. "
            "You help users explore strategies, run simulations, and generate value."
        ),
        "typewriter_delay": 0.015,
    },
    "cached_logo": None,
}


class Config:
    """JSON-backed config that agents can edit between runs."""

    def __init__(self, path=None):
        nexus_home = Path(os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
        self.path = Path(path) if path else nexus_home / "configs" / "ui_config.json"
        self.d = json.loads(json.dumps(DEFAULT_CONFIG))
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path) as f:
                    self._merge(self.d, json.load(f))
            except (json.JSONDecodeError, IOError):
                pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self.d, f, indent=2)

    def _merge(self, base, over):
        for k, v in over.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                self._merge(base[k], v)
            else:
                base[k] = v

    def __getitem__(self, key):
        return self.d[key]

    def get(self, *a, **kw):
        return self.d.get(*a, **kw)


# ═══════════════════════════════════════════════════════════════════════════
# TERMINAL — capabilities, cursor control, color rendering
# ═══════════════════════════════════════════════════════════════════════════

class Terminal:
    def __init__(self):
        self.w, self.h = self._size()
        self.has_color = self._detect_color()
        if hasattr(signal, "SIGWINCH"):
            signal.signal(signal.SIGWINCH, lambda *_: self._on_resize())

    def _size(self):
        try:
            c, r = shutil.get_terminal_size((80, 24))
            return c, r
        except Exception:
            return 80, 24

    def _detect_color(self):
        if os.environ.get("NO_COLOR"):
            return False
        if os.environ.get("COLORTERM") in ("truecolor", "24bit"):
            return True
        if os.environ.get("WT_SESSION"):
            return True
        term = os.environ.get("TERM", "")
        return term != "dumb" and bool(term)

    def _on_resize(self):
        self.w, self.h = self._size()

    def fg(self, r, g, b):
        return f"\033[38;2;{r};{g};{b}m" if self.has_color else ""

    def reset(self):
        return "\033[0m" if self.has_color else ""

    def bold(self):
        return "\033[1m" if self.has_color else ""

    def hide_cursor(self):
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

    def show_cursor(self):
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()

    def clear(self):
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()

    def write_frame(self, text):
        sys.stdout.write("\033[H" + text)
        sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════════
# LOGO — image conversion + procedural fallback
# ═══════════════════════════════════════════════════════════════════════════

def image_to_logo(image_path, target_w, ramp):
    """Convert an image to char grid + color grid using PIL.

    Handles dark-background logos by auto-cropping to the bright content
    region and stretching contrast so the logo fills the ASCII ramp.
    """
    if not HAS_PIL:
        return None
    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception:
        return None

    # Composite alpha onto dark background
    bg = Image.new("RGBA", img.size, (15, 16, 20, 255))
    bg.paste(img, mask=img.split()[3])
    img_rgb = bg.convert("RGB")

    # ── Auto-crop: find bounding box of bright content ──
    gray_full = img_rgb.convert("L")
    pixels = list(gray_full.getdata())
    w_orig, h_orig = gray_full.size
    threshold = 30  # pixels brighter than this are "content"

    top, bottom, left, right = h_orig, 0, w_orig, 0
    for y in range(h_orig):
        for x in range(w_orig):
            if pixels[y * w_orig + x] > threshold:
                top = min(top, y)
                bottom = max(bottom, y)
                left = min(left, x)
                right = max(right, x)

    if bottom <= top or right <= left:
        return None  # No bright content found

    # Add small padding (5% of crop size)
    pad_x = max(4, int((right - left) * 0.05))
    pad_y = max(2, int((bottom - top) * 0.05))
    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(w_orig, right + pad_x)
    bottom = min(h_orig, bottom + pad_y)

    img_crop = img_rgb.crop((left, top, right, bottom))

    # ── Resize to target width, accounting for char aspect ratio ──
    aspect = img_crop.width / img_crop.height
    target_h = max(8, int(target_w / aspect / 2.1))

    img_sm = img_crop.resize((target_w, target_h), Image.LANCZOS)
    gray = img_sm.convert("L")

    # ── Contrast stretch + gamma: push midtones brighter ──
    g_pixels = list(gray.getdata())
    sorted_px = sorted(p for p in g_pixels if p > 10)  # ignore pure black
    if len(sorted_px) < 10:
        sorted_px = sorted(g_pixels)
    # Use 5th and 95th percentile for aggressive stretch
    lo = sorted_px[max(0, int(len(sorted_px) * 0.05))]
    hi = sorted_px[min(len(sorted_px) - 1, int(len(sorted_px) * 0.95))]
    span = max(1, hi - lo)
    gamma = 0.65  # < 1.0 brightens midtones, making more of the glow visible

    chars = []
    colors = []
    ramp_n = len(ramp)

    for y in range(target_h):
        crow, ccol = [], []
        for x in range(target_w):
            raw_br = gray.getpixel((x, y))
            r, g, b = img_sm.getpixel((x, y))

            # Stretch contrast then apply gamma curve
            stretched = max(0.0, min(1.0, (raw_br - lo) / span))
            br = int(pow(stretched, gamma) * 255)

            # Boost color saturation for visible pixels
            if br > 20:
                max_c = max(r, g, b, 1)
                boost = min(2.8, 240 / max_c)
                r = min(255, int(r * boost))
                g = min(255, int(g * boost))
                b = min(255, int(b * boost))
            else:
                # Dim background pixels get no color
                r, g, b = 0, 0, 0

            idx = min(int(br / 256 * ramp_n), ramp_n - 1)
            crow.append(ramp[idx])
            ccol.append([r, g, b])
        chars.append("".join(crow))
        colors.append(ccol)

    return {"chars": chars, "colors": colors, "w": target_w, "h": target_h}


def generate_n_shape(w, h):
    """Procedurally generate the N letter shape."""
    stroke = max(2, w // 8)
    lines = []
    for y in range(h):
        t = y / max(1, h - 1)
        d_start = int(stroke + t * (w - 3 * stroke))
        d_end = min(w, d_start + stroke)
        row = []
        for x in range(w):
            if x < stroke or x >= w - stroke or d_start <= x < d_end:
                row.append("\u2588")  # █
            else:
                row.append(" ")
        lines.append("".join(row))
    return lines


def builtin_logo(term_w, cfg):
    """Generate the built-in N logo with computed colors."""
    logo_w = max(16, int(term_w * cfg["logo_width_ratio"]))
    logo_h = max(10, int(logo_w * 0.65))
    n_lines = generate_n_shape(logo_w, logo_h)

    # NEXUS text, spaced
    nexus_text = "N   E   X   U   S"
    text_pad = max(0, (logo_w - len(nexus_text)) // 2)
    nexus_line = " " * text_pad + nexus_text
    nexus_line = nexus_line.ljust(logo_w)

    chars = n_lines + [" " * logo_w, nexus_line, " " * logo_w]
    total_h = len(chars)

    warm = cfg["colors"]["warm"]
    cool = cfg["colors"]["cool"]
    text_c = cfg["colors"]["text"]

    colors = []
    for y, row in enumerate(chars):
        crow = []
        for x, ch in enumerate(row):
            if y >= logo_h:
                crow.append(text_c if ch.strip() else [0, 0, 0])
            elif ch.strip():
                zone = x / max(1, logo_w - 1)
                crow.append([
                    int(warm[0] + (cool[0] - warm[0]) * zone),
                    int(warm[1] + (cool[1] - warm[1]) * zone),
                    int(warm[2] + (cool[2] - warm[2]) * zone),
                ])
            else:
                crow.append([0, 0, 0])
        colors.append(crow)

    return {"chars": chars, "colors": colors, "w": logo_w, "h": total_h}


# ═══════════════════════════════════════════════════════════════════════════
# ANIMATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════

def smoothstep(edge0, edge1, x):
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0 + 1e-9)))
    return t * t * (3.0 - 2.0 * t)


def clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


class Animator:
    """Renders animated frames of the ASCII logo."""

    def __init__(self, logo, cfg, term):
        self.logo = logo
        self.cfg = cfg
        self.term = term
        self.chars = logo["chars"]
        self.colors = logo["colors"]
        self.lw = logo["w"]
        self.lh = logo["h"]
        self.cx = self.lw / 2
        self.cy = self.lh / 2
        # max distance from center (for normalizing)
        self.max_dist = math.sqrt((self.lw / 2) ** 2 + (self.lh) ** 2)
        self.anim = cfg["animation"]

    def _offsets(self):
        ox = max(0, (self.term.w - self.lw) // 2)
        oy = max(0, (self.term.h - self.lh) // 2 - 2)
        return ox, oy

    def render(self, t, settled=False):
        """Build a complete frame string for time t."""
        ox, oy = self._offsets()
        pad = " " * ox
        mat_dur = self.anim["materialize_duration"]
        pulse_per = self.anim["pulse_period"]
        pulse_amp = self.anim["pulse_amplitude"]
        flow_spd = self.anim["flow_speed"]
        hb_spd = self.anim["heartbeat_speed"]
        rst = self.term.reset()

        buf = ["\n"] * oy

        for y in range(self.lh):
            row_str = pad
            row_chars = self.chars[y]
            row_colors = self.colors[y]

            for x in range(self.lw):
                ch = row_chars[x] if isinstance(row_chars, list) else row_chars[x]
                cr, cg, cb = row_colors[x]

                if ch == " " or (cr == 0 and cg == 0 and cb == 0 and ch == " "):
                    row_str += " "
                    continue

                # Normalized position
                zone = x / max(1, self.lw - 1)  # 0=warm left, 1=cool right
                dx = (x - self.cx) / (self.lw * 0.5)
                dy = (y - self.cy) / (self.lh * 0.5)
                dist = math.sqrt(dx * dx * 0.6 + dy * dy) / 1.8

                # ── Materialize ──
                if t < mat_dur and not settled:
                    reveal = smoothstep(0.0, 1.0, t / mat_dur * 1.6 - dist)
                    if reveal < 0.02:
                        row_str += " "
                        continue
                    alpha = reveal
                else:
                    alpha = 1.0

                if settled:
                    brightness = 1.0
                else:
                    # ── Organic heartbeat (left side) ──
                    hb = (math.sin(t * hb_spd) ** 6) * 0.18 * (1.0 - zone)

                    # ── Circuit flow (right side) ──
                    flow = math.sin(y * 0.45 - t * flow_spd) * 0.14 * zone

                    # ── Global radial pulse ──
                    gp = math.sin(t * 2.0 * math.pi / pulse_per - dist * 4.0) * pulse_amp

                    brightness = alpha * (1.0 + hb + flow + gp * 0.6)

                brightness = clamp(brightness, 0.08, 1.6)
                fr = min(255, int(cr * brightness))
                fg = min(255, int(cg * brightness))
                fb = min(255, int(cb * brightness))
                row_str += self.term.fg(fr, fg, fb) + ch

            row_str += rst
            buf.append(row_str)

        # Pad remaining terminal rows
        remaining = self.term.h - oy - self.lh
        buf.extend([""] * max(0, remaining))

        return "\n".join(buf[: self.term.h])


# ═══════════════════════════════════════════════════════════════════════════
# BOOT PROGRESS — shown during startup
# ═══════════════════════════════════════════════════════════════════════════

def run_boot_sequence(term, cfg, duration):
    """Animated progress bar with status messages."""
    steps = cfg["boot_steps"]
    n = len(steps)
    bar_w = min(40, term.w - 10)
    cx = (term.w - bar_w - 8) // 2
    cy = term.h // 2

    warm = cfg["colors"]["warm"]
    cool = cfg["colors"]["cool"]
    dim = cfg["colors"]["dim"]
    rst = term.reset()

    start = time.monotonic()
    while True:
        elapsed = time.monotonic() - start
        if elapsed >= duration:
            break

        progress = min(1.0, elapsed / duration)
        step_idx = min(int(progress * n), n - 1)
        step_text = steps[step_idx]

        filled = int(progress * bar_w)
        pct = int(progress * 100)

        # Gradient color for progress bar
        pr = int(warm[0] + (cool[0] - warm[0]) * progress)
        pg = int(warm[1] + (cool[1] - warm[1]) * progress)
        pb = int(warm[2] + (cool[2] - warm[2]) * progress)

        bar = (
            term.fg(pr, pg, pb)
            + "\u2588" * filled
            + term.fg(*dim)
            + "\u2591" * (bar_w - filled)
            + rst
        )

        # Build frame
        lines = [""] * term.h
        if cy - 2 >= 0:
            title = "N E X U S"
            tp = (term.w - len(title)) // 2
            lines[cy - 2] = " " * tp + term.fg(*cfg["colors"]["text"]) + term.bold() + title + rst

        lines[cy] = " " * cx + f"[{bar}] {term.fg(*cfg['colors']['text'])}{pct:3d}%{rst}"

        sp = (term.w - len(step_text) - 4) // 2
        # Pulsing dots
        dots = "." * (1 + int(elapsed * 3) % 3)
        lines[cy + 2] = " " * sp + term.fg(*dim) + step_text + dots + rst

        term.write_frame("\n".join(lines[: term.h]))
        time.sleep(1.0 / cfg["animation"]["fps"])


# ═══════════════════════════════════════════════════════════════════════════
# PROMPT TYPEWRITER — types out the prompt text
# ═══════════════════════════════════════════════════════════════════════════

def typewriter(term, text, row, color, delay=0.04):
    """Type out text one character at a time at the given row."""
    col = (term.w - len(text)) // 2
    sys.stdout.write(f"\033[{row};{col}H")
    sys.stdout.write(term.fg(*color) + term.bold())
    for ch in text:
        sys.stdout.write(ch)
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write(term.reset())
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════════════════
# CHAT LOOP — interactive prompt with Ollama integration
# ═══════════════════════════════════════════════════════════════════════════

def ollama_available(url):
    try:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3):
            return True
    except Exception:
        return False


def ollama_pick_model(url, preferred):
    """Auto-detect the best available model from Ollama.

    Tries the preferred model first, then falls through a priority list.
    Returns the model name string, or None if nothing is available.
    """
    try:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
        installed = [m["name"] for m in data.get("models", [])]
    except Exception:
        return None

    if not installed:
        return None

    # If the configured model is installed, use it
    if preferred in installed:
        return preferred

    # Priority: prefer larger general-purpose qwen, then coder, then anything
    priority = [
        "qwen2.5:14b", "qwen2.5:7b", "qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5:0.5b",
        "qwen2.5-coder:7b", "qwen2.5-coder:3b",
        "llama3.1:8b", "llama3:8b", "mistral:7b", "gemma2:9b",
    ]
    for name in priority:
        if name in installed:
            return name

    # Last resort: just use the first installed model
    return installed[0]


def ollama_generate(prompt_text, cfg, model_override=None):
    """Send a prompt to Ollama and stream the response."""
    chat = cfg["chat"]
    model = model_override or chat["model"]
    url = f"{chat['ollama_url']}/api/generate"
    payload = json.dumps({
        "model": model,
        "system": chat["system_prompt"],
        "prompt": prompt_text,
        "stream": True,
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for raw_line in resp:
                if raw_line.strip():
                    try:
                        data = json.loads(raw_line)
                        token = data.get("response", "")
                        if token:
                            yield token
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        yield f"\n[Error: {e}]"


def chat_loop(term, cfg):
    """Interactive chat with Nexus."""
    rst = term.reset()
    prompt_c = cfg["colors"]["prompt"]
    user_c = cfg["colors"]["user"]
    dim_c = cfg["colors"]["dim"]
    chat_cfg = cfg["chat"]
    ollama_url = chat_cfg["ollama_url"]
    has_ollama = ollama_available(ollama_url)

    # Auto-detect the best available model
    model = None
    if has_ollama:
        model = ollama_pick_model(ollama_url, chat_cfg["model"])
        if model:
            sys.stdout.write(
                term.fg(*dim_c) + f"  [{model}]" + rst + "\n"
            )
        else:
            has_ollama = False

    if not has_ollama:
        sys.stdout.write(
            "\n"
            + term.fg(*dim_c)
            + "  [Ollama offline \u2014 start with: ollama serve]"
            + rst
            + "\n"
        )

    # Conversation history (last N turns for context)
    history = []

    while True:
        try:
            sys.stdout.write("\n" + term.fg(*prompt_c) + "  \u25b8 " + rst)
            sys.stdout.flush()
            user_input = input().strip()
        except (EOFError, KeyboardInterrupt):
            sys.stdout.write("\n" + term.fg(*dim_c) + "  [session ended]" + rst + "\n")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "/quit", "/exit"):
            sys.stdout.write(term.fg(*dim_c) + "  [goodbye]\n" + rst)
            break

        history.append(user_input)

        sys.stdout.write(term.fg(*cfg["colors"]["cool"]) + "  \u25c2 " + rst)
        sys.stdout.flush()

        if has_ollama:
            # Build context from recent history
            context = "\n".join(f"User: {h}" for h in history[-5:])
            full_prompt = f"{context}\nUser: {user_input}\nNexus:"

            for token in ollama_generate(full_prompt, cfg, model_override=model):
                sys.stdout.write(term.fg(*user_c) + token + rst)
                sys.stdout.flush()
                time.sleep(chat_cfg["typewriter_delay"])
            sys.stdout.write("\n")
        else:
            sys.stdout.write(
                term.fg(*dim_c)
                + "Nexus core is offline. Start Ollama to enable AI responses."
                + rst
                + "\n"
            )

        # Try to store in memory (best-effort)
        try:
            nexus_home = os.environ.get("NEXUS_HOME", str(Path.home() / "nexus"))
            venv_py = Path(nexus_home) / ".venv" / "bin" / "python"
            mem_script = Path(nexus_home) / "scripts" / "memory_system.py"
            if venv_py.exists() and mem_script.exists():
                import subprocess
                subprocess.Popen(
                    [str(venv_py), str(mem_script), "store", user_input,
                     "--type", "episodic", "--source", "chat", "--importance", "0.3"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — orchestrates the full startup sequence
# ═══════════════════════════════════════════════════════════════════════════

def run(image_path=None, config_path=None, no_chat=False, duration_override=None):
    cfg = Config(config_path)
    term = Terminal()

    # ── Resolve logo ──
    logo = None

    # 1. Check config cache
    if cfg["cached_logo"]:
        logo = cfg["cached_logo"]

    # 2. Try image conversion
    if logo is None and image_path:
        target_w = max(20, int(term.w * cfg["logo_width_ratio"]))
        logo = image_to_logo(image_path, target_w, cfg["ascii_ramp"])
        if logo:
            # Cache for future runs
            cfg.d["cached_logo"] = logo
            cfg.save()

    # 3. Fallback to built-in
    if logo is None:
        logo = builtin_logo(term.w, cfg.d)

    boot_dur = cfg["animation"]["boot_duration"]
    if duration_override is not None:
        boot_dur = duration_override

    term.hide_cursor()
    term.clear()

    try:
        # ── Boot progress bar ──
        run_boot_sequence(term, cfg.d, boot_dur)
        term.clear()

        # ── Prompt ──
        rst = term.reset()
        prompt_text = cfg["prompt_text"]
        cx = (term.w - len(prompt_text)) // 2
        cy = term.h // 2 - 1
        sys.stdout.write(f"\033[{cy};{cx}H")
        sys.stdout.write(term.fg(*cfg["colors"]["prompt"]) + term.bold())
        for ch in prompt_text:
            sys.stdout.write(ch)
            sys.stdout.flush()
            time.sleep(0.035)
        sys.stdout.write(rst)
        sys.stdout.flush()
        time.sleep(0.4)

    except KeyboardInterrupt:
        pass
    finally:
        term.show_cursor()

    if not no_chat:
        # Move cursor below prompt
        sys.stdout.write(f"\033[{term.h // 2 + 1};1H")
        sys.stdout.flush()
        chat_loop(term, cfg.d)

    # Save config (preserves any runtime changes)
    cfg.save()


def main():
    parser = argparse.ArgumentParser(description="Nexus animated UI")
    parser.add_argument("image", nargs="?", help="Path to logo image (PNG/JPG)")
    parser.add_argument("--config", "-c", help="Path to UI config JSON")
    parser.add_argument("--no-chat", action="store_true", help="Skip chat loop")
    parser.add_argument("--duration", "-d", type=float, help="Total animation duration override (seconds)")
    parser.add_argument("--save-config", action="store_true", help="Save default config and exit")
    args = parser.parse_args()

    if args.save_config:
        cfg = Config(args.config)
        cfg.save()
        print(f"Config saved to {cfg.path}")
        return

    try:
        run(
            image_path=args.image,
            config_path=args.config,
            no_chat=args.no_chat,
            duration_override=args.duration,
        )
    except KeyboardInterrupt:
        # Ensure cursor is restored
        sys.stdout.write("\033[?25h\033[0m\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

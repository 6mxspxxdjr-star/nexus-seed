#!/usr/bin/env python3
"""
nexus_dashboard.py — Visual companion dashboard for Nexus.

Opens a futuristic, dark-themed web UI at http://localhost:3800 with:
  - Interactive vis.js knowledge graph (left, 60%)
  - Tabbed status panels: System / Memory / Skills / RL (right, 40%)
  - Live activity feed (bottom)
  - Memory search with graph highlighting
  - Node click → detail panel with content + backlinks

Runs alongside the terminal UI; no conflict with nexus_api.py on port 3700.

Usage:
    python nexus_dashboard.py                  # Launch on :3800
    python nexus_dashboard.py --port 8080      # Custom port
    python nexus_dashboard.py --no-open        # Don't auto-open browser
"""

import argparse
import asyncio
import glob as _glob
import json
import logging
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

# ── Setup paths ──
NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
DASHBOARD_PORT = int(os.environ.get("NEXUS_DASHBOARD_PORT", 3800))
sys.path.insert(0, str(NEXUS_HOME / "scripts"))
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger("nexus.dashboard")

try:
    from nicegui import ui, app
except ImportError:
    print("\n  Nexus Dashboard requires NiceGUI.")
    print("  Install:  pip install nicegui\n")
    sys.exit(1)

try:
    from run_simulation import run_builtin_simulation, analyze_results
    _HAS_SIM = True
except Exception:
    _HAS_SIM = False


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE ACCESS — direct Python imports, API fallback
# ═══════════════════════════════════════════════════════════════════════════════

_router = None
_memory = None
_rl_proc = None


def get_router():
    global _router
    if _router is None:
        try:
            from model_router import ModelRouter
            _router = ModelRouter(str(NEXUS_HOME))
        except Exception as e:
            logger.warning(f"Router init failed: {e}")
    return _router


def get_memory():
    global _memory
    if _memory is None:
        try:
            from memory_system import MemorySystem
            _memory = MemorySystem(str(NEXUS_HOME))
        except Exception as e:
            logger.warning(f"Memory init failed: {e}")
    return _memory


def get_rl():
    global _rl_proc
    if _rl_proc is None:
        try:
            from rl_signals import RLSignalProcessor
            _rl_proc = RLSignalProcessor(str(NEXUS_HOME))
        except Exception as e:
            logger.warning(f"RL init failed: {e}")
    return _rl_proc


def check_ollama():
    """Check Ollama status and return (online, model_list)."""
    import urllib.request
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read())
            return True, [m["name"] for m in data.get("models", [])]
    except Exception:
        return False, []


# ═══════════════════════════════════════════════════════════════════════════════
# THEME — Futuristic dark palette
# ═══════════════════════════════════════════════════════════════════════════════

CATEGORY_COLORS = {
    "00_Core": "#00d4aa",
    "01_Conversations": "#4ecdc4",
    "02_Research": "#a78bfa",
    "03_Content": "#f472b6",
    "04_Simulations": "#fbbf24",
    "05_Decisions": "#ff6b35",
    "06_Archive": "#666680",
    "06_System": "#38bdf8",
    "memory-templates": "#4a4f60",
}

VIS_JS_CDN = "https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"

THEME_CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {
    --nx-bg:       #0a0a0f;
    --nx-card:     #12121a;
    --nx-border:   #1a1a2e;
    --nx-primary:  #00d4aa;
    --nx-secondary:#ff6b35;
    --nx-text:     #e0e0e0;
    --nx-dim:      #666680;
    --nx-glow:     rgba(0, 212, 170, 0.15);
}

body, .q-page {
    background: var(--nx-bg) !important;
    color: var(--nx-text) !important;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace !important;
}
.q-header  { background: var(--nx-bg) !important; }
.q-drawer  { background: var(--nx-bg) !important; }
.q-tab-panel { background: transparent !important; padding: 0 !important; }
.q-tab--active .q-tab__label { color: var(--nx-primary) !important; }
.q-tab__indicator { background: var(--nx-primary) !important; }
.q-tab { color: var(--nx-dim) !important; font-family: 'JetBrains Mono', monospace !important; font-size: 0.8rem !important; }
.q-tabs { border-bottom: 1px solid var(--nx-border) !important; }

.nx-card {
    background: var(--nx-card) !important;
    border: 1px solid var(--nx-border) !important;
    border-radius: 12px !important;
    transition: border-color 0.3s, box-shadow 0.3s;
}
.nx-card:hover {
    border-color: rgba(0, 212, 170, 0.3) !important;
    box-shadow: 0 0 20px var(--nx-glow) !important;
}

.nx-stat {
    font-size: 2rem;
    font-weight: 700;
    color: var(--nx-primary);
    line-height: 1;
}
.nx-label {
    color: var(--nx-dim);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    font-weight: 500;
    margin-top: 4px;
}
.nx-title {
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--nx-primary);
    margin-bottom: 12px;
}
.nx-code {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: var(--nx-primary);
}

.nx-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.65rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.nx-badge-on  { background: rgba(0,212,170,0.15); color: var(--nx-primary); border: 1px solid rgba(0,212,170,0.3); }
.nx-badge-off { background: rgba(255,107,53,0.15); color: var(--nx-secondary); border: 1px solid rgba(255,107,53,0.3); }
.nx-badge-tier{ background: rgba(0,212,170,0.1); color: var(--nx-primary); border: 1px solid rgba(0,212,170,0.2); }

.nx-graph-box {
    background: var(--nx-card);
    border: 1px solid var(--nx-border);
    border-radius: 12px;
    overflow: hidden;
}

.nx-search .q-field__control {
    background: var(--nx-card) !important;
    border: 1px solid var(--nx-border) !important;
    border-radius: 8px !important;
    color: var(--nx-text) !important;
}
.nx-search .q-field__control:focus-within {
    border-color: var(--nx-primary) !important;
    box-shadow: 0 0 0 2px var(--nx-glow) !important;
}
.nx-search .q-field__native { color: var(--nx-text) !important; }

.nx-gauge-bg {
    background: var(--nx-border);
    border-radius: 8px;
    height: 8px;
    overflow: hidden;
}
.nx-gauge-fill {
    height: 100%;
    border-radius: 8px;
    transition: width 0.8s ease;
}

.nx-feed-item {
    padding: 6px 12px;
    border-left: 2px solid var(--nx-border);
    margin-bottom: 2px;
    font-size: 0.75rem;
    transition: border-color 0.2s;
}
.nx-feed-item:hover { border-left-color: var(--nx-primary); }

.nx-skill-card {
    background: var(--nx-card);
    border: 1px solid var(--nx-border);
    border-radius: 8px;
    padding: 12px;
    transition: all 0.3s ease;
}
.nx-skill-card:hover {
    border-color: rgba(0, 212, 170, 0.4);
    box-shadow: 0 0 15px rgba(0, 212, 170, 0.08);
    transform: translateY(-1px);
}

.nx-detail {
    background: var(--nx-card);
    border: 1px solid var(--nx-border);
    border-radius: 8px;
    padding: 12px;
    font-size: 0.75rem;
    max-height: 180px;
    overflow-y: auto;
}

.nx-route-table { border-collapse: separate; border-spacing: 0; width: 100%; font-size: 0.75rem; }
.nx-route-table th {
    background: #181b24; color: var(--nx-dim);
    text-transform: uppercase; font-size: 0.65rem; letter-spacing: 0.08em;
    padding: 6px 10px; text-align: left; border-bottom: 1px solid var(--nx-border);
}
.nx-route-table td { padding: 5px 10px; border-bottom: 1px solid var(--nx-border); color: var(--nx-text); }
.nx-route-table tr:hover td { background: rgba(0,212,170,0.04); }

@keyframes pulse-glow { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
.nx-pulse { animation: pulse-glow 2s ease-in-out infinite; }

.nx-badge-risk-low { background: rgba(0,212,170,0.15); color: #00d4aa; border: 1px solid rgba(0,212,170,0.3); }
.nx-badge-risk-med { background: rgba(255,107,53,0.15); color: #ff6b35; border: 1px solid rgba(255,107,53,0.3); }
.nx-path-allowed  { border-left: 3px solid #00d4aa; padding: 3px 10px; margin: 2px 0; }
.nx-path-readonly { border-left: 3px solid #fbbf24; padding: 3px 10px; margin: 2px 0; }
.nx-path-denied   { border-left: 3px solid #ef4444; padding: 3px 10px; margin: 2px 0; }
.nx-sparkline     { stroke: #00d4aa; fill: none; stroke-width: 2; }

::-webkit-scrollbar       { width: 6px; }
::-webkit-scrollbar-track { background: var(--nx-bg); }
::-webkit-scrollbar-thumb { background: var(--nx-border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--nx-dim); }
"""


# ═══════════════════════════════════════════════════════════════════════════════
# DATA HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_graph():
    """Build vis.js-compatible graph from memory vault + wikilinks."""
    nodes, edges = [], []
    memory_dir = NEXUS_HOME / "memory"
    if not memory_dir.exists():
        return {"nodes": [], "edges": []}

    # Also load link_graph.json for additional edges
    link_graph = {}
    link_file = NEXUS_HOME / "memory" / ".system" / "link_graph.json"
    if link_file.exists():
        try:
            link_graph = json.loads(link_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    node_ids = set()
    for md_file in memory_dir.rglob("*.md"):
        if ".system" in str(md_file) or md_file.name.startswith("."):
            continue
        rel = str(md_file.relative_to(memory_dir)).replace("\\", "/")
        cat = md_file.parent.name if md_file.parent != memory_dir else "root"
        color = CATEGORY_COLORS.get(cat, "#4a4f60")
        size = max(8, min(30, md_file.stat().st_size // 200))

        nodes.append({
            "id": rel, "label": md_file.stem[:25],
            "color": color, "size": size, "category": cat,
            "title": f"{cat}/{md_file.name}",
        })
        node_ids.add(rel)

        try:
            content = md_file.read_text(errors="replace")
            for link in re.findall(r'\[\[([^\]]+)\]\]', content):
                edges.append({"from": rel, "to": link})
        except Exception:
            pass

    # Add edges from link_graph not already present
    seen_edges = {(e["from"], e["to"]) for e in edges}
    for source_id, data in link_graph.items():
        for target in data.get("links_to", []):
            if (source_id, target) not in seen_edges:
                edges.append({"from": source_id, "to": target})
                seen_edges.add((source_id, target))

    # Filter edges to valid nodes
    edges = [e for e in edges if e["from"] in node_ids and e["to"] in node_ids]
    return {"nodes": nodes, "edges": edges}


def fetch_status():
    """Gather system status from all subsystems."""
    result = {
        "ollama_online": False, "ollama_models": [],
        "anthropic": False, "openai": False,
        "memory_stats": None, "agents": [], "skills": [],
    }

    ollama_ok, models = check_ollama()
    result["ollama_online"] = ollama_ok
    result["ollama_models"] = models

    router = get_router()
    if router:
        avail = router.get_available_models()
        result["anthropic"] = avail.get("anthropic", False)
        result["openai"] = avail.get("openai", False)

    memory = get_memory()
    if memory:
        try:
            result["memory_stats"] = memory.stats()
        except Exception:
            pass

    agents_dir = NEXUS_HOME / "agents"
    if agents_dir.exists():
        for d in sorted(agents_dir.iterdir()):
            if d.is_dir():
                identity = ""
                f = d / "IDENTITY.md"
                if f.exists():
                    try:
                        identity = f.read_text(errors="replace")[:500]
                    except Exception:
                        pass
                result["agents"].append({
                    "name": d.name, "identity": identity,
                    "has_identity": f.exists(),
                })

    skills_dir = NEXUS_HOME / "skills"
    if skills_dir.exists():
        for d in sorted(skills_dir.iterdir()):
            if d.is_dir():
                desc = ""
                f = d / "SKILL.md"
                if f.exists():
                    try:
                        content = f.read_text(errors="replace")
                        for line in content.strip().split("\n"):
                            if line.strip() and not line.startswith("#") and not line.startswith("---"):
                                desc = line.strip()
                                break
                    except Exception:
                        pass
                result["skills"].append({
                    "name": d.name, "description": desc,
                    "executable": (d / "run").exists(),
                })

    return result


def fetch_routing():
    """Return routing table + tier definitions."""
    try:
        from model_router import ROUTING_TABLE, TIERS
        return {"table": ROUTING_TABLE, "tiers": TIERS}
    except Exception:
        return {"table": {}, "tiers": {}}


def fetch_key_status():
    """Get API key configuration status."""
    try:
        from setup_keys import load_keys, PROVIDERS
        keys = load_keys()
        result = {}
        for provider, info in PROVIDERS.items():
            key = keys.get(provider, "") or os.environ.get(info["env_var"], "")
            if key:
                masked = key[:8] + "..." + key[-4:] if len(key) > 12 else "***"
                result[provider] = {"configured": True, "masked": masked, "name": info["name"]}
            else:
                result[provider] = {"configured": False, "masked": "", "name": info["name"]}
        return result
    except Exception:
        return {}


def fetch_rl_metrics():
    """Get RL signal metrics."""
    proc = get_rl()
    if proc:
        try:
            return proc.compute_metrics(days=7)
        except Exception:
            pass
    return {
        "total_signals": 0, "agent_success_rate": 0.0,
        "user_satisfaction": 0.0, "correction_rate": 0.0,
        "avg_reward": 0.0, "by_agent": {}, "by_signal_type": {},
    }


def fetch_corrections():
    """Get recent correction pairs."""
    proc = get_rl()
    if proc:
        try:
            return proc.get_correction_pairs(days=7)
        except Exception:
            pass
    return []


def fetch_recent_signals(limit=10):
    """Get recent RL signals for activity feed."""
    proc = get_rl()
    if proc:
        try:
            signals = proc.read_signals(days=3)
            return sorted(signals, key=lambda s: s.get("timestamp", ""), reverse=True)[:limit]
        except Exception:
            pass
    return []


def fetch_openclaw_config():
    """Load OpenClaw orchestrator config."""
    cfg_path = NEXUS_HOME / "configs" / "openclaw.yaml"
    try:
        return yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def fetch_sandbox_policies():
    """Load NemoClaw sandbox policy files."""
    sandbox_dir = NEXUS_HOME / "configs" / "sandbox"
    result = {}
    for name in ("filesystem", "network", "process", "inference"):
        try:
            result[name] = yaml.safe_load(
                (sandbox_dir / f"{name}.yaml").read_text(encoding="utf-8")
            ) or {}
        except Exception:
            result[name] = {}
    return result


def fetch_optimization_log(limit=50):
    """Read the optimization log JSONL file."""
    log_path = NEXUS_HOME / "optimizer" / "optimization_log.jsonl"
    try:
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        entries = []
        for line in lines:
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
        return entries[-limit:]
    except Exception:
        return []


def fetch_optimizer_config():
    """Load autoresearch optimizer config."""
    cfg_path = NEXUS_HOME / "optimizer" / "config.yaml"
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        return data.get("autoresearch", {})
    except Exception:
        return {}


def fetch_consolidation_reports(limit=3):
    """Check consolidation log health."""
    pattern = str(NEXUS_HOME / "memory" / ".system" / "consolidation*.log")
    files = sorted(_glob.glob(pattern), key=os.path.getmtime, reverse=True)[:limit]
    if not files:
        return {"exists": False, "last_modified": None, "status": "unknown"}
    last = files[0]
    mtime = datetime.fromtimestamp(os.path.getmtime(last))
    age_hours = (datetime.now() - mtime).total_seconds() / 3600
    return {
        "exists": True,
        "last_modified": mtime.strftime("%Y-%m-%d %H:%M"),
        "status": "healthy" if age_hours < 48 else "stale",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# VIS.JS GRAPH BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def graph_javascript(graph_data):
    """Return the vis.js init script for the knowledge graph."""
    nodes_json = json.dumps(graph_data.get("nodes", []))
    edges_json = json.dumps(graph_data.get("edges", []))

    return f"""
    (function() {{
        var container = document.getElementById('nexus-graph');
        if (!container || typeof vis === 'undefined') {{ return; }}

        var rawNodes = {nodes_json};
        var rawEdges = {edges_json};

        var nodes = new vis.DataSet(rawNodes.map(function(n) {{
            return {{
                id: n.id, label: n.label, title: n.title || n.id,
                size: n.size || 12, category: n.category || '',
                color: {{
                    background: n.color, border: n.color,
                    highlight: {{ background: '#00d4aa', border: '#00d4aa' }},
                    hover: {{ background: n.color, border: '#00d4aa' }}
                }},
                font: {{ color: '#e0e0e0', size: 10, face: 'JetBrains Mono, monospace' }},
                borderWidth: 1,
                shadow: {{ enabled: true, color: n.color + '30', size: 8, x: 0, y: 0 }}
            }};
        }}));

        var edges = new vis.DataSet(rawEdges.map(function(e) {{
            return {{
                from: e.from, to: e.to,
                color: {{ color: '#1a1a2e', highlight: '#00d4aa', hover: '#00d4aa' }},
                width: 1,
                smooth: {{ type: 'continuous' }},
                arrows: {{ to: {{ enabled: true, scaleFactor: 0.4 }} }}
            }};
        }}));

        var network = new vis.Network(container, {{ nodes: nodes, edges: edges }}, {{
            physics: {{
                solver: 'barnesHut',
                barnesHut: {{
                    gravitationalConstant: -3000,
                    centralGravity: 0.3,
                    springLength: 150,
                    springConstant: 0.04,
                    damping: 0.3,
                    avoidOverlap: 0.5
                }},
                stabilization: {{ iterations: 150, fit: true }}
            }},
            interaction: {{
                hover: true, tooltipDelay: 200,
                hideEdgesOnDrag: true,
                zoomView: true, dragView: true
            }},
            nodes: {{ shape: 'dot' }}
        }});

        // Store original state for search reset
        var origColors = {{}};
        var origSizes = {{}};
        nodes.forEach(function(n) {{
            origColors[n.id] = n.color;
            origSizes[n.id] = n.size;
        }});

        // Node click → Python bridge
        network.on('click', function(params) {{
            if (params.nodes.length > 0) {{
                var nid = params.nodes[0];
                var n = nodes.get(nid);
                emitEvent('graph_node_click', {{
                    id: nid, label: n.label, category: n.category || ''
                }});
            }}
        }});

        // Search highlight function
        window.nxHighlight = function(query) {{
            if (!query) {{
                nodes.forEach(function(n) {{
                    nodes.update({{id: n.id, color: origColors[n.id], size: origSizes[n.id]}});
                }});
                return;
            }}
            var q = query.toLowerCase();
            nodes.forEach(function(n) {{
                var match = n.label.toLowerCase().includes(q) ||
                            (n.category && n.category.toLowerCase().includes(q));
                if (match) {{
                    nodes.update({{id: n.id, color: {{background:'#00d4aa',border:'#00d4aa',highlight:{{background:'#00d4aa',border:'#00d4aa'}},hover:{{background:'#00d4aa',border:'#00d4aa'}}}}, size: Math.max(origSizes[n.id] || 12, 22)}});
                }} else {{
                    nodes.update({{id: n.id, color: {{background:'#1a1a2e',border:'#1a1a2e',highlight:{{background:'#666680',border:'#666680'}},hover:{{background:'#666680',border:'#666680'}}}}, size: 5}});
                }}
            }});
        }};

        // Stop physics after stabilization
        network.once('stabilizationIterationsDone', function() {{
            network.setOptions({{ physics: {{ enabled: false }} }});
        }});
    }})();
    """


# ═══════════════════════════════════════════════════════════════════════════════
# PANEL BUILDERS
# ═══════════════════════════════════════════════════════════════════════════════

def build_header(status):
    """Top header bar: logo, title, status dots, model count."""
    with ui.header().classes("items-center justify-between px-6 py-2").style(
        "height:52px;background:linear-gradient(180deg,#0d0d14 0%,#0a0a0f 100%) !important;"
        "border-bottom:1px solid #1a1a2e !important"
    ):
        with ui.row().classes("items-center gap-4"):
            ui.html(
                '<span style="font-size:1.4rem;font-weight:800;'
                'background:linear-gradient(135deg,#00d4aa,#4ecdc4);'
                '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
                'background-clip:text">N</span>'
            )
            ui.label("NEXUS DASHBOARD").style(
                "font-size:0.85rem;font-weight:600;letter-spacing:0.15em;color:#e0e0e0"
            )

        with ui.row().classes("items-center gap-5"):
            # Ollama status
            ollama_ok = status["ollama_online"]
            dot_cls = "nx-pulse" if ollama_ok else ""
            dot_bg = "#00d4aa" if ollama_ok else "#ff6b35"
            dot_glow = "0 0 8px rgba(0,212,170,0.4)" if ollama_ok else "none"
            n_models = len(status["ollama_models"])
            ui.html(
                f'<div style="display:flex;align-items:center;gap:6px">'
                f'<div class="{dot_cls}" style="width:8px;height:8px;border-radius:50%;'
                f'background:{dot_bg};box-shadow:{dot_glow}"></div>'
                f'<span style="color:#666680;font-size:0.75rem">'
                f'Ollama {"online" if ollama_ok else "offline"}'
                f'{f" ({n_models})" if n_models else ""}</span></div>'
            )
            # Cloud status
            if status["anthropic"]:
                ui.html(
                    '<div style="display:flex;align-items:center;gap:6px">'
                    '<div class="nx-pulse" style="width:8px;height:8px;border-radius:50%;'
                    'background:#00d4aa;box-shadow:0 0 8px rgba(0,212,170,0.4)"></div>'
                    '<span style="color:#666680;font-size:0.75rem">Anthropic</span></div>'
                )


def build_graph_panel(status):
    """Left panel: vis.js knowledge graph + search bar + node detail."""
    graph = fetch_graph()
    n_nodes = len(graph.get("nodes", []))
    n_edges = len(graph.get("edges", []))

    with ui.column().classes("gap-2 w-full h-full"):
        # Search bar + stats
        with ui.row().classes("w-full items-center gap-2"):
            graph_search = ui.input(placeholder="Search graph...").classes(
                "nx-search flex-grow"
            ).props("dense outlined dark")
            ui.label(f"{n_nodes} nodes \u00b7 {n_edges} edges").style(
                "font-size:0.65rem;color:#666680;white-space:nowrap"
            )

        # Graph container
        if n_nodes > 0:
            ui.html(
                '<div id="nexus-graph" style="width:100%;height:520px"></div>'
            ).classes("nx-graph-box")

            # Load vis.js and init graph after DOM ready
            ui.run_javascript(graph_javascript(graph), timeout=10)
        else:
            with ui.card().classes("nx-card p-8 w-full").style("min-height:520px"):
                ui.label("No memory nodes yet.").style("color:#666680")
                ui.label("Store memories to populate the knowledge graph.").style(
                    "color:#666680;font-size:0.8rem"
                )

        # Legend
        legend_items = {
            "Core": "#00d4aa", "Conversations": "#4ecdc4", "Research": "#a78bfa",
            "Content": "#f472b6", "Simulations": "#fbbf24", "Decisions": "#ff6b35",
            "Archive": "#666680", "System": "#38bdf8",
        }
        with ui.row().classes("gap-3 flex-wrap"):
            for name, color in legend_items.items():
                ui.html(
                    f'<div style="display:flex;align-items:center;gap:4px">'
                    f'<div style="width:8px;height:8px;border-radius:50%;background:{color}"></div>'
                    f'<span style="color:#666680;font-size:0.6rem">{name}</span></div>'
                )

        # Node detail panel (filled by JS click events)
        detail_box = ui.column().classes("w-full")

        def on_node_click(e):
            detail_box.clear()
            node_id = e.args.get("id", "")
            label = e.args.get("label", "")
            category = e.args.get("category", "")
            with detail_box:
                with ui.element("div").classes("nx-detail"):
                    ui.html(
                        f'<span style="color:#00d4aa;font-weight:600">{label}</span>'
                        f'<span style="color:#666680;margin-left:8px;font-size:0.65rem">{category}</span>'
                    )
                    # Read file content
                    file_path = NEXUS_HOME / "memory" / node_id
                    if file_path.exists():
                        try:
                            raw = file_path.read_text(encoding="utf-8", errors="replace")[:600]
                            # Escape HTML
                            raw = raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                            ui.html(
                                f'<pre style="color:#e0e0e0;font-size:0.7rem;'
                                f'white-space:pre-wrap;margin-top:8px;line-height:1.4">{raw}</pre>'
                            )
                        except Exception:
                            pass
                    # Show backlinks
                    memory = get_memory()
                    if memory:
                        try:
                            linked = memory.get_linked(node_id)
                            if linked:
                                names = ", ".join(l.get("id", "?")[:30] for l in linked[:5])
                                ui.html(
                                    f'<div style="margin-top:8px;color:#00d4aa;font-size:0.65rem">'
                                    f'Linked ({len(linked)}): {names}</div>'
                                )
                        except Exception:
                            pass

        ui.on("graph_node_click", on_node_click)

        # Graph search → highlight
        def on_graph_search(e):
            q = e.value if hasattr(e, "value") else str(e)
            # Escape single quotes for JS
            q_safe = q.replace("'", "\\'").replace("\\", "\\\\")
            ui.run_javascript(f"if(window.nxHighlight) window.nxHighlight('{q_safe}');")

        graph_search.on("update:model-value", on_graph_search)


def build_system_tab(status):
    """System tab: Ollama models, API keys, router tiers."""
    with ui.column().classes("gap-3 p-3 w-full").style("overflow-y:auto;max-height:calc(100vh - 200px)"):
        # Ollama models
        with ui.card().classes("nx-card p-4"):
            ui.label("Ollama Models").classes("nx-title")
            if status["ollama_online"] and status["ollama_models"]:
                for m in sorted(status["ollama_models"]):
                    ui.html(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:3px 0">'
                        f'<div class="nx-pulse" style="width:6px;height:6px;border-radius:50%;background:#00d4aa"></div>'
                        f'<span style="color:#e0e0e0;font-size:0.8rem">{m}</span></div>'
                    )
            elif status["ollama_online"]:
                ui.label("Running, no models installed").style("color:#666680;font-size:0.8rem")
            else:
                ui.html(
                    '<div style="display:flex;align-items:center;gap:8px">'
                    '<div style="width:6px;height:6px;border-radius:50%;background:#ff6b35"></div>'
                    '<span style="color:#ff6b35;font-size:0.8rem">Offline \u2014 ollama serve</span></div>'
                )

        # API Keys
        with ui.card().classes("nx-card p-4"):
            ui.label("API Keys").classes("nx-title")
            keys = fetch_key_status()
            if keys:
                for provider, info in keys.items():
                    configured = info.get("configured", False)
                    name = info.get("name", provider)
                    masked = info.get("masked", "")
                    dot_bg = "#00d4aa" if configured else "#ff6b35"
                    ui.html(
                        f'<div style="display:flex;align-items:center;justify-content:space-between;padding:3px 0">'
                        f'<div style="display:flex;align-items:center;gap:8px">'
                        f'<div style="width:6px;height:6px;border-radius:50%;background:{dot_bg}"></div>'
                        f'<span style="color:#e0e0e0;font-size:0.8rem">{name}</span></div>'
                        f'<span style="color:#666680;font-size:0.7rem">{masked if configured else "not set"}</span></div>'
                    )
            else:
                ui.label("Key info unavailable").style("color:#666680;font-size:0.8rem")

        # Router tiers
        routing = fetch_routing()
        tiers = routing.get("tiers", {})
        if tiers:
            with ui.card().classes("nx-card p-4"):
                ui.label("Model Router Tiers").classes("nx-title")
                for tier_name, tier_def in tiers.items():
                    provider = tier_def.get("provider", "?")
                    model = tier_def.get("model", "?")
                    ui.html(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:2px 0">'
                        f'<span class="nx-badge nx-badge-tier">{tier_name}</span>'
                        f'<span style="color:#666680;font-size:0.7rem">{provider}/{model}</span></div>'
                    )

            # Routing table
            table = routing.get("table", {})
            if table:
                with ui.card().classes("nx-card p-4"):
                    ui.label("Routing Matrix").classes("nx-title")
                    levels = ["low", "medium", "high", "critical"]
                    html = '<table class="nx-route-table"><tr><th>Task</th>'
                    for lv in levels:
                        html += f"<th>{lv[:3].title()}</th>"
                    html += "</tr>"
                    for task_type, mapping in table.items():
                        html += f'<tr><td style="color:#00d4aa">{task_type}</td>'
                        for lv in levels:
                            tier = mapping.get(lv, "\u2014")
                            html += f'<td><span class="nx-badge nx-badge-tier">{tier}</span></td>'
                        html += "</tr>"
                    html += "</table>"
                    ui.html(html)

        # ── Consolidation Status (enhancement) ──
        with ui.card().classes("nx-card p-4"):
            ui.label("Consolidation Status").classes("nx-title")
            consol = fetch_consolidation_reports()
            if consol.get("exists"):
                status_str = consol["status"]
                color = "#00d4aa" if status_str == "healthy" else "#ff6b35"
                badge_cls = "nx-badge-on" if status_str == "healthy" else "nx-badge-off"
                ui.html(
                    f'<div style="display:flex;align-items:center;gap:8px">'
                    f'<span class="nx-badge {badge_cls}">{status_str}</span>'
                    f'<span style="color:#666680;font-size:0.7rem">'
                    f'Last run: {consol["last_modified"]}</span></div>'
                )
            else:
                ui.label("No consolidation logs found").style("color:#666680;font-size:0.8rem")


def build_memory_tab():
    """Memory tab: stats, vault structure, search."""
    memory = get_memory()
    stats = {}
    if memory:
        try:
            stats = memory.stats()
        except Exception:
            pass

    with ui.column().classes("gap-3 p-3 w-full").style("overflow-y:auto;max-height:calc(100vh - 200px)"):
        # Stat cards
        with ui.row().classes("gap-2 w-full"):
            for val, lbl in [
                (stats.get("total_markdown_files", 0), "Files"),
                (stats.get("total_vectors", 0), "Vectors"),
                (stats.get("total_links", 0), "Links"),
            ]:
                with ui.card().classes("nx-card p-3").style("flex:1"):
                    ui.html(f'<div class="nx-stat" style="font-size:1.5rem">{val}</div>')
                    ui.html(f'<div class="nx-label">{lbl}</div>')

        # Vault structure
        subdirs = stats.get("subdirectories", {})
        if subdirs:
            with ui.card().classes("nx-card p-4"):
                ui.label("Vault Structure").classes("nx-title")
                for name, count in sorted(subdirs.items()):
                    color = CATEGORY_COLORS.get(name, "#666680")
                    ui.html(
                        f'<div style="display:flex;align-items:center;justify-content:space-between;padding:2px 0">'
                        f'<div style="display:flex;align-items:center;gap:6px">'
                        f'<div style="width:8px;height:8px;border-radius:2px;background:{color}"></div>'
                        f'<span style="color:#e0e0e0;font-size:0.75rem">{name}</span></div>'
                        f'<span style="color:#666680;font-size:0.75rem">{count}</span></div>'
                    )

        # Search
        with ui.card().classes("nx-card p-4"):
            ui.label("Search Memories").classes("nx-title")
            results_box = ui.column().classes("w-full gap-1")
            search_input = ui.input(placeholder="Search...").classes(
                "nx-search w-full"
            ).props("dense outlined dark")

            async def do_search(e):
                q = e.value if hasattr(e, "value") else str(e)
                results_box.clear()
                if not q or len(q) < 2:
                    return

                mem = get_memory()
                if not mem:
                    with results_box:
                        ui.label("Memory system unavailable").style("color:#ff6b35;font-size:0.8rem")
                    return

                try:
                    results = mem.search_hybrid(q, top_k=8)
                except Exception:
                    try:
                        results = mem.search(q, top_k=8)
                    except Exception:
                        results = []

                type_colors = {
                    "episodic": "#00d4aa", "semantic": "#4ecdc4",
                    "procedural": "#a78bfa", "strategic": "#ff6b35",
                }

                with results_box:
                    if not results:
                        ui.label("No results").style("color:#666680;font-size:0.75rem")
                        return
                    for r in results:
                        preview = (r.get("content", ""))[:120]
                        mtype = r.get("type", "?")
                        score = r.get("hybrid_score", r.get("similarity_score", 0))
                        tc = type_colors.get(mtype, "#666680")
                        ui.html(
                            f'<div style="padding:5px 8px;border-left:2px solid {tc};margin-top:3px">'
                            f'<span style="color:{tc};font-size:0.7rem;font-weight:600">{mtype}</span>'
                            f'<span style="color:#666680;margin-left:6px;font-size:0.65rem">{score:.3f}</span>'
                            f'<div style="color:#e0e0e0;font-size:0.7rem;margin-top:2px;line-height:1.3">'
                            f'{preview}</div></div>'
                        )

                # Also highlight in graph
                q_safe = q.replace("'", "\\'").replace("\\", "\\\\")
                ui.run_javascript(f"if(window.nxHighlight) window.nxHighlight('{q_safe}');")

            search_input.on("update:model-value", do_search)


def build_skills_tab(status):
    """Skills tab: skill cards grid + agent identity previews + risk badges."""
    skills = status.get("skills", [])
    agents = status.get("agents", [])

    # Load openclaw config for risk/guardian metadata
    oc = fetch_openclaw_config()
    skills_cfg = oc.get("skills", {})
    agents_cfg = oc.get("agents", {})

    skill_icons = {
        "search-memory": "\U0001f50d", "store-memory": "\U0001f4be",
        "ask-questions": "\u2753", "create-agent": "\U0001f916",
        "run-simulation": "\U0001f4ca", "guardian-review": "\U0001f6e1",
        "trading-simulator": "\U0001f4c8", "lead-generator": "\U0001f3af",
        "content-creator": "\u270d",
    }
    agent_icons = {
        "strategist": "\U0001f3af", "guardian": "\U0001f6e1",
        "worker": "\u2699", "evolution": "\U0001f9ec",
    }

    with ui.column().classes("gap-3 p-3 w-full").style("overflow-y:auto;max-height:calc(100vh - 200px)"):
        # Skills grid
        ui.label(f"Skills ({len(skills)})").classes("nx-title")
        if skills:
            with ui.element("div").style(
                "display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:6px"
            ):
                for skill in skills:
                    icon = skill_icons.get(skill["name"], "\u26a1")
                    scfg = skills_cfg.get(skill["name"], {})
                    risk = scfg.get("risk", "")
                    needs_guardian = scfg.get("requires_guardian", False)
                    with ui.element("div").classes("nx-skill-card"):
                        dot_bg = "#00d4aa" if skill["executable"] else "#666680"
                        risk_html = ""
                        if risk:
                            badge_cls = "nx-badge-risk-low" if risk == "low" else "nx-badge-risk-med"
                            risk_html = f'<span class="nx-badge {badge_cls}" style="font-size:0.55rem;margin-left:4px">{risk}</span>'
                        guardian_html = ""
                        if needs_guardian:
                            guardian_html = '<span style="color:#ff6b35;margin-left:2px;font-size:0.75rem">&#x1f6e1;</span>'
                        ui.html(
                            f'<div style="display:flex;align-items:center;gap:6px">'
                            f'<span style="font-size:1rem">{icon}</span>'
                            f'<span style="font-size:0.75rem;font-weight:600;color:#e0e0e0">'
                            f'{skill["name"]}</span>'
                            f'{risk_html}{guardian_html}'
                            f'<div style="width:5px;height:5px;border-radius:50%;background:{dot_bg};margin-left:auto"></div>'
                            f'</div>'
                        )
                        if skill["description"]:
                            desc = skill["description"][:80]
                            ui.html(
                                f'<div style="color:#666680;font-size:0.65rem;margin-top:4px;line-height:1.3">'
                                f'{desc}</div>'
                            )
        else:
            ui.label("No skills found").style("color:#666680;font-size:0.8rem")

        # Agent-Skill Map
        if agents_cfg:
            all_skills = sorted({s for a in agents_cfg.values() for s in a.get("skills", [])})
            if all_skills:
                with ui.card().classes("nx-card p-4"):
                    ui.label("Agent-Skill Map").classes("nx-title")
                    html = '<table class="nx-route-table"><tr><th>Agent</th>'
                    for s in all_skills:
                        html += f'<th style="font-size:0.55rem">{s.split("-")[-1][:6]}</th>'
                    html += '</tr>'
                    for aname, acfg in agents_cfg.items():
                        agent_skills = set(acfg.get("skills", []))
                        html += f'<tr><td style="color:#00d4aa">{aname}</td>'
                        for s in all_skills:
                            if s in agent_skills:
                                html += '<td style="text-align:center;color:#00d4aa">&#x2713;</td>'
                            else:
                                html += '<td style="text-align:center;color:#1a1a2e">&#x2014;</td>'
                        html += '</tr>'
                    html += '</table>'
                    ui.html(html)

        # Agents
        ui.label(f"Agents ({len(agents)})").classes("nx-title").style("margin-top:12px")
        if agents:
            for agent in agents:
                icon = agent_icons.get(agent["name"], "\U0001f916")
                with ui.card().classes("nx-card p-3"):
                    dot_bg = "#00d4aa" if agent.get("has_identity") else "#ff6b35"
                    ui.html(
                        f'<div style="display:flex;align-items:center;gap:8px">'
                        f'<span style="font-size:1.2rem">{icon}</span>'
                        f'<span style="font-size:0.8rem;font-weight:600;color:#e0e0e0">'
                        f'{agent["name"].upper()}</span>'
                        f'<div style="width:5px;height:5px;border-radius:50%;background:{dot_bg};margin-left:auto"></div>'
                        f'</div>'
                    )
                    identity = agent.get("identity", "")
                    if identity:
                        lines = [
                            l.strip() for l in identity.split("\n")
                            if l.strip() and not l.startswith("#") and not l.startswith("---")
                        ][:4]
                        preview = "\n".join(lines)[:250]
                        # Escape HTML
                        preview = preview.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                        ui.html(
                            f'<pre style="color:#666680;font-size:0.65rem;white-space:pre-wrap;'
                            f'margin-top:6px;line-height:1.3">{preview}</pre>'
                        )


def build_rl_tab():
    """RL tab: success rate gauges, signal metrics, correction pairs."""
    metrics = fetch_rl_metrics()

    with ui.column().classes("gap-3 p-3 w-full").style("overflow-y:auto;max-height:calc(100vh - 200px)"):
        # Stat cards
        total = metrics.get("total_signals", 0)
        success = metrics.get("agent_success_rate", 0)
        avg_rwd = metrics.get("avg_reward", 0)

        with ui.row().classes("gap-2 w-full"):
            with ui.card().classes("nx-card p-3").style("flex:1"):
                ui.html(f'<div class="nx-stat" style="font-size:1.5rem">{total}</div>')
                ui.html('<div class="nx-label">Signals</div>')
            with ui.card().classes("nx-card p-3").style("flex:1"):
                ui.html(f'<div class="nx-stat" style="font-size:1.5rem">{success*100:.0f}%</div>')
                ui.html('<div class="nx-label">Success</div>')
            with ui.card().classes("nx-card p-3").style("flex:1"):
                ui.html(f'<div class="nx-stat" style="font-size:1.5rem">{avg_rwd:.2f}</div>')
                ui.html('<div class="nx-label">Avg Reward</div>')

        # Success gauge
        with ui.card().classes("nx-card p-4"):
            pct = success * 100
            color = "#00d4aa" if pct >= 70 else ("#ff6b35" if pct >= 40 else "#ef4444")
            ui.html(
                f'<div style="font-size:0.75rem;color:#666680;margin-bottom:6px">Agent Success Rate</div>'
                f'<div class="nx-gauge-bg">'
                f'<div class="nx-gauge-fill" style="width:{pct}%;background:{color}"></div></div>'
            )

        # User satisfaction gauge
        sat = metrics.get("user_satisfaction", 0) * 100
        with ui.card().classes("nx-card p-4"):
            sat_color = "#00d4aa" if sat >= 70 else ("#ff6b35" if sat >= 40 else "#ef4444")
            ui.html(
                f'<div style="font-size:0.75rem;color:#666680;margin-bottom:6px">User Satisfaction</div>'
                f'<div class="nx-gauge-bg">'
                f'<div class="nx-gauge-fill" style="width:{sat}%;background:{sat_color}"></div></div>'
            )

        # By agent
        by_agent = metrics.get("by_agent", {})
        if by_agent:
            with ui.card().classes("nx-card p-4"):
                ui.label("By Agent").classes("nx-title")
                for aname, adata in by_agent.items():
                    ar = adata.get("avg_reward", 0)
                    ti = adata.get("total_interactions", 0)
                    ui.html(
                        f'<div style="display:flex;align-items:center;gap:8px;padding:2px 0">'
                        f'<span style="color:#e0e0e0;font-size:0.75rem;min-width:70px">{aname}</span>'
                        f'<span style="color:#666680;font-size:0.65rem">'
                        f'reward: {ar:.2f} \u00b7 interactions: {ti}</span></div>'
                    )

        # Correction pairs
        pairs = fetch_corrections()
        with ui.card().classes("nx-card p-4"):
            ui.label(f"Corrections ({len(pairs)})").classes("nx-title").style(
                "color:#ff6b35" if pairs else ""
            )
            if pairs:
                for pair in pairs[:5]:
                    ts = pair.get("timestamp", "")[:16]
                    agent = pair.get("agent", "?")
                    wrong = (pair.get("wrong_action", ""))[:60]
                    correct = (pair.get("correct_action", ""))[:60]
                    # Escape HTML
                    wrong = wrong.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    correct = correct.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                    ui.html(
                        f'<div style="padding:4px 8px;border-left:2px solid #ff6b35;margin-bottom:4px">'
                        f'<span style="color:#666680;font-size:0.65rem">{ts}</span> '
                        f'<span style="color:#00d4aa;font-size:0.65rem">{agent}</span>'
                        f'<div style="color:#ff6b35;font-size:0.65rem;margin-top:1px">\u2212 {wrong}</div>'
                        f'<div style="color:#00d4aa;font-size:0.65rem;margin-top:1px">+ {correct}</div>'
                        f'</div>'
                    )
            else:
                ui.label("No corrections in last 7 days").style("color:#666680;font-size:0.75rem")

        # ── Training Pipeline Card (enhancement) ──
        with ui.card().classes("nx-card p-4"):
            ui.label("Training Pipeline").classes("nx-title")
            signals_dir = NEXUS_HOME / "memory" / ".system" / "rl_signals"
            sig_files = sorted(signals_dir.glob("signals_*.jsonl")) if signals_dir.exists() else []
            batch_dir = signals_dir / "batches" if signals_dir.exists() else Path(".")
            batch_files = sorted(batch_dir.glob("batch_*.json")) if batch_dir.exists() else []
            ui.html(
                f'<div style="font-size:0.75rem;color:#e0e0e0;padding:2px 0">'
                f'Signal files: <span style="color:#00d4aa">{len(sig_files)}</span></div>'
                f'<div style="font-size:0.75rem;color:#e0e0e0;padding:2px 0">'
                f'Batch files: <span style="color:#00d4aa">{len(batch_files)}</span></div>'
            )
            if sig_files:
                latest_sig = datetime.fromtimestamp(sig_files[-1].stat().st_mtime)
                ui.html(
                    f'<div style="font-size:0.65rem;color:#666680;padding:2px 0">'
                    f'Latest signal: {latest_sig.strftime("%Y-%m-%d %H:%M")}</div>'
                )
            if batch_files:
                latest_batch = datetime.fromtimestamp(batch_files[-1].stat().st_mtime)
                ui.html(
                    f'<div style="font-size:0.65rem;color:#666680;padding:2px 0">'
                    f'Latest batch: {latest_batch.strftime("%Y-%m-%d %H:%M")}</div>'
                )
            opt_log = fetch_optimization_log(limit=1)
            if opt_log:
                last = opt_log[-1]
                rl_score = last.get("results", {}).get("rl_score", 0)
                composite = last.get("results", {}).get("metric", 0)
                ui.html(
                    f'<div style="font-size:0.75rem;color:#e0e0e0;padding:4px 0;margin-top:4px;'
                    f'border-top:1px solid #1a1a2e">'
                    f'Last composite: <span style="color:#00d4aa">{composite:.4f}</span> '
                    f'(RL component: {rl_score:.4f})</div>'
                )


def build_config_tab():
    """Config tab: OpenClaw orchestrator, guardian policies, agent registry."""
    oc = fetch_openclaw_config()
    orch = oc.get("orchestrator", {})
    agents_cfg = oc.get("agents", {})
    skills_cfg = oc.get("skills", {})
    guardian = orch.get("guardian", {})
    memory_cfg = orch.get("memory", {})
    llm = orch.get("llm", {})

    with ui.column().classes("gap-3 p-3 w-full").style("overflow-y:auto;max-height:calc(100vh - 200px)"):
        if not orch:
            ui.label("openclaw.yaml not found").style("color:#666680;font-size:0.8rem")
            return

        # ── Orchestrator Overview ──
        with ui.card().classes("nx-card p-4"):
            ui.label("Orchestrator Overview").classes("nx-title")
            name = orch.get("name", "nexus")
            version = orch.get("version", "?")
            provider = llm.get("provider", "?")
            model = llm.get("model", "?")
            endpoint = llm.get("endpoint", "?")
            fallback = llm.get("fallback_model", "none")
            ui.html(
                f'<div style="font-size:0.8rem;color:#e0e0e0;margin-bottom:8px">'
                f'<span style="color:#00d4aa;font-weight:600">{name}</span> v{version}</div>'
                f'<div style="font-size:0.7rem;color:#666680">'
                f'Provider: {provider} &middot; Model: {model} &middot; Fallback: {fallback}</div>'
                f'<div style="font-size:0.65rem;color:#666680;margin-top:2px">Endpoint: {endpoint}</div>'
            )
            sandbox_on = orch.get("sandbox", {}).get("enabled", False)
            guardian_on = guardian.get("enabled", False)
            auto_log = memory_cfg.get("auto_log", False)
            ui.html(
                f'<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">'
                f'<span class="nx-badge {"nx-badge-on" if sandbox_on else "nx-badge-off"}">'
                f'sandbox {"on" if sandbox_on else "off"}</span>'
                f'<span class="nx-badge {"nx-badge-on" if guardian_on else "nx-badge-off"}">'
                f'guardian {"on" if guardian_on else "off"}</span>'
                f'<span class="nx-badge {"nx-badge-on" if auto_log else "nx-badge-off"}">'
                f'auto_log {"on" if auto_log else "off"}</span></div>'
            )

        # ── Guardian Policies ──
        if guardian:
            with ui.card().classes("nx-card p-4"):
                ui.label("Guardian Policies").classes("nx-title")
                require = guardian.get("require_approval", [])
                auto = guardian.get("auto_approve", [])
                with ui.row().classes("gap-4 w-full"):
                    with ui.column().style("flex:1"):
                        ui.html('<div style="font-size:0.7rem;color:#ff6b35;font-weight:600;margin-bottom:4px">Require Approval</div>')
                        for item in require:
                            ui.html(f'<div style="border-left:3px solid #ff6b35;padding:2px 8px;margin:2px 0;'
                                    f'font-size:0.7rem;color:#e0e0e0">{item}</div>')
                    with ui.column().style("flex:1"):
                        ui.html('<div style="font-size:0.7rem;color:#00d4aa;font-weight:600;margin-bottom:4px">Auto Approve</div>')
                        for item in auto:
                            ui.html(f'<div style="border-left:3px solid #00d4aa;padding:2px 8px;margin:2px 0;'
                                    f'font-size:0.7rem;color:#e0e0e0">{item}</div>')
                cloud = guardian.get("cloud_verification", {})
                if cloud.get("enabled"):
                    ui.html(
                        f'<div style="margin-top:8px;font-size:0.65rem;color:#666680">'
                        f'Cloud verification: {cloud.get("provider", "?")} '
                        f'(threshold: {cloud.get("threshold", "?")})</div>'
                    )

        # ── Agent Registry ──
        if agents_cfg:
            with ui.card().classes("nx-card p-4"):
                ui.label("Agent Registry").classes("nx-title")
                for aname, acfg in agents_cfg.items():
                    auto_start = acfg.get("auto_start", False)
                    schedule = acfg.get("schedule", "")
                    skills = acfg.get("skills", [])
                    badge_cls = "nx-badge-on" if auto_start else "nx-badge-off"
                    sched_html = (f' <span style="color:#666680;font-size:0.6rem">'
                                  f'cron: {schedule}</span>') if schedule else ""
                    skills_html = ", ".join(f'<span style="color:#4ecdc4">{s}</span>' for s in skills)
                    ui.html(
                        f'<div style="padding:6px 0;border-bottom:1px solid #1a1a2e">'
                        f'<div style="display:flex;align-items:center;gap:8px">'
                        f'<span style="color:#e0e0e0;font-size:0.8rem;font-weight:600">{aname}</span>'
                        f'<span class="nx-badge {badge_cls}">{"auto" if auto_start else "manual"}</span>'
                        f'{sched_html}</div>'
                        f'<div style="font-size:0.65rem;margin-top:3px">{skills_html}</div></div>'
                    )

        # ── Skill Risk Matrix ──
        if skills_cfg:
            with ui.card().classes("nx-card p-4"):
                ui.label("Skill Risk Matrix").classes("nx-title")
                html = '<table class="nx-route-table"><tr><th>Skill</th><th>Risk</th><th>Guardian</th></tr>'
                for sname, scfg in skills_cfg.items():
                    risk = scfg.get("risk", "low")
                    badge = "nx-badge-risk-low" if risk == "low" else "nx-badge-risk-med"
                    needs_guardian = scfg.get("requires_guardian", False)
                    shield = '<span style="color:#ff6b35">&#x1f6e1;</span>' if needs_guardian else ""
                    html += (f'<tr><td style="color:#e0e0e0">{sname}</td>'
                             f'<td><span class="nx-badge {badge}">{risk}</span></td>'
                             f'<td>{shield}</td></tr>')
                html += '</table>'
                ui.html(html)

        # ── Memory Config ──
        if memory_cfg:
            with ui.card().classes("nx-card p-4"):
                ui.label("Memory Config").classes("nx-title")
                decay = memory_cfg.get("decay_lambda", 0)
                half_life = f"{math.log(2) / decay:.1f} days" if decay > 0 else "infinite"
                ui.html(
                    f'<div style="font-size:0.75rem;color:#e0e0e0">'
                    f'decay_lambda: {decay} &rarr; half-life: '
                    f'<span style="color:#00d4aa">{half_life}</span></div>'
                )
                hybrid = memory_cfg.get("hybrid_search", False)
                link_graph = memory_cfg.get("link_graph", False)
                auto_log = memory_cfg.get("auto_log", False)
                ui.html(
                    f'<div style="margin-top:6px;display:flex;gap:6px;flex-wrap:wrap">'
                    f'<span class="nx-badge {"nx-badge-on" if hybrid else "nx-badge-off"}">hybrid_search</span>'
                    f'<span class="nx-badge {"nx-badge-on" if link_graph else "nx-badge-off"}">link_graph</span>'
                    f'<span class="nx-badge {"nx-badge-on" if auto_log else "nx-badge-off"}">auto_log</span></div>'
                )


def build_sandbox_tab():
    """Sandbox tab: NemoClaw security policies."""
    policies = fetch_sandbox_policies()
    proc = policies.get("process", {})
    fs = policies.get("filesystem", {})
    net = policies.get("network", {})
    inf = policies.get("inference", {})
    nexus_str = str(NEXUS_HOME).replace("\\", "/")

    def _expand(s):
        return str(s).replace("${NEXUS_HOME}", nexus_str)

    with ui.column().classes("gap-3 p-3 w-full").style("overflow-y:auto;max-height:calc(100vh - 200px)"):
        # ── Process Limits ──
        with ui.row().classes("gap-2 w-full"):
            max_agents = proc.get("max_concurrent_agents", "?")
            max_exec = proc.get("max_execution_seconds", 0)
            max_mem = proc.get("max_memory_mb", 0)
            for val, lbl in [
                (str(max_agents), "Max Agents"),
                (f"{max_exec // 60} min" if isinstance(max_exec, int) and max_exec else str(max_exec), "Max Exec Time"),
                (f"{max_mem / 1024:.0f} GB" if isinstance(max_mem, (int, float)) and max_mem else str(max_mem), "Max Memory"),
            ]:
                with ui.card().classes("nx-card p-3").style("flex:1"):
                    ui.html(f'<div class="nx-stat" style="font-size:1.5rem">{val}</div>')
                    ui.html(f'<div class="nx-label">{lbl}</div>')

        # ── Filesystem Policy ──
        if fs:
            with ui.card().classes("nx-card p-4"):
                ui.label("Filesystem Policy").classes("nx-title")
                for paths, label, css_cls in [
                    (fs.get("allowed_paths", []), "Allowed", "nx-path-allowed"),
                    (fs.get("read_only_paths", []), "Read-Only", "nx-path-readonly"),
                    (fs.get("denied_paths", []), "Denied", "nx-path-denied"),
                ]:
                    if paths:
                        ui.html(f'<div style="font-size:0.7rem;color:#666680;font-weight:600;margin:6px 0 2px">{label}</div>')
                        for p in paths:
                            ui.html(f'<div class="{css_cls}" style="font-size:0.7rem;color:#e0e0e0">{_expand(p)}</div>')

        # ── Network Policy ──
        if net:
            with ui.card().classes("nx-card p-4"):
                ui.label("Network Policy").classes("nx-title")
                endpoints = net.get("allowed_endpoints", [])
                if endpoints:
                    html = '<table class="nx-route-table"><tr><th>Host</th><th>Port</th><th>Protocol</th></tr>'
                    for ep in endpoints:
                        html += (f'<tr><td style="color:#e0e0e0">{ep.get("host", "?")}</td>'
                                 f'<td>{ep.get("port", "?")}</td>'
                                 f'<td>{ep.get("protocol", "?")}</td></tr>')
                    html += '</table>'
                    ui.html(html)
                allow_local = net.get("allow_localhost", False)
                blocked = net.get("blocked_ranges", [])
                ui.html(
                    f'<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">'
                    f'<span class="nx-badge {"nx-badge-on" if allow_local else "nx-badge-off"}">'
                    f'allow_localhost</span>'
                    f'<span style="font-size:0.65rem;color:#666680">'
                    f'Blocked ranges: {", ".join(str(b) for b in blocked) if blocked else "None"}</span></div>'
                )

        # ── Inference Policy ──
        if inf:
            with ui.card().classes("nx-card p-4"):
                ui.label("Inference Policy").classes("nx-title")
                backends = inf.get("approved_backends", [])
                if backends:
                    html = '<table class="nx-route-table"><tr><th>Provider</th><th>Endpoint</th><th>Models</th></tr>'
                    for b in backends:
                        models = b.get("models", [])
                        models_str = ", ".join(models) if models else "any"
                        html += (f'<tr><td style="color:#e0e0e0">{b.get("provider", "?")}</td>'
                                 f'<td>{b.get("endpoint", "?")}</td>'
                                 f'<td style="font-size:0.65rem">{models_str}</td></tr>')
                    html += '</table>'
                    ui.html(html)
                require_router = inf.get("require_router", False)
                max_tok = inf.get("max_tokens_per_request", "?")
                rate = inf.get("rate_limit_rpm", "?")
                ui.html(
                    f'<div style="margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
                    f'<span class="nx-badge {"nx-badge-on" if require_router else "nx-badge-off"}">'
                    f'require_router</span>'
                    f'<span style="font-size:0.65rem;color:#666680">'
                    f'max_tokens: {max_tok} &middot; rate_limit: {rate} rpm</span></div>'
                )

        # ── Denied Syscalls ──
        if proc:
            with ui.card().classes("nx-card p-4"):
                ui.label("Denied Syscalls").classes("nx-title")
                denied = proc.get("denied_syscalls", [])
                if denied:
                    ui.html(
                        '<div style="display:flex;gap:6px;flex-wrap:wrap">' +
                        "".join(f'<span class="nx-badge nx-badge-off" style="font-size:0.65rem">{s}</span>' for s in denied) +
                        '</div>'
                    )
                priv_esc = proc.get("allow_privilege_escalation", False)
                badge_cls = "nx-badge-off" if priv_esc else "nx-badge-on"
                ui.html(
                    f'<div style="margin-top:8px">'
                    f'<span class="nx-badge {badge_cls}">'
                    f'privilege_escalation: {"allowed" if priv_esc else "denied"}</span></div>'
                )


def _build_sparkline_svg(values, width=320, height=60):
    """Build an inline SVG sparkline from a list of numeric values."""
    if not values or len(values) < 2:
        return ""
    vmin, vmax = min(values), max(values)
    vrange = vmax - vmin if vmax != vmin else 1
    n = len(values)
    points = []
    for i, v in enumerate(values):
        x = (i / (n - 1)) * width
        y = height - ((v - vmin) / vrange) * (height - 4) - 2
        points.append(f"{x:.1f},{y:.1f}")
    polyline = " ".join(points)
    # Area fill
    area = f"0,{height} " + polyline + f" {width},{height}"
    return (
        f'<svg width="{width}" height="{height}" style="display:block">'
        f'<polygon points="{area}" fill="rgba(0,212,170,0.1)" />'
        f'<polyline points="{polyline}" class="nx-sparkline" />'
        f'</svg>'
    )


def build_optimizer_tab():
    """Optimizer tab: autoresearch, simulation launcher."""
    opt_log = fetch_optimization_log(limit=50)
    opt_cfg = fetch_optimizer_config()

    with ui.column().classes("gap-3 p-3 w-full").style("overflow-y:auto;max-height:calc(100vh - 200px)"):
        # ── Score Trend ──
        with ui.card().classes("nx-card p-4"):
            ui.label("Optimization Score Trend").classes("nx-title")
            if opt_log:
                metrics = [e.get("results", {}).get("metric", 0) for e in opt_log]
                svg = _build_sparkline_svg(metrics)
                if svg:
                    ui.html(svg)
                latest = opt_log[-1].get("results", {})
                metric_val = latest.get("metric", 0)
                sim_score = latest.get("sim_score", 0)
                rl_score = latest.get("rl_score", 0)
                ui.html(
                    f'<div style="margin-top:8px">'
                    f'<span class="nx-stat" style="font-size:1.8rem">{metric_val:.4f}</span>'
                    f'<span style="color:#666680;font-size:0.7rem;margin-left:8px">composite</span></div>'
                    f'<div style="font-size:0.7rem;color:#666680;margin-top:4px">'
                    f'sim_score: {sim_score:.4f} (60%) &middot; rl_score: {rl_score:.4f} (40%)</div>'
                )
            else:
                ui.label("No optimization data yet").style("color:#666680;font-size:0.8rem")

        # ── Latest Run Summary ──
        if opt_log:
            with ui.card().classes("nx-card p-4"):
                ui.label("Latest Run").classes("nx-title")
                last = opt_log[-1]
                ts = last.get("timestamp", "?")
                dur = last.get("duration_seconds", 0)
                res = last.get("results", {})
                ui.html(
                    f'<div style="font-size:0.7rem;color:#666680">{ts} &middot; {dur:.0f}s</div>'
                )
                # Metrics breakdown
                breakdown_keys = [
                    ("mean_roi_pct", "Mean ROI %"), ("sharpe_ratio", "Sharpe"),
                    ("win_rate_pct", "Win Rate %"), ("agent_success_rate", "Agent Success"),
                    ("user_satisfaction", "User Satisfaction"),
                ]
                prev = opt_log[-2].get("results", {}) if len(opt_log) >= 2 else {}
                for key, label in breakdown_keys:
                    val = res.get(key, 0)
                    prev_val = prev.get(key, None)
                    delta_html = ""
                    if prev_val is not None:
                        diff = val - prev_val
                        if abs(diff) > 0.0001:
                            arrow = "&#x25B2;" if diff > 0 else "&#x25BC;"
                            color = "#00d4aa" if diff > 0 else "#ef4444"
                            delta_html = f' <span style="color:{color};font-size:0.6rem">{arrow} {abs(diff):.3f}</span>'
                    ui.html(
                        f'<div style="display:flex;justify-content:space-between;padding:2px 0;'
                        f'font-size:0.75rem">'
                        f'<span style="color:#666680">{label}</span>'
                        f'<span style="color:#e0e0e0">{val:.4f}{delta_html}</span></div>'
                    )

        # ── Search Space ──
        search_space = opt_cfg.get("search_space", {})
        if search_space:
            with ui.card().classes("nx-card p-4"):
                ui.label("Search Space").classes("nx-title")
                # Group by category prefix
                categories = {"Simulation": [], "Routing": [], "Memory": [], "RL": [], "Other": []}
                for pname, pdef in search_space.items():
                    if pname.startswith("num_") or pname in ("lookback_min", "lookback_max",
                            "threshold_min", "threshold_max", "momentum_weight",
                            "mean_reversion_weight", "position_sizing"):
                        categories["Simulation"].append((pname, pdef))
                    elif pname.startswith("routing_"):
                        categories["Routing"].append((pname, pdef))
                    elif pname.startswith("memory_"):
                        categories["Memory"].append((pname, pdef))
                    elif pname.startswith("rl_"):
                        categories["RL"].append((pname, pdef))
                    else:
                        categories["Other"].append((pname, pdef))

                latest_params = opt_log[-1].get("params", {}) if opt_log else {}
                for cat_name, params in categories.items():
                    if not params:
                        continue
                    ui.html(f'<div style="font-size:0.7rem;color:#00d4aa;font-weight:600;margin:8px 0 4px">{cat_name}</div>')
                    for pname, pdef in params:
                        ptype = pdef.get("type", "?")
                        current = latest_params.get(pname, "—")
                        if ptype == "categorical":
                            vals = pdef.get("values", [])
                            range_str = " | ".join(str(v) for v in vals)
                        else:
                            pmin = pdef.get("min", "")
                            pmax = pdef.get("max", "")
                            range_str = f"{pmin} – {pmax}"
                        ui.html(
                            f'<div style="display:flex;justify-content:space-between;padding:1px 0;'
                            f'font-size:0.65rem">'
                            f'<span style="color:#e0e0e0">{pname}</span>'
                            f'<span style="color:#666680">{current} <span style="color:#4a4f60">[{range_str}]</span></span></div>'
                        )

        # ── Schedule ──
        schedule = opt_cfg.get("schedule", {})
        early_stop = opt_cfg.get("early_stopping", {})
        if schedule or early_stop:
            with ui.card().classes("nx-card p-4"):
                ui.label("Schedule").classes("nx-title")
                if schedule:
                    mode = schedule.get("mode", "?")
                    start = schedule.get("start_hour", "?")
                    end = schedule.get("end_hour", "?")
                    max_iter = schedule.get("max_iterations", "?")
                    timeout = schedule.get("timeout_minutes", "?")
                    ui.html(
                        f'<div style="font-size:0.75rem;color:#e0e0e0">'
                        f'Mode: {mode} &middot; Hours: {start}–{end} &middot; '
                        f'Max iters: {max_iter} &middot; Timeout: {timeout} min</div>'
                    )
                if early_stop:
                    patience = early_stop.get("patience", "?")
                    min_imp = early_stop.get("min_improvement", "?")
                    ui.html(
                        f'<div style="font-size:0.7rem;color:#666680;margin-top:4px">'
                        f'Early stopping: patience {patience}, min improvement {min_imp}</div>'
                    )

        # ── Simulation Launcher ──
        with ui.card().classes("nx-card p-4"):
            ui.label("Simulation Launcher").classes("nx-title")
            if not _HAS_SIM:
                ui.label("run_simulation module not available").style("color:#666680;font-size:0.8rem")
            else:
                sim_agents = ui.number("Agents", value=100, min=10, max=1000, step=10).props(
                    "dense outlined dark"
                ).classes("nx-search").style("max-width:120px")
                sim_rounds = ui.number("Rounds", value=30, min=5, max=500, step=5).props(
                    "dense outlined dark"
                ).classes("nx-search").style("max-width:120px")
                sim_market = ui.select(["crypto", "stocks", "forex"], value="crypto", label="Market").props(
                    "dense outlined dark"
                ).classes("nx-search").style("max-width:140px")

                sim_results_box = ui.column().classes("w-full gap-2")
                sim_spinner = ui.spinner("dots", size="sm", color="primary").style("display:none")

                async def run_sim():
                    sim_results_box.clear()
                    sim_spinner.style("display:inline-block")
                    try:
                        na = int(sim_agents.value)
                        nr = int(sim_rounds.value)
                        mkt = sim_market.value
                        result = await asyncio.to_thread(
                            run_builtin_simulation, na, nr, mkt, {}
                        )
                        analysis = analyze_results(result)
                        sim_spinner.style("display:none")
                        with sim_results_box:
                            with ui.card().classes("nx-card p-4"):
                                ui.label("Simulation Results").classes("nx-title")
                                mean_roi = analysis.get("mean_roi_pct", 0)
                                sharpe = analysis.get("sharpe_ratio", 0)
                                win_rate = analysis.get("win_rate_pct", 0)
                                ui.html(
                                    f'<div style="display:flex;gap:16px;margin-bottom:8px">'
                                    f'<div><span class="nx-stat" style="font-size:1.3rem">{mean_roi:.2f}%</span>'
                                    f'<div class="nx-label">Mean ROI</div></div>'
                                    f'<div><span class="nx-stat" style="font-size:1.3rem">{sharpe:.3f}</span>'
                                    f'<div class="nx-label">Sharpe</div></div>'
                                    f'<div><span class="nx-stat" style="font-size:1.3rem">{win_rate:.1f}%</span>'
                                    f'<div class="nx-label">Win Rate</div></div></div>'
                                )
                                # Strategy breakdown
                                strategies = analysis.get("strategy_breakdown", analysis.get("strategies", {}))
                                if strategies:
                                    html = '<table class="nx-route-table"><tr><th>Strategy</th><th>Count</th><th>Avg ROI</th></tr>'
                                    for sname, sdata in strategies.items():
                                        if isinstance(sdata, dict):
                                            cnt = sdata.get("count", 0)
                                            avg = sdata.get("avg_roi_pct", sdata.get("mean_roi", 0))
                                        else:
                                            cnt = sdata
                                            avg = 0
                                        html += f'<tr><td style="color:#e0e0e0">{sname}</td><td>{cnt}</td><td>{avg:.2f}%</td></tr>'
                                    html += '</table>'
                                    ui.html(html)
                                # Best/worst
                                best = analysis.get("best_agent", {})
                                worst = analysis.get("worst_agent", {})
                                if best:
                                    ui.html(
                                        f'<div style="font-size:0.7rem;color:#00d4aa;margin-top:4px">'
                                        f'Best: {best.get("strategy", "?")} ROI {best.get("roi_pct", 0):.2f}%</div>'
                                    )
                                if worst:
                                    ui.html(
                                        f'<div style="font-size:0.7rem;color:#ef4444">'
                                        f'Worst: {worst.get("strategy", "?")} ROI {worst.get("roi_pct", 0):.2f}%</div>'
                                    )
                    except Exception as ex:
                        sim_spinner.style("display:none")
                        with sim_results_box:
                            ui.label(f"Error: {ex}").style("color:#ef4444;font-size:0.8rem")

                ui.button("Run Simulation", on_click=run_sim).props("dense flat").style(
                    "background:rgba(0,212,170,0.15);color:#00d4aa;margin-top:8px"
                )


def build_activity_feed():
    """Bottom activity feed with auto-refresh."""
    feed_box = ui.column().classes("w-full")

    def refresh():
        feed_box.clear()
        signals = fetch_recent_signals(limit=10)
        with feed_box:
            if not signals:
                ui.html(
                    '<div style="color:#666680;font-size:0.7rem;padding:4px">No recent activity</div>'
                )
                return
            for sig in signals:
                ts = sig.get("timestamp", "")[:19]
                agent = sig.get("agent", "system")
                stype = sig.get("signal_type", "?")
                reward = sig.get("reward", 0)
                action = (sig.get("action", ""))[:60]
                # Escape
                action = action.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

                tc = "#00d4aa" if stype == "confirmation" else (
                    "#ff6b35" if stype == "correction" else "#666680"
                )
                ui.html(
                    f'<div class="nx-feed-item">'
                    f'<span style="color:#666680;font-size:0.65rem">{ts}</span> '
                    f'<span style="color:{tc};font-weight:600;font-size:0.65rem">{stype}</span> '
                    f'<span style="color:#e0e0e0;font-size:0.65rem">{agent}</span> '
                    f'<span style="color:#666680;font-size:0.65rem">r={reward:.2f}</span>'
                    f'{"<div style=color:#666680;font-size:0.6rem;margin-left:12px>" + action + "</div>" if action else ""}'
                    f'</div>'
                )

    refresh()
    return refresh


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@ui.page("/")
def main_page():
    ui.dark_mode(True)
    ui.add_css(THEME_CSS)
    ui.add_head_html(f'<script src="{VIS_JS_CDN}"></script>')
    ui.add_head_html(
        '<link rel="icon" href="data:image/svg+xml,'
        '<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22>'
        '<text y=%22.9em%22 font-size=%2290%22>%F0%9F%94%AE</text></svg>">'
    )

    status = fetch_status()

    # Header
    build_header(status)

    # Main content: graph (60%) | tabbed panel (40%)
    with ui.row().classes("w-full gap-4 p-4").style(
        "min-height:calc(100vh - 140px);align-items:stretch"
    ):
        # Left: Knowledge Graph (flex:3)
        with ui.column().style("flex:3;min-width:0"):
            build_graph_panel(status)

        # Right: Tabbed Panel (flex:2)
        with ui.column().style("flex:2;min-width:300px"):
            with ui.tabs().classes("w-full") as tabs:
                t_sys = ui.tab("System")
                t_mem = ui.tab("Memory")
                t_skills = ui.tab("Skills")
                t_rl = ui.tab("RL")
                t_config = ui.tab("Config")
                t_sandbox = ui.tab("Sandbox")
                t_optimizer = ui.tab("Optimizer")

            with ui.tab_panels(tabs, value=t_sys).classes("w-full flex-grow").style(
                "background:transparent !important"
            ):
                with ui.tab_panel(t_sys).style("padding:0"):
                    build_system_tab(status)
                with ui.tab_panel(t_mem).style("padding:0"):
                    build_memory_tab()
                with ui.tab_panel(t_skills).style("padding:0"):
                    build_skills_tab(status)
                with ui.tab_panel(t_rl).style("padding:0"):
                    build_rl_tab()
                with ui.tab_panel(t_config).style("padding:0"):
                    build_config_tab()
                with ui.tab_panel(t_sandbox).style("padding:0"):
                    build_sandbox_tab()
                with ui.tab_panel(t_optimizer).style("padding:0"):
                    build_optimizer_tab()

    # Bottom: Activity Feed
    with ui.element("div").classes("w-full").style(
        "border-top:1px solid #1a1a2e;padding:10px 24px"
    ):
        with ui.row().classes("items-center gap-3 mb-1"):
            ui.html(
                '<span style="font-size:0.8rem;font-weight:600;color:#00d4aa">'
                'Activity Feed</span>'
            )
            ui.html(
                '<span style="font-size:0.6rem;color:#666680">auto-refresh 10s</span>'
            )

        refresh_feed = build_activity_feed()

        # Auto-refresh timer (10s)
        ui.timer(10.0, refresh_feed)


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Nexus Visual Dashboard")
    parser.add_argument("--port", "-p", type=int, default=DASHBOARD_PORT,
                        help=f"Dashboard port (default: {DASHBOARD_PORT})")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    ui.run(
        title="Nexus Dashboard",
        port=args.port,
        host=args.host,
        dark=True,
        reload=False,
        show=not args.no_open,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()

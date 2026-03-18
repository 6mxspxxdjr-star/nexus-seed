#!/usr/bin/env python3
"""
Nexus Backend API — HTTP server exposing all Nexus features.

Runs on localhost:3700 and provides endpoints for:
- Chat with intelligent model routing
- Memory search, store, and graph
- Simulation engine
- API key management
- System status and model info
- Update mechanism

The new UI frontend talks to this API.

Usage:
    python nexus_api.py                    # Start on :3700
    python nexus_api.py --port 4000        # Custom port
    python nexus_api.py --host 0.0.0.0     # Listen on all interfaces
"""

import json
import logging
import os
import sys
import threading
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

# Setup paths
NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
sys.path.insert(0, str(NEXUS_HOME / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("nexus.api")

# Lazy imports — these may not exist on first run
_router = None
_memory = None


def get_router():
    global _router
    if _router is None:
        try:
            from model_router import ModelRouter
            _router = ModelRouter(str(NEXUS_HOME))
        except Exception as e:
            logger.error(f"Failed to init router: {e}")
    return _router


def get_memory():
    global _memory
    if _memory is None:
        try:
            from memory_system import MemorySystem
            _memory = MemorySystem(str(NEXUS_HOME))
        except Exception as e:
            logger.error(f"Failed to init memory: {e}")
    return _memory


class NexusAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the Nexus API."""

    def log_message(self, format, *args):
        logger.info(f"{self.address_string()} {format % args}")

    def _send_json(self, data, status=200):
        body = json.dumps(data, indent=2, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_sse_start(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def _send_sse_event(self, data, event=None):
        if event:
            self.wfile.write(f"event: {event}\n".encode())
        self.wfile.write(f"data: {json.dumps(data)}\n\n".encode())
        self.wfile.flush()

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        try:
            if path == "/api/status":
                self._handle_status()
            elif path == "/api/models":
                self._handle_models()
            elif path == "/api/memory/search":
                query = params.get("q", [""])[0]
                limit = int(params.get("limit", ["10"])[0])
                self._handle_memory_search(query, limit)
            elif path == "/api/memory/stats":
                self._handle_memory_stats()
            elif path == "/api/memory/graph":
                self._handle_memory_graph()
            elif path == "/api/agents":
                self._handle_agents()
            elif path == "/api/skills":
                self._handle_skills()
            elif path == "/api/keys":
                self._handle_keys_list()
            elif path == "/api/config":
                self._handle_config()
            else:
                self._send_json({"error": "Not found", "endpoints": [
                    "GET /api/status", "GET /api/models", "GET /api/agents",
                    "GET /api/skills", "GET /api/keys", "GET /api/config",
                    "GET /api/memory/search?q=...", "GET /api/memory/stats",
                    "GET /api/memory/graph",
                    "POST /api/chat", "POST /api/chat/stream",
                    "POST /api/memory/store", "POST /api/simulate",
                    "POST /api/keys", "DELETE /api/keys/:provider",
                    "POST /api/classify", "POST /api/update",
                ]}, 404)
        except Exception as e:
            logger.error(traceback.format_exc())
            self._send_json({"error": str(e)}, 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            body = self._read_body()

            if path == "/api/chat":
                self._handle_chat(body)
            elif path == "/api/chat/stream":
                self._handle_chat_stream(body)
            elif path == "/api/classify":
                self._handle_classify(body)
            elif path == "/api/memory/store":
                self._handle_memory_store(body)
            elif path == "/api/simulate":
                self._handle_simulate(body)
            elif path == "/api/keys":
                self._handle_keys_save(body)
            elif path == "/api/update":
                self._handle_update()
            else:
                self._send_json({"error": "Not found"}, 404)
        except Exception as e:
            logger.error(traceback.format_exc())
            self._send_json({"error": str(e)}, 500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            if path.startswith("/api/keys/"):
                provider = path.split("/")[-1]
                self._handle_keys_delete(provider)
            else:
                self._send_json({"error": "Not found"}, 404)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ==================================================================
    # Status & Info
    # ==================================================================

    def _handle_status(self):
        router = get_router()
        memory = get_memory()

        models = router.get_available_models() if router else {}
        mem_stats = None
        if memory:
            try:
                mem_stats = memory.stats()
            except Exception:
                pass

        self._send_json({
            "status": "online",
            "nexus_home": str(NEXUS_HOME),
            "ollama": bool(models.get("ollama")),
            "ollama_models": models.get("ollama", []),
            "anthropic": models.get("anthropic", False),
            "openai": models.get("openai", False),
            "memory": mem_stats,
            "agents": ["strategist", "guardian", "worker", "evolution"],
            "skills_count": len(list((NEXUS_HOME / "skills").iterdir())) if (NEXUS_HOME / "skills").exists() else 0,
        })

    def _handle_models(self):
        router = get_router()
        if not router:
            self._send_json({"error": "Router not available"}, 503)
            return

        available = router.get_available_models()
        from model_router import TIERS, ROUTING_TABLE
        self._send_json({
            "available": available,
            "tiers": TIERS,
            "routing_table": ROUTING_TABLE,
        })

    def _handle_config(self):
        config_file = NEXUS_HOME / "configs" / "openclaw.yaml"
        config = {}
        if config_file.exists():
            try:
                import yaml
                config = yaml.safe_load(config_file.read_text()) or {}
            except Exception:
                config = {"raw": config_file.read_text()}
        self._send_json(config)

    # ==================================================================
    # Chat
    # ==================================================================

    def _handle_chat(self, body):
        """Non-streaming chat — returns full response."""
        router = get_router()
        if not router:
            self._send_json({"error": "Router not available"}, 503)
            return

        prompt = body.get("prompt", "")
        task_hint = body.get("task_hint")
        system_prompt = body.get("system_prompt")

        if not prompt:
            self._send_json({"error": "prompt required"}, 400)
            return

        decision = router.route(prompt, task_hint=task_hint)
        response = router.generate_sync(prompt, task_hint=task_hint, system_prompt=system_prompt)

        self._send_json({
            "response": response,
            "routing": decision.to_dict(),
        })

    def _handle_chat_stream(self, body):
        """SSE streaming chat — tokens arrive as events."""
        router = get_router()
        if not router:
            self._send_json({"error": "Router not available"}, 503)
            return

        prompt = body.get("prompt", "")
        task_hint = body.get("task_hint")
        system_prompt = body.get("system_prompt")

        if not prompt:
            self._send_json({"error": "prompt required"}, 400)
            return

        decision = router.route(prompt, task_hint=task_hint)

        self._send_sse_start()
        self._send_sse_event(decision.to_dict(), event="routing")

        try:
            for token in router.generate(prompt, task_hint=task_hint, system_prompt=system_prompt):
                self._send_sse_event({"token": token}, event="token")
            self._send_sse_event({"done": True}, event="done")
        except Exception as e:
            self._send_sse_event({"error": str(e)}, event="error")

    def _handle_classify(self, body):
        """Classify a task without generating."""
        router = get_router()
        if not router:
            self._send_json({"error": "Router not available"}, 503)
            return

        task = body.get("task", "")
        if not task:
            self._send_json({"error": "task required"}, 400)
            return

        decision = router.route(task, task_hint=body.get("task_hint"))
        self._send_json(decision.to_dict())

    # ==================================================================
    # Memory
    # ==================================================================

    def _handle_memory_search(self, query, limit):
        memory = get_memory()
        if not memory:
            self._send_json({"error": "Memory system not available"}, 503)
            return

        if not query:
            self._send_json({"error": "q parameter required"}, 400)
            return

        try:
            results = memory.search(query, top_k=limit)
            self._send_json({"query": query, "results": results})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_memory_store(self, body):
        memory = get_memory()
        if not memory:
            self._send_json({"error": "Memory system not available"}, 503)
            return

        content = body.get("content", "")
        if not content:
            self._send_json({"error": "content required"}, 400)
            return

        try:
            result = memory.store(
                content,
                memory_type=body.get("type", "semantic"),
                source=body.get("source", "api"),
                importance=body.get("importance", 0.5),
                tags=body.get("tags", []),
            )
            self._send_json({"stored": True, "result": result})
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_memory_stats(self):
        memory = get_memory()
        if not memory:
            self._send_json({"error": "Memory system not available"}, 503)
            return

        try:
            stats = memory.stats()
            self._send_json(stats)
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    def _handle_memory_graph(self):
        """Return the link graph for visualization."""
        graph_file = NEXUS_HOME / "memory" / ".system" / "link_graph.json"
        if graph_file.exists():
            try:
                graph = json.loads(graph_file.read_text())
                self._send_json(graph)
                return
            except Exception:
                pass

        # Build a basic graph from memory files
        nodes = []
        edges = []
        memory_dir = NEXUS_HOME / "memory"
        if memory_dir.exists():
            for md_file in memory_dir.rglob("*.md"):
                rel = str(md_file.relative_to(memory_dir))
                nodes.append({
                    "id": rel,
                    "label": md_file.stem,
                    "category": md_file.parent.name,
                    "size": md_file.stat().st_size,
                })
                # Find wikilinks
                try:
                    content = md_file.read_text(errors="replace")
                    import re
                    links = re.findall(r'\[\[([^\]]+)\]\]', content)
                    for link in links:
                        edges.append({"source": rel, "target": link})
                except Exception:
                    pass

        self._send_json({"nodes": nodes, "edges": edges})

    # ==================================================================
    # Agents & Skills
    # ==================================================================

    def _handle_agents(self):
        agents = []
        agents_dir = NEXUS_HOME / "agents"
        if agents_dir.exists():
            for agent_dir in agents_dir.iterdir():
                if agent_dir.is_dir():
                    identity_file = agent_dir / "IDENTITY.md"
                    identity = ""
                    if identity_file.exists():
                        identity = identity_file.read_text(errors="replace")
                    agents.append({
                        "name": agent_dir.name,
                        "identity": identity,
                        "has_identity": identity_file.exists(),
                    })
        self._send_json({"agents": agents})

    def _handle_skills(self):
        skills = []
        skills_dir = NEXUS_HOME / "skills"
        if skills_dir.exists():
            for skill_dir in skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    description = ""
                    if skill_md.exists():
                        description = skill_md.read_text(errors="replace")
                    has_run = (skill_dir / "run").exists()
                    skills.append({
                        "name": skill_dir.name,
                        "description": description,
                        "executable": has_run,
                    })
        self._send_json({"skills": skills})

    # ==================================================================
    # Keys
    # ==================================================================

    def _handle_keys_list(self):
        keys_file = NEXUS_HOME / "configs" / "keys.json"
        configured = {}
        if keys_file.exists():
            try:
                raw = json.loads(keys_file.read_text())
                for provider, key in raw.items():
                    configured[provider] = {
                        "configured": True,
                        "masked": key[:8] + "..." + key[-4:] if len(key) > 12 else "***",
                    }
            except Exception:
                pass

        # Check environment too
        for provider, env_var in [("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY")]:
            if provider not in configured and os.environ.get(env_var):
                key = os.environ[env_var]
                configured[provider] = {
                    "configured": True,
                    "masked": key[:8] + "..." + key[-4:] if len(key) > 12 else "***",
                    "source": "environment",
                }

        self._send_json({"providers": configured})

    def _handle_keys_save(self, body):
        """Save API keys."""
        keys_file = NEXUS_HOME / "configs" / "keys.json"
        existing = {}
        if keys_file.exists():
            try:
                existing = json.loads(keys_file.read_text())
            except Exception:
                pass

        for provider in ("anthropic", "openai"):
            key = body.get(provider)
            if key:
                existing[provider] = key

        keys_file.parent.mkdir(parents=True, exist_ok=True)
        keys_file.write_text(json.dumps(existing, indent=2))

        # Restrict permissions
        try:
            if sys.platform == "win32":
                import subprocess
                username = os.environ.get("USERNAME", "")
                if username:
                    subprocess.run(
                        ["icacls", str(keys_file), "/inheritance:r",
                         "/grant:r", f"{username}:(R,W)"],
                        capture_output=True,
                    )
            else:
                import stat
                os.chmod(keys_file, stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

        # Reload router to pick up new keys
        global _router
        _router = None

        self._send_json({"saved": True})

    def _handle_keys_delete(self, provider):
        keys_file = NEXUS_HOME / "configs" / "keys.json"
        if keys_file.exists():
            try:
                keys = json.loads(keys_file.read_text())
                if provider in keys:
                    del keys[provider]
                    keys_file.write_text(json.dumps(keys, indent=2))
            except Exception:
                pass

        global _router
        _router = None
        self._send_json({"deleted": provider})

    # ==================================================================
    # Simulation
    # ==================================================================

    def _handle_simulate(self, body):
        """Run a simulation and return results."""
        try:
            from run_simulation import run_builtin_simulation, analyze_results
        except ImportError:
            self._send_json({"error": "Simulation engine not available"}, 503)
            return

        agents = body.get("agents", 100)
        rounds = body.get("rounds", 50)
        market = body.get("market", "crypto")
        params = body.get("params", {})

        try:
            results, prices = run_builtin_simulation(agents, rounds, market, params)
            analysis = analyze_results(results, prices)
            self._send_json({
                "agents": agents,
                "rounds": rounds,
                "market": market,
                "summary": analysis,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)

    # ==================================================================
    # Update
    # ==================================================================

    def _handle_update(self):
        try:
            from update import check_update, get_remote_version, get_current_version
            current = get_current_version()
            remote = get_remote_version()
            has_update = current != remote and remote != ""
            self._send_json({
                "current_version": current,
                "latest_version": remote,
                "update_available": has_update,
            })
        except Exception as e:
            self._send_json({"error": str(e)}, 500)


def run_server(host="127.0.0.1", port=3700):
    """Start the Nexus API server."""
    server = HTTPServer((host, port), NexusAPIHandler)
    logger.info(f"Nexus API running on http://{host}:{port}")
    logger.info(f"NEXUS_HOME: {NEXUS_HOME}")

    router = get_router()
    if router:
        models = router.get_available_models()
        logger.info(f"Ollama models: {models.get('ollama', [])}")
        logger.info(f"Anthropic: {'yes' if models.get('anthropic') else 'no'}")
        logger.info(f"OpenAI: {'yes' if models.get('openai') else 'no'}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nexus Backend API")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=3700, help="Port (default: 3700)")
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Nexus Model Router — Intelligent task routing across model tiers.

Routes tasks to the optimal model based on complexity classification:
- Local small (qwen2.5:0.5b) for simple queries
- Local large (qwen2.5:7b / qwen2.5-coder:7b) for medium tasks
- Cloud economy (Claude Sonnet) for complex tasks
- Cloud premium (Claude Opus) for critical tasks

A fast 0.5b classifier triages each task. Skills bypass classification
via task_hint for deterministic routing.

Usage:
    from model_router import ModelRouter
    router = ModelRouter()
    for token in router.generate("What is Bitcoin?"):
        print(token, end="")

CLI:
    python model_router.py classify "What is Bitcoin?"
    python model_router.py route "Write a 2000 word blog post"
    python model_router.py models
"""

import json
import logging
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger("nexus.router")

# ============================================================================
# Configuration
# ============================================================================

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Model tier definitions
TIERS = {
    "local_small": {"provider": "ollama", "model": "qwen2.5:0.5b"},
    "local_large": {"provider": "ollama", "model": "qwen2.5:7b"},
    "local_code": {"provider": "ollama", "model": "qwen2.5-coder:7b"},
    "cloud_economy": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    "cloud_premium": {"provider": "anthropic", "model": "claude-opus-4-20250514"},
}

# Task type → complexity → tier
ROUTING_TABLE = {
    "simple_qa": {
        "low": "local_small",
        "medium": "local_large",
        "high": "cloud_economy",
        "critical": "cloud_premium",
    },
    "content_gen": {
        "low": "local_large",
        "medium": "local_large",
        "high": "cloud_economy",
        "critical": "cloud_premium",
    },
    "code": {
        "low": "local_code",
        "medium": "local_large",
        "high": "cloud_economy",
        "critical": "cloud_premium",
    },
    "analysis": {
        "low": "local_large",
        "medium": "cloud_economy",
        "high": "cloud_premium",
        "critical": "cloud_premium",
    },
    "safety": {
        "low": "local_large",
        "medium": "cloud_economy",
        "high": "cloud_premium",
        "critical": "cloud_premium",
    },
    "financial": {
        "low": "local_large",
        "medium": "cloud_economy",
        "high": "cloud_premium",
        "critical": "cloud_premium",
    },
}

# Keyword heuristic fallback when 0.5b fails to parse
KEYWORD_HINTS = {
    "financial": ["trade", "invest", "portfolio", "money", "profit", "loss", "roi", "stock", "crypto", "market"],
    "code": ["code", "function", "class", "debug", "error", "import", "script", "compile", "program", "api"],
    "safety": ["delete", "remove", "deploy", "production", "credentials", "password", "security", "risk"],
    "content_gen": ["write", "blog", "article", "post", "draft", "essay", "story", "generate content"],
    "analysis": ["analyze", "compare", "evaluate", "research", "investigate", "explain why", "deep dive"],
}

COMPLEXITY_KEYWORDS = {
    "high": ["detailed", "comprehensive", "thorough", "in-depth", "2000 word", "complex", "advanced"],
    "low": ["what is", "define", "simple", "quick", "yes or no", "how many", "when did"],
}


@dataclass
class RoutingDecision:
    """Result of routing a task to a model tier."""
    tier: str
    provider: str
    model: str
    task_type: str
    complexity: str
    reason: str
    classification_source: str  # "0.5b", "heuristic", "task_hint"

    def to_dict(self) -> dict:
        return {
            "tier": self.tier,
            "provider": self.provider,
            "model": self.model,
            "task_type": self.task_type,
            "complexity": self.complexity,
            "reason": self.reason,
            "classification_source": self.classification_source,
        }


class ModelRouter:
    """Routes tasks to optimal model tiers based on classification."""

    def __init__(self, nexus_home: Optional[str] = None):
        self.home = Path(nexus_home or os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
        self.ollama_url = OLLAMA_URL
        self._available_models = None
        self._anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        self._openai_key = os.environ.get("OPENAI_API_KEY")

    # ========================================================================
    # Public API
    # ========================================================================

    def get_available_models(self) -> dict:
        """Probe Ollama and check cloud API availability."""
        if self._available_models is not None:
            return self._available_models

        result = {"ollama": [], "anthropic": False, "openai": False}

        # Probe Ollama
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
            result["ollama"] = [m["name"] for m in data.get("models", [])]
        except Exception:
            pass

        # Check cloud keys
        result["anthropic"] = bool(self._anthropic_key)
        result["openai"] = bool(self._openai_key)

        self._available_models = result
        return result

    def classify(self, task: str) -> dict:
        """Classify a task using 0.5b for fast JSON classification.

        Returns dict with 'type' and 'complexity' keys.
        Falls back to keyword heuristic if 0.5b fails.
        """
        available = self.get_available_models()
        classifier_model = TIERS["local_small"]["model"]

        if classifier_model in available["ollama"]:
            result = self._classify_with_model(task, classifier_model)
            if result:
                return result

        # Heuristic fallback
        return self._classify_heuristic(task)

    def route(self, task: str, context: Optional[str] = None, task_hint: Optional[str] = None) -> RoutingDecision:
        """Classify then pick the optimal model for this task.

        Args:
            task: The task description or prompt
            context: Optional context for better classification
            task_hint: Skip classification — directly specify task type
                       (e.g., "simple_qa", "content_gen", "code")
        """
        if task_hint:
            # Skills pass task_hint to skip 0.5b classification
            classification = self._hint_to_classification(task_hint)
            source = "task_hint"
        else:
            classification = self.classify(task)
            source = classification.get("_source", "0.5b")

        task_type = classification["type"]
        complexity = classification["complexity"]

        # Look up tier from routing table
        tier_name = ROUTING_TABLE.get(task_type, ROUTING_TABLE["simple_qa"]).get(
            complexity, "local_large"
        )

        # Resolve tier to actual available model
        tier_name, provider, model = self._resolve_tier(tier_name, task_type)

        return RoutingDecision(
            tier=tier_name,
            provider=provider,
            model=model,
            task_type=task_type,
            complexity=complexity,
            reason=f"{task_type}/{complexity} -> {tier_name}",
            classification_source=source,
        )

    def generate(
        self,
        prompt: str,
        task: Optional[str] = None,
        context: Optional[str] = None,
        task_hint: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        """Route and stream tokens from the selected model.

        Args:
            prompt: The full prompt to send
            task: Task description for classification (defaults to prompt)
            context: Optional context
            task_hint: Skip classification (for skills)
            system_prompt: Optional system prompt
        """
        decision = self.route(task or prompt, context, task_hint)
        logger.info(f"Routed to {decision.model} ({decision.reason})")

        if decision.provider == "ollama":
            yield from self._call_ollama(prompt, decision.model, system_prompt)
        elif decision.provider == "anthropic":
            yield from self._call_anthropic(prompt, decision.model, system_prompt)
        elif decision.provider == "openai":
            yield from self._call_openai(prompt, decision.model, system_prompt)
        else:
            yield f"[Error: unknown provider {decision.provider}]"

    def generate_sync(
        self,
        prompt: str,
        task: Optional[str] = None,
        context: Optional[str] = None,
        task_hint: Optional[str] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Non-streaming generation for skills. Returns complete response."""
        return "".join(self.generate(prompt, task, context, task_hint, system_prompt))

    # ========================================================================
    # Classification
    # ========================================================================

    def _classify_with_model(self, task: str, model: str) -> Optional[dict]:
        """Use 0.5b model for fast JSON classification."""
        classify_prompt = (
            'Classify this task. Respond ONLY with JSON.\n'
            '{"type":"<simple_qa|content_gen|code|analysis|safety|financial>",'
            '"complexity":"<low|medium|high|critical>"}\n'
            f'Task: {task[:500]}'
        )

        try:
            payload = json.dumps({
                "model": model,
                "prompt": classify_prompt,
                "stream": False,
                "options": {"num_predict": 100, "temperature": 0.1},
            }).encode()

            req = urllib.request.Request(
                f"{self.ollama_url}/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())

            response_text = data.get("response", "").strip()

            # Try to extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                task_type = result.get("type", "").lower()
                complexity = result.get("complexity", "").lower()

                valid_types = set(ROUTING_TABLE.keys())
                valid_complexities = {"low", "medium", "high", "critical"}

                if task_type in valid_types and complexity in valid_complexities:
                    return {"type": task_type, "complexity": complexity, "_source": "0.5b"}

        except Exception as e:
            logger.debug(f"0.5b classification failed: {e}")

        return None

    def _classify_heuristic(self, task: str) -> dict:
        """Keyword-based fallback classification."""
        task_lower = task.lower()

        # Detect task type
        task_type = "simple_qa"
        best_score = 0
        for ttype, keywords in KEYWORD_HINTS.items():
            score = sum(1 for kw in keywords if kw in task_lower)
            if score > best_score:
                best_score = score
                task_type = ttype

        # Detect complexity
        complexity = "medium"
        if len(task.split()) < 8:
            complexity = "low"
        for kw in COMPLEXITY_KEYWORDS.get("high", []):
            if kw in task_lower:
                complexity = "high"
                break
        for kw in COMPLEXITY_KEYWORDS.get("low", []):
            if kw in task_lower:
                complexity = "low"
                break

        return {"type": task_type, "complexity": complexity, "_source": "heuristic"}

    def _hint_to_classification(self, hint: str) -> dict:
        """Convert a task_hint to a classification dict."""
        # task_hint can be "simple_qa", "content_gen", "code", etc.
        # Optionally "code:high" for explicit complexity
        parts = hint.split(":")
        task_type = parts[0] if parts[0] in ROUTING_TABLE else "simple_qa"
        complexity = parts[1] if len(parts) > 1 and parts[1] in {"low", "medium", "high", "critical"} else "medium"
        return {"type": task_type, "complexity": complexity, "_source": "task_hint"}

    # ========================================================================
    # Tier Resolution
    # ========================================================================

    def _resolve_tier(self, tier_name: str, task_type: str) -> tuple:
        """Resolve a tier name to an actually available (tier, provider, model).

        Falls back gracefully: cloud -> local_large -> local_small -> error.
        """
        available = self.get_available_models()
        tier_def = TIERS.get(tier_name, TIERS["local_large"])

        # Use code model for code tasks at local_large tier
        if task_type == "code" and tier_name in ("local_large", "local_code"):
            code_model = TIERS["local_code"]["model"]
            if code_model in available["ollama"]:
                return "local_code", "ollama", code_model

        # Try the requested tier
        if tier_def["provider"] == "ollama":
            if tier_def["model"] in available["ollama"]:
                return tier_name, tier_def["provider"], tier_def["model"]
        elif tier_def["provider"] == "anthropic":
            if available["anthropic"]:
                return tier_name, "anthropic", tier_def["model"]
        elif tier_def["provider"] == "openai":
            if available["openai"]:
                return tier_name, "openai", tier_def["model"]

        # Fallback chain: try each tier from cloud down to local
        fallback_order = ["cloud_economy", "local_large", "local_code", "local_small"]
        for fb_tier in fallback_order:
            fb_def = TIERS[fb_tier]
            if fb_def["provider"] == "ollama" and fb_def["model"] in available["ollama"]:
                return fb_tier, fb_def["provider"], fb_def["model"]
            if fb_def["provider"] == "anthropic" and available["anthropic"]:
                return fb_tier, "anthropic", fb_def["model"]

        # Last resort: use whatever Ollama has
        if available["ollama"]:
            return "local_fallback", "ollama", available["ollama"][0]

        return tier_name, tier_def["provider"], tier_def["model"]

    # ========================================================================
    # Provider Calls
    # ========================================================================

    def _call_ollama(
        self, prompt: str, model: str, system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Stream tokens from Ollama. Reuses urllib pattern from nexus_ui.py."""
        payload_dict = {
            "model": model,
            "prompt": prompt,
            "stream": True,
        }
        if system_prompt:
            payload_dict["system"] = system_prompt

        payload = json.dumps(payload_dict).encode()
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
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
            yield f"\n[Ollama error: {e}]"

    def _call_anthropic(
        self, prompt: str, model: str, system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Stream tokens from Anthropic API."""
        if not self._anthropic_key:
            yield "[Error: ANTHROPIC_API_KEY not set]"
            return

        messages = [{"role": "user", "content": prompt}]
        payload_dict = {
            "model": model,
            "max_tokens": 4096,
            "messages": messages,
            "stream": True,
        }
        if system_prompt:
            payload_dict["system"] = system_prompt

        payload = json.dumps(payload_dict).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self._anthropic_key,
                "anthropic-version": "2023-06-01",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            if data.get("type") == "content_block_delta":
                                text = data.get("delta", {}).get("text", "")
                                if text:
                                    yield text
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"\n[Anthropic error: {e}]"

    def _call_openai(
        self, prompt: str, model: str, system_prompt: Optional[str] = None
    ) -> Generator[str, None, None]:
        """Stream tokens from OpenAI-compatible API."""
        if not self._openai_key:
            yield "[Error: OPENAI_API_KEY not set]"
            return

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": model,
            "messages": messages,
            "max_tokens": 4096,
            "stream": True,
        }).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._openai_key}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for raw_line in resp:
                    line = raw_line.decode("utf-8").strip()
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            token = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                            if token:
                                yield token
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            yield f"\n[OpenAI error: {e}]"


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Nexus Model Router")
    parser.add_argument("--home", default=None, help="Nexus home directory")
    sub = parser.add_subparsers(dest="command")

    # classify
    cls_p = sub.add_parser("classify", help="Classify a task")
    cls_p.add_argument("task", help="Task to classify")

    # route
    route_p = sub.add_parser("route", help="Route a task to a model")
    route_p.add_argument("task", help="Task to route")
    route_p.add_argument("--hint", default=None, help="Task hint (skip classification)")

    # generate
    gen_p = sub.add_parser("generate", help="Generate a response")
    gen_p.add_argument("prompt", help="Prompt text")
    gen_p.add_argument("--hint", default=None, help="Task hint")
    gen_p.add_argument("--system", default=None, help="System prompt")

    # models
    sub.add_parser("models", help="List available models")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    router = ModelRouter(args.home)

    if args.command == "classify":
        result = router.classify(args.task)
        result.pop("_source", None)
        print(json.dumps(result, indent=2))

    elif args.command == "route":
        decision = router.route(args.task, task_hint=args.hint)
        print(json.dumps(decision.to_dict(), indent=2))

    elif args.command == "generate":
        for token in router.generate(args.prompt, task_hint=args.hint, system_prompt=args.system):
            sys.stdout.write(token)
            sys.stdout.flush()
        print()

    elif args.command == "models":
        models = router.get_available_models()
        print(json.dumps(models, indent=2))


if __name__ == "__main__":
    main()

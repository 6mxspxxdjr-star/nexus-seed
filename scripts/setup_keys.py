#!/usr/bin/env python3
"""
Nexus API Key Setup — Interactive wizard for configuring cloud model access.

Stores keys in ~/nexus/configs/keys.json with restricted file permissions.
Called automatically on first launch or via: python setup_keys.py

Usage:
    python setup_keys.py              # Interactive setup
    python setup_keys.py --list       # Show configured providers
    python setup_keys.py --remove anthropic  # Remove a key
"""

import json
import os
import stat
import sys
from pathlib import Path

NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
KEYS_FILE = NEXUS_HOME / "configs" / "keys.json"

PROVIDERS = {
    "anthropic": {
        "name": "Anthropic (Claude)",
        "env_var": "ANTHROPIC_API_KEY",
        "prefix": "sk-ant-",
        "models": "Claude Sonnet 4, Claude Opus 4",
        "url": "https://console.anthropic.com/settings/keys",
    },
    "openai": {
        "name": "OpenAI (GPT)",
        "env_var": "OPENAI_API_KEY",
        "prefix": "sk-",
        "models": "GPT-4o, GPT-4o-mini",
        "url": "https://platform.openai.com/api-keys",
    },
}

# ANSI colors
CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
DIM = "\033[2m"
BOLD = "\033[1m"
NC = "\033[0m"


def load_keys() -> dict:
    """Load keys from the secure keys file."""
    if KEYS_FILE.exists():
        try:
            return json.loads(KEYS_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_keys(keys: dict):
    """Save keys to file with restricted permissions."""
    KEYS_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEYS_FILE.write_text(json.dumps(keys, indent=2))
    # Restrict file permissions (owner read/write only)
    try:
        if sys.platform == "win32":
            # Windows: use icacls to restrict access
            import subprocess
            username = os.environ.get("USERNAME", "")
            if username:
                subprocess.run(
                    ["icacls", str(KEYS_FILE), "/inheritance:r",
                     "/grant:r", f"{username}:(R,W)"],
                    capture_output=True,
                )
        else:
            os.chmod(KEYS_FILE, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def inject_keys():
    """Load keys from file and set as environment variables.

    Call this at startup so the model router can find them.
    """
    keys = load_keys()
    for provider_id, info in PROVIDERS.items():
        key = keys.get(provider_id)
        if key and not os.environ.get(info["env_var"]):
            os.environ[info["env_var"]] = key


def list_keys():
    """Show which providers are configured."""
    keys = load_keys()
    print(f"\n{BOLD}  Configured API Keys{NC}\n")
    for pid, info in PROVIDERS.items():
        key = keys.get(pid, "")
        env_key = os.environ.get(info["env_var"], "")
        if key:
            masked = key[:8] + "..." + key[-4:]
            print(f"  {GREEN}●{NC} {info['name']}: {DIM}{masked}{NC}")
        elif env_key:
            masked = env_key[:8] + "..." + env_key[-4:]
            print(f"  {GREEN}●{NC} {info['name']}: {DIM}{masked} (from env){NC}")
        else:
            print(f"  {DIM}○{NC} {info['name']}: {DIM}not configured{NC}")
    print()


def interactive_setup():
    """Run the interactive key setup wizard."""
    print(f"\n{CYAN}{BOLD}  Nexus — API Key Setup{NC}\n")
    print(f"  Cloud models give Nexus access to more powerful reasoning.")
    print(f"  Keys are stored locally in {DIM}{KEYS_FILE}{NC}")
    print(f"  {DIM}Press Enter to skip any provider.{NC}\n")

    keys = load_keys()
    changed = False

    for pid, info in PROVIDERS.items():
        existing = keys.get(pid, "")
        env_key = os.environ.get(info["env_var"], "")

        if existing:
            masked = existing[:8] + "..." + existing[-4:]
            print(f"  {GREEN}●{NC} {BOLD}{info['name']}{NC} — {info['models']}")
            print(f"    Current: {DIM}{masked}{NC}")
            try:
                resp = input(f"    Update? (y/N): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if resp != "y":
                continue
        elif env_key:
            masked = env_key[:8] + "..." + env_key[-4:]
            print(f"  {GREEN}●{NC} {BOLD}{info['name']}{NC} — {info['models']}")
            print(f"    Found in environment: {DIM}{masked}{NC}")
            try:
                resp = input(f"    Save to Nexus keyfile? (Y/n): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if resp != "n":
                keys[pid] = env_key
                changed = True
                print(f"    {GREEN}Saved.{NC}")
            continue
        else:
            print(f"  {DIM}○{NC} {BOLD}{info['name']}{NC} — {info['models']}")
            print(f"    Get a key: {DIM}{info['url']}{NC}")

        try:
            key = input(f"    API key: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not key:
            print(f"    {DIM}Skipped.{NC}\n")
            continue

        # Basic validation
        if pid == "anthropic" and not key.startswith("sk-ant-"):
            print(f"    {YELLOW}Warning: Anthropic keys usually start with 'sk-ant-'{NC}")
        elif pid == "openai" and not key.startswith("sk-"):
            print(f"    {YELLOW}Warning: OpenAI keys usually start with 'sk-'{NC}")

        keys[pid] = key
        changed = True
        print(f"    {GREEN}Saved.{NC}\n")

    if changed:
        save_keys(keys)
        inject_keys()
        print(f"  {GREEN}{BOLD}Keys saved to {KEYS_FILE}{NC}\n")
    else:
        print(f"  {DIM}No changes made.{NC}\n")

    return keys


def remove_key(provider: str):
    """Remove a specific provider's key."""
    keys = load_keys()
    if provider in keys:
        del keys[provider]
        save_keys(keys)
        print(f"  {GREEN}Removed {provider} key.{NC}")
    else:
        print(f"  {DIM}{provider} key not found.{NC}")


def has_any_keys() -> bool:
    """Check if any API keys are configured (file or environment)."""
    keys = load_keys()
    if keys:
        return True
    for info in PROVIDERS.values():
        if os.environ.get(info["env_var"]):
            return True
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nexus API Key Setup")
    parser.add_argument("--list", action="store_true", help="Show configured keys")
    parser.add_argument("--remove", type=str, help="Remove a provider's key")
    parser.add_argument("--check", action="store_true", help="Exit 0 if keys exist, 1 if not")
    args = parser.parse_args()

    if args.list:
        list_keys()
    elif args.remove:
        remove_key(args.remove)
    elif args.check:
        sys.exit(0 if has_any_keys() else 1)
    else:
        interactive_setup()


if __name__ == "__main__":
    main()

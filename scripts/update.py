#!/usr/bin/env python3
"""
Nexus Updater — Pull latest changes and redeploy.

Usage:
    python update.py          # Update from GitHub
    python update.py --check  # Check if update is available (no changes)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPO_URL = "https://github.com/6mxspxxdjr-star/nexus-seed.git"
REPO_API = "https://api.github.com/repos/6mxspxxdjr-star/nexus-seed/commits/master"
NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
VERSION_FILE = NEXUS_HOME / "configs" / ".version"

CYAN = "\033[0;36m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
DIM = "\033[2m"
BOLD = "\033[1m"
NC = "\033[0m"


def log(msg):
    print(f"{CYAN}[nexus]{NC} {msg}")


def ok(msg):
    print(f"{GREEN}[  ok ]{NC} {msg}")


def warn(msg):
    print(f"{YELLOW}[ warn]{NC} {msg}")


def get_current_version() -> str:
    """Read the stored commit hash."""
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return ""


def save_version(commit_hash: str):
    """Store the current commit hash."""
    VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSION_FILE.write_text(commit_hash)


def get_remote_version() -> str:
    """Check the latest commit on GitHub."""
    try:
        req = urllib.request.Request(REPO_API, headers={"User-Agent": "nexus-updater"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data.get("sha", "")[:12]
    except Exception:
        return ""


def check_update() -> bool:
    """Check if an update is available."""
    current = get_current_version()
    remote = get_remote_version()

    if not remote:
        warn("Could not check for updates (no network?)")
        return False

    if current == remote:
        ok(f"Nexus is up to date ({current})")
        return False
    else:
        log(f"Update available: {current or 'unknown'} -> {remote}")
        return True


def update():
    """Pull latest and redeploy files."""
    print(f"\n{CYAN}{BOLD}  Nexus Updater{NC}\n")

    # Check for git
    git_cmd = shutil.which("git")
    if not git_cmd:
        warn("git not found. Install git and try again.")
        sys.exit(1)

    # Clone to temp dir
    log("Downloading latest version...")
    clone_dir = Path(tempfile.mkdtemp()) / "nexus-seed"

    result = subprocess.run(
        [git_cmd, "clone", "--depth", "1", REPO_URL, str(clone_dir)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        warn(f"Clone failed: {result.stderr.strip()}")
        sys.exit(1)
    ok("Downloaded latest version")

    # Get commit hash
    result = subprocess.run(
        [git_cmd, "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, cwd=str(clone_dir),
    )
    commit = result.stdout.strip() if result.returncode == 0 else "unknown"

    # Deploy files
    log("Deploying updated files...")

    # Scripts
    scripts_src = clone_dir / "scripts"
    scripts_dst = NEXUS_HOME / "scripts"
    scripts_dst.mkdir(parents=True, exist_ok=True)
    for f in scripts_src.iterdir():
        if f.is_file():
            shutil.copy2(f, scripts_dst / f.name)
            ok(f"  scripts/{f.name}")

    # Agents
    for agent in ["strategist", "guardian", "worker", "evolution"]:
        src = clone_dir / "agents" / agent / "IDENTITY.md"
        dst = NEXUS_HOME / "agents" / agent / "IDENTITY.md"
        if src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # Skills
    skills_src = clone_dir / "skills"
    if skills_src.exists():
        for skill_dir in skills_src.iterdir():
            if skill_dir.is_dir():
                dst = NEXUS_HOME / "skills" / skill_dir.name
                dst.mkdir(parents=True, exist_ok=True)
                for f in skill_dir.iterdir():
                    if f.is_file():
                        shutil.copy2(f, dst / f.name)

    # Configs (don't overwrite keys.json or user.yaml)
    configs_src = clone_dir / "configs"
    configs_dst = NEXUS_HOME / "configs"
    protected = {"keys.json", "user.yaml"}
    for f in configs_src.rglob("*"):
        if f.is_file() and f.name not in protected:
            rel = f.relative_to(configs_src)
            dst = configs_dst / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dst)

    # Optimizer
    opt_src = clone_dir / "optimizer"
    opt_dst = NEXUS_HOME / "optimizer"
    if opt_src.exists():
        opt_dst.mkdir(parents=True, exist_ok=True)
        for f in opt_src.iterdir():
            if f.is_file():
                shutil.copy2(f, opt_dst / f.name)

    # UI and launcher
    for fname in ["nexus_ui.py", "launch.bat", "nexus.ico", "README.md"]:
        src = clone_dir / fname
        if src.exists():
            shutil.copy2(src, NEXUS_HOME / fname)

    # Save version
    save_version(commit)

    # Cleanup
    shutil.rmtree(clone_dir.parent, ignore_errors=True)

    print(f"\n{GREEN}{BOLD}  Nexus updated to {commit}{NC}")
    print(f"  {DIM}Restart Nexus to use the new version.{NC}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Nexus Updater")
    parser.add_argument("--check", action="store_true", help="Check for updates only")
    args = parser.parse_args()

    if args.check:
        has_update = check_update()
        sys.exit(0 if not has_update else 2)
    else:
        update()


if __name__ == "__main__":
    main()

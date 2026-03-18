#Requires -Version 5.1
<#
.SYNOPSIS
    Nexus Installer for Windows
.DESCRIPTION
    One-command install:
    powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/6mxspxxdjr-star/nexus-seed/master/install.ps1 | iex"
#>
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# === Configuration ===
$NexusHome = if ($env:NEXUS_HOME) { $env:NEXUS_HOME } else { "$env:USERPROFILE\nexus" }
$SkipModels = $env:NEXUS_SKIP_MODELS -eq "1"
$LogFile = "$env:TEMP\nexus-install-$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# === Logging ===
function Log($msg)  { $l = "[nexus] $msg"; Write-Host $l -ForegroundColor Cyan;  Add-Content $LogFile $l }
function Ok($msg)   { $l = "[  ok ] $msg"; Write-Host $l -ForegroundColor Green;  Add-Content $LogFile $l }
function Warn($msg) { $l = "[ warn] $msg"; Write-Host $l -ForegroundColor Yellow; Add-Content $LogFile $l }
function Err($msg)  { $l = "[error] $msg"; Write-Host $l -ForegroundColor Red;    Add-Content $LogFile $l }

# === Banner ===
Write-Host ""
Write-Host "  _   _ _____ __  __ _   _ ____  " -ForegroundColor Cyan
Write-Host " | \ | | ____|\ \/ /| | | / ___| " -ForegroundColor Cyan
Write-Host " |  \| |  _|   \  / | | | \___ \ " -ForegroundColor Cyan
Write-Host " | |\  | |___  /  \ | |_| |___) |" -ForegroundColor Cyan
Write-Host " |_| \_|_____|/_/\_\ \___/|____/ " -ForegroundColor Cyan
Write-Host ""
Write-Host "  Autonomous Intelligence System - Windows Installer" -ForegroundColor White
Write-Host "  Install log: $LogFile" -ForegroundColor DarkGray
Write-Host ""

# === Platform Detection ===
Log "Detecting platform..."
$RAM_GB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
$Arch = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else { "x86" }
Ok "Windows $([Environment]::OSVersion.Version) ($Arch)"
Ok "RAM: ${RAM_GB}GB"

if ($RAM_GB -lt 8) { Warn "Low RAM (${RAM_GB}GB < 8GB). Will use smaller models." }

# Choose model based on RAM
$OllamaLLM = if ($RAM_GB -ge 16) { "qwen2.5:14b" } elseif ($RAM_GB -ge 8) { "qwen2.5:7b" } else { "qwen2.5:3b" }
Log "Selected LLM model: $OllamaLLM (based on ${RAM_GB}GB RAM)"

# === Helper: Check if command exists ===
function Test-Command($cmd) {
    $null = Get-Command $cmd -ErrorAction SilentlyContinue
    return $?
}

# === Helper: winget install with retry ===
function Install-Winget($id, $name) {
    if (Test-Command "winget") {
        Log "Installing $name via winget..."
        winget install --id $id --accept-package-agreements --accept-source-agreements --silent 2>$null
        if ($LASTEXITCODE -eq 0) { Ok "$name installed" } else { Warn "$name install may need manual action" }
    } else {
        Warn "winget not available. Please install $name manually."
    }
}

# ============================================================================
# DEPENDENCY INSTALLATION
# ============================================================================
Write-Host "`n--- Installing Dependencies ---`n" -ForegroundColor Blue

# --- Git ---
if (-not (Test-Command "git")) {
    Install-Winget "Git.Git" "Git"
    $env:Path = "$env:Path;$env:ProgramFiles\Git\cmd"
}
if (Test-Command "git") { Ok "Git: $(git --version 2>&1)" } else { Err "Git not found - install from https://git-scm.com" }

# --- Python ---
$PythonCmd = $null
foreach ($cmd in @("python3.12", "python3.11", "python3", "python", "py")) {
    if (Test-Command $cmd) {
        try {
            $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            $parts = $ver -split '\.'
            if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 11) {
                $PythonCmd = $cmd
                break
            }
        } catch {}
    }
}
# Try py launcher
if (-not $PythonCmd -and (Test-Command "py")) {
    try {
        $ver = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        $parts = $ver -split '\.'
        if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 11) { $PythonCmd = "py -3" }
    } catch {}
}
if (-not $PythonCmd) {
    Install-Winget "Python.Python.3.12" "Python 3.12"
    $env:Path = "$env:Path;$env:LOCALAPPDATA\Programs\Python\Python312;$env:LOCALAPPDATA\Programs\Python\Python312\Scripts"
    $PythonCmd = "python"
}
if ($PythonCmd) {
    $pyver = & $PythonCmd -c "import sys; print(sys.version)" 2>$null
    Ok "Python: $pyver"
} else { Err "Python 3.11+ not found" }

# --- Node.js ---
if (-not (Test-Command "node")) {
    Install-Winget "OpenJS.NodeJS" "Node.js"
    $env:Path = "$env:Path;$env:ProgramFiles\nodejs"
}
if (Test-Command "node") { Ok "Node: $(node --version 2>&1)" } else { Warn "Node.js not installed (optional)" }

# --- Ollama ---
if (-not (Test-Command "ollama")) {
    Install-Winget "Ollama.Ollama" "Ollama"
    $env:Path = "$env:Path;$env:LOCALAPPDATA\Programs\Ollama"
}
if (Test-Command "ollama") { Ok "Ollama: $(ollama --version 2>&1)" } else { Warn "Ollama not found - install from https://ollama.com" }

# ============================================================================
# DIRECTORY STRUCTURE
# ============================================================================
Write-Host "`n--- Creating Directory Structure ---`n" -ForegroundColor Blue

$dirs = @(
    "memory\00_Core", "memory\01_Conversations", "memory\02_Research", "memory\03_Content",
    "memory\04_Simulations", "memory\05_Decisions", "memory\06_Archive",
    "memory\.system\chroma", "memory\.system\reports",
    "agents\strategist", "agents\guardian", "agents\worker", "agents\evolution",
    "skills\search-memory", "skills\store-memory", "skills\ask-questions", "skills\create-agent",
    "skills\run-simulation", "skills\guardian-review", "skills\trading-simulator",
    "skills\lead-generator", "skills\content-creator",
    "configs", "configs\sandbox", "scripts", "simulations", "optimizer"
)
foreach ($d in $dirs) { New-Item -ItemType Directory -Path "$NexusHome\$d" -Force | Out-Null }
Ok "Directory structure created at $NexusHome"

# ============================================================================
# PYTHON VIRTUAL ENVIRONMENT
# ============================================================================
Write-Host "`n--- Setting Up Python Environment ---`n" -ForegroundColor Blue

$VenvDir = "$NexusHome\.venv"
$VenvPython = "$VenvDir\Scripts\python.exe"
$VenvPip = "$VenvDir\Scripts\pip.exe"

if (-not (Test-Path $VenvPython)) {
    Log "Creating virtual environment..."
    if ($PythonCmd -eq "py -3") {
        & py -3 -m venv $VenvDir
    } else {
        & $PythonCmd -m venv $VenvDir
    }
    Ok "Virtual environment created"
} else {
    Ok "Virtual environment already exists"
}

Log "Installing Python packages..."
& $VenvPip install --upgrade pip setuptools wheel -q 2>$null
& $VenvPip install -q chromadb sentence-transformers pyyaml requests numpy 2>$null
if ($LASTEXITCODE -eq 0) { Ok "Python packages installed" } else { Warn "Some packages may have failed" }

# Optional packages
foreach ($pkg in @("engramai[all]", "agentmem")) {
    & $VenvPip install -q $pkg 2>$null
    if ($LASTEXITCODE -ne 0) { Warn "Optional package $pkg not available" }
}

# ============================================================================
# OLLAMA MODELS
# ============================================================================
Write-Host "`n--- Pulling Ollama Models ---`n" -ForegroundColor Blue

if ($SkipModels) {
    Warn "Skipping model pulls (NEXUS_SKIP_MODELS=1)"
} elseif (Test-Command "ollama") {
    # Start Ollama if not running
    try { Invoke-RestMethod -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 | Out-Null }
    catch {
        Log "Starting Ollama server..."
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
        Start-Sleep -Seconds 5
    }

    foreach ($model in @("nomic-embed-text", "qwen2.5:0.5b", $OllamaLLM)) {
        Log "Pulling $model..."
        & ollama pull $model 2>$null
        if ($LASTEXITCODE -eq 0) { Ok "$model ready" } else { Warn "Failed to pull $model" }
    }
} else {
    Warn "Ollama not available - skipping model pulls"
}

# ============================================================================
# DEPLOY FILES
# ============================================================================
Write-Host "`n--- Deploying Nexus Files ---`n" -ForegroundColor Blue

# Check if we're running from the repo
$ScriptDir = $PSScriptRoot
$FromRepo = $false
if ($ScriptDir -and (Test-Path "$ScriptDir\scripts\memory_system.py")) {
    $FromRepo = $true
    Log "Installing from local repository at $ScriptDir"
}

if (-not $FromRepo) {
    # Clone the repo
    Log "Cloning nexus-seed repository..."
    $CloneDir = "$env:TEMP\nexus-seed-$(Get-Random)"
    if (Test-Command "git") {
        git clone --depth 1 https://github.com/6mxspxxdjr-star/nexus-seed.git $CloneDir 2>$null
        if ($LASTEXITCODE -eq 0) {
            $ScriptDir = $CloneDir
            $FromRepo = $true
            Ok "Repository cloned"
        } else {
            Warn "Clone failed - generating bootstrap files"
        }
    }
}

if ($FromRepo) {
    Log "Copying files from repository..."

    # Scripts
    foreach ($f in @("memory_system.py", "run_simulation.py", "nightly_consolidation.py", "model_router.py", "rl_signals.py", "first-boot.sh", "test.sh")) {
        $src = "$ScriptDir\scripts\$f"
        if (Test-Path $src) { Copy-Item $src "$NexusHome\scripts\" -Force }
    }

    # Agents
    foreach ($a in @("strategist", "guardian", "worker", "evolution")) {
        $src = "$ScriptDir\agents\$a\IDENTITY.md"
        if (Test-Path $src) { Copy-Item $src "$NexusHome\agents\$a\" -Force }
    }

    # Skills
    foreach ($s in @("search-memory", "store-memory", "ask-questions", "create-agent", "run-simulation", "guardian-review", "trading-simulator", "lead-generator", "content-creator")) {
        $src = "$ScriptDir\skills\$s"
        if (Test-Path $src) { Copy-Item "$src\*" "$NexusHome\skills\$s\" -Force }
    }

    # Configs
    Copy-Item "$ScriptDir\configs\*.yaml" "$NexusHome\configs\" -Force 2>$null
    if (Test-Path "$ScriptDir\configs\sandbox") {
        Copy-Item "$ScriptDir\configs\sandbox\*" "$NexusHome\configs\sandbox\" -Force 2>$null
    }

    # Optimizer
    if (Test-Path "$ScriptDir\optimizer") {
        Copy-Item "$ScriptDir\optimizer\*" "$NexusHome\optimizer\" -Force 2>$null
    }

    # UI & launcher
    if (Test-Path "$ScriptDir\nexus_ui.py") { Copy-Item "$ScriptDir\nexus_ui.py" "$NexusHome\" -Force }
    if (Test-Path "$ScriptDir\launch.bat") { Copy-Item "$ScriptDir\launch.bat" "$NexusHome\" -Force }
    if (Test-Path "$ScriptDir\nexus.ico") { Copy-Item "$ScriptDir\nexus.ico" "$NexusHome\" -Force }
    if (Test-Path "$ScriptDir\README.md") { Copy-Item "$ScriptDir\README.md" "$NexusHome\" -Force }

    Ok "All files deployed from repository"
} else {
    Warn "Could not clone repo. Install manually: git clone https://github.com/6mxspxxdjr-star/nexus-seed.git"
}

# ============================================================================
# CREATE LAUNCH SHORTCUT
# ============================================================================
Write-Host "`n--- Creating Desktop Shortcut ---`n" -ForegroundColor Blue

$ShortcutPath = "$env:USERPROFILE\Desktop\Nexus.lnk"
try {
    $WshShell = New-Object -ComObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut($ShortcutPath)
    $Shortcut.TargetPath = "$NexusHome\launch.bat"
    $Shortcut.WorkingDirectory = $NexusHome
    $Shortcut.Description = "Launch Nexus AI"
    if (Test-Path "$NexusHome\nexus.ico") { $Shortcut.IconLocation = "$NexusHome\nexus.ico" }
    $Shortcut.Save()
    Ok "Desktop shortcut created"
} catch {
    Warn "Could not create shortcut"
}

# ============================================================================
# VALIDATION
# ============================================================================
Write-Host "`n--- Running Validation ---`n" -ForegroundColor Blue

$pass = 0; $fail = 0
function Test-Check($name, $condition) {
    if ($condition) { Ok $name; $script:pass++ } else { Warn $name; $script:fail++ }
}

Test-Check "Directory: $NexusHome" (Test-Path $NexusHome)
Test-Check "Python venv" (Test-Path $VenvPython)
Test-Check "Memory system" (Test-Path "$NexusHome\scripts\memory_system.py")
Test-Check "Model router" (Test-Path "$NexusHome\scripts\model_router.py")
Test-Check "Simulation engine" (Test-Path "$NexusHome\scripts\run_simulation.py")
Test-Check "UI" (Test-Path "$NexusHome\nexus_ui.py")

foreach ($a in @("strategist", "guardian", "worker", "evolution")) {
    Test-Check "Agent: $a" (Test-Path "$NexusHome\agents\$a\IDENTITY.md")
}

$skillCount = (Get-ChildItem "$NexusHome\skills" -Directory).Count
Test-Check "Skills: $skillCount registered" ($skillCount -ge 9)

# ============================================================================
# DONE
# ============================================================================
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Nexus installed successfully!" -ForegroundColor Green
Write-Host "  Location: $NexusHome" -ForegroundColor Green
Write-Host "  Passed: $pass  Warnings: $fail" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  To launch:" -ForegroundColor White
Write-Host "    $VenvPython $NexusHome\nexus_ui.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Or double-click the Nexus shortcut on your Desktop" -ForegroundColor White
Write-Host ""
Write-Host "  Install log: $LogFile" -ForegroundColor DarkGray
Write-Host ""

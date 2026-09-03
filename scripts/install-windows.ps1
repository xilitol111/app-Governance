# One-time local install of this repo's governance hooks for native Windows
# Claude Code CLI/Desktop (PowerShell/cmd, no WSL).
#
# If you're actually running Claude Code inside WSL, use install-local.sh
# instead (run it from within your WSL shell) -- WSL is a real Linux
# environment, so the existing bash-based install applies unmodified there.
# This script exists specifically for native Windows, where a bash script
# with a `#!/bin/bash` shebang won't run without Git Bash, and Claude
# Code's hook runner invokes commands directly rather than through a POSIX
# shell -- see legacy/hooks/session-start.py's docstring for why that file exists
# as a separate, pure-Python twin of hooks/session-start.sh.
#
# Usage (run once, in a PowerShell prompt):
#   irm https://raw.githubusercontent.com/xilitol111/app-Governance/main/scripts/install-windows.ps1 | iex
#
# IMPORTANT CAVEAT: this script was written without access to a real
# Windows machine to test it against, based on how Claude Code's hook
# runner is understood to behave natively on Windows (no shebang support;
# hook commands need an explicit interpreter). If your next Claude Code
# turn shows a hook failing, or hooks visibly not firing at all, that is
# the most likely place something is off -- please report back what you
# see so this script can be corrected for the next person.
#
# What this does, and does NOT do:
# - Installs legacy/hooks/session-start.py, legacy/hooks/archive-turn.py,
#   legacy/hooks/session-end.py, and CLAUDE.md to $env:USERPROFILE\.claude\, and
#   registers them in $env:USERPROFILE\.claude\settings.json (merging into
#   any existing settings.json rather than overwriting it).
# - Bakes the absolute resolved path and interpreter into each hook's
#   command string at install time, rather than relying on Claude Code to
#   expand `~` or an env var inside the command later -- deliberately
#   avoids depending on shell-expansion behavior that wasn't verifiable
#   while writing this.
# - Does NOT touch any project you're currently working in, and does NOT
#   push anything on its own. From here on, archive-turn.py's Stop hook
#   handles collection automatically on every future turn, in any project
#   directory, via its own separate clone of this repo at
#   ~/.claude/governance-usage-mirror used purely for syncing
#   docs/token-usage-events.jsonl.
# - Requires Git for Windows to be installed and already able to
#   `git push` to xilitol111/app-Governance (e.g. via Git Credential
#   Manager, which Git for Windows sets up by default) for usage data to
#   actually leave this machine. Without it, collection still runs locally
#   -- only the push step is skipped, silently, same as any other network
#   failure this hook already tolerates.

$ErrorActionPreference = "Stop"

$GovRaw = "https://raw.githubusercontent.com/xilitol111/app-Governance/main"
$ClaudeDir = Join-Path $env:USERPROFILE ".claude"
$HooksDir = Join-Path $ClaudeDir "hooks"

New-Item -ItemType Directory -Force -Path $HooksDir | Out-Null

Write-Host "Detecting a Python interpreter..."
$PythonCmd = $null
foreach ($candidate in @("python", "py")) {
    try {
        & $candidate --version *> $null
        if ($LASTEXITCODE -eq 0) { $PythonCmd = $candidate; break }
    } catch {
        continue
    }
}
if (-not $PythonCmd) {
    Write-Error "No Python interpreter found (tried 'python' and 'py'). Install Python from https://python.org (check 'Add python.exe to PATH' during setup) and re-run this script."
    exit 1
}
Write-Host "Using Python interpreter: $PythonCmd"

try {
    & git --version *> $null
    if ($LASTEXITCODE -ne 0) { throw "git not found" }
} catch {
    Write-Warning "git was not found on PATH. Local collection will still work, but nothing will sync to GitHub without Git for Windows installed and authenticated: https://git-scm.com/download/win"
}

$Files = @("CLAUDE.md", "legacy/hooks/session-start.py", "legacy/hooks/archive-turn.py", "legacy/hooks/session-end.py")
foreach ($f in $Files) {
    if ($f -eq "CLAUDE.md") {
        $dest = Join-Path $ClaudeDir "CLAUDE.md"
    } else {
        $dest = Join-Path $HooksDir (Split-Path $f -Leaf)
    }
    Write-Host "Fetching $f ..."
    Invoke-WebRequest -Uri "$GovRaw/$f" -OutFile $dest -UseBasicParsing
}

$StartHook = Join-Path $HooksDir "session-start.py"
$StopHook = Join-Path $HooksDir "archive-turn.py"
$EndHook = Join-Path $HooksDir "session-end.py"

$SettingsPath = Join-Path $ClaudeDir "settings.json"
if ((Test-Path $SettingsPath) -and ((Get-Item $SettingsPath).Length -gt 0)) {
    $Settings = Get-Content $SettingsPath -Raw | ConvertFrom-Json
} else {
    $Settings = [PSCustomObject]@{}
}
if (-not $Settings.PSObject.Properties["hooks"]) {
    $Settings | Add-Member -MemberType NoteProperty -Name "hooks" -Value ([PSCustomObject]@{})
}

function Add-GovernanceHook {
    param([string]$EventName, [string]$Command)

    if (-not $Settings.hooks.PSObject.Properties[$EventName]) {
        $Settings.hooks | Add-Member -MemberType NoteProperty -Name $EventName -Value @()
    }
    $existing = @($Settings.hooks.$EventName)
    $alreadyPresent = $false
    foreach ($entry in $existing) {
        foreach ($h in @($entry.hooks)) {
            if ($h.command -eq $Command) { $alreadyPresent = $true }
        }
    }
    if (-not $alreadyPresent) {
        $item = [PSCustomObject]@{ hooks = @([PSCustomObject]@{ type = "command"; command = $Command }) }
        $Settings.hooks.$EventName = $existing + @($item)
    }
}

Add-GovernanceHook -EventName "SessionStart" -Command "$PythonCmd `"$StartHook`""
Add-GovernanceHook -EventName "Stop" -Command "$PythonCmd `"$StopHook`""
Add-GovernanceHook -EventName "SessionEnd" -Command "$PythonCmd `"$EndHook`""

$Settings | ConvertTo-Json -Depth 10 | Set-Content -Path $SettingsPath -Encoding UTF8

Write-Host ""
Write-Host "Installed hooks to $HooksDir and registered them in $SettingsPath."
Write-Host ""
Write-Host "From your next Claude Code CLI turn onward (in any project, anywhere on"
Write-Host "this machine), token usage should be collected automatically."
Write-Host ""
Write-Host "Please verify: start a new Claude Code session in any project and check"
Write-Host "that CLAUDE.md content actually loaded and no hook errors appear. If"
Write-Host "something looks wrong, that's this script's untested Windows assumptions"
Write-Host "showing -- report back what happened."

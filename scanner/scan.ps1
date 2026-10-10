# cv-tailor scheduled scan for Windows.
# install-task.ps1 copies this file into <job-search folder>\scan\ and the Windows Task Scheduler
# runs it from there. It runs Claude Code headless with /cv-tailor:scan and logs each run.
#
#   scan\DRY_RUN         if this file exists, the scan writes nothing to the tracker
#   scan\plugin-dir.txt  optional: a local plugin folder to load (for testing a clone)
#   scan\logs\           one log per run (last 60 kept); errors.log, skipped.log

$ErrorActionPreference = 'Stop'
$ScanDir   = $PSScriptRoot
$Workspace = Split-Path -Parent $ScanDir
$LogDir    = Join-Path $ScanDir 'logs'
$Stamp     = Get-Date -Format 'yyyy-MM-dd_HHmm'
$TimeoutMs = 25 * 60 * 1000   # hard cap so a stuck run can't burn usage
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Line($file, $text) {
    Add-Content -Path (Join-Path $LogDir $file) -Value "$Stamp $text" -Encoding UTF8
}

# One scan at a time: hold an exclusive lock for the whole run.
$LockPath = Join-Path $ScanDir 'scan.lock'
try {
    $Lock = [System.IO.File]::Open($LockPath, 'OpenOrCreate', 'ReadWrite', 'None')
} catch {
    Write-Line 'skipped.log' 'previous scan still running, skipping'
    exit 0
}

try {
    $Claude = (Get-Command claude -ErrorAction SilentlyContinue).Source
    if (-not $Claude) { $Claude = Join-Path $env:USERPROFILE '.local\bin\claude.exe' }
    if (-not (Test-Path $Claude)) { Write-Line 'errors.log' "claude not found ($Claude)"; exit 1 }

    $Tools = 'Read,Write,Edit,Glob,Grep,WebFetch,ToolSearch,ArtifactData,Bash(python:*)'
    $ClaudeArgs = @('-p', '"/cv-tailor:scan auto"', '--model', 'sonnet', '--allowedTools', "`"$Tools`"")
    $PluginFile = Join-Path $ScanDir 'plugin-dir.txt'
    if (Test-Path $PluginFile) {
        $PluginDir = (Get-Content $PluginFile -Raw).Trim()
        if ($PluginDir) { $ClaudeArgs += @('--plugin-dir', "`"$PluginDir`"") }
    }

    $Log = Join-Path $LogDir "scan_$Stamp.log"
    $Err = Join-Path $LogDir "scan_$Stamp.err.log"
    $Proc = Start-Process -FilePath $Claude -ArgumentList $ClaudeArgs -WorkingDirectory $Workspace `
        -NoNewWindow -PassThru -RedirectStandardOutput $Log -RedirectStandardError $Err
    $null = $Proc.Handle   # cache the handle, or ExitCode stays empty after the process ends
    if (-not $Proc.WaitForExit($TimeoutMs)) {
        Stop-Process -Id $Proc.Id -Force
        Write-Line 'errors.log' 'scan killed after 25 minutes'
    } elseif ($Proc.ExitCode -ne 0) {
        Write-Line 'errors.log' "scan exited with code $($Proc.ExitCode)"
    }
    if ((Test-Path $Err) -and (Get-Item $Err).Length -eq 0) { Remove-Item $Err }

    # Keep the last 60 run logs.
    Get-ChildItem $LogDir -Filter 'scan_*.log' | Sort-Object LastWriteTime -Descending |
        Select-Object -Skip 60 | Remove-Item -Force
} catch {
    Write-Line 'errors.log' "runner error: $($_.Exception.Message)"
    exit 1
} finally {
    $Lock.Close()
}

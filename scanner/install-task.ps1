# Install (or update) the cv-tailor scan as a Windows scheduled task for the current user.
#
#   powershell -ExecutionPolicy Bypass -File install-task.ps1 -Workspace "C:\...\job-search"
#       [-Times "09:30,17:30"] [-Days "Sunday,Monday,Tuesday,Wednesday,Thursday"] [-PluginDir "C:\...\cv-tailor"]
#
# The task runs only while this user is signed in to Windows (no password is stored), starts a
# missed run as soon as the computer is available again, and may wake the computer from sleep.
param(
    [Parameter(Mandatory = $true)][string]$Workspace,
    [string]$Times = '09:30,17:30',
    [string]$Days = 'Sunday,Monday,Tuesday,Wednesday,Thursday',
    [string]$PluginDir = '',
    [string]$TaskName = 'cv-tailor scan'
)
$ErrorActionPreference = 'Stop'

$Workspace = (Resolve-Path $Workspace).Path
if (-not (Test-Path (Join-Path $Workspace 'cv-tailor.config.json'))) {
    throw "No cv-tailor.config.json in $Workspace. Run /cv-tailor:cv-setup there first."
}

$ScanDir = Join-Path $Workspace 'scan'
New-Item -ItemType Directory -Force -Path $ScanDir | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'scan.ps1') (Join-Path $ScanDir 'scan.ps1') -Force
$PluginFile = Join-Path $ScanDir 'plugin-dir.txt'
if ($PluginDir) { Set-Content -Path $PluginFile -Value $PluginDir -Encoding UTF8 }
elseif (Test-Path $PluginFile) { Remove-Item $PluginFile }

$DayList = $Days.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ }
$Triggers = foreach ($t in ($Times.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
    New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DayList -At $t
}
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScanDir\scan.ps1`"" `
    -WorkingDirectory $Workspace
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -MultipleInstances IgnoreNew
$Principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Triggers -Settings $Settings `
    -Principal $Principal -Description "cv-tailor job scan for $Workspace" -Force | Out-Null

$Info = Get-ScheduledTaskInfo -TaskName $TaskName
Write-Output "Installed task '$TaskName' for $Workspace"
Write-Output "Times: $Times on $Days"
Write-Output "Next run: $($Info.NextRunTime)"

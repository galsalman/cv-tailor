# Remove the cv-tailor scheduled scan. Your job-search folder, logs and results are kept.
#   powershell -ExecutionPolicy Bypass -File uninstall-task.ps1
param([string]$TaskName = 'cv-tailor scan')
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output "Removed task '$TaskName'. Your job-search folder was not touched."
} else {
    Write-Output "No task named '$TaskName' is installed."
}

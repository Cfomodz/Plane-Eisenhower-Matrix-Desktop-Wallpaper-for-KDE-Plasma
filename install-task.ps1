# install-task.ps1 — Register a Windows Task Scheduler job to refresh the wallpaper.
# Usage (from repo directory, in PowerShell):
#   .\install-task.ps1                  # every 30 minutes (default)
#   .\install-task.ps1 -IntervalMinutes 15

param(
    [int]$IntervalMinutes = 30
)

$ErrorActionPreference = "Stop"

if ($IntervalMinutes -lt 1) {
    Write-Host "Interval must be >= 1 minute."
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PythonScript = Join-Path $ScriptDir "desktop_background.py"

if (-not (Test-Path $PythonScript)) {
    Write-Host "Error: desktop_background.py not found in $ScriptDir"
    exit 1
}

$TaskName = "TodoEisenhowerMatrixWallpaper"

# Find python
$Python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $Python) {
    $Python = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $Python) {
    Write-Host "Error: python not found in PATH."
    exit 1
}

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task '$TaskName'."
}

# Create the scheduled task
$Action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "`"$PythonScript`"" `
    -WorkingDirectory $ScriptDir

$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
    -RepetitionDuration (New-TimeSpan -Days 9999)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Refresh Eisenhower Matrix wallpaper from Microsoft To Do every $IntervalMinutes minute(s)."

Write-Host ""
Write-Host "Scheduled task '$TaskName' created: runs every $IntervalMinutes minute(s)."
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName'"

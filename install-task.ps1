# install-task.ps1
# Add a Windows Task Scheduler job to refresh the Plane Eisenhower matrix wallpaper.
# Run from the repo directory:  powershell -ExecutionPolicy Bypass -File install-task.ps1 [interval_minutes]
# Example:  .\install-task.ps1 30   -> every 30 minutes

param(
    [int]$IntervalMinutes = 30
)

$ErrorActionPreference = "Stop"
$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskName = "PlaneEisenhowerMatrixWallpaper"
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $PythonExe) {
    Write-Error "Python not found in PATH. Install Python and try again."
    exit 1
}

$ScriptPath = Join-Path $RepoDir "desktop_background.py"
if (-not (Test-Path $ScriptPath)) {
    Write-Error "desktop_background.py not found in $RepoDir"
    exit 1
}

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing scheduled task '$TaskName'."
}

# Build the action: run python desktop_background.py from the repo directory
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $RepoDir

# Trigger: repeat every N minutes, starting now, indefinitely
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)

# Settings: allow on battery, don't stop on battery, run whether logged in or not
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Refreshes the Plane Eisenhower Matrix desktop wallpaper every $IntervalMinutes minute(s)." `
    -RunLevel Limited

Write-Host ""
Write-Host "Scheduled task '$TaskName' created: runs every $IntervalMinutes minute(s)."
Write-Host "  Python : $PythonExe"
Write-Host "  Script : $ScriptPath"
Write-Host ""
Write-Host "To remove later:  Unregister-ScheduledTask -TaskName '$TaskName'"

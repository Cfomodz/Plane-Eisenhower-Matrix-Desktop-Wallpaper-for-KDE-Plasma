# install-task.ps1 — Register a Windows Task Scheduler job to refresh the wallpaper.
# No admin required. Usage (from repo directory, in PowerShell):
#   .\install-task.ps1                     # every 30 minutes (default)
#   .\install-task.ps1 -IntervalMinutes 15

param(
    [int]$IntervalMinutes = 30
)

$ErrorActionPreference = 'Stop'

if ($IntervalMinutes -lt 1) {
    Write-Host 'Interval must be >= 1 minute.'
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$MainScript = Join-Path $ScriptDir 'eisenhower-wallpaper.ps1'

if (-not (Test-Path $MainScript)) {
    Write-Host "Error: eisenhower-wallpaper.ps1 not found in $ScriptDir"
    exit 1
}

$TaskName = 'TodoEisenhowerMatrixWallpaper'

# Remove existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task '$TaskName'."
}

# Create the scheduled task (runs as current user, no elevation)
$Action = New-ScheduledTaskAction `
    -Execute 'powershell.exe' `
    -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$MainScript`"" `
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

Write-Host ''
Write-Host "Scheduled task '$TaskName' created: runs every $IntervalMinutes minute(s)."
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName'"

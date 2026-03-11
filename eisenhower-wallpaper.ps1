#Requires -Version 5.1
<#
.SYNOPSIS
    Generates an Eisenhower Matrix desktop wallpaper from Microsoft To Do tasks.
.DESCRIPTION
    Fetches tasks from Microsoft To Do (via Microsoft Graph API), renders them as
    sticky notes on an Eisenhower Matrix image, and sets it as the Windows wallpaper.
    No Python, no admin privileges, no Azure app registration required.
    First run: sign in via browser (device code flow). Tokens are cached for future runs.
.NOTES
    Run: powershell -ExecutionPolicy Bypass -File eisenhower-wallpaper.ps1
#>

# ==========================================
# CONFIGURATION — edit these to customize
# ==========================================
$Script:Config = @{
    # Output image
    OutputPath = [IO.Path]::Combine([Environment]::GetFolderPath('MyPictures'), 'todo_matrix_wallpaper.png')
    Width      = 1920
    Height     = 1080

    # Font (Segoe UI ships with all Windows 10/11 installs)
    FontFamily = 'Segoe UI'

    # Microsoft Graph auth — uses a Microsoft first-party public client ID.
    # No app registration needed. Change TenantId if using a work/school account.
    ClientId = '14d82eec-204b-4c2f-b7e8-296a70dab67e'  # Microsoft Graph Command Line Tools
    TenantId = 'consumers'  # 'consumers' for personal MS accounts, 'common' for any, or your tenant ID

    # Max sticky notes shown per quadrant
    MaxNotesPerQuadrant = 6
    NoteWidth   = 200
    NoteHeight  = 200
    NotePadding = 20

    # Map your Microsoft To Do list names to quadrants (case-insensitive).
    # Create lists in To Do with these names, or change the mapping here.
    ListMapping = @{
        'do it now'        = 'q1'
        'do first'         = 'q1'
        'urgent'           = 'q1'
        'q1'               = 'q1'
        'do it next'       = 'q2'
        'schedule'         = 'q2'
        'planned'          = 'q2'
        'q2'               = 'q2'
        'do if extra time' = 'q3'
        'if time'          = 'q3'
        'someday'          = 'q3'
        'q3'               = 'q3'
        "don't do"         = 'q4'
        "don't do it"      = 'q4'
        'eliminate'         = 'q4'
        'q4'               = 'q4'
    }
}

# ==========================================
# SETUP
# ==========================================
Add-Type -AssemblyName System.Drawing

Add-Type -TypeDefinition @"
using System.Runtime.InteropServices;
public class WallpaperHelper {
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern int SystemParametersInfo(int uAction, int uParam, string lpvParam, int fuWinIni);
}
"@

$Script:TokenCachePath = [IO.Path]::Combine($PSScriptRoot, '.token_cache.json')

# ==========================================
# COLORS
# ==========================================
$Script:Colors = @{
    Background = [Drawing.Color]::White
    Axis       = [Drawing.ColorTranslator]::FromHtml('#333333')
    Text       = [Drawing.Color]::Black
    Q1Note     = [Drawing.ColorTranslator]::FromHtml('#89C4F4')  # Blue
    Q2Note     = [Drawing.ColorTranslator]::FromHtml('#F4B37D')  # Orange
    Q3Note     = [Drawing.ColorTranslator]::FromHtml('#FCE373')  # Yellow
    Q4Note     = [Drawing.ColorTranslator]::FromHtml('#9CA3AF')  # Grey
    Shadow     = [Drawing.ColorTranslator]::FromHtml('#DDDDDD')
}

# ==========================================
# AUTH — Device Code Flow (no app registration)
# ==========================================
function Save-TokenCache($tokenResponse) {
    $obj = @{
        access_token  = $tokenResponse.access_token
        refresh_token = $tokenResponse.refresh_token
        expires_on    = (Get-Date).AddSeconds($tokenResponse.expires_in).ToString('o')
    }
    $obj | ConvertTo-Json | Set-Content -Path $Script:TokenCachePath -Encoding UTF8
}

function Get-GraphToken {
    $authority = "https://login.microsoftonline.com/$($Config.TenantId)/oauth2/v2.0"

    # Try cached refresh token first
    if (Test-Path $Script:TokenCachePath) {
        try {
            $cached = Get-Content $Script:TokenCachePath -Raw | ConvertFrom-Json
            if ($cached.refresh_token) {
                $body = @{
                    client_id     = $Config.ClientId
                    grant_type    = 'refresh_token'
                    refresh_token = $cached.refresh_token
                    scope         = 'Tasks.Read offline_access'
                }
                $resp = Invoke-RestMethod -Uri "$authority/token" -Method POST -Body $body -ErrorAction Stop
                Save-TokenCache $resp
                return $resp.access_token
            }
        } catch {
            Write-Host 'Cached token expired or invalid. Re-authenticating...'
        }
    }

    # Device code flow — user signs in via browser
    $body = @{
        client_id = $Config.ClientId
        scope     = 'Tasks.Read offline_access'
    }
    $deviceCode = Invoke-RestMethod -Uri "$authority/devicecode" -Method POST -Body $body

    Write-Host ''
    Write-Host $deviceCode.message -ForegroundColor Cyan
    Write-Host ''

    # Open browser automatically
    try { Start-Process $deviceCode.verification_uri } catch {}

    # Poll until user completes sign-in
    $pollBody = @{
        client_id   = $Config.ClientId
        grant_type  = 'urn:ietf:params:oauth:grant-type:device_code'
        device_code = $deviceCode.device_code
    }
    $interval = [Math]::Max($deviceCode.interval, 5)
    $deadline = (Get-Date).AddSeconds($deviceCode.expires_in)

    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds $interval
        try {
            $resp = Invoke-RestMethod -Uri "$authority/token" -Method POST -Body $pollBody -ErrorAction Stop
            Save-TokenCache $resp
            Write-Host 'Signed in successfully.' -ForegroundColor Green
            return $resp.access_token
        } catch {
            $errBody = $null
            try { $errBody = $_.ErrorDetails.Message | ConvertFrom-Json } catch {}
            if ($errBody.error -eq 'authorization_pending') { continue }
            if ($errBody.error -eq 'slow_down') { $interval += 5; continue }
            throw $_
        }
    }
    throw 'Device code sign-in timed out.'
}

# ==========================================
# MICROSOFT TO DO — fetch tasks via Graph API
# ==========================================
function Get-TodoTasks {
    $token = Get-GraphToken
    $headers = @{ Authorization = "Bearer $token" }
    $graphBase = 'https://graph.microsoft.com/v1.0'

    # Get all task lists
    try {
        $listsResp = Invoke-RestMethod -Uri "$graphBase/me/todo/lists" -Headers $headers -ErrorAction Stop
    } catch {
        Write-Host "Error fetching To Do lists: $_" -ForegroundColor Red
        return @()
    }

    $tasks = [System.Collections.ArrayList]::new()
    $mapping = $Config.ListMapping

    foreach ($list in $listsResp.value) {
        $listName = ($list.displayName).Trim()
        $quadrant = $mapping[$listName.ToLower()]
        if (-not $quadrant) { continue }

        # Fetch incomplete tasks from this list
        try {
            $uri = "$graphBase/me/todo/lists/$($list.id)/tasks?`$filter=status ne 'completed'"
            $tasksResp = Invoke-RestMethod -Uri $uri -Headers $headers -ErrorAction Stop
        } catch {
            Write-Host "Error fetching tasks from '$listName': $_" -ForegroundColor Yellow
            continue
        }

        foreach ($t in $tasksResp.value) {
            [void]$tasks.Add(@{
                Name     = $t.title
                Quadrant = $quadrant
            })
        }
    }

    return $tasks.ToArray()
}

# ==========================================
# IMAGE GENERATION
# ==========================================
function New-RoundedRectPath([float]$X, [float]$Y, [float]$W, [float]$H, [float]$R) {
    $path = [Drawing.Drawing2D.GraphicsPath]::new()
    $d = $R * 2
    if ($d -gt $W) { $d = $W }
    if ($d -gt $H) { $d = $H }
    $path.AddArc($X, $Y, $d, $d, 180, 90)
    $path.AddArc($X + $W - $d, $Y, $d, $d, 270, 90)
    $path.AddArc($X + $W - $d, $Y + $H - $d, $d, $d, 0, 90)
    $path.AddArc($X, $Y + $H - $d, $d, $d, 90, 90)
    $path.CloseFigure()
    return $path
}

function Get-WrappedLines([string]$Text, [int]$MaxChars) {
    $words = $Text -split '\s+'
    $lines = [System.Collections.ArrayList]::new()
    $current = ''
    foreach ($word in $words) {
        if ($current.Length -gt 0 -and ($current.Length + 1 + $word.Length) -gt $MaxChars) {
            [void]$lines.Add($current)
            $current = $word
        } else {
            if ($current.Length -gt 0) { $current += ' ' }
            $current += $word
        }
    }
    if ($current.Length -gt 0) { [void]$lines.Add($current) }
    return $lines.ToArray()
}

function Draw-CenteredText([Drawing.Graphics]$G, [float]$CX, [float]$CY, [string]$Text,
                           [Drawing.Font]$Font, [Drawing.Brush]$Brush) {
    $sf = [Drawing.StringFormat]::new()
    $sf.Alignment = [Drawing.StringAlignment]::Center
    $sf.LineAlignment = [Drawing.StringAlignment]::Center

    $lines = $Text -split "`n"
    $lineHeight = $G.MeasureString('Ay', $Font).Height
    $totalH = $lines.Count * $lineHeight
    $startY = $CY - $totalH / 2

    foreach ($line in $lines) {
        $size = $G.MeasureString($line, $Font)
        $G.DrawString($line, $Font, $Brush, ($CX - $size.Width / 2), $startY)
        $startY += $lineHeight
    }
}

function Draw-NoteWithText([Drawing.Graphics]$G, [float]$X, [float]$Y, [float]$W, [float]$H,
                           [Drawing.Color]$NoteColor, [string]$Text, [Drawing.Font]$Font) {
    $radius = 10

    # Shadow
    $shadowBrush = [Drawing.SolidBrush]::new($Script:Colors.Shadow)
    $shadowPath = New-RoundedRectPath ($X + 4) ($Y + 4) $W $H $radius
    $G.FillPath($shadowBrush, $shadowPath)
    $shadowBrush.Dispose(); $shadowPath.Dispose()

    # Note background
    $noteBrush = [Drawing.SolidBrush]::new($NoteColor)
    $notePath = New-RoundedRectPath $X $Y $W $H $radius
    $G.FillPath($noteBrush, $notePath)
    $noteBrush.Dispose(); $notePath.Dispose()

    # Text on note
    $lines = Get-WrappedLines $Text 14
    $lineHeight = 26
    $totalTextH = $lines.Count * $lineHeight
    $textY = $Y + ($H - $totalTextH) / 2
    $textBrush = [Drawing.SolidBrush]::new($Script:Colors.Text)

    foreach ($line in $lines) {
        $size = $G.MeasureString($line, $Font)
        $textX = $X + ($W - $size.Width) / 2
        $G.DrawString($line, $Font, $textBrush, $textX, $textY)
        $textY += $lineHeight
    }
    $textBrush.Dispose()
}

function New-WallpaperImage([array]$Tasks) {
    $w = $Config.Width
    $h = $Config.Height
    $bmp = [Drawing.Bitmap]::new($w, $h)
    $g = [Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [Drawing.Text.TextRenderingHint]::ClearTypeGridFit

    # Background
    $bgBrush = [Drawing.SolidBrush]::new($Script:Colors.Background)
    $g.FillRectangle($bgBrush, 0, 0, $w, $h)
    $bgBrush.Dispose()

    # Fonts
    $fontFamily = $Config.FontFamily
    $fontAxis   = [Drawing.Font]::new($fontFamily, 16, [Drawing.FontStyle]::Bold)
    $fontHeader = [Drawing.Font]::new($fontFamily, 18)
    $fontNote   = [Drawing.Font]::new($fontFamily, 13)

    $axisBrush = [Drawing.SolidBrush]::new($Script:Colors.Axis)
    $axisPen   = [Drawing.Pen]::new($Script:Colors.Axis, 3)
    $textBrush = [Drawing.SolidBrush]::new($Script:Colors.Text)

    # Center
    $cx = [int]($w / 2)
    $cy = [int]($h / 2)

    # Axis extents
    $effortMargin = 75
    $hLeft  = $effortMargin + 55
    $hRight = $w - $effortMargin - 55
    $vTop    = 55
    $vBottom = $h - 50
    $arrowLen  = 12
    $arrowHalf = 8

    # Axis lines
    $g.DrawLine($axisPen, ($hLeft + $arrowLen), $cy, ($hRight - $arrowLen), $cy)
    $g.DrawLine($axisPen, $cx, ($vTop + $arrowLen), $cx, ($vBottom - $arrowLen))

    # Arrowheads
    $g.FillPolygon($axisBrush, @(
        [Drawing.PointF]::new($cx, $vTop),
        [Drawing.PointF]::new($cx - $arrowHalf, $vTop + $arrowLen),
        [Drawing.PointF]::new($cx + $arrowHalf, $vTop + $arrowLen)))
    $g.FillPolygon($axisBrush, @(
        [Drawing.PointF]::new($cx, $vBottom),
        [Drawing.PointF]::new($cx - $arrowHalf, $vBottom - $arrowLen),
        [Drawing.PointF]::new($cx + $arrowHalf, $vBottom - $arrowLen)))
    $g.FillPolygon($axisBrush, @(
        [Drawing.PointF]::new($hLeft, $cy),
        [Drawing.PointF]::new($hLeft + $arrowLen, $cy - $arrowHalf),
        [Drawing.PointF]::new($hLeft + $arrowLen, $cy + $arrowHalf)))
    $g.FillPolygon($axisBrush, @(
        [Drawing.PointF]::new($hRight, $cy),
        [Drawing.PointF]::new($hRight - $arrowLen, $cy - $arrowHalf),
        [Drawing.PointF]::new($hRight - $arrowLen, $cy + $arrowHalf)))

    # Axis labels
    Draw-CenteredText $g $cx 30 'High Value' $fontAxis $textBrush
    Draw-CenteredText $g $cx ($h - 35) 'Low Value' $fontAxis $textBrush
    Draw-CenteredText $g $effortMargin $cy "Low`nEffort" $fontAxis $textBrush
    Draw-CenteredText $g ($w - $effortMargin) $cy "High`nEffort" $fontAxis $textBrush

    # Quadrant headers
    $headerTopY    = 60
    $headerBottomY = $cy + 30
    $headers = @{
        q1 = @{ Text = 'Do it now';                    X = [int]($cx / 2);              Y = $headerTopY }
        q2 = @{ Text = 'Do it next';                   X = [int]($cx + ($w - $cx) / 2); Y = $headerTopY }
        q3 = @{ Text = 'Do it if/when there is time';  X = [int]($cx / 2);              Y = $headerBottomY }
        q4 = @{ Text = "Don't do it";                  X = [int]($cx + ($w - $cx) / 2); Y = $headerBottomY }
    }
    foreach ($qh in $headers.Values) {
        Draw-CenteredText $g $qh.X $qh.Y $qh.Text $fontHeader $textBrush
    }

    # Bucket tasks by quadrant
    $buckets = @{ q1 = @(); q2 = @(); q3 = @(); q4 = @() }
    foreach ($task in $Tasks) {
        $q = $task.Quadrant
        if ($buckets.ContainsKey($q)) {
            $buckets[$q] += $task.Name
        }
    }

    # Content areas for each quadrant
    $margin = 50
    $headerBottom = 110
    $qContent = @{
        q1 = @{ Left = $margin;      Top = $headerBottom; Right = $cx - $margin;  Bottom = $cy - $margin }
        q2 = @{ Left = $cx + $margin; Top = $headerBottom; Right = $w - $margin;   Bottom = $cy - $margin }
        q3 = @{ Left = $margin;      Top = $cy + $margin; Right = $cx - $margin;  Bottom = $h - $margin }
        q4 = @{ Left = $cx + $margin; Top = $cy + $margin; Right = $w - $margin;   Bottom = $h - $margin }
    }

    $noteColorMap = @{
        q1 = $Script:Colors.Q1Note
        q2 = $Script:Colors.Q2Note
        q3 = $Script:Colors.Q3Note
        q4 = $Script:Colors.Q4Note
    }

    $nw = $Config.NoteWidth
    $nh = $Config.NoteHeight
    $pad = $Config.NotePadding
    $maxNotes = $Config.MaxNotesPerQuadrant

    foreach ($qKey in @('q1','q2','q3','q4')) {
        $titles = $buckets[$qKey]
        if ($titles.Count -eq 0) { continue }
        if ($titles.Count -gt $maxNotes) { $titles = $titles[0..($maxNotes - 1)] }

        $area = $qContent[$qKey]
        $qw = $area.Right - $area.Left
        $qh2 = $area.Bottom - $area.Top

        $cols = [Math]::Min(3, [Math]::Max(1, [Math]::Floor($qw / ($nw + $pad))))
        $rows = [Math]::Ceiling($titles.Count / $cols)
        $blockW = $cols * $nw + ($cols - 1) * $pad
        $blockH = $rows * $nh + ($rows - 1) * $pad
        $startX = $area.Left + ($qw - $blockW) / 2
        $startY = $area.Top + ($qh2 - $blockH) / 2

        for ($i = 0; $i -lt $titles.Count; $i++) {
            $row = [Math]::Floor($i / $cols)
            $col = $i % $cols
            $nx = [float]($startX + $col * ($nw + $pad))
            $ny = [float]($startY + $row * ($nh + $pad))

            Draw-NoteWithText $g $nx $ny $nw $nh $noteColorMap[$qKey] $titles[$i] $fontNote
        }
    }

    # Save
    $outDir = [IO.Path]::GetDirectoryName($Config.OutputPath)
    if (-not (Test-Path $outDir)) { [void](New-Item -ItemType Directory -Path $outDir -Force) }
    $bmp.Save($Config.OutputPath, [Drawing.Imaging.ImageFormat]::Png)
    Write-Host "Wallpaper saved to: $($Config.OutputPath)"

    # Cleanup
    $fontAxis.Dispose(); $fontHeader.Dispose(); $fontNote.Dispose()
    $axisBrush.Dispose(); $axisPen.Dispose(); $textBrush.Dispose()
    $g.Dispose(); $bmp.Dispose()
}

# ==========================================
# SET WINDOWS WALLPAPER
# ==========================================
function Set-Wallpaper([string]$ImagePath) {
    $absPath = (Resolve-Path $ImagePath).Path
    $SPI_SETDESKWALLPAPER = 0x0014
    $flags = 0x01 -bor 0x02  # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE
    $result = [WallpaperHelper]::SystemParametersInfo($SPI_SETDESKWALLPAPER, 0, $absPath, $flags)
    if ($result) {
        Write-Host 'Wallpaper updated successfully.'
    } else {
        Write-Host 'Failed to set wallpaper.' -ForegroundColor Red
    }
}

# ==========================================
# MAIN
# ==========================================
Write-Host 'Fetching tasks from Microsoft To Do...'
$tasks = @()
try {
    $tasks = @(Get-TodoTasks)
} catch {
    Write-Host "API error: $_" -ForegroundColor Red
}

if ($tasks.Count -eq 0) {
    Write-Host 'No mapped tasks found (or API error). Generating demo matrix...'
    $tasks = @(
        @{ Name = 'Test High Value / Low Effort';  Quadrant = 'q1' }
        @{ Name = 'Test High Value / High Effort'; Quadrant = 'q2' }
        @{ Name = 'Test Low Value / Low Effort';   Quadrant = 'q3' }
        @{ Name = "Test Don't Do It";              Quadrant = 'q4' }
    )
}

Write-Host "Processing $($tasks.Count) tasks..."
New-WallpaperImage $tasks
Set-Wallpaper $Config.OutputPath

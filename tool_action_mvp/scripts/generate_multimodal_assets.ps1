$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$mediaDir = Join-Path $root "data\media"
New-Item -ItemType Directory -Force -Path $mediaDir | Out-Null

Add-Type -AssemblyName System.Drawing

function New-NoticeImage {
    param(
        [string]$Path,
        [string]$Title,
        [string[]]$Lines,
        [System.Drawing.Color]$Accent
    )

    $bitmap = [System.Drawing.Bitmap]::new(1000, 620)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit

    $background = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(248, 249, 251))
    $cardBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::White)
    $textBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(30, 35, 45))
    $mutedBrush = [System.Drawing.SolidBrush]::new([System.Drawing.Color]::FromArgb(88, 96, 110))
    $accentBrush = [System.Drawing.SolidBrush]::new($Accent)
    $borderPen = [System.Drawing.Pen]::new([System.Drawing.Color]::FromArgb(210, 216, 225), 3)

    $graphics.FillRectangle($background, 0, 0, 1000, 620)
    $graphics.FillRectangle($cardBrush, 90, 70, 820, 480)
    $graphics.DrawRectangle($borderPen, 90, 70, 820, 480)
    $graphics.FillRectangle($accentBrush, 90, 70, 820, 18)

    $titleFont = [System.Drawing.Font]::new("Arial", 42, [System.Drawing.FontStyle]::Bold)
    $labelFont = [System.Drawing.Font]::new("Arial", 28, [System.Drawing.FontStyle]::Bold)
    $bodyFont = [System.Drawing.Font]::new("Arial", 30, [System.Drawing.FontStyle]::Regular)

    $graphics.DrawString($Title, $titleFont, $textBrush, 135, 125)
    $y = 220
    foreach ($line in $Lines) {
        $parts = $line.Split(":", 2)
        if ($parts.Length -eq 2) {
            $graphics.DrawString(($parts[0] + ":"), $labelFont, $mutedBrush, 135, $y)
            $graphics.DrawString($parts[1].Trim(), $bodyFont, $textBrush, 330, $y - 2)
        } else {
            $graphics.DrawString($line, $bodyFont, $textBrush, 135, $y)
        }
        $y += 76
    }

    $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    $graphics.Dispose()
    $bitmap.Dispose()
}

New-NoticeImage `
    -Path (Join-Path $mediaDir "meeting_notice.png") `
    -Title "Meeting Notice" `
    -Lines @("Title: Product Sync", "Date: Tomorrow", "Time: 14:00", "Location: Zoom") `
    -Accent ([System.Drawing.Color]::FromArgb(49, 116, 173))

New-NoticeImage `
    -Path (Join-Path $mediaDir "weather_card.png") `
    -Title "Weather Card" `
    -Lines @("Location: Seoul", "Date: Tomorrow", "Forecast: Rain", "Temp: 18 C") `
    -Accent ([System.Drawing.Color]::FromArgb(32, 128, 96))

function New-SpokenWav {
    param(
        [string]$Path,
        [string]$Text
    )

    $voice = New-Object -ComObject SAPI.SpVoice
    $stream = New-Object -ComObject SAPI.SpFileStream
    $stream.Open($Path, 3, $false)
    $voice.AudioOutputStream = $stream
    [void]$voice.Speak($Text, 0)
    $stream.Close()
}

New-SpokenWav `
    -Path (Join-Path $mediaDir "email_instruction.wav") `
    -Text "Send an email to Professor Kim. Subject: Assignment submission. Body: I have submitted the report."

New-SpokenWav `
    -Path (Join-Path $mediaDir "slack_instruction.wav") `
    -Text "Post a Slack message to the project channel. Message: The meeting starts in ten minutes."

Write-Output "Generated multimodal assets in $mediaDir"

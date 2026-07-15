Add-Type -AssemblyName System.Drawing
$size = 256
$bmp = New-Object System.Drawing.Bitmap $size, $size
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit

# Dark rounded background
$bg = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 30, 30, 30))
$bgPath = New-Object System.Drawing.Drawing2D.GraphicsPath
$radius = 48
$bgPath.AddArc(0, 0, $radius * 2, $radius * 2, 180, 90)
$bgPath.AddArc($size - $radius * 2, 0, $radius * 2, $radius * 2, 270, 90)
$bgPath.AddArc($size - $radius * 2, $size - $radius * 2, $radius * 2, $radius * 2, 0, 90)
$bgPath.AddArc(0, $size - $radius * 2, $radius * 2, $radius * 2, 90, 90)
$bgPath.CloseFigure()
$g.FillPath($bg, $bgPath)

# Teal accent shield
$shieldBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 78, 201, 176))
$shieldPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(255, 110, 224, 199)), 4
$shieldPoints = @(
    (New-Object System.Drawing.PointF 128, 44),
    (New-Object System.Drawing.PointF 200, 78),
    (New-Object System.Drawing.PointF 200, 138),
    (New-Object System.Drawing.PointF 128, 212),
    (New-Object System.Drawing.PointF 56, 138),
    (New-Object System.Drawing.PointF 56, 78)
)
$g.FillPolygon($shieldBrush, $shieldPoints)
$g.DrawPolygon($shieldPen, $shieldPoints)

# Dark inner shield for depth
$innerBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 24, 60, 54))
$innerPoints = @(
    (New-Object System.Drawing.PointF 128, 64),
    (New-Object System.Drawing.PointF 184, 90),
    (New-Object System.Drawing.PointF 184, 134),
    (New-Object System.Drawing.PointF 128, 192),
    (New-Object System.Drawing.PointF 72, 134),
    (New-Object System.Drawing.PointF 72, 90)
)
$g.FillPolygon($innerBrush, $innerPoints)

# Checkmark (white) - audit/guard symbol
$checkPen = New-Object System.Drawing.Pen ([System.Drawing.Color]::White), 12
$checkPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
$checkPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
$checkPen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
$g.DrawLine($checkPen, 96, 124, 118, 148)
$g.DrawLine($checkPen, 118, 148, 162, 102)

# Small "D" overlay dot (decision/audit marker) at top-left of shield
$dotBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 215, 163, 58))
$g.FillEllipse($dotBrush, 92, 76, 18, 18)

# Small "A" overlay dot (assumption) at top-right
$dotBrush2 = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 106, 153, 85))
$g.FillEllipse($dotBrush2, 146, 76, 18, 18)

# Small "ΔD" overlay dot at bottom-center
$dotBrush3 = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 244, 135, 113))
$g.FillEllipse($dotBrush3, 119, 168, 18, 18)

$tmp = "$env:TEMP\nohn_icon_tmp.png"
$bmp.Save($tmp, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose()
$bmp.Dispose()
Write-Host "SAVED_TO:$tmp"

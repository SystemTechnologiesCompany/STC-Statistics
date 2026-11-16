param([Parameter(Mandatory=$true)][string]$Stage)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
$projectRoot=Split-Path $PSScriptRoot -Parent
$source=[System.Drawing.Image]::FromFile((Join-Path $projectRoot 'packaging\stc-statistics-desktop.png'))
try {
    foreach ($kind in @('large','small')) {
        $width=if ($kind -eq 'large') {328} else {116}
        $height=if ($kind -eq 'large') {628} else {116}
        $bitmap=[System.Drawing.Bitmap]::new($width,$height)
        $graphics=[System.Drawing.Graphics]::FromImage($bitmap)
        try {
            $graphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#0A0F0D'))
            $graphics.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
            if ($kind -eq 'large') {
                $graphics.DrawImage($source,[System.Drawing.Rectangle]::new(44,82,240,240))
                $font=[System.Drawing.Font]::new('Segoe UI',23,[System.Drawing.FontStyle]::Bold)
                $smallFont=[System.Drawing.Font]::new('Segoe UI',12)
                $brush=[System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#5FD9A0'))
                $muted=[System.Drawing.SolidBrush]::new([System.Drawing.ColorTranslator]::FromHtml('#B7CBC0'))
                $format=[System.Drawing.StringFormat]::new()
                $format.Alignment=[System.Drawing.StringAlignment]::Center
                try {
                    $graphics.DrawString('STC',$font,$brush,[System.Drawing.RectangleF]::new(0,352,328,50),$format)
                    $graphics.DrawString('STATISTICS',$smallFont,$muted,[System.Drawing.RectangleF]::new(0,408,328,32),$format)
                    $graphics.DrawLine([System.Drawing.Pens]::DarkSeaGreen,90,472,238,472)
                } finally { $font.Dispose(); $smallFont.Dispose(); $brush.Dispose(); $muted.Dispose(); $format.Dispose() }
            } else { $graphics.DrawImage($source,[System.Drawing.Rectangle]::new(4,4,108,108)) }
            $bitmap.Save((Join-Path $Stage ('wizard-'+$kind+'.bmp')),[System.Drawing.Imaging.ImageFormat]::Bmp)
        } finally { $graphics.Dispose(); $bitmap.Dispose() }
    }
} finally { $source.Dispose() }

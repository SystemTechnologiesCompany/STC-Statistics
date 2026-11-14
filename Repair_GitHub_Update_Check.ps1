param(
    [string]$RuntimeHome = (Join-Path $env:LOCALAPPDATA 'STCStatistics'),
    [string]$BuildMetadata = (Join-Path $PSScriptRoot 'dist\STC_Statistics_build.json')
)
$ErrorActionPreference = 'Stop'
$build = Get-Content -Raw -LiteralPath $BuildMetadata | ConvertFrom-Json
$digest = [string]$build.payload_sha256
if ($digest -notmatch '^[a-f0-9]{64}$') { throw 'Invalid build metadata.' }
$runtime = Join-Path $RuntimeHome ('runtime-' + $digest.Substring(0,16))
$marker = Join-Path $runtime '.complete'
if (!(Test-Path -LiteralPath $marker) -or (Get-Content -Raw -LiteralPath $marker).Trim() -ne $digest) {
    throw 'Open the matching existing EXE once, let it prepare, then close it.'
}
$python = Join-Path $runtime 'python.exe'
$pythonw = Join-Path $runtime 'pythonw.exe'
if (@(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $python -or $_.Path -eq $pythonw }).Count -gt 0) {
    throw 'Save your work and close STC Statistics before repairing the update checker.'
}
$target = Join-Path $runtime 'app\stc_statistics\updates.py'
if (!(Test-Path -LiteralPath (Join-Path $runtime 'app\stc_statistics\update_flow.py'))) {
    throw 'Enable the in-app updater first with Enable_In_App_Updates.ps1.'
}
$source = Join-Path $PSScriptRoot 'stc_statistics\updates.py'
$backup = $target + '.before-url-repair'
if (!(Test-Path -LiteralPath $backup)) { Copy-Item -LiteralPath $target -Destination $backup }
$temporary = $target + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
try {
    Copy-Item -LiteralPath $source -Destination $temporary
    & $python -B -c 'import ast,sys; from pathlib import Path; ast.parse(Path(sys.argv[1]).read_bytes())' $temporary
    if ($LASTEXITCODE -ne 0) { throw 'Repair failed syntax validation. Installed app was not changed.' }
    Move-Item -LiteralPath $temporary -Destination $target -Force
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
}
Write-Output 'GitHub redirect handling repaired. The EXE and workspace files are unchanged.'
Write-Output 'Publish the corrected v0.5.3 release, then reopen the app and check for updates.'

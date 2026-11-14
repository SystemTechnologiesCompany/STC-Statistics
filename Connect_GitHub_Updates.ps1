param(
    [string]$RuntimeHome = (Join-Path $env:LOCALAPPDATA 'STCStatistics'),
    [string]$BuildMetadata = (Join-Path $PSScriptRoot 'dist\STC_Statistics_build.json')
)
$ErrorActionPreference = 'Stop'

# Configure the existing extracted runtime; never rebuild or replace the EXE.
$build = Get-Content -Raw -LiteralPath $BuildMetadata | ConvertFrom-Json
$digest = [string]$build.payload_sha256
if ($digest -notmatch '^[a-f0-9]{64}$') { throw 'Invalid build metadata.' }
$runtime = Join-Path $RuntimeHome ('runtime-' + $digest.Substring(0,16))
$marker = Join-Path $runtime '.complete'
if (!(Test-Path -LiteralPath $marker)) {
    throw 'Open the existing EXE once and let it finish preparing, then close it and run this script again.'
}
if ((Get-Content -Raw -LiteralPath $marker).Trim() -ne $digest) {
    throw 'Runtime does not match this EXE build.'
}
$config = Join-Path $runtime 'app\stc_statistics\update_config.json'
if (!(Test-Path -LiteralPath $config)) { throw 'The installed update configuration is missing.' }
$backup = $config + '.before-github'
if (!(Test-Path -LiteralPath $backup)) { Copy-Item -LiteralPath $config -Destination $backup }
$settings = @{
    manifest_url = 'https://github.com/SystemTechnologiesCompany/STC-Statistics/releases/latest/download/update.json'
    download_url = 'https://github.com/SystemTechnologiesCompany/STC-Statistics/releases/latest'
}
$temporary = $config + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
try {
    [IO.File]::WriteAllText($temporary, ($settings | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temporary -Destination $config -Force
} finally {
    if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary }
}
Write-Output 'GitHub release checks connected. Restart STC Statistics and open Updates.'
Write-Output 'The EXE was not changed. Checking requires a published release containing update.json.'
Write-Output 'This configures release checks/downloads; automatic patch installation is not implemented yet.'

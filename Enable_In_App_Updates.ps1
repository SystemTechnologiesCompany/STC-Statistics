param(
    [string]$RuntimeHome = (Join-Path $env:LOCALAPPDATA 'STCStatistics'),
    [string]$BuildMetadata = (Join-Path $PSScriptRoot 'dist\STC_Statistics_build.json'),
    [string]$Package = (Join-Path $PSScriptRoot 'releases\bootstrap\STC_Statistics_0.5.1_Update.zip')
)
$ErrorActionPreference = 'Stop'
$build = Get-Content -Raw -LiteralPath $BuildMetadata | ConvertFrom-Json
$digest = [string]$build.payload_sha256
if ($digest -notmatch '^[a-f0-9]{64}$') { throw 'Invalid build metadata.' }
$runtime = Join-Path $RuntimeHome ('runtime-' + $digest.Substring(0,16))
$marker = Join-Path $runtime '.complete'
if (!(Test-Path -LiteralPath $marker) -or (Get-Content -Raw -LiteralPath $marker).Trim() -ne $digest) {
    throw 'Open the existing EXE once, let startup finish, then close it before enabling updates.'
}
$python = Join-Path $runtime 'python.exe'
$pythonw = Join-Path $runtime 'pythonw.exe'
$running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $python -or $_.Path -eq $pythonw })
if ($running.Count -gt 0) { throw 'Close STC Statistics and its notebook kernel first, then run this script again.' }
$installedVersion = (& $python -B -c 'from stc_statistics.version import APP_VERSION; print(APP_VERSION)').Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not read the installed app version.' }
if ([version]$installedVersion -ge [version]'0.5.1') {
    Write-Output 'In-app updates are already enabled. Open STC Statistics and use Updates.'
    exit 0
}
if ($installedVersion -ne '0.5.0') { throw 'This activation package requires STC Statistics 0.5.0.' }
if (!(Test-Path -LiteralPath $Package)) { throw 'The bootstrap update package is missing. Generate it using make_patch.py first.' }
$folder = Join-Path (Join-Path $RuntimeHome 'updates') ([guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $folder -Force | Out-Null
Copy-Item -LiteralPath $Package -Destination (Join-Path $folder 'update.zip')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'stc_statistics\update_installer.py') -Destination (Join-Path $folder 'installer.py')
$job = @{
    runtime = $runtime
    pid = 0
    from_version = '0.5.0'
    version = '0.5.1'
    sha256 = (Get-FileHash -LiteralPath (Join-Path $folder 'update.zip') -Algorithm SHA256).Hash.ToLowerInvariant()
}
[IO.File]::WriteAllText((Join-Path $folder 'job.json'), ($job | ConvertTo-Json), [Text.UTF8Encoding]::new($false))
& $python -B (Join-Path $folder 'installer.py') (Join-Path $folder 'job.json')
if ($LASTEXITCODE -ne 0) { throw ('Updater activation failed. Recovery details: ' + (Join-Path $folder 'status.json')) }
Write-Output 'In-app updates enabled. STC Statistics has reopened. The original EXE is unchanged.'

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
# Keep all installation files within this project.
$taskTemp = Join-Path $PSScriptRoot '.tmp'
New-Item -ItemType Directory -Force -Path $taskTemp | Out-Null
$env:TEMP = $taskTemp
$env:TMP = $taskTemp
$taskPython = $null
$taskCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.14-64\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Python\pythoncore-3.13-64\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe')
)
foreach ($candidate in $taskCandidates) {
    if (Test-Path -LiteralPath $candidate) {
        $taskPython = $candidate
        break
    }
}
if (-not $taskPython) {
    foreach ($name in @('python', 'py')) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            try {
                $resolved = & $command.Source -c 'import sys; print(sys.executable)' 2>$null
                if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $resolved)) {
                    $taskPython = $resolved
                    break
                }
            } catch { }
        }
    }
}
if (-not $taskPython) {
    throw 'Install Python 3.12 or later from python.org, then run Setup again. / Installez Python 3.12 ou une version ultérieure, puis relancez Setup.'
}
$taskVenv = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskVenv)) {
    & $taskPython -m venv --without-pip .venv
    if ($LASTEXITCODE -ne 0) { throw "Could not create Python environment / Creation de l'environnement impossible." }
}
& $taskVenv -m ensurepip --upgrade
if ($LASTEXITCODE -ne 0) { throw 'pip setup failed / Échec de la configuration de pip.' }
$taskCache = Join-Path $PSScriptRoot '.tools\pip-cache'
$taskInstalled = $false
# Retry the full command too: some SSL stream failures bypass pip's download retries.
for ($taskAttempt = 1; $taskAttempt -le 3; $taskAttempt++) {
    Write-Host "Installing dependencies, attempt $taskAttempt/3 / Installation, tentative $taskAttempt/3"
    & $taskVenv -m pip --disable-pip-version-check install --prefer-binary --timeout 60 --retries 2 --resume-retries 5 --cache-dir $taskCache -r requirements.txt
    if ($LASTEXITCODE -eq 0) {
        $taskInstalled = $true
        break
    }
    if ($taskAttempt -lt 3) {
        Write-Host 'Download failed; retrying with cached packages. / Echec du telechargement ; nouvelle tentative.'
    }
}
if (-not $taskInstalled) { throw "Dependency download failed after 3 attempts. Try a different connection and run Setup.cmd again. / Echec apres 3 tentatives. Essayez une autre connexion et relancez Setup.cmd." }
Write-Host 'Ready! Double-click Start.cmd. / Prêt ! Double-cliquez sur Start.cmd.'

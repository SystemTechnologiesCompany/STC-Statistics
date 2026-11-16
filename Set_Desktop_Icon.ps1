# Desktop shortcut only. Does not rebuild/replace the EXE or change in-app logos.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$sourceIcon = Join-Path $PSScriptRoot 'packaging\stc-statistics-desktop.ico'
$application = Join-Path $PSScriptRoot 'dist\STC Statistics.exe'
if (-not (Test-Path -LiteralPath $sourceIcon -PathType Leaf)) {
    throw 'STC desktop icon is missing from packaging/.'
}
if (-not (Test-Path -LiteralPath $application -PathType Leaf)) {
    throw 'STC Statistics.exe was not found in dist/. Keep this script in the app project folder.'
}
$iconFolder = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'STCStatistics\icons'
New-Item -ItemType Directory -Path $iconFolder -Force | Out-Null
$installedIcon = Join-Path $iconFolder 'stc-statistics-desktop.ico'
Copy-Item -LiteralPath $sourceIcon -Destination $installedIcon -Force
$desktopFolder = [Environment]::GetFolderPath('DesktopDirectory')
$shortcutPath = Join-Path $desktopFolder 'STC Statistics.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
# Preserve a valid existing shortcut target and launch arguments.
if (-not $shortcut.TargetPath -or -not (Test-Path -LiteralPath $shortcut.TargetPath -PathType Leaf)) {
    $shortcut.TargetPath = $application
    $shortcut.Arguments = ''
    $shortcut.WorkingDirectory = Split-Path $application -Parent
}
$shortcut.IconLocation = $installedIcon + ',0'
$shortcut.Description = 'STC Statistics'
$shortcut.Save()
# Ask Explorer to refresh icons; no cache deletion or Explorer restart.
try {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class STCDesktopIconRefresh {
    [DllImport("shell32.dll")]
    public static extern void SHChangeNotify(uint eventId, uint flags, IntPtr item1, IntPtr item2);
}
'@
    [STCDesktopIconRefresh]::SHChangeNotify(0x08000000,0,[IntPtr]::Zero,[IntPtr]::Zero)
} catch { Write-Verbose 'Explorer will refresh the icon on its next normal refresh.' }
Write-Output 'STC Statistics desktop shortcut updated. EXE and in-app logos unchanged.'

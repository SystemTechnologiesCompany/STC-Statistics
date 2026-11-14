# GitHub updates

Repository: https://github.com/SystemTechnologiesCompany/STC-Statistics

The source updater is configured to request:

`https://github.com/SystemTechnologiesCompany/STC-Statistics/releases/latest/download/update.json`

GitHub must have a published, non-prerelease release containing an asset named exactly `update.json`. Until that exists, checking for updates will fail. A repository alone is not an update feed. No release has been published by this change.

## Connect the existing EXE once

1. Launch the existing `dist/STC Statistics.exe` once, let startup finish, then close the app.
2. Open PowerShell in this project and run `powershell -NoProfile -ExecutionPolicy Bypass -File .\Connect_GitHub_Updates.ps1`.
3. Reopen the same EXE and go to Updates. Check uses the feed above; Download opens the latest release page until a newer manifest supplies a specific download link.

The script uses `dist/STC_Statistics_build.json` to identify the matching extracted runtime. It verifies the runtime completion marker, backs up the existing config and changes only the update URLs. It does not rebuild, recompile or replace the EXE. If you use a custom `STC_RUNTIME_HOME`, pass the same directory using `-RuntimeHome`.

## Release feed format

The current checker accepts a JSON object with `version` (`major.minor.patch`), `download_url` (an HTTPS asset URL), and optional `release_notes`. The release packaging command also produces a `sha256` field, but the current checker does not verify or install downloads. Do not describe a source ZIP as an installable app patch.

The existing `make_release.py` prepares complete source releases or full Windows releases. An actual app patch format, validated installer, restart/rollback behavior and test release still need implementation before testing patch installation end to end. Keep the existing EXE unchanged for that work.

## Publish project changes

Commit and push the configuration, this guide and the connection script using VS Code Source Control. Publishing a GitHub Release is a separate action. The ignored `dist/`, `build/`, `.venv/`, `.tmp/` and release ZIPs should stay out of Git source commits.

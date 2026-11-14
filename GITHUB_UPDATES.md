# In-app updates through GitHub Releases

Repository: https://github.com/SystemTechnologiesCompany/STC-Statistics

The existing EXE remains the original 0.5.0 binary. Application code updates independently inside its extracted private runtime; no EXE rebuild is needed.

## Activate the updater once

1. Save your current work and close STC Statistics and its notebook kernel.
2. If the EXE has never started, open dist/STC Statistics.exe, let preparation finish, then close it.
3. Run this from the project PowerShell terminal:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Enable_In_App_Updates.ps1
~~~

The bootstrap package is releases/bootstrap/STC_Statistics_0.5.1_Update.zip. The script uses dist/STC_Statistics_build.json to identify the matching extracted runtime, verifies its marker and activates 0.5.1 using its private interpreter. It retains the old app directory and opens the updated app. Re-running after activation reports that updates are already enabled. Use -RuntimeHome if you have a custom runtime cache.

This activation is necessary because the original EXE embeds an updater that only opens browser downloads. Connect_GitHub_Updates.ps1 configures release URLs but does not enable patch installation.

## Publish the first test update

Prepared assets:

- releases/test/STC_Statistics_0.5.2_Update.zip
- releases/test/update.json

On GitHub, create a release at tag **v0.5.2** and attach both files with those exact names. Publish it as the normal latest release, not a draft or prerelease. No release is published automatically.

The activated app checks:

https://github.com/SystemTechnologiesCompany/STC-Statistics/releases/latest/download/update.json

Open Updates, click Check for updates, then **Update app**. The test release changes the displayed version to 0.5.2 and exercises download, verification, workspace saving, installation, restart and restoration.

## Update and recovery behavior

- Download progress displays transferred MiB and supports cancellation. A modal progress window protects the workspace from edits; the Updates page also displays its progress bar.
- SHA-256, archive paths, source/target versions, Python compatibility and Python syntax are checked. Cancellation or a failed download/check leaves the current app and unsaved work open.
- Before installation, a recovery project saves the working dataset, notebook code/results, chart/statistical/report settings, selected page, editor positions and project/dirty state. Installation does not start if saving fails.
- The app closes, a separate helper swaps application directories, and the new app loads the checkpoint. Startup acknowledgement follows successful workspace loading and a running Qt event loop.
- Failed installation/startup restores the previous app directory and reopens the checkpoint. Previous app files, failed app files, recovery projects, status.json and restart.log remain in the runtime/update cache.
- Original Excel files, user project files and the EXE are not overwritten.

Arbitrary live Python variables outside df are not serialized; rerun their notebook cells after restarting. This patch format keeps the same bundled Python and third-party libraries. Changes requiring new dependencies need a separate runtime update design. Backups are deliberately retained; no automatic deletion of user data is performed.

## Build later updates

~~~powershell
.venv\Scripts\python.exe make_patch.py --version 0.5.3 --from-version 0.5.2 --output releases\0.5.3 --notes "Describe the changes"
~~~

Repeat --from-version only when the update has been verified against every listed source version. The builder creates a complete application-code patch and update.json with SHA-256 and exact download size; it excludes the interpreter, libraries and EXE. It writes the target version inside the package without changing the working source version. Publish using the exact tag and asset names in update.json.

Qt network-reply tests cover progress/cancellation/failures; real private-runtime subprocess tests cover installation, restart, workspace restoration and rollback. Live GitHub downloads require the release assets to be published first. Never publish intentionally broken diagnostic packages from .tmp.

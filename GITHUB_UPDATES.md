# In-app updates through GitHub Releases

## Current release: v1.0.1

Publish a normal GitHub Release with the exact tag **v1.0.1** and attach these two matching files:

- `releases/1.0.1/STC_Statistics_1.0.1_Update.zip`
- `releases/1.0.1/update.json`

Upload both assets before publishing. Their names and the tag case must match the URL inside the JSON. Existing 0.5.6 setup customers use Updates → Check for updates → Update app. This release changes application code only and keeps their bundled interpreter, libraries and activation. No new EXE or installer was rebuilt. See [V1_RELEASE.md](V1_RELEASE.md) for the feature scope and validation limits.

Version 1.0.1 adds preview-based decimal-comma preparation to Map Studio/3D Studio and actionable numeric-selection validation (STC-SCI102). It supports the existing 1.0.0 application plus compatible 0.5.1–0.5.6 patch updaters. The 1.0.0 assets are retained unchanged. The instructions below include historical bootstrap/test releases; do not publish those old versions instead of v1.0.1.

**0.5.6 licensing update:** Supabase activation has been deployed and the developer's live verification passed (signed activation, saved-token validation and second-seat rejection). The desktop public key is provisioned. The application-only release candidate is in `releases/0.5.6/`; publish with the exact tag `v0.5.6` and attach both the update ZIP and `update.json`. Have a valid STC UNIC CODE ready before installing. Customers need internet at startup and no Supabase account. Existing EXEs are unchanged. See [SUPABASE_SETUP.md](SUPABASE_SETUP.md) for code administration and [LICENSING.md](LICENSING.md) for protection limits. A physical second-PC test is still recommended before customer rollout.

Repository: https://github.com/SystemTechnologiesCompany/STC-Statistics

New-customer setup: attach `dist/setup/STC_Statistics_0.5.6_Setup.exe` to release `v0.5.6`. Keep the existing application-patch ZIP and `update.json` for in-app updates. The setup checksum JSON is a separate metadata file and must not replace `update.json`. See [WINDOWS_SETUP.md](WINDOWS_SETUP.md).

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

### Repair for GitHub checks in 0.5.1 / 0.5.2

The first published test exposed a URL-validation bug: Qt's display representation decodes spaces in GitHub's signed redirect URLs. The corrected checker uses the fully encoded URL, allows 60 seconds for the redirect chain and displays the actual network error when a check fails.

Save and close the app, then run:

~~~powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Repair_GitHub_Update_Check.ps1
~~~

Publish the corrected assets from releases/0.5.3 as a normal latest **v0.5.3** release, preserving the names STC_Statistics_0.5.3_Update.zip and update.json. That update supports installed versions 0.5.1 and 0.5.2 and keeps the fix after installation. The old published 0.5.2 package predates the fix; do not overwrite the fixed checker by installing that old package after the repair. The repair script changes only the extracted updater module and keeps a backup; it does not change the EXE or workspace files.

- Download progress displays transferred MiB and supports cancellation. A modal progress window protects the workspace from edits; the Updates page also displays its progress bar.
- SHA-256, archive paths, source/target versions, Python compatibility and Python syntax are checked. Cancellation or a failed download/check leaves the current app and unsaved work open.
- Before installation, a recovery project saves the working dataset, notebook code/results, chart/statistical/report settings, selected page, editor positions and project/dirty state. Installation does not start if saving fails.
- The app closes, a separate helper swaps application directories, and the new app loads the checkpoint. Startup acknowledgement follows successful workspace loading and a running Qt event loop.
- Failed installation/startup restores the previous app directory and reopens the checkpoint. Previous app files, failed app files, recovery projects, status.json and restart.log remain in the runtime/update cache.
- Original Excel files, user project files and the EXE are not overwritten.

Arbitrary live Python variables outside df are not serialized; rerun their notebook cells after restarting. This patch format keeps the same bundled Python and third-party libraries. Changes requiring new dependencies need a separate runtime update design. Backups are deliberately retained; no automatic deletion of user data is performed.

## Build later updates

The general-review release is **V0.5.5** (capital V). Upload releases/0.5.5/STC_Statistics_0.5.5_Update.zip and releases/0.5.5/update.json together. The patch supports installed versions 0.5.1 through 0.5.4. The release tag must match the case in the generated download URL. The publisher accepts --tag when you want to choose the tag explicitly.

The Updates help now describes the in-app process; customer instructions do not require manual ZIP extraction or setup scripts. File-operation support codes use STC-Fxxx, input/session issues use STC-Axxx and dataset refresh issues use STC-D101. Technical diagnostics remain local.

Customer messaging policy (0.5.4 and later): the app renders only user_notes.en / user_notes.fr, with a friendly generic fallback for old release feeds. Technical legacy release_notes are never shown in the product. Use --public-notes-en and --public-notes-fr to describe user benefits. Update failures display a friendly localized explanation plus a stable STC-Uxxx support code; full details remain in bounded local logs/update-diagnostics.log under the runtime home. No diagnostic logs are uploaded automatically.

Support codes: STC-U101 (checking connection), STC-U102 (release information), STC-U201 (download), STC-U202 (verification), STC-U301 (workspace saving), STC-U401 (installation), STC-U402 (update preparation). Cancellation is not reported as an error.

The prepared customer-messaging release is v0.5.4: publish releases/0.5.4/STC_Statistics_0.5.4_Update.zip and releases/0.5.4/update.json. Installed versions 0.5.1, 0.5.2 and 0.5.3 are supported. No activation or EXE rebuild is required for an already working 0.5.3 updater.

~~~powershell
.venv\Scripts\python.exe make_patch.py --version 0.5.3 --from-version 0.5.2 --output releases\0.5.3 --notes "Describe the changes"
~~~

Repeat --from-version only when the update has been verified against every listed source version. The builder creates a complete application-code patch and update.json with SHA-256 and exact download size; it excludes the interpreter, libraries and EXE. It writes the target version inside the package without changing the working source version. Publish using the exact tag and asset names in update.json.

Qt network-reply tests cover progress/cancellation/failures; real private-runtime subprocess tests cover installation, restart, workspace restoration and rollback. Live GitHub downloads require the release assets to be published first. Never publish intentionally broken diagnostic packages from .tmp.

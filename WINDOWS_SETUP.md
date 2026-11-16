# STC Statistics Windows setup

Installer: `dist/setup/STC_Statistics_0.5.6_Setup.exe`

Give customers this single file. They do not need Python, pip, VS Code, a source folder or a Supabase account. Setup includes the verified private Python runtime, the licensed 0.5.6 app, its libraries and the new desktop icon. It does not include STC signing keys, issued codes, saved activation tokens or server administration files. The older portable `dist/STC Statistics.exe` is unchanged.

## Installation

1. Close STC Statistics after saving your work.
2. Open the setup EXE. Choose English or French.
3. Review the activation information, choose an installation folder and whether to create a desktop shortcut, then install.
4. Open STC Statistics and enter the code STC issued after purchase. No account registration is required. An internet connection is required at startup.

Target: **Windows 10 (1809 or newer) / Windows 11 x64**, with roughly 650 MB for installed program files and additional space for projects, caches and update backups. Setup blocks older Windows versions, matching the bundled Qt requirements. Other operating systems and 32-bit Windows are not supported by this package. The installer permits x64-compatible systems, but ARM emulation has not been tested. It installs for the current Windows account without administrator rights; another Windows account needs its own installation and licensed seat.

The default directory is `%LOCALAPPDATA%\Programs\STC Statistics`. Projects default to `Documents\STC Statistics`; the user can save them elsewhere. The installed launcher uses its adjacent `runtime/` folder. Application patches replace only `runtime/app/`, preserving Python and libraries. The existing in-app updater works immediately, without the old portable bootstrap script.

## Distribution through GitHub

Attach `STC_Statistics_0.5.6_Setup.exe` to the existing **v0.5.6** GitHub release for new customers. Keep `STC_Statistics_0.5.6_Update.zip` and its `update.json` as the two in-app update assets. The setup's separate `STC_Statistics_0.5.6_Setup.json` records the installer checksum; **do not rename it to update.json** or replace the app-patch feed with it.

First-time customers download Setup. Existing working installations use Updates inside the app. A valid STC UNIC CODE is required for either installation method. Do not distribute owner/test credentials with the download.

This installer is currently **unsigned**: STC has not supplied an Authenticode code-signing certificate. Windows may display an unknown-publisher or SmartScreen prompt. Do not describe it as digitally signed or as tested on every PC. Before university rollout, test on a separate clean Windows PC, including activation, notebook execution, report exports, an in-app update and uninstall. Sign the installer with STC's trusted certificate when one is available.

## Upgrading, repair and uninstall

Setup refuses to overwrite an application patched to a newer version. The check reads the app version rather than relying only on the installed launcher version. Setup and uninstall also refuse to proceed while the updater's installation lock is present. Never delete an active update lock to force an installation.

Use Windows Settings > Apps > STC Statistics > Uninstall, or the Start menu uninstall shortcut. The uninstaller removes generated application/runtime files and installed shortcuts. It preserves saved user projects, the installation's `licensing/` folder, `updates/` recovery checkpoints, user settings and user caches. It therefore may leave the installation folder present. Reinstalling at the same location can reuse the protected activation credential on the same PC/account. The server's seat assignment is not reset by uninstalling; contact STC for a legitimate transfer.

## Rebuilding Setup

`Build_Setup.cmd` invokes `packaging/build_installer.py`. It does not invoke `Build_EXE.cmd` or replace the original portable EXE. The builder:

- Verifies `build/portable/runtime.zip` against the private runtime's recorded SHA-256.
- Excludes the runtime ZIP's old `app/` directory and stages the current licensed source instead.
- Preserves library licenses and publicly distributed certificate-authority bundles.
- Compiles a separate installed launcher with the statistics icon.
- Uses Inno Setup 7+ for long-path support and the dark English/French setup and uninstaller.
- Records a checksum and verifies the original portable EXE remains unchanged.

Set `STC_ISCC` to a trusted Inno Setup 7+ `ISCC.exe` if the compiler is not found. A portable compiler has been prepared in `build/installer-tools/InnoSetup7/` from the official digitally signed Inno Setup download. Inno Setup is copyright Jordan Russell and Martijn Laan; its included license and notices remain in the compiler distribution.

For a repeat compilation from an unchanged, already validated staging directory:

```powershell
.venv\Scripts\python.exe packaging\build_installer.py --reuse-stage
```

Do not reuse an old stage after changing application source. A new app version gets a new staging directory. Keep `build/`, private licensing files and activation credentials out of the public repository and release assets.

## Validation scope

Local tests check the staging checksum, absence of private material, correct current app, runtime path and installed version. The real installed launcher was run with external Python paths removed and PATH restricted to Windows System32; statistics, PCA/confidence intervals, graphs, project archives, Word/Excel exports and the English/French activation screen were exercised. An unlicensed launch did not construct the workbench.

The setup/uninstaller integration harness uses `/STCISOLATED=1` with `/NOICONS` and desktop tasks disabled. This only skips the Windows uninstall-registry entry during an isolated test; it does **not** bypass licensing or replace the app. Normal customer installation registers the uninstaller and creates the selected shortcuts. Profile registry registration and shortcuts need a normal install test outside the managed test environment, where those Windows locations are writable.

# STC Statistics

This project is an English/French Windows statistics application for STC (System Technologies Company).

## Update workflow

- The user wants future changes delivered as update packages so the app's update flow can be tested.
- Do not rebuild, recompile, replace, or redistribute the Windows executable unless the user explicitly requests it. Keep the existing executable as the baseline.
- Test source changes and prepare update packages separately from full executable builds.
- Clearly distinguish checking/downloading releases from installing an application patch. Do not claim an update was installed without testing the installed application.
- The original EXE embeds 0.5.0. Source 0.5.1 implements application-only patches, in-app progress, workspace checkpoints, restart and startup rollback. Enable_In_App_Updates.ps1 installs the one-time bootstrap into the matching extracted runtime, without changing the EXE. Ordinary updates then use GitHub Releases and make_patch.py.
- Patch packages must retain the existing bundled Python/libraries, list compatible source versions and pass checksum/path/version checks. Do not publish the deliberately broken rollback-test package under .tmp.
- User-facing update messages must use friendly English/French wording and STC support codes, never raw exceptions, paths, URLs or technical repair descriptions. Keep diagnostics in bounded local logs. Publish customer-facing summaries in user_notes (en/fr); legacy release_notes are developer metadata and must not be rendered in the app.

## Windows setup wizard

- Build new-customer setup with `packaging/build_installer.py` / `Build_Setup.cmd`, not by replacing the original portable EXE. Setup stages the verified private runtime, excludes its old app, and includes the current licensed source plus a separate installed launcher.
- Use Inno Setup 7+ for long-path support. Default install is for the current user in LocalAppData/Programs so application-only updates remain writable.
- Preserve projects, licensing and update recovery files on uninstall. Never put private signing keys, issued codes or activation credentials into an installer.
- The `/STCISOLATED=1` installer test option skips uninstall-registry registration; use `/NOICONS` and disable desktop tasks with it. It never bypasses activation. Normal customer installs register normally. Do not claim normal profile/registry integration was tested when only isolated tests were possible.

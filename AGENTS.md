# STC Statistics

This project is an English/French Windows statistics application for STC (System Technologies Company).

## Update workflow

- The user wants future changes delivered as update packages so the app's update flow can be tested.
- Do not rebuild, recompile, replace, or redistribute the Windows executable unless the user explicitly requests it. Keep the existing executable as the baseline.
- Test source changes and prepare update packages separately from full executable builds.
- Clearly distinguish checking/downloading releases from installing an application patch. Do not claim an update was installed without testing the installed application.
- The original EXE embeds 0.5.0. Source 0.5.1 implements application-only patches, in-app progress, workspace checkpoints, restart and startup rollback. Enable_In_App_Updates.ps1 installs the one-time bootstrap into the matching extracted runtime, without changing the EXE. Ordinary updates then use GitHub Releases and make_patch.py.
- Patch packages must retain the existing bundled Python/libraries, list compatible source versions and pass checksum/path/version checks. Do not publish the deliberately broken rollback-test package under .tmp.

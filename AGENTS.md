# STC Statistics

This project is an English/French Windows statistics application for STC (System Technologies Company).

## Update workflow

- The user wants future changes delivered as update packages so the app's update flow can be tested.
- Do not rebuild, recompile, replace, or redistribute the Windows executable unless the user explicitly requests it. Keep the existing executable as the baseline.
- Test source changes and prepare update packages separately from full executable builds.
- Clearly distinguish checking/downloading releases from installing an application patch. Do not claim an update was installed without testing the installed application.
- The current 0.5.0 updater checks HTTPS feeds and opens browser downloads; it does not install patches. Its bundled update URLs are currently empty. Adding patch installation requires an explicit implementation/bootstrap strategy compatible with the existing executable; do not silently bypass this by rebuilding the executable.

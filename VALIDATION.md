# Validation status

## Version 0.5.1 updater — 14 November 2026

- PASS: all 52 unittest checks completed with exit code 0. Twelve new patch checks cover archive/checksum validation, trusted release metadata, install locks, directory swap failure, startup rollback, in-app progress/checkpoint/restart dispatch, cancellation, corrupted downloads, checkpoint-write failure, installer-start failure and transient Windows file locks.
- PASS: the real Qt download controller (with a simulated network reply) launched the separate installer, waited for readiness, exited its actual process and reopened the real private-runtime app with the dataset, code, printed output and unsaved state restored. This also verifies the Windows parent-process wait/handshake. The EXE stayed byte-identical.
- PASS: actual bundled-runtime installation 0.5.0 → 0.5.1 → 0.5.2, each followed by real Qt startup and recovery of a saved three-row dataset, notebook cell/results and unsaved workspace state.
- PASS: an intentionally broken 0.5.3 startup triggered rollback to 0.5.2; the recovery project stayed byte-identical. Diagnostic failure artifacts remain under .tmp and must not be published.
- PASS: the existing EXE SHA-256 remained 01e259e9540517130ad35ec27a1a03cc6dccf36e10a1b43471d897018a121ae8. No executable rebuild or replacement was performed.
- PASS: rendered/inspected the Updates progress page in English and French at 1350 × 738; checked the activation script's already-enabled path against the real test runtime.
- Network tests use simulated Qt replies. The GitHub Release assets have not been published by this work, so live GitHub download testing remains pending publication.
- Recovery includes df, notebook code/results and desktop settings. Arbitrary live kernel objects are not serialized. Patches retain the existing Python and installed libraries. Old code, workspace checkpoints and installer status/logs are retained for rollback/recovery.

## Version 0.5.0 — 14 November 2026

- PASS: rebuilt 0.5.0 Windows EXE and launched it with external Python paths removed. Its bundled runtime passed GUI, advanced statistics, typed projects, graph and Word/Excel export diagnostics.
- PASS: the bundled notebook kernel executed a calculation, advanced statistics, a typed project round trip, one HTML table and one PNG graph. The diagnostic runner exited with code 0.
- First extraction exceeded the initial 120-second diagnostic limit. Retrying with a 300-second bound completed successfully; subsequent launches reuse the extracted runtime. Windows ZIP: approximately 214 MiB.

- PASS: 40 unittest checks, including the real IPython kernel, completed with exit code 0. Numerical checks compare confidence intervals and hypothesis tests with SciPy; regression recovers known coefficients; PCA and seeded clustering are checked separately.
- PASS: typed project round trips retain nullable integers larger than 2^53, dates, notebook outputs and chart options. GUI save/open restores the workspace without starting a kernel or executing saved code.
- PASS: editable table exposes all rows, accepts decimal commas, preserves large integer precision and supports missing integer cells. Cleaning leaves its input unchanged. Kernel bridge checks verify data transfer into Python and return modified data to the desktop.
- PASS: report builder accepts selections, result comments and introductions and restores its choices. Existing editable Word/Excel table and original PNG export checks remain passing.
- PASS: RQI/FZI calculations use explicit mD/fraction units and exclude physically invalid porosity/permeability. Depth profiles invert the vertical axis. Permeability classes are editable screening intervals rather than inferred lithology.
- PASS: rendered and inspected French Analysis and Geology at 1350 × 738. All eight navigation links fit; advanced tools are above the fold. Data EN/FR, Charts, Exports, Projects, Updates and Notebook were also rendered.
- The Windows event-loop adapter uses a selector policy for Jupyter/ZeroMQ. This resolved a reproducible invalid-handle exit after all tests had completed. This policy is available in the bundled Python 3.14; Python 3.16 will need a future adapter update.
- Word preview verifies selected content rather than matching Microsoft Word pagination. Word output validation remains structural; no Microsoft Word visual rendering is claimed.
- Projects retain `df` and notebook outputs, not arbitrary live Python objects. Mixed object columns unsupported by Parquet must be normalized before saving. A synchronization error blocks project saving until corrected.

The older entries below describe earlier versions and their limitations.

Checked on 13 November 2026 using Python 3.14.4 on Windows.

- PASS: Python source and test files compile and parse.
- PASS: all interface translation keys exist in English and French.
- PASS: the PowerShell setup script parses successfully.
- PASS: five statistics tests, including sample variance, missing/infinite values, decimal comma conversion, generated code in both languages and multi-sheet Excel round-trip.
- PASS: bilingual GUI and editable-cell test.
- PASS: five-page navigation regression test: selected columns and edited notebook cells persist across all pages; the shared selector moves between Analysis and Charts; current-page headings update in French.
- PASS: chart visibility regression checks. Histogram, box plot and scatter code render with white backgrounds and high-resolution output. Simulated real PNG output opens the dedicated Charts viewer, preserves the source pixel width, supports zoom/fit and exports identical original PNG bytes. The large chart viewer was rendered and inspected in English and French at 1350 × 738. These checks exercise rendering and message handling without starting a kernel.
- PASS: histogram layout regression checks using six-digit X/Y coordinates and negative elevations. Adjacent x-axis label bounding boxes do not overlap, and bar heights exactly equal NumPy's 15-bin histogram counts. Seven selected variables are split into figures with four and three panels. Tall multi-panel figures open at readable width with vertical scrolling; Fit still shows the entire figure.
- PASS: six report/statistics checks: result filtering and executed-code snapshots; typed Excel values and literal formula-like strings; original graph bytes embedded in Word/Excel; valid Word package XML and editable tables; HTML table fallback; selected population statistics/custom percentiles and pairwise Spearman ranks.
- PASS: three GUI workflow checks: statistical options commit correctly; Excel and Word export buttons produce packages without starting a kernel; cell duplication/reordering/output clearing works. The updated Analysis and Exports layouts were rendered and inspected in French.
- Word report verification is structural (XML, relationships, table content and embedded images). Microsoft Word page rendering has not been verified in this environment.
- PASS: update tests cover numeric version ordering, malformed/non-HTTPS sources, disabled unconfigured actions, bilingual navigation, newer/current release states, browser download dispatch, and request/feed processing through a simulated network reply. Release packaging embeds the configured feed and produces a matching archive SHA-256. No live public update endpoint is configured or claimed to be tested.
- Windows EXE 0.4.0: built a single 64-bit GUI executable with embedded private Python/runtime packages and the STC icon. The initial PyInstaller prototype failed its Qt DLL import check and is not the delivered packaging method.
- PASS: launched the final executable with external PYTHONHOME/PYTHONPATH removed and PATH restricted to Windows System32. Its GUI, logo, statistics, Matplotlib graphs and Word/Excel exports passed diagnostics from the bundled private runtime.
- Notebook integration: the bundled interpreter executed a calculation and produced one HTML table and one PNG graph. Its diagnostic report records success. The command runner returned a nonzero code during process shutdown despite the successful result report; clean notebook shutdown remains a limitation of this automated check.
- PASS: PE header verification identifies the deliverable as a Windows x64 GUI executable. Runtime/launcher source and the editable project are retained for future builds.
- PASS: two animation/control tests, including keyboard dropdown selection, arrow and tab animations, hover transitions and reduced motion.
- PASS: rendered and inspected the welcome screen, English/French data views, French notebook and dropdown. System font registration was added for the offscreen Windows renderer.
- LIMITED: full IPython kernel integration could not be completed in this restricted execution session. A bounded diagnostic stalls in Windows socket.accept while creating asyncio's internal socket pair, before kernel startup. The two blocked test processes were stopped. Kernel execution still needs verification outside this session.

The page-based workspace was rendered at 1350 × 738, matching the supplied screenshot size, in addition to the earlier visual checks. This validates the calculations and redesigned interface, not full end-to-end notebook execution. Restart the app with Start.cmd to load the new design. Qt's glass effect is simulated within the app rather than using desktop backdrop blur.

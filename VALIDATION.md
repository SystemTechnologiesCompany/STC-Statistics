# Validation status

## v1.0.1 map input fix — 15 November 2026

- Reproduced the reported missing-column failure with decimal-comma spreadsheet fields. The selectors correctly excluded nonnumeric data, but a missing scalar/coordinate led to a misleading generic engine error.
- PASS: a 131-test source suite, including the three new regression cases for mixed Excel coordinates, decimal-comma scalar preparation/reselection and scalar-free point maps. After the final caption shortening, the installed private-runtime run passed all **36** scientific/studio tests, covering the final captions and input behavior.
- PASS: all four worksheets of the user's supplied workbook through the real Qt cleaning picker/preview/apply path, automatic refreshed selectors and actual map QProcess calculations. Undo preserved each pre-conversion DataFrame and input-file SHA-256 stayed unchanged. The workbook is not included in release assets. Evidence: `.tmp/map-workbook-report.json`, `.tmp/map-workbook.log` and EN/FR `.tmp/map-fix-*.png` captures.
- Data-quality finding: two source POR measurements remain above 100 after representation conversion. They were preserved without inferred decimal placement or unit changes; the user must check the original measurements before treating them as porosity percentages.
- PASS: real isolated **1.0.0 → 1.0.1** application-only installation/restart, retained old-app backup, unchanged checkpoint bytes and enforced activation. The final installed application then passed the 36 bundled-runtime tests and rendered all 17 scientific display modes. Evidence: `.tmp/map-fix-install-report.json`, `.tmp/map-fix-private-runtime-report.json`, `.tmp/map-fix-private-tests.log`.
- Prepared `releases/1.0.1/STC_Statistics_1.0.1_Update.zip` and matching `update.json`, tag **v1.0.1**. No GitHub release was published, no live download is claimed, and the user's customer installation was not changed. Original EXE/setup hashes and the previous 1.0.0 package remain unchanged. Scientific algorithms, source values, licensing protocol and bundled dependencies were not altered.

## V1.0.0 scientific workspaces and application patch — 15 November 2026

- PASS: full source suite **128 tests**, including licensing, updater, projects, statistics, reports and the new workspaces. After the final language-restoration adjustment, the seven focused Qt studio tests passed again.
- PASS: **33 scientific/studio tests** under the existing bundled Python with external Python paths removed and PATH restricted to Windows System32. Imports were verified to come from the isolated private runtime, not the development venv. This includes numerical fixtures, real cancellable QProcess jobs, train/test leakage checks, typed exports, live-camera changes and `.stcp` restoration without retraining.
- PASS: all **17 map/scene/correlation display modes** computed, round-tripped through safe JSON and rendered using bundled libraries. A real defect in empty `(0, 3)` volume mesh restoration was fixed and regression-tested. Rendered modes include hillshade, regional residuals, TIN, scalar slices, voxels, density and scatter matrices. RF/GB diagnostics are exercised by the scientific/studio tests and report probe.
- PASS: actual **0.5.6 → 1.0.0 application-only installation and restart** in an isolated copy of the shipped runtime, using the old runtime's installer helper and the final release ZIP. The old application backup remained, checkpoint bytes were unchanged, and the restarted V1 activation dialog acknowledged its recovered checkpoint in memory. A fresh unlicensed launch retained STC-L100 and did not construct the workbench. No real customer activation credentials were copied or bypassed.
- PASS: actual V1 results produced Word and Excel reports containing **10 tables and 7 figures**, valid package XML/relationships/media and numeric Excel values. Microsoft Word page rendering was not exercised. Full numerical table CSV/Excel exports and native-coordinate ASCII/OBJ geometry are covered separately.
- PASS: the four new workspaces were rendered and visually inspected at **1350 × 738** in English/French. Fixed overlapping control rows, reduced 3D tick crowding and simplified correlation annotations. Dense multi-panel plots retain minimum readable sizes with scrolling; expanded live views returned correctly. Pair counts remain in their full table rather than overprinted inside heatmap cells.
- PASS: final patch validates archive paths, all application hashes, Python syntax/ABI, exact target version and every declared source version 0.5.1–0.5.6. It contains only the application and `patch.json`, without an interpreter, EXE, installer, server, private signing key, issued codes or activation credentials. The original portable EXE and existing setup SHA-256 remain unchanged.
- Evidence: `.tmp/v1-release-tests.log`, `.tmp/v1-studio-release.log`, `.tmp/v1-private-runtime-report.json`, `.tmp/v1-install-report.json`, `.tmp/v1-report-export-report.json`, `.tmp/v1-package-report.json` and the eight `.tmp/v1-*-en/fr.png` page captures. Test runtime work is isolated under `.tmp/v1-runtime-4267ab89`.
- Release assets: `releases/1.0.0/STC_Statistics_1.0.0_Update.zip` and matching `update.json`, tag **v1.0.0**. Nothing was published to GitHub and no live GitHub download of this release has been tested. The customer's actual installed app, existing EXE and setup were not replaced. Physical second-PC/account rollout checks remain outstanding. This release implements the defined tools in [V1_RELEASE.md](V1_RELEASE.md), not complete parity with commercial GIS/geophysics suites.

The following sections record older releases and their historical limitations.

## Windows setup wizard (0.5.6) - 14 November 2026

- Built `dist/setup/STC_Statistics_0.5.6_Setup.exe` with Inno Setup 7.1.1, English/French pages, STC artwork, a separate installed launcher, selectable desktop shortcut, Start menu entries and uninstaller. The source app version and original portable EXE remain 0.5.6 and unchanged baseline 0.5.0 respectively; the portable EXE checksum still matches its recorded value.
- PASS: five installer tests cover the runtime checksum, exclusion of the old unlicensed app, current licensed source, path traversal, private credential/key rejection, retained vendor notices/CA certificates, preservation rules, architecture, OS minimum and downgrade protection.
- PASS: actual installed launcher/private Python diagnostics with external Python paths removed and PATH restricted to Windows System32: descriptive/advanced statistics, PCA, graphs, projects, GUI, Word/Excel exports, ipykernel imports and kernel command. A fresh normal application startup displayed the bilingual activation dialog with STC-L100 and never constructed an unlicensed workbench. The installed runtime satisfied the existing in-app updater checks.
- PASS: actual French setup and uninstall in an isolated workspace directory with Windows uninstall-key registration and shortcuts disabled. Newer app code was not overwritten by older setup; an active update lock blocked setup. Uninstall removed the runtime/application while retaining project, licensing and update recovery sentinels.
- The first Inno 6 build exposed a real long-path rename failure in bundled Qt artifacts and rolled back. The final build requires Inno 7+; the repeated install/uninstall succeeded with extended Windows paths. Final UI/OS configuration requires Windows 10 build 17763 (1809) or newer, matching Qt, and includes a dark title bar. Final installer checksum is recorded separately from the application-patch feed.
- LIMITS: the setup is unsigned (no STC Authenticode certificate supplied). Normal Windows Apps registration/Start menu/desktop creation could not be tested in the restricted profile; only isolated mode was exercised. A separate physical clean Windows PC/second account, live customer activation and actual installed in-app upgrade remain rollout checks. The existing source/runtime and Supabase live checks are recorded below; do not claim testing on every PC.

## Supabase live verification and 0.5.6 release candidate - 14 November 2026

- USER-VERIFIED: the supplied terminal screenshot shows `supabase_setup.py verify` passing live signed activation, saved-token validation and second-seat rejection, and provisioning the desktop public key. The earlier browser screenshot shows the deployed health route responding successfully. No secret codes, tokens or keys were shared in those screenshots.
- PASS: 12 patch/installer tests and 6 update/feed tests after changing the source version to 0.5.6 and provisioning the key.
- Prepared `releases/0.5.6/STC_Statistics_0.5.6_Update.zip` and `update.json` with the exact release tag `v0.5.6` and friendly English/French customer notes. Archive checksum/path/version verification covers all supported bases 0.5.1 through 0.5.5. Server administration, SQL, private signing material and activation credentials are excluded; only the desktop source/assets, public key and endpoint are included.
- Existing EXE checksum is unchanged. The release candidate has not been published, installed or tested in the existing EXE by the assistant. The developer must have a valid code ready for first activation after installing. A real second PC/account test and ordinary customer workflow test remain necessary before university rollout; the live verification used a second device fingerprint.

## Supabase licensing adaptation - 14 November 2026

- PASS: 90 Python tests and 9 Node handler/protocol tests. The Node tests exercise real handler code with a substituted RPC; Python verifies a Node-generated RSA-PSS response through the real Windows CNG verifier and rejects a tampered response.
- Prepared project `zwjhjfgoiofbiyguhcbx`: private PostgreSQL schema/admin functions, backend-only RPC, row locks for seat assignment, hashed codes/tokens, transactional denial counters, and a TypeScript Edge Function with code/token authorization instead of customer Auth accounts. Admin operations are not public routes. Current and legacy server-side Supabase keys are supported without placing keys in the desktop app.
- PASS: public dashboard bundle matches modular sources; no external module dependencies are required. Missing signing material fails before seat assignment; service errors expose only safe STC codes. Failed live setup cannot provision the desktop public key. The unverified build remains blocked from packaging.
- Prepared private signing material locally in an ignored directory; no key values were printed or added to the public function. The desktop endpoint is set but its trusted key remains unconfigured until the live activation/validation/second-seat rejection test succeeds.
- NOT RUN: remote SQL migration/transaction tests, deployed Deno function and real Supabase activation. No authenticated Supabase management access, local Postgres, Deno or Supabase CLI is available here. The supplied project URL alone cannot authorize deployment. `SUPABASE_SETUP.md` gives dashboard steps and `supabase/tests/licensing.sql` rolls back temporary test changes.
- Existing EXE SHA-256 unchanged: `01e259e9540517130ad35ec27a1a03cc6dccf36e10a1b43471d897018a121ae8`. No EXE build or release publication was performed.

## STC UNIC CODE licensing development - 14 November 2026

- PASS: 86 tests, including 18 licensing checks for atomic first activation, rejection of another PC/account, token rotation, revocation, expiry, transfer with a replacement code, private hashed storage, rate limits, malformed requests, missing/corrupt/copied credentials, TLS configuration requirements, RSA-PSS signatures, wrong keys, changed payloads, stale challenges and expiry, bilingual UI, and a gated startup that does not construct the workbench when verification fails.
- PASS: real Windows DPAPI round trip and corrupted-data rejection; stable hashed Windows identity; Windows CNG verification of server signatures. The client adds no third-party runtime dependency. Cryptography is server/test tooling only.
- PASS: separate source-launch integration over locally trusted HTTPS with a real licensing server, signed activation response and DPAPI credential. Startup first acknowledged the saved checkpoint in memory while the workbench was inaccessible; activation then opened the workspace, restored the dataset/notebook, and wrote the normal restored health acknowledgement. This used isolated temporary settings/data, not the production license location.
- PASS: release preparation refuses missing endpoint/key before writing an archive. Public-only client provisioning contains no server secrets. A local HTTP integration verified that activation/validation work and admin/issue/transfer routes are unavailable remotely.
- Rendered and inspected English/French activation screens with STC branding and the supplied LinkedIn purchase/help link. Content scrolls on smaller windows.
- NOT DEPLOYED: no production HTTPS service, signing key or real buyer codes have been provisioned; Docker deployment instructions are prepared but have not been run on a production host. Existing EXE/release files were not rebuilt, changed or published.
- LIMITS: one seat means one PC and Windows account, not verified human identity. Tests simulate a different device fingerprint and verify local encryption; a separate physical second PC/account was not available. Source tampering, old unlicensed builds and full Windows clones remain outside this protection. Online validation occurs at startup; active sessions are not forcibly interrupted.

## General interface review (0.5.5) — 14 November 2026

- PASS: 68 tests completed with exit code 0. Review checks cover bilingual update guidance, inactive update downloads before a release check, accurate project/export wording, dataset naming, safe import failure, method-specific analysis fields, distinct numeric geology defaults, empty report guidance, reload availability and exact release-tag case.
- PASS: project round trips now preserve correlation method, chart type and report-content flags. Statistical options and selected controls mark the project as changed. Update recovery retains the saved dirty state after restoring controls.
- Corrected closing prompts to refer to projects; clarified notebook code import and Word/Excel exports; removed obsolete manual update instructions. The normal Updates help describes in-app download, automatic saving and restart; legacy download-page guidance appears only for legacy releases.
- File-operation errors use friendly localized messages and support codes while diagnostic details remain local. User-written Python errors remain available in notebook results.
- Report builder labels now describe applying a selection, empty reports explain the next action and outdated comments are not assigned to changed results. Advanced analysis ignores irrelevant fields; geology selectors start with distinct numeric columns.
- Rendered all workspace pages and inspected Data, Exports, Geology and Updates at 1350 × 738 in the reviewed English/French states. The application style and EXE were retained.
- Prepared the application-only patch for exact tag V0.5.5 (capital V), with compatible source versions 0.5.1–0.5.4. The builder now accepts an explicit tag to avoid case mismatches.

## Project filename update (same 0.5.4 package)

- New public project saves use .stcp. Older .stcproj and .stcproject files remain readable and save to .stcp without stacking suffixes or overwriting the legacy original.
- PASS: 22 focused project, statistics and update checks, including a real save/reopen and migration of both legacy suffixes with byte-identical originals retained.
- Internal updater checkpoints keep their existing filename contract for compatibility with earlier installer/recovery code. The refreshed 0.5.4 ZIP and feed must be uploaded together; the EXE is unchanged.

## Customer-facing updater messages (0.5.4) — 14 November 2026

- PASS: 58 tests completed with exit code 0. Added checks ensure technical release notes never reach the app, public summaries follow English/French selection, raw exceptions/paths/URLs are hidden, support codes match update stages and diagnostic details remain in local logs.
- PASS: logging failures do not interrupt the user-facing error path. Update logs rotate locally; no automatic diagnostic upload was added.
- Update errors now display friendly text plus STC-Uxxx codes. Release notes render only customer-facing user_notes, with a localized fallback for legacy feeds. Internal update-checkpoint paths no longer appear in the status bar.
- Prepared v0.5.4 application-only update assets compatible with 0.5.1, 0.5.2 and 0.5.3. The original EXE is unchanged; publishing remains a separate user action.

## GitHub release-check repair — 14 November 2026

- Reproduced the redirect regression: QUrl's default PrettyDecoded string introduces a literal space from GitHub's percent-encoded response-content-disposition query. The old validator rejects it; FullyEncoded preserves the valid HTTPS URL.
- PASS: 18 updater/patch tests, including two new regressions for GitHub redirect handling and visible network-error details.
- PASS: the corrected Qt checker read the live published 0.5.2 GitHub feed and reported updates_available with no error. The diagnostic honors the execution host's configured HTTPS proxy; no TLS verification was disabled.
- PASS: ran the one-time repair script against the isolated real private-runtime cache. The production EXE remains unchanged.
- Prepared a corrected 0.5.3 patch compatible with 0.5.1 and 0.5.2; publishing that release remains a separate user action.

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

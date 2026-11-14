# STC Statistics

An English/French Windows app for Excel statistics and editable Python notebook cells.

The interface uses STC's verified website palette: #0A0F0D background, #121A17 surfaces, #3FBF7F emerald, #5FD9A0 highlights, #E8ECE9 text, and #8A968F secondary text. Glass-style panels, pointer-sensitive button highlights, fading dropdowns, rotating chevrons, sliding tabs and cell entry animations are native Qt controls. Enable Reduce motion / Réduire les animations to reduce transitions. The glass effect is drawn inside the app; it does not blur other desktop windows.

## Workspace pages / Pages de travail

Version 0.5 adds seven integrated tools:

| Tool | Where to find it |
| --- | --- |
| Editable data and cleaning | Data: double-click cells; Clean selected columns opens a column picker, operation and preview. Missing-value filling, decimal commas and duplicate removal keep the original file unchanged. Undo/redo restores the previous data change. |
| Advanced statistics | Analysis → Advanced statistics: confidence intervals, multiple regression with an explicit response, one-sample/paired/Welch t-tests, ANOVA, Shapiro normality, standardized PCA and deterministic K-means. Generate a cell, inspect it, then Run. |
| Automatic explanations | Descriptive and advanced analysis cells print English/French interpretations, sample sizes, exclusions and assumptions. These explanations can be exported as report text. |
| Chart customization | Charts → Chart appearance: title, axis labels, color, histogram bins and linear/log scales. Settings apply when generating a new chart cell. Logarithmic axes require positive values. |
| Complete projects | Projects → Save/Open `.stcproj`; Ctrl+S saves a project. Typed data, notebook code/results, selected columns, statistics options, chart settings and report selections travel together. Opening a project never executes code. Arbitrary Python variables outside `df` must be recreated by rerunning the relevant cells. |
| Report builder | Exports → Build and preview report: check results, drag to reorder, add an introduction and result comments, preview, then Save. The existing Word/Excel buttons export that selection. Rebuild the selection when results change. The preview shows report content; Word pagination may differ. |
| Geology workspace | Geology → Configure analysis: assign porosity/permeability or profile/depth columns and units. Generate porosity–permeability plots, RQI/FZI tables, depth profiles and correlation matrices. Matrix columns use the shared Analysis/Charts selection. Editable permeability thresholds provide screening classes, not inferred lithology. |

The data table displays the entire dataset through Qt's virtual table model. Edits and cleaning are transferred into the notebook's `df` before execution; changes to `df` in Python return to the table after execution. A synchronization error is shown if `df` stops being a serializable DataFrame; fix it before saving the project. Parquet preserves numeric/date/nullable types; unsupported mixed object columns must be normalized before saving.

En français : les mêmes outils sont disponibles dans Données, Analyse, Graphiques, Projets, Exportations et Géologie. Les résultats et interprétations restent dans le notebook. Ctrl+S enregistre le projet complet, et l'ouverture n'exécute aucun code. Les variables Python autres que `df` se recréent en réexécutant les cellules nécessaires.

Statistical implementation references: [SciPy statistics](https://docs.scipy.org/doc/scipy/reference/stats.html), [PCA](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html), [K-means](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html). Reservoir indices follow [Amaefule et al., SPE 26436 (1993)](https://doi.org/10.2118/26436-MS): `RQI = 0.0314 sqrt(k/phi)`, `FZI = RQI / (phi/(1-phi))`, with permeability in mD and effective porosity as a fraction.

| Page | Purpose / Fonction |
| --- | --- |
| Data / Données | Open files, view data and row counts. Import settings expand on demand. / Importation, aperçu, effectifs et options d’importation dépliables. |
| Analysis / Analyse | Choose columns, generate statistics or convert numeric text. / Choix des colonnes, statistiques et conversion des nombres. |
| Charts / Graphiques | Choose columns and a chart, then create its editable Python cell. / Choix des colonnes et du graphique, puis génération de sa cellule Python. |
| Python Notebook / Notebook Python | Edit and run cells in the full workspace width. / Modification et exécution des cellules sur toute la largeur disponible. |
| Exports / Exportations | Save Word/Excel reports with tables and graphs, or a Jupyter notebook. / Rapports Word/Excel avec tableaux et graphiques, ou notebook Jupyter. |
| Updates / Mises à jour | View the installed version, check published releases and open an update download. / Version installée, vérification des versions publiées et téléchargement. |

The same column selection is shared between Analysis and Charts. Changing pages preserves data, cells and the Python session. Imports keep you on Data; generated analysis and chart cells open Notebook. / La sélection de colonnes est commune à Analyse et Graphiques. Les données, cellules et la session Python restent disponibles en changeant de page. L’importation reste sur Données ; les cellules générées s’ouvrent dans Notebook.

Completed chart cells automatically open the large result viewer on Charts. Use Fit, wheel/button zoom, drag to pan, Full screen, or Save PNG. Chart settings and the result have separate views. The notebook retains the original image and a View chart button. New generated chart code uses a white plotting background, dark labels, and high-resolution output. Regenerate old chart cells to apply the new styling. / Les graphiques terminés s’ouvrent automatiquement en grand dans Graphiques. Utilisez Ajuster, le zoom, le déplacement, Plein écran et Enregistrer PNG. Les options et le résultat ont des vues séparées. Le notebook conserve l’image originale et un bouton Voir le graphique. Régénérez les anciennes cellules pour appliquer le nouveau style clair et les grandes étiquettes.

## Start / Démarrer

**Windows EXE release:** extract the Windows ZIP and double-click **STC Statistics.exe**. Python and the required packages are bundled; Setup.cmd is not needed. / **Version EXE Windows :** extrayez le ZIP Windows et ouvrez **STC Statistics.exe**. Python et les bibliothèques sont inclus ; Setup.cmd n’est pas nécessaire.

The following steps are for the editable source project only:

1. Double-click **Setup.cmd** once. This requires Python 3.12+ and internet access to download packages. Installation stays inside the project folder.
2. Double-click **Start.cmd**.
3. Select **English** or **Français** at the top right.
4. Click **Try sample data / Essayer un exemple**, or open your Excel file.

If Python is missing, install it from <https://www.python.org/downloads/windows/> first. If setup fails, its window displays the error. To see application errors, run `.venv\Scripts\python.exe main.py` in this folder.

Setup installs PySide6-Essentials, which includes the QtCore, QtGui and QtWidgets modules used by this app, without the unused Addons package. Downloads have retry/resume settings; setup retries the installation up to three times and caches completed downloads. If an SSL transfer error persists, try another connection and rerun Setup.cmd. Certificate verification stays enabled.

Setup installe PySide6-Essentials, qui contient les modules QtCore, QtGui et QtWidgets utilisés par l’application, sans le paquet Addons inutilisé. Les téléchargements peuvent être repris et l’installation est retentée jusqu’à trois fois, avec un cache des téléchargements terminés. Si une erreur SSL persiste, essayez une autre connexion et relancez Setup.cmd. La vérification des certificats reste activée.

## English

- Open `.xlsx`, `.xls`, `.xlsm` or UTF-8 CSV. Choose the worksheet and header row, then reload. CSV separator and decimal character are configurable.
- The Data page displays all imported rows. Double-click a cell to edit it. The table and Python DataFrame stay synchronized after execution.
- Select columns on the left. Numeric columns are selected automatically. Text and date columns are excluded from numerical calculations.
- Click Descriptive statistics, Correlation or a chart. This inserts **editable code** into the notebook. Review it and click Run cell or press Shift+Enter.
- Cells share variables through a separate IPython process. The imported data is named `df`. The last expression displays its result; `print()` and `display()` also work. Inline Matplotlib plots are supported.
- Add cells, run all in order, interrupt, or restart Python. Run all stops after an error. Restart clears variables; rerun the data-loading cell afterwards.
- Text numbers: select the columns, enable Decimal comma if needed, click Convert, then run the generated code. Invalid strings become missing values. The imported source file remains unchanged.
- On Exports, choose tables, graphs, printed results and optionally executed code. Excel reports contain numeric worksheets and embedded graph images. Word reports contain editable tables and original PNG graphs. Both use existing notebook outputs without recalculating values. To export a full dataset, display that table in a notebook cell first. Export notebook saves code and outputs as a standard `.ipynb` usable in Jupyter and VS Code.
- Statistics options lets you choose measures, sample/population variance and extra percentiles (e.g. `5; 95`). Choose Pearson or Spearman before generating a correlation cell. Spearman uses pairwise complete observations and average ranks for ties.
- Cell actions lets you duplicate, move or clear a cell's output. Duplicated cells start without results. Ctrl+Enter and Shift+Enter run a cell; Ctrl+S saves the complete project.
- The `.ipynb ↗` button appends code cells from another notebook for review. It does not run them or load saved outputs. Export before closing to retain your work.

## Français

- Ouvrez un fichier `.xlsx`, `.xls`, `.xlsm` ou CSV UTF-8. Choisissez la feuille et la ligne d’en-tête, puis rechargez. Le séparateur CSV et le caractère décimal sont configurables.
- La page Données affiche les 1 000 premières lignes importées. Python analyse **toutes les lignes**. Cet aperçu reste celui du fichier importé et ne reflète pas les modifications ultérieures de `df` dans Python.
- Sélectionnez les colonnes à gauche. Les colonnes numériques sont cochées automatiquement. Les textes et les dates sont exclus des calculs numériques.
- Cliquez sur Statistiques descriptives, Corrélation ou un graphique pour générer le code. Modifiez-le, puis cliquez sur Exécuter ou utilisez Maj+Entrée.
- Les cellules partagent les variables dans un processus IPython séparé. Les données importées portent le nom `df`. La dernière expression affiche son résultat ; `print()` et `display()` fonctionnent aussi. Les graphiques Matplotlib apparaissent dans les sorties.
- Ajoutez des cellules, exécutez-les dans l’ordre, interrompez un calcul ou redémarrez Python. Tout exécuter s’arrête en cas d’erreur. Après redémarrage, relancez la cellule de chargement.
- Pour les nombres stockés en texte, cochez les colonnes et éventuellement Virgule décimale, puis générez et exécutez la conversion. Les textes non valides deviennent des valeurs manquantes. Le fichier source reste inchangé.
- Dans Exportations, choisissez tableaux, graphiques, résultats imprimés et éventuellement le code exécuté. Excel contient des feuilles numériques et les images des graphiques ; Word contient des tableaux modifiables et les graphiques PNG originaux. Les rapports utilisent les sorties existantes sans recalcul. Pour exporter les données complètes, affichez ce tableau dans une cellule. Le notebook `.ipynb` conserve le code et les sorties pour Jupyter et VS Code.
- Options statistiques permet de choisir les mesures, la variance d’échantillon/de population et des centiles supplémentaires (ex. `5; 95`). Choisissez Pearson ou Spearman avant de générer la corrélation. Spearman utilise les observations complètes par paire et les rangs moyens pour les égalités.
- Actions de cellule permet de dupliquer, déplacer ou effacer les sorties. Une cellule dupliquée n’a pas de résultat. Ctrl+Entrée et Maj+Entrée exécutent ; Ctrl+S enregistre le projet complet.
- Le bouton `.ipynb ↗` ajoute les cellules de code d’un notebook pour lecture. Il n’exécute aucun code et n’importe pas les anciennes sorties. Exportez votre notebook pour conserver votre travail.

## Statistical conventions / Conventions statistiques

Histograms keep 15 bins and show at most four variables per figure. Tick density and panel typography are adjusted for coordinate data. Tall figures open at full readable width; use the vertical scrollbar or drag to see lower panels, or choose Fit to display the entire figure. / Les histogrammes conservent 15 classes et affichent au plus quatre variables par figure. Les graduations et les textes sont adaptés aux coordonnées. Les figures hautes s’ouvrent en pleine largeur ; défilez avec la barre verticale ou déplacez l’image pour voir les panneaux inférieurs, ou utilisez Ajuster pour tout afficher.

- Count excludes missing and infinite values; Missing includes both. / L’effectif exclut les valeurs manquantes et infinies ; elles sont comptées comme manquantes.
- Variance and standard deviation default to sample (`ddof=1`); Statistics options also offers population (`ddof=0`). The output row labels state the convention. / La variance et l’écart-type utilisent par défaut `n−1` ; l’option population utilise `n`. Les noms des lignes précisent la convention.
- Quartiles use linear interpolation. / Les quartiles utilisent l’interpolation linéaire.
- All repeated modes are listed; no repeated values displays `—`. / Tous les modes répétés sont affichés ; aucune répétition donne `—`.
- Skewness and excess kurtosis use pandas estimators. Pearson/Spearman correlations require at least two pairwise complete observations. Undefined values become blank numeric cells in exported reports. / L’asymétrie et l’excès d’aplatissement utilisent pandas. Pearson/Spearman exigent au moins deux observations complètes par paire. Les valeurs indéfinies donnent des cellules numériques vides dans les rapports.
- Excel formulas use cached results last saved by Excel. / Les formules Excel utilisent les dernières valeurs calculées enregistrées par Excel.

## Updating and publishing releases

The Updates page is available in English and French. Checks happen only when requested. The download button opens a configured HTTPS ZIP link in the default browser; it does not execute an installer or replace a running application. Save notebooks, close the app, extract a new release into a new folder, run Setup.cmd, then Start.cmd.

Public release hosting is not configured in this prototype. `stc_statistics/update_config.json` contains empty `manifest_url` and `download_url` settings. The app explicitly shows this state and keeps unavailable actions disabled. STC must publish a ZIP and optionally an `update.json` feed before those actions can be connected. These are ordinary public HTTPS links; no account keys belong in the config.

Publisher workflow:

1. Set the new release version in `stc_statistics/version.py` using `major.minor.patch`.
2. Run `.venv\Scripts\python.exe make_release.py --download-url "PUBLIC_HTTPS_ZIP_URL" --feed-url "PUBLIC_HTTPS_UPDATE_JSON_URL" --notes "Release notes"`, replacing both placeholders with real hosting URLs.
3. Upload the generated `releases/STC_Statistics_VERSION.zip` and `releases/update.json` to those exact URLs. Nothing is uploaded by the script.
4. The generated ZIP contains the update-source settings for future checks. For the current development copy, set the same addresses in `stc_statistics/update_config.json` and restart.

For Windows executable releases, configure `update_config.json` **before** building, run Build_EXE.cmd, then add `--windows-exe` to the publishing command. This packages the EXE rather than source scripts. The publisher verifies that its feed URLs and version match the recorded executable build.

The release feed includes a version, HTTPS download URL, release notes and package SHA-256. The current app compares numeric versions and opens the download in the browser; it does not yet verify the downloaded archive's hash or auto-install it. Keep the feed URL stable across releases and publish the ZIP before its feed entry.

La page Mises à jour ne remplace pas l’application ouverte. Les liens publics sont encore à configurer par STC. Le script de publication prépare le ZIP et le fichier de version, sans les mettre en ligne. Enregistrez vos notebooks, fermez l’application, extrayez la nouvelle version dans un nouveau dossier, puis lancez Setup.cmd et Start.cmd.

## Scope

The Windows 64-bit release is a self-contained executable. On first launch it prepares a private Python runtime under the current user's application-data folder; subsequent launches reuse that runtime. No separate Python installation is needed. The editable source project remains available for development. It supports Python code cells, not full Jupyter extensions, Markdown cells, interactive input prompts, or widgets. Execution is interrupted after two minutes. Large files must fit in RAM. Excel import runs in a background thread; the notebook uses a separate Python process from the bundled runtime.

For developers, Build_EXE.cmd uses packaging/build_portable.py and the Windows .NET Framework C# compiler to create the executable from the working virtual environment. The launcher embeds the runtime and application, validates extraction paths and keeps each packaged runtime separate. It does not install system-wide Python or modify an existing Python installation.

Code runs with your Windows account's permissions. Data files are not uploaded by the app. Code you enter can access files or the network, like ordinary local Python.

## Development checks

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests cover known statistics, missing values, decimal comma conversion, generated code in both languages, multi-sheet Excel, bilingual controls, and real kernel output, shared variables, errors and plots. GUI tests use Qt's offscreen platform.

Sources for the underlying libraries: [Qt for Python](https://pypi.org/project/PySide6/), [pandas Excel I/O](https://pandas.pydata.org/docs/user_guide/io.html#excel-files).

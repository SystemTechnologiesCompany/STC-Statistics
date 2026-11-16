# STC Statistics 1.0.0

## Corrective patch 1.0.1 / Correctif 1.0.1

Map/3D selectors list columns whose data type is numeric. Excel cells such as `0,2113` can be stored as text, leaving a required role empty. Previously this led to a generic STC-SCI101 missing-column error. The new preflight gives **STC-SCI102**, identifies missing roles and explains how to prepare the numbers. The **Prepare numbers / Préparer les nombres** shortcut opens the existing cleaning dialog with eligible decimal-comma columns suggested; the user must review/apply the preview. Text identifiers are not suggested, no automatic change is made, and Undo retains the previous dataset. Newly converted scalar columns become available immediately; point-only maps still work without a scalar.

To use the existing 1.0.0 app: Data → Clean selected columns → select the numeric-text fields (not identifiers) → Decimal comma → numbers → review and Apply. Return to Map Studio and assign X, Y and the property. Conversion repairs numeric representation, not an incorrect original measurement or an unknown unit. Validate physically implausible source values separately.

Dans l’application 1.0.0 : Données → Nettoyer les colonnes sélectionnées → sélectionner les champs numériques stockés en texte, sans les identifiants → Virgule → nombres → vérifier et Appliquer. Dans Atelier cartes, choisir X, Y et la propriété. Le correctif 1.0.1 ajoute **Préparer les nombres** directement aux ateliers et explique les sélections manquantes. La conversion ne devine pas les mesures erronées ni leurs unités.

Publish `releases/1.0.1/STC_Statistics_1.0.1_Update.zip` with its matching `update.json` under exact tag **v1.0.1**. This is an application-only patch compatible with 1.0.0 and enabled 0.5.1–0.5.6 updaters. The original 1.0.0 package remains intact. The V1 feature guide follows.

## New workspaces / Nouveaux espaces

| Page | Tools / Outils |
| --- | --- |
| Map Studio / Atelier cartes | Point maps, filled contours, contour lines, IDW/linear/nearest grids, hillshade, gradient magnitude, regional-plane residuals and line profiles. / Localisation des points, isovaleurs, grilles, ombrage, gradients, résidus régionaux et profils. |
| 3D Studio / Atelier 3D | Rotatable point clouds, gridded surfaces, TIN, wireframes, interpolated scalar-volume slices and thresholded voxels. Camera angles, vertical exaggeration and depth direction. / Nuages, surfaces, TIN, maillages, coupes et voxels ; caméra, exagération et sens des profondeurs. |
| Correlation Lab / Corrélations | Pearson, Spearman and Kendall; annotated signed/squared heatmaps, scatter matrices, bivariate scatter with OLS and density; pair counts, p, BH-adjusted q, slopes and OLS R². / Cartes annotées, nuages, densités et statistiques bivariées. |
| Prediction Lab / Prédiction | Random Forest and Gradient Boosting regression, shared train/test splits, mean baseline, repeated experiments, training-only hyperparameter search, R²/RMSE/MAE, observed/predicted charts, residuals and feature importances. / Régression RF/GB, apprentissage/test, répétitions, optimisation et diagnostics. |

Open data on Data, assign variable roles on the relevant page, then **Compute**. Results stay on that page and are recorded with their Python recipe in Notebook. **Editable Python** creates a self-contained recipe that can be edited and executed. Existing Analysis correlation also produces a graphical heatmap.

Importez les données dans Données, attribuez les variables et cliquez sur **Calculer**. Le résultat reste dans son espace et sa recette Python est conservée dans Notebook. **Python modifiable** crée une recette autonome à modifier et exécuter. La corrélation d’Analyse produit aussi une carte graphique.

## Saving and exports / Enregistrement et exports

- Save a `.stcp` project to retain data, options, numerical results and the latest live result/camera in each new workspace. Opening never executes code or retrains models. Historical notebook images/code remain; only the latest interactive payload per workspace is retained to bound project size.
- Every workspace has **Visuals**, **Values & export** and **Methods & limits** tabs. Save figures as PNG/PDF/SVG; export the entire selected numerical table as Excel/CSV. Map grids export as ESRI ASCII plus a UTM `.prj` when the app performed that transform. Surface/TIN/wireframe geometry exports as OBJ in native coordinates, without display exaggeration.
- Notebook/report previews show at most 150 rows per new result table. Word/Excel reports can include these previews and full-resolution figures. Use **Values & export** for complete numerical tables, or the recipe’s `result['tables']` in Python. Trained estimators are deliberately not serialized; rerun the recipe to train again.

Enregistrez un projet `.stcp` pour conserver données, paramètres, valeurs et dernière vue interactive de chaque nouvel espace. L’ouverture n’exécute aucun code. Les exports complets CSV/Excel sont dans **Valeurs et export** ; les figures PNG/PDF/SVG restent disponibles. Les rapports Word/Excel utilisent les aperçus de tables (150 lignes maximum) et les figures. Pour toutes les valeurs, utilisez l’export de table complet. Les modèles entraînés ne sont pas sérialisés.

## Scientific scope and limits / Portée et limites

This release supplies a defined local scientific toolset inspired by GIS and statistics workflows. It does **not** reproduce all ArcGIS, Statistica or Oasis montaj functions.

- Inputs: existing Excel/CSV, GeoJSON **Point** features and ESRI ASCII grids. No shapefile/geodatabase, arbitrary vector geometry, GeoTIFF, basemaps, GDAL or general datum-reprojection engine is included.
- Coordinates: planar X/Y in the same linear unit, or WGS84 longitude/latitude transformed into one ordinary UTM zone and hemisphere. Automatic zone is based on mean longitude; an explicit zone is available. Latitude −80° to 84°, longitude within 3.5° of the zone’s central meridian. Special Norway/Svalbard zones, poles and other datums need an external CRS tool. A custom CRS label alone performs no transform. Z is not vertically reprojected; keep its unit consistent with projected X/Y for meaningful physical aspect.
- Interpolation: duplicate coordinates are averaged; nonfinite rows are excluded and counted. All grid methods mask outside the sample convex hull. Geometry must span an area/volume. IDW uses nearest neighbours and user-selected power; linear interpolation uses Delaunay simplices. These are not kriging, geological inversion, fault/stratigraphic modeling or uncertainty estimates. Surface-only measurements cannot establish subsurface properties.
- Limits: 100,000 finite map/surface/cloud samples; 15,000 unique TIN samples; 10,000 unique volume samples. 2D resolution is 12–200 on the longest axis, with square cells. Volume slices use 12–28 samples per axis; voxels use 12–20. Point clouds display a deterministic maximum 15,000 points but export all valid points. Scatter matrices display at most 3,000 observations per pair; bivariate and model scatter plots at most 5,000. Coefficients, fits, metrics and tables use the full eligible data.
- The 3D view preserves coordinate proportions at exaggeration 1; user exaggeration affects only display. Hillshade is relative illumination; gradients have property units per coordinate unit. Residuals subtract a fitted regional plane, not a physical geological trend model.
- Correlations: 2–12 variables; scatter matrices at most 6. Pairwise complete observations; constant/insufficient pairs are undefined, never zero-filled. p values assume independent samples, and q uses Benjamini–Hochberg across valid unique pairs. Squared association is distinct from predictive holdout R²; OLS R² is for a simple linear model with intercept. Correlation does not establish causation.
- Regression: numeric response/predictors; 12–100,000 labelled rows, at least 6 train/3 test. Median imputation and randomized hyperparameter search are fitted on training rows and inside training CV folds only. Test rows are never used for tuning. Random, held-out site/well-group and ordered splits are available. Use groups/appropriate study design to avoid spatial leakage; ordered rows must already be in the desired order. Ordered repeats reuse the same holdout boundary and are not independent validation datasets.
- Models use 10–500 trees, 1–10 experiments, test fraction 0.1–0.5. Tuning uses 2–5 training CV folds and 1–12 search trials per model/repeat; tuning draws tree count/depth/rate from its documented recipe search space, which can override manual settings. Prediction history is limited to 200,000 rows across models and repeats. R² may be negative or undefined for a constant held-out response. RMSE/MAE retain the response unit; repeated-split SD is not a confidence interval. Impurity-based importances may favour high-cardinality variables. Missing responses can be predicted with training-fitted models; they are not evaluated as labelled test data.
- Compute runs in a cancellable local process. Saved interactive payloads are JSON/Parquet, not executable/pickled models. Existing project size limits remain enforced; reduce grid/data/repeats if a project becomes too large. Custom notebook code still executes with the Windows user’s permissions.

Cette version fournit un ensemble défini d’outils ; elle ne reproduit pas toutes les fonctions des suites citées. Les cartes et volumes sont des interpolations limitées par les mesures disponibles, pas des inversions géologiques. Les limites, unités, exclusions et hypothèses sont affichées dans **Méthodes et limites** et conservées avec les résultats. Les séparations par puits/groupes permettent de mieux contrôler les fuites spatiales ; l’utilisateur reste responsable du plan de validation.

## Application-only release / Mise à jour applicative

The release package is `releases/1.0.0/STC_Statistics_1.0.0_Update.zip`, with its matching `update.json`. The GitHub tag must be exactly **v1.0.0** (lowercase v). Attach both files to the same normal published release. Do not rename assets or publish the JSON before attaching the ZIP. No release is published by this project’s local build.

Installed app versions 0.5.1–0.5.6 with the application-patch updater are supported by archive validation. The original embedded 0.5.0 portable app needs its existing one-time updater bootstrap. Users of the 0.5.6 setup can update in-app. No EXE, installer, bundled interpreter or third-party library rebuild is needed for this release. Existing activation codes and Supabase protocol remain unchanged; no customer registration is introduced.

Publiez ensemble le ZIP et `update.json` sous **v1.0.0**. Dans l’application : **Mises à jour → Vérifier les mises à jour → Mettre à jour l’application**. Le projet est sauvegardé avant installation, puis l’application redémarre. Les variables Python autres que `df` doivent être recréées en exécutant les cellules nécessaires. Les codes d’activation existants restent valables.

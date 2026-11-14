"""Analysis code is also inserted verbatim into the user's notebook."""
import inspect

import numpy as np
import pandas as pd


METRICS = {
    "en": ["Count", "Missing", "Mean", "Median", "Mode(s)", "Minimum", "Maximum",
           "Range", "Sample variance", "Sample standard deviation", "Q1 (25%)",
           "Q3 (75%)", "Interquartile range", "Sum", "Skewness", "Excess kurtosis"],
    "fr": ["Effectif", "Valeurs manquantes", "Moyenne", "Médiane", "Mode(s)", "Minimum", "Maximum",
           "Étendue", "Variance de l’échantillon", "Écart-type de l’échantillon", "Q1 (25 %)",
           "Q3 (75 %)", "Écart interquartile", "Somme", "Asymétrie", "Aplatissement (excès)"],
}


def summarize(data, columns, ddof=1, percentiles=None):
    """Numeric data only; infinities count as missing; ddof=1 uses sample variance."""
    numeric = data.loc[:, columns].select_dtypes(include="number").replace([np.inf, -np.inf], np.nan)
    if numeric.empty and not len(numeric.columns):
        raise ValueError("Select numeric columns / Sélectionnez des colonnes numériques")
    result = {}
    for column in numeric:
        values = numeric[column]
        valid = values.dropna()
        modes = valid.mode()
        # No repeated observations means no informative mode.
        mode = ", ".join(str(x) for x in modes) if len(modes) < len(valid) else "—"
        q1, q3 = valid.quantile([0.25, 0.75])
        result[column] = [valid.count(), values.isna().sum(), valid.mean(), valid.median(),
                          mode, valid.min(), valid.max(), valid.max() - valid.min(),
                          valid.var(ddof=ddof), valid.std(ddof=ddof), q1, q3, q3 - q1,
                          valid.sum(min_count=1), valid.skew(), valid.kurt()]
        result[column].extend(valid.quantile(p / 100) for p in (percentiles or []))
    return pd.DataFrame(result)


TABLE_MIME = 'application/vnd.stc.table+json'


def table_display_code(variable, title=''):
    return ("from IPython.display import display\n"
            f"display({{'text/html': {variable}.to_html(), {TABLE_MIME!r}: "
            f"{variable}.to_json(orient='split', double_precision=15)}}, raw=True, metadata={{'stc': {{'title': {title!r}}}}})\n")


def analysis_code(columns, language="en", metric_indices=None, ddof=1, percentiles=None):
    percentiles = list(percentiles or [])
    labels = list(METRICS[language])
    if ddof == 0:
        labels[8:10] = (['Population variance', 'Population standard deviation'] if language == 'en'
                        else ['Variance de la population', 'Écart-type de la population'])
    labels += [f"{'Percentile' if language == 'en' else 'Centile'} {p:g}%" for p in percentiles]
    rows = list(range(16)) if metric_indices is None else list(metric_indices)
    rows += list(range(16, 16 + len(percentiles)))
    return ("import pandas as pd\nimport numpy as np\n\n" + inspect.getsource(summarize)
            + f"\nselected_columns = {list(columns)!r}\n"
            + f"summary = summarize(df, selected_columns, ddof={ddof!r}, percentiles={percentiles!r})\n"
            + f"summary.index = {labels!r}\nsummary = summary.iloc[{rows!r}]\n"
            + table_display_code('summary', ('Statistics' if language == 'en' else 'Statistiques') + (' (sample n-1)' if ddof == 1 else ' (population n)'))
            + '\n' + inspect.getsource(describe_data) + f'\nprint(describe_data(df, selected_columns, {language!r}))')


def describe_data(df, columns, language='en'):
    import numpy as np
    import pandas as pd
    notes = []
    for c in df[columns].select_dtypes(include='number'):
        x = df[c].replace([np.inf,-np.inf], np.nan).dropna()
        if x.empty:
            notes.append(f'{c}: ' + ('aucune valeur numérique finie.' if language=='fr' else 'no finite numeric values.'))
            continue
        q1,q3=x.quantile([.25,.75])
        outliers=int(((x<q1-1.5*(q3-q1))|(x>q3+1.5*(q3-q1))).sum())
        if language=='fr':
            notes.append(f'{c}: n={len(x)}, moyenne={x.mean():.6g}, médiane={x.median():.6g}; 50 % des valeurs entre {q1:.6g} et {q3:.6g}. {len(df)-len(x)} valeurs exclues; {outliers} valeurs au-delà des limites de Tukey (1,5 × IQR).')
        else:
            notes.append(f'{c}: n={len(x)}, mean={x.mean():.6g}, median={x.median():.6g}; middle 50% between {q1:.6g} and {q3:.6g}. {len(df)-len(x)} excluded values; {outliers} values beyond Tukey fences (1.5 × IQR).')
    notes.append('Résumé descriptif; les valeurs signalées ne sont pas forcément des erreurs. Aucune causalité déduite.' if language=='fr' else 'Descriptive summary; flagged values are not necessarily errors. No causal conclusions are implied.')
    return '\n'.join(notes)


def correlation_code(method='pearson'):
    if method == 'spearman':
        return ("# Spearman: rank each pair's complete observations; ties use average ranks.\n"
                "correlation = pd.DataFrame(np.nan, index=numeric.columns, columns=numeric.columns)\n"
                "for left in numeric.columns:\n"
                "    for right in numeric.columns:\n"
                "        pair = pd.concat([numeric[left], numeric[right]], axis=1).dropna()\n"
                "        if len(pair) >= 2:\n"
                "            correlation.loc[left, right] = pair.rank(method='average').corr().iloc[0, 1]\n"
                + table_display_code('correlation', 'Correlation (Spearman)'))
    return ("# Pearson correlation; at least two complete observations per pair.\n"
            "correlation = numeric.corr(method='pearson', min_periods=2)\n"
            + table_display_code('correlation', 'Correlation (Pearson)'))


def conversion_code(columns, decimal_comma=False):
    return (f"# Convert only the selected columns; keep the original file unchanged.\n"
            f"for column in {list(columns)!r}:\n"
            "    values = df[column].astype('string').str.strip()\n"
            + ("    values = values.str.replace(' ', '', regex=False).str.replace('\\u00a0', '', regex=False)\n"
               "    values = values.str.replace(',', '.', regex=False)\n" if decimal_comma else "")
            + "    df[column] = pd.to_numeric(values, errors='coerce')\n"
            + "df.head()\n")

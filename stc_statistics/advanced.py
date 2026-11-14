"""Reproducible numerical recipes used by the notebook and desktop controls."""
import inspect


def advanced_analysis(df, method, columns, language='en', confidence=.95, reference=0., clusters=3):
    import numpy as np
    import pandas as pd
    from scipy import stats
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
    from sklearn.cluster import KMeans
    fr = language == 'fr'
    if not columns:
        raise ValueError('Select numeric columns / Sélectionnez des colonnes numériques')
    if method in ('one_t', 'normality'):
        columns = columns[:1]
    numeric = df[columns].apply(pd.to_numeric, errors='coerce').replace([np.inf, -np.inf], np.nan)
    data = numeric.dropna()
    if method in ('welch','anova','ci'):
        if min(numeric.count()) < 3:
            raise ValueError('Each group needs at least 3 numeric values / Au moins 3 valeurs par groupe')
    elif len(data) < 3:
        raise ValueError('At least 3 complete rows required / Au moins 3 lignes complètes requises')
    if not 0 < confidence < 1:
        raise ValueError('Invalid confidence level')
    alpha = 1-confidence
    notes = [f"n = {len(data)}; " + (f"lignes exclues : {len(df)-len(data)}." if fr else f"excluded rows: {len(df)-len(data)}.")]
    p = None
    if method == 'ci':
        result = []
        for name in columns:
            x = numeric[name].dropna()
            margin = stats.t.ppf(1-alpha/2, len(x)-1)*stats.sem(x)
            result.append([len(x), x.mean(), x.mean()-margin, x.mean()+margin])
        table = pd.DataFrame(result, index=columns, columns=['n', 'Moyenne' if fr else 'Mean', 'IC bas' if fr else 'CI lower', 'IC haut' if fr else 'CI upper'])
        notes = [('Valeurs manquantes exclues séparément pour chaque colonne.' if fr else 'Missing values excluded separately for each column.')]
        notes.append((f"IC de Student à {confidence:.1%}. Échantillon indépendant; moyenne approximativement normale." if fr else f"Student-t intervals at {confidence:.1%}. Independent observations; approximately normal sampling distribution of the mean."))
    elif method == 'regression':
        if len(columns) < 2:
            raise ValueError('Select predictors then response as last column / Réponse en dernière colonne')
        x = np.column_stack([np.ones(len(data)), data.iloc[:, :-1].to_numpy()])
        y = data.iloc[:, -1].to_numpy()
        if len(data) <= x.shape[1] or np.linalg.matrix_rank(x) < x.shape[1]:
            raise ValueError('Insufficient rows or collinear predictors / Données insuffisantes ou colinéaires')
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        residual = y-x@beta
        se = np.sqrt(np.diag(np.linalg.inv(x.T@x)) * (residual@residual)/(len(y)-len(beta)))
        critical = stats.t.ppf(1-alpha/2, len(y)-len(beta))
        table = pd.DataFrame({'Coefficient': beta, 'Erreur-type' if fr else 'SE': se, 'IC bas' if fr else 'CI lower': beta-critical*se, 'IC haut' if fr else 'CI upper': beta+critical*se}, index=['Constante' if fr else 'Intercept']+columns[:-1])
        total = ((y-y.mean())**2).sum()
        notes.append(f"Response / Réponse: {columns[-1]}; R² = {1-(residual@residual)/total:.4f}" if total else 'Constant response / Réponse constante')
        notes.append('Linéarité, indépendance, variance constante et résidus normaux pour les IC. Association ≠ causalité.' if fr else 'Intervals assume linearity, independence, constant variance and normal residuals. Association does not establish causality.')
    elif method in ('pca', 'cluster'):
        if len(columns) < 2 or (data.std() == 0).any():
            raise ValueError('Select at least two nonconstant columns / Deux colonnes non constantes minimum')
        z = StandardScaler().fit_transform(data)
        if method == 'pca':
            model = PCA().fit(z)
            table = pd.DataFrame(model.components_.T, index=columns, columns=[f'PC{i+1}' for i in range(len(model.components_))])
            notes.append(('Variance expliquée : ' if fr else 'Explained variance: ')+', '.join(f'{v:.1%}' for v in model.explained_variance_ratio_))
        else:
            if not 2 <= clusters <= min(len(data), len(np.unique(z, axis=0))):
                raise ValueError('Invalid cluster count / Nombre de groupes invalide')
            labels = KMeans(n_clusters=clusters, random_state=42, n_init=20).fit_predict(z)
            table = data.copy()
            table['Cluster'] = labels+1
        notes.append('Variables standardisées; analyse exploratoire, groupes à valider avec le contexte.' if fr else 'Features standardized; exploratory analysis, validate patterns against domain knowledge.')
    else:
        arrays = [numeric[c].dropna().to_numpy() for c in columns] if method in ('welch','anova') else [data[c].to_numpy() for c in columns]
        if method in ('welch','anova'):
            notes = [('Effectifs par groupe : ' if fr else 'Group sample sizes: ')+', '.join(f'{c}: {len(a)}' for c,a in zip(columns,arrays))]
        if any(np.std(a) == 0 for a in arrays):
            raise ValueError('Constant samples are not supported / Échantillon constant')
        if method == 'one_t':
            test = stats.ttest_1samp(arrays[0], reference)
        elif method in ('welch', 'paired'):
            if len(arrays) != 2:
                raise ValueError('Select exactly two columns / Sélectionnez exactement deux colonnes')
            test = stats.ttest_ind(*arrays, equal_var=False) if method == 'welch' else stats.ttest_rel(*arrays)
        elif method == 'anova':
            if len(arrays) < 2:
                raise ValueError('Select at least two group columns / Deux groupes minimum')
            test = stats.f_oneway(*arrays)
        elif method == 'normality':
            if len(data) > 5000:
                raise ValueError('Shapiro: maximum 5000 rows / 5000 lignes maximum')
            test = stats.shapiro(arrays[0])
        else:
            raise ValueError('Unknown method')
        statistic, p = float(test.statistic), float(test.pvalue)
        if not np.isfinite([statistic, p]).all():
            raise ValueError('Undefined test / Test indéfini')
        table = pd.DataFrame({'Statistique' if fr else 'Statistic': [statistic], 'p-value': [p], 'alpha': [alpha]})
        notes.append(('Rejet de H0.' if p < alpha else 'H0 non rejetée; cela ne prouve pas son exactitude.') if fr else ('Reject H0.' if p < alpha else 'Do not reject H0; this does not prove it true.'))
        notes.append('Vérifier indépendance et normalité. ANOVA classique : variances égales. Tests t bilatéraux; Shapiro : H0 = normalité. Colonnes = groupes indépendants (valeurs manquantes exclues par groupe); test apparié : lignes complètes correspondantes.' if fr else 'Check independence and normality. Classical ANOVA assumes equal variances. T-tests are two-sided; Shapiro H0 is normality. Columns represent independent groups (missing values omitted per group); paired tests match complete rows.')
    return table, '\n'.join(notes)


def recipe(method, columns, language, **options):
    from .analysis import table_display_code
    return ('import pandas as pd\nimport numpy as np\n'+inspect.getsource(advanced_analysis)+
            f'\nresult, interpretation = advanced_analysis(df, {method!r}, {columns!r}, {language!r}, **{options!r})\n'+
            table_display_code('result', method)+'\nprint(interpretation)')


def geology(df, method, columns, percent=True, thresholds=(1, 10, 100, 1000)):
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    d = df[columns].apply(pd.to_numeric, errors='coerce').replace([np.inf,-np.inf],np.nan).dropna()
    if d.empty:
        raise ValueError('No complete numeric rows / Aucune ligne numérique complète')
    if method == 'matrix':
        matrix = d.corr()
        fig, ax = plt.subplots(figsize=(9,7), layout='constrained')
        image = ax.imshow(matrix, vmin=-1, vmax=1, cmap='BrBG')
        ax.set_xticks(range(len(columns)), columns, rotation=35, ha='right')
        ax.set_yticks(range(len(columns)), columns)
        for i in range(len(columns)):
            for j in range(len(columns)):
                ax.text(j,i,f'{matrix.iloc[i,j]:.2f}', ha='center', va='center')
        fig.colorbar(image,ax=ax)
        plt.show()
        return matrix
    if len(columns) != 2:
        raise ValueError('Exactly two assigned columns required / Deux colonnes requises')
    if method == 'depth':
        d = d.sort_values(columns[1])
        fig, ax = plt.subplots(figsize=(7,9), layout='constrained')
        ax.plot(d.iloc[:,0], d.iloc[:,1], color='#20945f')
        ax.invert_yaxis()
        ax.set(xlabel=str(columns[0]), ylabel=str(columns[1]), title='Depth profile / Profil de profondeur')
        ax.grid(alpha=.25)
        plt.show()
        return d
    phi = d.iloc[:,0]/(100 if percent else 1)
    k = d.iloc[:,1]
    valid = (phi>0)&(phi<1)&(k>0)
    result = d.loc[valid].copy()
    if result.empty:
        raise ValueError('Require 0 < porosity < 1 and permeability > 0 mD')
    phi, k = phi[valid], k[valid]
    result['RQI_um'] = .0314*np.sqrt(k/phi)
    result['FZI_um'] = result['RQI_um']/(phi/(1-phi))
    if sorted(set(thresholds)) != list(thresholds) or any(t<=0 for t in thresholds):
        raise ValueError('Thresholds must increase and be positive')
    result['Permeability class / Classe'] = pd.cut(k, [0,*thresholds,np.inf], right=False).astype(str)
    fig, ax = plt.subplots(figsize=(10,6), layout='constrained')
    ax.scatter(phi*100,k,c='#20945f',alpha=.8,edgecolors='white')
    ax.set(xlabel='Porosity / Porosité (%)',ylabel='Permeability / Perméabilité (mD)',yscale='log')
    ax.grid(alpha=.25)
    plt.show()
    print(f'Excluded / Exclues: {len(df)-len(result)}. RQI/FZI: k in mD, porosity fraction. Classes are screening thresholds, not lithology / Classes indicatives, pas une lithologie.')
    return result


def geology_recipe(method, columns, **options):
    from .analysis import table_display_code
    return ('%matplotlib inline\n'+inspect.getsource(geology)+f'\nresult = geology(df, {method!r}, {columns!r}, **{options!r})\n'+table_display_code('result',method))

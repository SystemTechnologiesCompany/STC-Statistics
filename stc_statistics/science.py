"""Reproducible spatial, relationship and predictive-regression calculations.

Only libraries already shipped in STC's Windows runtime are used. No network,
pickle loading or proprietary GIS engine is involved.
"""
import json
import math
import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial import cKDTree,Delaunay,QhullError
from scipy.interpolate import LinearNDInterpolator
from matplotlib.figure import Figure

CMAPS=('viridis','terrain','plasma','coolwarm','cividis')
TABLE_MIME='application/vnd.stc.table+json'
FRENCH_COLUMNS={'Model':'Modèle','Repeat':'Répétition','Split':'Ensemble','Observed':'Observé','Predicted':'Prédit',
    'Residual (observed - predicted)':'Résidu (observé - prédit)','Row position (0-based)':'Position de ligne (base 0)',
    'Source index':'Index source','Feature':'Variable','Importance':'Importance','Parameters':'Paramètres',
    'Training CV RMSE':'RMSE de validation d’apprentissage','Value':'Valeur','Distance':'Distance',
    'Coefficient':'Coefficient','Squared coefficient':'Coefficient au carré','p (uncorrected)':'p (non corrigé)',
    'OLS slope':'Pente OLS','OLS intercept':'Constante OLS','OLS R²':'R² OLS',
    'Coordinate centre':'Centre des coordonnées','Coordinate scale':'Échelle des coordonnées','Colour value':'Valeur de couleur'}


def display_table(name,table,language):
    if language!='fr' or name in ('Correlation','Pair counts'): return table
    result=table.rename(columns=FRENCH_COLUMNS)
    if 'Ensemble' in result:
        result=result.copy(); result['Ensemble']=result['Ensemble'].replace({'Train':'Apprentissage','Test':'Test','Unlabelled':'Sans étiquette'})
    return result

FRENCH_NOTES={
 'Use measurements distributed through a volume. Surface-only samples do not establish subsurface properties.':
 'Utilisez des mesures réparties dans un volume. Des échantillons de surface seuls ne déterminent pas les propriétés du sous-sol.',
 'Sample locations only; no grid interpolation or profile is computed.':
 'Localisation des points uniquement ; aucune interpolation de grille ni aucun profil n’est calculé.',
 'Planar coordinates: X/Y must have the same linear unit. CRS labels do not transform coordinates.':
 'Les coordonnées projetées X/Y doivent avoir la même unité linéaire. Les simples étiquettes de SCR ne transforment pas les coordonnées.',
 'Residual = interpolated value minus the least-squares regional plane fitted to unique samples.':
 'Résidu = valeur interpolée moins le plan régional ajusté par moindres carrés aux points uniques.',
 'Gradient magnitude: property units per coordinate unit. Boundary cells next to missing values may remain masked.':
 'Norme du gradient : unité de la propriété par unité de coordonnées. Les cellules voisines de données manquantes peuvent rester masquées.',
 'This is an interpolated scalar volume, not an inferred lithology, fault model or geophysical inversion.':
 'Il s’agit d’un volume scalaire interpolé, sans inférence de lithologie, de faille ou d’inversion géophysique.',
 'Rotate with the mouse. Z exaggeration changes the view, not the source values.':
 'Rotation à la souris. L’exagération de Z modifie la vue, pas les données sources.',
 'Pairwise complete observations; constant/insufficient pairs remain undefined, not zero.':
 'Observations complètes par paire ; les paires constantes ou insuffisantes restent indéfinies, sans remplacement par zéro.',
 'Squared association is not the predictive test R². OLS R² refers only to a simple linear fit with intercept. Correlation does not prove causation.':
 'Le coefficient au carré n’est pas le R² prédictif de test. Le R² OLS correspond à une régression linéaire simple avec constante. Une corrélation ne prouve pas une causalité.',
 'Median imputation is fitted on training data only, including inside each CV fold. Model selection uses training CV RMSE; test rows are held out.':
 'L’imputation médiane est ajustée uniquement sur l’apprentissage, y compris dans chaque pli. La sélection utilise le RMSE de validation d’apprentissage ; le test reste séparé.',
 'R² can be negative and is undefined for a constant response. RMSE/MAE keep the response unit. Repeated-split SD is not a confidence interval.':
 'Le R² peut être négatif et reste indéfini pour une réponse constante. RMSE/MAE conservent l’unité de la réponse. L’écart-type des répétitions n’est pas un intervalle de confiance.',
 'Random splits assume independent observations; use held-out site/well groups for spatially correlated data. Ordered splits preserve row order.':
 'Une séparation aléatoire suppose des observations indépendantes ; utilisez des groupes de sites/puits séparés pour les données spatialement corrélées. La séparation ordonnée conserve l’ordre des lignes.',
 'Tree importances are impurity-based training diagnostics and may favour high-cardinality features. Plots show repeat 1; exported tables contain every repeat.':
 'Les importances reposent sur la réduction d’impureté en apprentissage et peuvent favoriser les variables à nombreuses valeurs. Les graphiques montrent la répétition 1 ; les tables exportées contiennent toutes les répétitions.',
 'Unlabelled predictions use the training model, not a model secretly refitted on the test set. Trained estimators are not saved in project files.':
 'Les réponses manquantes sont prédites par le modèle d’apprentissage, sans réajustement caché sur le test. Les modèles entraînés ne sont pas sérialisés dans les projets.'}


def localize_result(result):
    result.setdefault('notes_en',list(result['notes']))
    if result['options'].get('language')=='fr':
        replacements=[('Valid samples:','Échantillons valides :'),('duplicate coordinates averaged:','doublons de coordonnées moyennés :'),
            ('Finite XYZ samples:','Échantillons XYZ valides :'),('Displayed:','Affichés :'),('(deterministic display sample only)','(échantillon d’affichage déterministe uniquement)'),
            ('Coordinate reference:','Référence des coordonnées :'),('Missing colour values assigned the finite median:','Couleurs manquantes remplacées par la médiane finie :'),
            ('Labelled rows:','Lignes étiquetées :'),('missing responses:','réponses manquantes :'),('split:','séparation :'),('seed:','graine :'),('repeats:','répétitions :'),
            ('Method:','Méthode :'),('minimum pairs:','minimum de paires :'),('p values assume independent samples; q uses Benjamini–Hochberg correction.','Les valeurs p supposent des échantillons indépendants ; q utilise Benjamini–Hochberg.'),
            ('interpolation; cells outside the sample convex hull are masked. Interpolation is not geological inversion.','interpolation ; les cellules hors de l’enveloppe convexe des échantillons sont masquées. L’interpolation n’est pas une inversion géologique.')]
        notes=[]
        for note in result['notes']:
            translated=FRENCH_NOTES.get(note,note)
            for old,new in replacements: translated=translated.replace(old,new)
            notes.append(translated)
        result['notes']=notes
    return result


def require(condition,en,fr):
    if not condition:
        raise ValueError(en+' / '+fr)


def numeric_frame(frame,columns):
    require(len(columns)==len(set(columns)),'Choose different columns for each role','Choisissez des colonnes distinctes')
    require(all(c in frame.columns for c in columns),'A selected column is missing','Une colonne sélectionnée est absente')
    return frame[columns].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)


def project_xy(points,options):
    """WGS84 Transverse Mercator series for one ordinary UTM zone, or no transform.

    Snyder-style series through A^6, k0=.9996. Explicit zone is supported; this
    limited transform is not a general EPSG/datum conversion engine.
    """
    points=np.asarray(points,float).copy()
    if options.get('coordinate_mode','planar')!='wgs84':
        return points,str(options.get('crs','Local / projected coordinates')),None
    lon,lat=points[:,0],points[:,1]
    require(np.all((-180<=lon)&(lon<=180)&(-80<=lat)&(lat<=84)),
            'UTM input needs longitude −180…180 and latitude −80…84 degrees','UTM : longitude −180…180 et latitude −80…84 degrés')
    require(np.all(lat>=0) or np.all(lat<=0),'Use one UTM hemisphere per analysis','Utilisez un seul hémisphère UTM par analyse')
    zone=int(options.get('utm_zone',0)) or min(60,max(1,int((float(np.mean(lon))+180)//6)+1))
    require(1<=zone<=60,'UTM zone must be 1–60','La zone UTM doit être comprise entre 1 et 60')
    central=zone*6-183
    require(np.max(np.abs(lon-central))<=3.5,'Use coordinates within one UTM zone; choose the correct zone','Utilisez une seule zone UTM ; choisissez la zone correcte')
    a=6378137.; e2=0.0066943799901413165; ep2=e2/(1-e2); k=.9996
    phi=np.radians(lat); lam=np.radians(lon-central)
    sin=np.sin(phi); cos=np.cos(phi); tangent=np.tan(phi)
    n=a/np.sqrt(1-e2*sin*sin); t=tangent*tangent; c=ep2*cos*cos; b=cos*lam
    meridian=a*((1-e2/4-3*e2**2/64-5*e2**3/256)*phi
                -(3*e2/8+3*e2**2/32+45*e2**3/1024)*np.sin(2*phi)
                +(15*e2**2/256+45*e2**3/1024)*np.sin(4*phi)
                -35*e2**3/3072*np.sin(6*phi))
    points[:,0]=500000+k*n*(b+(1-t+c)*b**3/6+(5-18*t+t*t+72*c-58*ep2)*b**5/120)
    points[:,1]=k*(meridian+n*tangent*(b*b/2+(5-t+9*c+4*c*c)*b**4/24+(61-58*t+t*t+600*c-330*ep2)*b**6/720))
    south=bool(np.any(lat<0))
    if south: points[:,1]+=10000000
    epsg=(32700 if south else 32600)+zone
    return points,f'WGS84 / UTM {zone}{"S" if south else "N"} · EPSG:{epsg} · metres',epsg


def idw(points,values,targets,neighbors=12,power=2):
    """Local inverse-distance weighting, with exact interpolation at samples."""
    count=min(int(neighbors),len(points))
    require(count>=1 and 0.1<=float(power)<=8,'Invalid IDW settings','Paramètres IDW invalides')
    distance,index=cKDTree(points).query(targets,k=count)
    if count==1:
        return np.asarray(values)[index].astype(float)
    exact=distance[:,0]<=np.finfo(float).eps
    # Divide by each row's nearest distance to avoid overflow at tiny distances.
    safe=np.maximum(distance,np.finfo(float).tiny)
    weights=(safe[:,[0]]/safe)**float(power)
    result=(weights*np.asarray(values)[index]).sum(axis=1)/weights.sum(axis=1)
    result[exact]=np.asarray(values)[index[exact,0]]
    return result


def grid_samples(frame,options,dimensions=2):
    coords=[options['x'],options['y']]+([options['z']] if dimensions==3 else [])
    value=options['value']
    data=numeric_frame(frame,coords+[value]).dropna()
    require(len(data)>=dimensions+1,'Not enough finite samples','Échantillons valides insuffisants')
    require(len(data)<=100000,'Limit this analysis to 100,000 samples','Limitez cette analyse à 100 000 échantillons')
    grouped=data.groupby(coords,sort=True,as_index=False)[value].mean()
    if dimensions==3:
        require(len(grouped)<=10000,'Volume interpolation is limited to 10,000 unique samples','Interpolation volumique limitée à 10 000 échantillons uniques')
    if options.get('mode')=='tin':
        require(len(grouped)<=15000,'TIN views are limited to 15,000 unique samples; choose a gridded surface for larger data','Vue TIN limitée à 15 000 points uniques ; utilisez une surface interpolée pour les grands jeux')
    points,crs,epsg=project_xy(grouped[coords].to_numpy(float),options)
    values=grouped[value].to_numpy(float)
    require(len(points)>=dimensions+1 and np.linalg.matrix_rank(points-points.mean(axis=0))==dimensions,
            'Coordinates must span an area or a volume; collinear/coplanar samples cannot define this grid',
            'Les coordonnées doivent couvrir une aire ou un volume ; données colinéaires/coplanaires insuffisantes')
    resolution=int(options.get('resolution',70 if dimensions==2 else 18))
    require(12<=resolution<=(200 if dimensions==2 else 28),'Grid resolution is outside the supported range','Résolution hors limites')
    lower=points.min(axis=0); upper=points.max(axis=0)
    if dimensions==2:
        spacing=float(np.max(upper-lower)/(resolution-1))
        axes=[lower[i]+np.arange(int(np.ceil((upper[i]-lower[i])/spacing-1e-10))+1)*spacing for i in range(2)]
        xx,yy=np.meshgrid(*axes,indexing='xy')
        targets=np.column_stack([xx.ravel(),yy.ravel()])
        shape=xx.shape
    else:
        axes=[np.linspace(lower[i],upper[i],resolution) for i in range(3)]
        meshes=np.meshgrid(*axes,indexing='ij')
        targets=np.column_stack([a.ravel() for a in meshes]); shape=meshes[0].shape
        spacing=None
    try:
        hull=Delaunay(points)
    except QhullError:
        raise ValueError('Coordinates cannot define a stable interpolation hull / Coordonnées géométriquement instables') from None
    inside=hull.find_simplex(targets)>=0
    method=options.get('interpolation','idw')
    require(method in ('idw','linear','nearest'),'Choose an interpolation method','Choisissez une interpolation')
    if method=='linear':
        field=np.asarray(LinearNDInterpolator(hull,values)(targets))
    elif method=='nearest':
        field=values[cKDTree(points).query(targets,k=1)[1]].astype(float)
    else:
        field=idw(points,values,targets,options.get('neighbors',12),options.get('power',2))
    field[~inside]=np.nan
    require(np.isfinite(field).sum()>0,'The grid has no supported cells','La grille ne contient aucune cellule valide')
    notes=[f'Valid samples: {len(data)} / {len(frame)}; duplicate coordinates averaged: {len(data)-len(points)}.',
           'Coordinate reference: '+crs,
           'Planar coordinates: X/Y must have the same linear unit. CRS labels do not transform coordinates.',
           f'{method.upper()} interpolation; cells outside the sample convex hull are masked. Interpolation is not geological inversion.']
    return {'axes':axes,'field':field.reshape(shape),'points':points,'values':values,'spacing':spacing,
            'triangles':hull.simplices if dimensions==2 else np.empty((0,3),int),
            'value_name':value,'coordinate_names':(['Easting (m)','Northing (m)']+coords[2:]) if epsg else coords,
            'crs':crs,'crs_epsg':epsg,'notes':notes}


def spatial_analysis(frame,options,volume=False):
    mode=options.get('mode','surface' if volume else 'contour')
    require(mode in (('points','surface','wireframe','tin','slices','voxels') if volume else
                     ('samples','contour','lines','grid','hillshade','gradient','residual')),
            'Choose a supported map/model type','Choisissez un type de carte/modèle pris en charge')
    if mode=='voxels':
        require(int(options.get('resolution',18))<=20,'Voxel resolution is limited to 20 cells per axis','Résolution voxel limitée à 20 cellules par axe')
    if not volume and mode=='samples':
        columns=[options['x'],options['y']]+([options['value']] if options.get('value') is not None else [])
        data=numeric_frame(frame,columns).dropna()
        require(len(data)>0,'No finite point samples','Aucun échantillon ponctuel valide')
        require(len(data)<=100000,'Point maps are limited to 100,000 finite samples','Cartes ponctuelles limitées à 100 000 points valides')
        grouped=data.groupby(columns[:2],as_index=False,sort=True)[columns[2]].mean() if len(columns)==3 else data.drop_duplicates(columns[:2])
        points,crs,epsg=project_xy(grouped[columns[:2]].to_numpy(),options)
        values=grouped[columns[2]].to_numpy() if len(columns)==3 else np.zeros(len(points))
        table=pd.DataFrame({'X':points[:,0],'Y':points[:,1]})
        if len(columns)==3: table['Value']=values
        return {'kind':'map','mode':'samples','options':options,'points':points,'values':values,
                'coordinate_names':(['Easting (m)','Northing (m)'] if epsg else columns[:2]),
                'value_name':columns[2] if len(columns)==3 else 'Point locations','crs':crs,'crs_epsg':epsg,'tables':{'Sample values':table},
                'notes':[f'Valid samples: {len(data)} / {len(frame)}; duplicate coordinates averaged: {len(data)-len(points)}.',
                         'Coordinate reference: '+crs,'Sample locations only; no grid interpolation or profile is computed.']}
    if volume and mode=='points':
        coords=[options['x'],options['y'],options['z']]
        data=numeric_frame(frame,coords).dropna()
        require(len(data)>0,'No finite XYZ samples','Aucun échantillon XYZ valide')
        original=len(data)
        require(original<=100000,'Point clouds are limited to 100,000 finite samples','Nuages limités à 100 000 points valides')
        value_name=options.get('value',options['z'])
        colors=pd.to_numeric(frame.loc[:,value_name],errors='coerce').replace([np.inf,-np.inf],np.nan) if value_name in frame else None
        # Position-based color lookup works even when the source index is duplicated.
        positions=np.flatnonzero(numeric_frame(frame,coords).notna().all(axis=1).to_numpy())
        all_points,crs,epsg=project_xy(data.to_numpy(float),options)
        all_color=colors.iloc[positions].to_numpy(float) if colors is not None else data.iloc[:,2].to_numpy(float)
        require(np.isfinite(all_color).any(),'The colour property has no finite values','La propriété de couleur ne contient aucune valeur valide')
        missing_color=int((~np.isfinite(all_color)).sum())
        all_color=np.where(np.isfinite(all_color),all_color,np.nanmedian(all_color))
        keep=np.arange(original)
        if original>15000:
            keep=np.sort(np.random.default_rng(42).choice(original,15000,replace=False))
        return {'kind':'scene','mode':mode,'options':options,'points':all_points[keep],'values':all_color[keep],
                'coordinate_names':(['Easting (m)','Northing (m)',coords[2]] if epsg else coords),'value_name':value_name,
                'crs':crs,'crs_epsg':epsg,'tables':{'Point cloud':pd.DataFrame(np.column_stack([all_points,all_color]),columns=['X','Y','Z','Colour value'])},
                'notes':[f'Finite XYZ samples: {original}. Displayed: {len(keep)} (deterministic display sample only).',
                         f'Coordinate reference: {crs}. Missing colour values assigned the finite median: {missing_color}.',
                         'Rotate with the mouse. Z exaggeration changes the view, not the source values.']}
    dimensions=3 if volume and mode in ('slices','voxels') else 2
    if volume and dimensions==2:
        grid_options=dict(options,value=options['z'],interpolation='linear' if mode=='tin' else options.get('interpolation','idw'))
    else:
        grid_options=options
    grid=grid_samples(frame,grid_options,dimensions)
    field=grid['field']
    tables={}
    if dimensions==2:
        x,y=grid['axes']; xx,yy=np.meshgrid(x,y)
        if mode=='residual':
            points=grid['points']; center=points.mean(axis=0); scale=np.ptp(points,axis=0)
            coefficients=np.linalg.lstsq(np.column_stack([np.ones(len(points)),(points-center)/scale]),grid['values'],rcond=None)[0]
            plane=coefficients[0]+coefficients[1]*(xx-center[0])/scale[0]+coefficients[2]*(yy-center[1])/scale[1]
            grid['field']=field-plane
            tables['Regional plane']=pd.DataFrame({'Coefficient':coefficients,'Coordinate centre':[0,*center],'Coordinate scale':[1,*scale]},index=['Intercept','Normalized X','Normalized Y'])
            grid['notes'].append('Residual = interpolated value minus the least-squares regional plane fitted to unique samples.')
        if mode=='gradient':
            gy,gx=np.gradient(field,grid['spacing'],grid['spacing'])
            grid['field']=np.hypot(gx,gy)
            grid['notes'].append('Gradient magnitude: property units per coordinate unit. Boundary cells next to missing values may remain masked.')
        tables['Grid values']=pd.DataFrame({'X':xx.ravel(),'Y':yy.ravel(),'Value':grid['field'].ravel()})
        if options.get('profile'):
            from scipy.interpolate import RegularGridInterpolator
            start=np.array([float(options['start_x']),float(options['start_y'])])
            end=np.array([float(options['end_x']),float(options['end_y'])])
            line=start+(end-start)*np.linspace(0,1,150)[:,None]
            values=RegularGridInterpolator((y,x),grid['field'],bounds_error=False,fill_value=np.nan)(line[:,::-1])
            tables['Profile']=pd.DataFrame({'Distance':np.linalg.norm(line-start,axis=1),'X':line[:,0],'Y':line[:,1],'Value':values})
            require(np.isfinite(values).any(),'Profile lies outside the supported grid; use map coordinates','Profil hors de la grille ; utilisez les coordonnées de la carte')
    else:
        xx,yy,zz=np.meshgrid(*grid['axes'],indexing='ij')
        tables['Volume values']=pd.DataFrame({'X':xx.ravel(),'Y':yy.ravel(),'Z':zz.ravel(),'Value':field.ravel()})
        grid['notes'].append('This is an interpolated scalar volume, not an inferred lithology, fault model or geophysical inversion.')
        grid['notes'].append('Use measurements distributed through a volume. Surface-only samples do not establish subsurface properties.')
    return dict(grid,kind='scene' if volume else 'map',mode=mode,options=options,tables=tables)


def relationship_analysis(frame,options):
    columns=list(options['columns'])
    mode=options.get('mode','heatmap'); method=options.get('method','pearson')
    require(mode in ('heatmap','matrix','scatter','density'),'Choose a relationship plot','Choisissez un graphique de relation')
    require(2<=len(columns)<=12,'Select 2–12 numeric variables','Sélectionnez 2 à 12 variables numériques')
    require(method in ('pearson','spearman','kendall'),'Unknown correlation method','Méthode de corrélation inconnue')
    require(mode!='matrix' or len(columns)<=6,'Scatter matrices are limited to six variables for readability','Matrice de nuages limitée à six variables')
    numeric=numeric_frame(frame,columns)
    minimum=int(options.get('min_pairs',3))
    require(minimum>=3,'At least three pairs are required','Trois paires minimum')
    corr=pd.DataFrame(np.nan,index=columns,columns=columns)
    counts=pd.DataFrame(0,index=columns,columns=columns)
    pairs=[]
    for i,left in enumerate(columns):
        for j,right in enumerate(columns):
            pair=numeric[[left,right]].dropna() if i!=j else numeric[[left]].dropna()
            n=len(pair); counts.iloc[i,j]=n
            if n<minimum or pair.iloc[:,0].nunique()<2 or (i!=j and pair.iloc[:,1].nunique()<2):
                continue
            if i==j:
                corr.iloc[i,j]=1.; continue
            fn={'pearson':stats.pearsonr,'spearman':stats.spearmanr,'kendall':stats.kendalltau}[method]
            coefficient,p=fn(pair.iloc[:,0],pair.iloc[:,1])
            corr.iloc[i,j]=coefficient
            if i<j:
                fit=stats.linregress(pair.iloc[:,0],pair.iloc[:,1])
                pairs.append([left,right,n,coefficient,coefficient**2,p,fit.slope,fit.intercept,fit.rvalue**2])
    table=pd.DataFrame(pairs,columns=['X','Y','n','Coefficient','Squared coefficient','p (uncorrected)','OLS slope','OLS intercept','OLS R²'])
    if len(table):
        p=table['p (uncorrected)'].to_numpy(); order=np.argsort(p)
        q=np.minimum.accumulate((p[order]*len(p)/np.arange(1,len(p)+1))[::-1])[::-1]
        result=np.empty(len(p)); result[order]=np.clip(q,0,1); table['q (BH)']=result
    require(len(table)>0,'No variable pair has enough nonconstant finite observations','Aucune paire ne contient assez de valeurs valides et variables')
    return {'kind':'correlation','mode':mode,'options':options,'numeric':numeric,'correlation':corr,'counts':counts,
            'tables':{'Correlation':corr,'Pair counts':counts,'Bivariate statistics':table},
            'notes':['Pairwise complete observations; constant/insufficient pairs remain undefined, not zero.',
                     f'Method: {method}; minimum pairs: {minimum}. p values assume independent samples; q uses Benjamini–Hochberg correction.',
                     'Squared association is not the predictive test R². OLS R² refers only to a simple linear fit with intercept. Correlation does not prove causation.']}


def regression_metrics(observed,predicted):
    observed=np.asarray(observed,float); predicted=np.asarray(predicted,float)
    residual=observed-predicted
    total=np.sum((observed-observed.mean())**2)
    return {'R²':1-np.sum(residual**2)/total if len(observed)>1 and total>0 else np.nan,
            'RMSE':float(np.sqrt(np.mean(residual**2))),'MAE':float(np.mean(np.abs(residual)))}


def prediction_analysis(frame,options,progress=None):
    from sklearn.ensemble import RandomForestRegressor,GradientBoostingRegressor
    from sklearn.dummy import DummyRegressor
    from sklearn.pipeline import Pipeline
    from sklearn.impute import SimpleImputer
    from sklearn.model_selection import train_test_split,GroupShuffleSplit,GroupKFold,KFold,TimeSeriesSplit,RandomizedSearchCV
    from threadpoolctl import threadpool_limits
    features=list(options['features']); target=options['target']; split=options.get('split','random')
    require(features and target not in features,'Select predictors separate from the response','Séparez les prédicteurs et la réponse')
    data=numeric_frame(frame,features+[target])
    valid=data[target].notna().to_numpy()
    positions=np.flatnonzero(valid); unknown=np.flatnonzero(~valid)
    require(12<=len(positions)<=100000,'Regression needs 12–100,000 labelled rows','La régression nécessite 12 à 100 000 lignes étiquetées')
    x=data.loc[valid,features]; y=data.loc[valid,target]
    require(y.nunique()>1,'The response must vary','La réponse doit varier')
    fraction=float(options.get('test_fraction',.2)); repeats=int(options.get('repeats',3)); seed=int(options.get('seed',42))
    require(.1<=fraction<=.5 and 1<=repeats<=10,'Invalid test fraction or repeats','Fraction de test ou répétitions invalides')
    require(split in ('random','group','ordered'),'Choose a split strategy','Choisissez une séparation')
    groups=None
    if split=='group':
        group=options.get('group')
        require(group in frame and group not in features+[target],'Use a separate site/well group column','Utilisez une colonne distincte de site/puits')
        require(frame.loc[valid,group].notna().all(),'Group labels cannot be missing','Les groupes ne peuvent pas être manquants')
        groups=frame.loc[valid,group].astype(str).to_numpy()
        require(len(np.unique(groups))>=3,'At least three independent groups are required','Trois groupes indépendants minimum')
    requested=options.get('algorithm','both')
    require(requested in ('both','rf','gb'),'Unknown model','Modèle inconnu')
    require(10<=int(options.get('trees',100))<=500,'Use 10–500 trees','Utilisez 10 à 500 arbres')
    require(len(frame)*repeats*(3 if requested=='both' else 2)<=200000,
            'Reduce data size or repeats: prediction history is limited to 200,000 rows',
            'Réduisez les données ou répétitions : historique limité à 200 000 prédictions')
    rows=[]; predictions=[]; importance=[]; parameters=[]
    for repeat in range(repeats):
        rng=seed+repeat
        if split=='group':
            train,test=next(GroupShuffleSplit(n_splits=1,test_size=fraction,random_state=rng).split(x,y,groups))
        elif split=='ordered':
            boundary=int(len(x)*(1-fraction)); train=np.arange(boundary); test=np.arange(boundary,len(x))
        else:
            train,test=train_test_split(np.arange(len(x)),test_size=fraction,random_state=rng)
        require(len(train)>=6 and len(test)>=3,'Each split needs six training and three test rows','Chaque séparation exige six lignes d’apprentissage et trois de test')
        require(not x.iloc[train].isna().all().any(),'A predictor has no training values; choose another split or variable','Un prédicteur est entièrement manquant en apprentissage')
        models={'Mean baseline':DummyRegressor(strategy='mean')}
        common={'n_estimators':int(options.get('trees',100)),'min_samples_leaf':int(options.get('min_leaf',1)),'random_state':rng}
        if requested in ('both','rf'):
            models['Random Forest']=RandomForestRegressor(**common,max_depth=int(options.get('rf_depth',0)) or None,n_jobs=1)
        if requested in ('both','gb'):
            models['Gradient Boosting']=GradientBoostingRegressor(**common,max_depth=int(options.get('gb_depth',3)),learning_rate=float(options.get('learning_rate',.05)))
        for name,estimator in models.items():
            pipeline=Pipeline([('imputer',SimpleImputer(strategy='median')),('model',estimator)])
            cv_rmse=np.nan
            with threadpool_limits(limits=1):
                if options.get('tune') and name!='Mean baseline':
                    folds=int(options.get('folds',3)); trials=int(options.get('trials',6))
                    require(2<=folds<=5 and 1<=trials<=12,'Use 2–5 CV folds and 1–12 search trials','Utilisez 2 à 5 plis et 1 à 12 essais')
                    if split=='group':
                        require(len(np.unique(groups[train]))>=folds,'Not enough training groups for CV','Groupes d’apprentissage insuffisants pour la validation croisée')
                        cv=GroupKFold(n_splits=folds)
                    elif split=='ordered':
                        cv=TimeSeriesSplit(n_splits=folds)
                    else:
                        cv=KFold(n_splits=folds,shuffle=True,random_state=rng)
                    distribution={'model__n_estimators':[50,100,200], 'model__min_samples_leaf':[1,2,4]}
                    if name=='Random Forest':
                        distribution.update({'model__max_depth':[None,6,12,20],'model__max_features':['sqrt',1.]})
                    else:
                        distribution.update({'model__max_depth':[2,3,5],'model__learning_rate':[.02,.05,.1]})
                    search=RandomizedSearchCV(pipeline,distribution,n_iter=trials,scoring='neg_root_mean_squared_error',
                        cv=cv,random_state=rng,n_jobs=1,refit=True,error_score='raise')
                    search.fit(x.iloc[train],y.iloc[train],**({'groups':groups[train]} if split=='group' else {}))
                    pipeline=search.best_estimator_; cv_rmse=-float(search.best_score_)
                else:
                    pipeline.fit(x.iloc[train],y.iloc[train])
                for subset,index in [('Train',train),('Test',test)]:
                    predicted=pipeline.predict(x.iloc[index]); observed=y.iloc[index].to_numpy()
                    rows.append(dict(Model=name,Repeat=repeat+1,Split=subset,n=len(index),**regression_metrics(observed,predicted)))
                    predictions.extend([[name,repeat+1,subset,int(positions[i]),str(frame.index[positions[i]]),float(a),float(b),float(a-b)] for i,a,b in zip(index,observed,predicted)])
                if len(unknown) and options.get('predict_missing',True):
                    predicted=pipeline.predict(data.iloc[unknown][features])
                    predictions.extend([[name,repeat+1,'Unlabelled',int(i),str(frame.index[i]),np.nan,float(b),np.nan] for i,b in zip(unknown,predicted)])
            if name!='Mean baseline':
                importance.extend([[name,repeat+1,c,float(v)] for c,v in zip(features,pipeline.named_steps['model'].feature_importances_)])
            params=pipeline.named_steps['model'].get_params(deep=False)
            parameters.append([name,repeat+1,cv_rmse,json.dumps({k:v for k,v in params.items() if isinstance(v,(str,int,float,bool,type(None)))},sort_keys=True)])
        if progress:
            progress(int(90*(repeat+1)/repeats))
    metrics=pd.DataFrame(rows)
    summary=metrics.groupby(['Model','Split'],sort=False)[['R²','RMSE','MAE']].agg(['mean','std'])
    summary.columns=[a+' '+b for a,b in summary.columns]; summary=summary.reset_index()
    return {'kind':'prediction','options':options,'tables':{'Train and test metrics':metrics,'Repeated-split summary':summary,
            'Predictions':pd.DataFrame(predictions,columns=['Model','Repeat','Split','Row position (0-based)','Source index','Observed','Predicted','Residual (observed - predicted)']),
            'Feature importance':pd.DataFrame(importance,columns=['Model','Repeat','Feature','Importance']),
            'Hyperparameters':pd.DataFrame(parameters,columns=['Model','Repeat','Training CV RMSE','Parameters'])},
            'notes':[f'Labelled rows: {len(positions)}; missing responses: {len(unknown)}; split: {split}; seed: {seed}; repeats: {repeats}.',
                     'Median imputation is fitted on training data only, including inside each CV fold. Model selection uses training CV RMSE; test rows are held out.',
                     'R² can be negative and is undefined for a constant response. RMSE/MAE keep the response unit. Repeated-split SD is not a confidence interval.',
                     'Random splits assume independent observations; use held-out site/well groups for spatially correlated data. Ordered splits preserve row order.',
                     'Tree importances are impurity-based training diagnostics and may favour high-cardinality features. Plots show repeat 1; exported tables contain every repeat.',
                     'Unlabelled predictions use the training model, not a model secretly refitted on the test set. Trained estimators are not saved in project files.']}


def compute(kind,frame,options,progress=None):
    if kind=='maps': result=spatial_analysis(frame,options)
    elif kind=='scene': result=spatial_analysis(frame,options,True)
    elif kind=='relations': result=relationship_analysis(frame,options)
    elif kind=='prediction': result=prediction_analysis(frame,options,progress)
    else: raise ValueError('Unknown workspace / Espace inconnu')
    return localize_result(result)


def new_figure(title,rows=1,cols=1,size=(10,7)):
    fig=Figure(figsize=size,dpi=125,facecolor='white',layout='constrained')
    fig.suptitle(title,color='#172a20',fontsize=13)
    axes=fig.subplots(rows,cols,squeeze=False)
    for ax in axes.flat:
        ax.set_facecolor('white'); ax.tick_params(labelsize=9)
        ax.grid(alpha=.22)
        ax.ticklabel_format(style='plain',useOffset=False,axis='both')
    return fig,axes


def scene_box_aspect(result,exaggeration):
    if result['mode']=='points': spans=np.ptp(result['points'],axis=0)
    elif result['mode'] in ('slices','voxels'): spans=np.array([np.ptp(a) for a in result['axes']])
    else: spans=np.array([np.ptp(result['axes'][0]),np.ptp(result['axes'][1]),np.nanmax(result['field'])-np.nanmin(result['field'])])
    spans=np.maximum(spans,max(float(np.max(spans)),1.)*1e-6)
    return spans*np.array([1,1,exaggeration])


def scene_limits(result):
    """Fixed, finite bounds keep the orbit target at the data-box centre."""
    if result['mode']=='points':
        table=result.get('tables',{}).get('Point cloud')
        points=table[['X','Y','Z']].to_numpy(float) if table is not None else result['points']
        lower=points.min(axis=0); upper=points.max(axis=0)
    else:
        axes=result['axes']
        lower=[a.min() for a in axes]; upper=[a.max() for a in axes]
        if len(axes)==2:
            values=result['values'] if result['mode']=='tin' else result['field']
            lower.append(np.nanmin(values)); upper.append(np.nanmax(values))
        lower=np.asarray(lower,float); upper=np.asarray(upper,float)
    span=upper-lower
    padding=np.maximum(span*.04,np.maximum(np.abs(lower),1)*1e-9)
    return [(float(lo-pad),float(hi+pad)) for lo,hi,pad in zip(lower,upper,padding)]


def translate_figures(plots,language):
    """Translate generated captions, retaining original user variable names."""
    words={'Map':'Carte','Profile':'Profil','3D view':'Vue 3D','Correlation heatmap':'Carte des corrélations',
        'Scatter matrix':'Matrice de nuages','Bivariate plot':'Graphique bivarié','Model comparison':'Comparaison des modèles',
        'Residual diagnostics':'Diagnostic des résidus','Observed vs predicted':'Observé et prédit','Feature importance':'Importance des variables',
        'Train / test RMSE · repeated-split mean':'RMSE apprentissage / test · moyenne des répétitions',
        'Residuals · repeat 1':'Résidus · répétition 1','Observed vs predicted · repeat 1':'Observé et prédit · répétition 1',
        'Feature importance · repeated-model mean':'Importance des variables · moyenne des répétitions',
        'Observed':'Observé','Predicted':'Prédit','Observed - predicted':'Observé - prédit',
        'Impurity-based importance':'Importance selon l’impureté','Train':'Apprentissage','Test':'Test','undefined':'indéfini',
        'Distance (coordinate unit)':'Distance (unité des coordonnées)'}
    for mode,fr in [('points','points'),('surface','surface'),('tin','surface triangulée'),('wireframe','maillage filaire'),('slices','coupes du volume'),('voxels','voxels')]:
        words['3D · '+mode]='3D · '+fr
    for method in ('pearson','spearman','kendall'):
        words[method+' · squared association']=method+' · coefficient au carré'
        words[method+' · signed correlation']=method+' · corrélation signée'
    def caption(item):
        if not hasattr(item,'_stc_english_text'): item._stc_english_text=item.get_text()
        original=item._stc_english_text
        translated=words.get(original,original)
        for model in ('Random Forest','Gradient Boosting'):
            if original.startswith(model+' · Train\n'):
                translated=original.replace(' · Train\n',' · Apprentissage\n',1)
        item.set_text(translated if language=='fr' else original)
    result=[]
    for name,figure in plots:
        if not hasattr(figure,'_stc_plot_name'): figure._stc_plot_name=name
        original=figure._stc_plot_name
        if figure._suptitle: caption(figure._suptitle)
        for ax in figure.axes:
            caption(ax.title)
            if original in ('Observed vs predicted','Residual diagnostics','Feature importance','Profile'):
                caption(ax.xaxis.label)
                if original!='Profile': caption(ax.yaxis.label)
            legend=ax.get_legend()
            if legend and original=='Model comparison':
                for item in legend.get_texts(): caption(item)
        result.append((words.get(original,original) if language=='fr' else original,figure))
    return result


def render_result(result):
    """Return named live Matplotlib figures; called on the GUI thread or in Jupyter."""
    options=result['options']; kind=result['kind']; plots=[]
    cmap=options.get('cmap','viridis')
    require(cmap in CMAPS,'Choose a supported colour map','Palette non prise en charge')
    if kind in ('map','scene'):
        mode=result['mode']
        if kind=='scene':
            # Fixed margins: constrained-layout moves the axes as rotated labels
            # change size, making the model appear to orbit an unstable centre.
            fig=Figure(figsize=(10,7),dpi=125,facecolor='white'); ax=fig.add_subplot(111,projection='3d')
            fig.subplots_adjust(left=.02,right=.80,bottom=.08,top=.91)
            exaggeration=float(options.get('exaggeration',1))
            require(.01<=exaggeration<=100,'Invalid vertical exaggeration','Exagération verticale invalide')
            if mode=='points':
                p=result['points']; artist=ax.scatter(p[:,0],p[:,1],p[:,2],c=result['values'],s=8,cmap=cmap,alpha=.85)
                label=result['value_name']
            elif mode in ('slices','voxels'):
                x,y,z=result['axes']; field=result['field']; finite=field[np.isfinite(field)]
                norm=__import__('matplotlib.colors',fromlist=['Normalize']).Normalize(vmin=finite.min(),vmax=finite.max())
                color=__import__('matplotlib',fromlist=['colormaps']).colormaps[cmap]
                if mode=='voxels':
                    threshold=float(np.percentile(finite,float(options.get('threshold',50))))
                    # Voxel edge coordinates are half a cell beyond sample centres.
                    edges=[np.r_[a-(a[1]-a[0])/2,a[-1]+(a[1]-a[0])/2] for a in (x,y,z)]
                    xx,yy,zz=np.meshgrid(*edges,indexing='ij')
                    ax.voxels(xx,yy,zz,np.isfinite(field)&(field>=threshold),facecolors=color(norm(np.nan_to_num(field,nan=finite.min()))),edgecolor=None)
                    ax.set_title(f'Cells ≥ percentile {options.get("threshold",50):g}; threshold={threshold:.5g}',fontsize=10)
                else:
                    ix,iy,iz=[len(a)//2 for a in (x,y,z)]
                    yy,zz=np.meshgrid(y,z,indexing='ij')
                    ax.plot_surface(np.full_like(yy,x[ix]),yy,zz,facecolors=color(norm(field[ix,:,:])),shade=False)
                    xx,zz=np.meshgrid(x,z,indexing='ij')
                    ax.plot_surface(xx,np.full_like(xx,y[iy]),zz,facecolors=color(norm(field[:,iy,:])),shade=False)
                    xx,yy=np.meshgrid(x,y,indexing='ij')
                    ax.plot_surface(xx,yy,np.full_like(xx,z[iz]),facecolors=color(norm(field[:,:,iz])),shade=False)
                from matplotlib.cm import ScalarMappable
                artist=ScalarMappable(norm=norm,cmap=cmap); label=result['value_name']
            else:
                x,y=result['axes']; xx,yy=np.meshgrid(x,y); field=result['field']
                if mode=='tin':
                    p=result['points']
                    artist=ax.plot_trisurf(p[:,0],p[:,1],result['values'],triangles=np.asarray(result['triangles'],int),cmap=cmap,linewidth=.1)
                elif mode=='wireframe':
                    ax.plot_wireframe(xx,yy,field,color='#22965e',rcount=35,ccount=35); artist=None
                else:
                    artist=ax.plot_surface(xx,yy,field,cmap=cmap,rcount=min(100,len(y)),ccount=min(100,len(x)),linewidth=0,antialiased=True)
                label=result['value_name']
            names=result['coordinate_names']
            ax.set(xlabel=names[0],ylabel=names[1],zlabel=options['z'])
            from matplotlib.ticker import MaxNLocator
            for axis in (ax.xaxis,ax.yaxis,ax.zaxis):
                axis.set_major_locator(MaxNLocator(3))
                axis.set_tick_params(labelsize=8,pad=2)
            ax.ticklabel_format(style='sci',scilimits=(-3,4),useOffset=False)
            ax.set_box_aspect(scene_box_aspect(result,exaggeration))
            bounds=scene_limits(result)
            ax.set_xlim3d(*bounds[0]); ax.set_ylim3d(*bounds[1]); ax.set_zlim3d(*bounds[2])
            ax.view_init(elev=float(options.get('elevation',28)),azim=float(options.get('azimuth',-60)),roll=0)
            if options.get('depth_down'): ax.invert_zaxis()
            if artist is not None: fig.colorbar(artist,cax=fig.add_axes([.88,.23,.022,.54]),label=label)
            fig.suptitle('3D · '+mode)
            plots.append(('3D view',fig))
        else:
            fig,axes=new_figure(result['value_name']+' · '+mode); ax=axes[0,0]
            if mode=='samples':
                p=result['points']
                artist=ax.scatter(p[:,0],p[:,1],c=result['values'],s=22,cmap=cmap) if options.get('value') is not None else ax.scatter(p[:,0],p[:,1],s=22,color='#22965e')
            else:
                x,y=result['axes']; field=np.ma.masked_invalid(result['field']); xx,yy=np.meshgrid(x,y)
            if mode in ('contour','lines'):
                artist=ax.contourf(xx,yy,field,levels=15,cmap=cmap) if mode=='contour' else ax.contour(xx,yy,field,levels=12,cmap=cmap)
                if mode=='lines': ax.clabel(artist,inline=True,fontsize=8)
            elif mode=='hillshade':
                from matplotlib.colors import LightSource
                from scipy.ndimage import binary_erosion
                finite=np.isfinite(result['field']); filled=np.where(finite,result['field'],np.nanmedian(result['field']))
                image=LightSource(azdeg=315,altdeg=45).hillshade(filled,dx=result['spacing'],dy=result['spacing'])
                supported=binary_erosion(finite,structure=np.ones((3,3)),border_value=1)
                artist=ax.pcolormesh(xx,yy,np.ma.masked_where(~supported,image),cmap='gray',shading='nearest')
            elif mode!='samples':
                artist=ax.pcolormesh(xx,yy,field,cmap=cmap,shading='nearest')
            ax.set(xlabel=result['coordinate_names'][0],ylabel=result['coordinate_names'][1]); ax.set_aspect('equal',adjustable='box')
            ax.tick_params(axis='x',labelrotation=20)
            if mode!='samples' or options.get('value') is not None:
                fig.colorbar(artist,ax=ax,label='Hillshade (relative)' if mode=='hillshade' else result['value_name'])
            plots.append(('Map',fig))
        if 'Profile' in result['tables']:
            profile=result['tables']['Profile']; fig,axes=new_figure('Profile')
            axes[0,0].plot(profile['Distance'],profile['Value'],color='#188650')
            axes[0,0].set(xlabel='Distance (coordinate unit)',ylabel=result['value_name']); plots.append(('Profile',fig))
    elif kind=='correlation':
        numeric=result['numeric']; corr=result['correlation']; mode=result['mode']; columns=list(numeric.columns)
        if mode=='heatmap':
            squared=bool(options.get('squared')); values=corr.to_numpy()**2 if squared else corr.to_numpy()
            fig,axes=new_figure(options.get('method','pearson')+(' · squared association' if squared else ' · signed correlation'))
            ax=axes[0,0]; ax.grid(False)
            artist=ax.imshow(np.ma.masked_invalid(values),vmin=0 if squared else -1,vmax=1,cmap='viridis' if squared else 'coolwarm',aspect='auto')
            ax.set_xticks(range(len(columns)),columns,rotation=25,ha='right',fontsize=8); ax.set_yticks(range(len(columns)),columns,fontsize=8)
            for i in range(len(columns)):
                for j in range(len(columns)):
                    value=values[i,j]; ax.text(j,i,'—' if not np.isfinite(value) else f'{value:.2f}',ha='center',va='center',fontsize=max(5,min(9,45/len(columns))),color='white' if squared and np.isfinite(value) and value<.45 else 'black')
            fig.colorbar(artist,ax=ax); plots.append(('Correlation heatmap',fig))
        elif mode=='matrix':
            n=len(columns); fig,axes=new_figure('Scatter matrix',n,n,(max(9,2.5*n),max(8,2.5*n)))
            for i in range(n):
                for j in range(n):
                    ax=axes[i,j]; pair=numeric[[columns[j],columns[i]]].dropna() if i!=j else numeric[[columns[i]]].dropna()
                    if i==j: ax.hist(pair.iloc[:,0],bins=15,color='#22965e')
                    else:
                        shown=pair.sample(3000,random_state=42) if len(pair)>3000 else pair
                        ax.scatter(shown.iloc[:,0],shown.iloc[:,1],s=5,alpha=.5,color='#22965e')
                        r=corr.iloc[i,j]; ax.set_title('undefined' if not np.isfinite(r) else f'r={r:.3f}',fontsize=9)
                    if i==n-1: ax.set_xlabel(columns[j])
                    if j==0: ax.set_ylabel(columns[i])
                    ax.tick_params(labelsize=7,axis='x',labelrotation=25)
                    from matplotlib.ticker import MaxNLocator
                    ax.xaxis.set_major_locator(MaxNLocator(3)); ax.yaxis.set_major_locator(MaxNLocator(3))
            plots.append(('Scatter matrix',fig))
        else:
            x,y=columns[:2]; pair=numeric[[x,y]].dropna(); fig,axes=new_figure(f'{y} vs {x}'); ax=axes[0,0]
            if mode=='density':
                artist=ax.hexbin(pair[x],pair[y],gridsize=35,mincnt=1,cmap=cmap); fig.colorbar(artist,ax=ax,label='Count')
            else:
                shown=pair.sample(5000,random_state=42) if len(pair)>5000 else pair
                ax.scatter(shown[x],shown[y],s=16,alpha=.65,color='#22965e')
            if len(pair)>=3 and pair[x].nunique()>1:
                fit=stats.linregress(pair[x],pair[y]); line=np.linspace(pair[x].min(),pair[x].max(),100)
                coefficient=corr.iloc[0,1]
                ax.plot(line,fit.intercept+fit.slope*line,color='#ca6d28',label=f'{options.get("method","pearson")}={coefficient:.4f}; OLS R²={fit.rvalue**2:.4f}; n={len(pair)}'); ax.legend()
            ax.set(xlabel=x,ylabel=y); ax.tick_params(axis='x',labelrotation=20); plots.append(('Bivariate plot',fig))
    elif kind=='prediction':
        metrics=result['tables']['Train and test metrics']; prediction=result['tables']['Predictions']; importance=result['tables']['Feature importance']
        summary=metrics.groupby(['Model','Split'])['RMSE'].mean().unstack()
        fig,axes=new_figure('Train / test RMSE · repeated-split mean')
        axis=axes[0,0]; xx=np.arange(len(summary))
        axis.bar(xx-.18,summary['Train'],.36,label='Train',color='#22965e'); axis.bar(xx+.18,summary['Test'],.36,label='Test',color='#426eae')
        axis.set_xticks(xx,summary.index); axis.set_ylabel('RMSE'); axis.legend(); plots.append(('Model comparison',fig))
        models=[m for m in metrics.Model.unique() if m!='Mean baseline']
        for residual in (False,True):
            fig,axes=new_figure('Residuals · repeat 1' if residual else 'Observed vs predicted · repeat 1',len(models),2,(11,4*len(models)))
            for i,model in enumerate(models):
                for j,subset in enumerate(('Train','Test')):
                    part=prediction[(prediction.Model==model)&(prediction.Repeat==1)&(prediction.Split==subset)]; ax=axes[i,j]
                    shown=part.sample(5000,random_state=42) if len(part)>5000 else part
                    ax.scatter(shown['Predicted'] if residual else shown['Observed'],shown['Residual (observed - predicted)'] if residual else shown['Predicted'],s=12,alpha=.65,color='#22965e' if j==0 else '#426eae')
                    if residual: ax.axhline(0,color='#b66b32'); ax.set(xlabel='Predicted',ylabel='Observed - predicted')
                    else:
                        lower=min(part.Observed.min(),part.Predicted.min()); upper=max(part.Observed.max(),part.Predicted.max())
                        ax.plot([lower,upper],[lower,upper],color='#b66b32'); ax.set(xlabel='Observed',ylabel='Predicted')
                    scores=metrics[(metrics.Model==model)&(metrics.Repeat==1)&(metrics.Split==subset)].iloc[0]
                    r2=f'{scores["R²"]:.3f}' if np.isfinite(scores['R²']) else '—'
                    ax.set_title(f'{model} · {subset}\nR²={r2}, RMSE={scores.RMSE:.4g}, MAE={scores.MAE:.4g}',fontsize=10)
            plots.append(('Residual diagnostics' if residual else 'Observed vs predicted',fig))
        fig,axes=new_figure('Feature importance · repeated-model mean',1,len(models),(11,6))
        for ax,model in zip(axes.flat,models):
            values=importance[importance.Model==model].groupby('Feature').Importance.mean().sort_values()
            ax.barh(values.index,values,color='#22965e'); ax.set_title(model); ax.set_xlabel('Impurity-based importance')
        plots.append(('Feature importance',fig))
    return translate_figures(plots,options.get('language','en'))


def pack_result(result):
    """Safe JSON payload for project metadata and the subprocess boundary."""
    def pack(value):
        if isinstance(value,pd.DataFrame): return {'__table__':json.loads(value.to_json(orient='split',date_format='iso',double_precision=15))}
        if isinstance(value,np.ndarray):
            clean=value.astype(object)
            clean[~np.isfinite(value)]=None
            return {'__array__':True,'shape':list(value.shape),'values':clean.tolist()}
        if isinstance(value,dict): return {k:pack(v) for k,v in value.items()}
        if isinstance(value,(list,tuple)): return [pack(v) for v in value]
        if isinstance(value,np.generic): return value.item()
        return value
    return pack(result)


def unpack_result(result):
    def unpack(value):
        if isinstance(value,dict) and '__table__' in value:
            item=value['__table__']; require(len(item['data'])<=3000000,'Saved table too large','Table enregistrée trop grande')
            return pd.DataFrame(item['data'],columns=item['columns'],index=item['index'])
        if isinstance(value,dict) and value.get('__array__'):
            require(math.prod(value['shape'])<=2000000,'Saved array too large','Tableau enregistré trop grand')
            array=np.asarray(value['values'],dtype=float)
            if array.size==0 and math.prod(value['shape'])==0:
                array=array.reshape(value['shape'])
            require(list(array.shape)==value['shape'],'Invalid saved shape','Dimensions enregistrées invalides')
            return array
        if isinstance(value,dict): return {k:unpack(v) for k,v in value.items()}
        if isinstance(value,list): return [unpack(v) for v in value]
        return value
    return unpack(result)


def emit_result(result):
    from IPython.display import display
    for name,table in result['tables'].items():
        preview=display_table(name,table.head(150),result['options'].get('language'))
        display({'text/html':preview.to_html(),TABLE_MIME:preview.to_json(orient='split',double_precision=15)},raw=True,metadata={'stc':{'title':name+(f' · preview {len(preview)} / {len(table)}' if len(preview)<len(table) else '')}})
    for name,figure in render_result(result): display(figure)
    print('\n'.join(result['notes']))
    print('Full numerical tables: result["tables"]. Large tables are previewed above. / Tables complètes : result["tables"]. Aperçu des grandes tables ci-dessus.')

# RECIPE END

def notebook_code(kind,options):
    import inspect
    source=inspect.getsource(__import__(__name__,fromlist=['compute'])).split('# RECIPE END')[0]
    return ('# STC Statistics · reproducible recipe. Edit options here, then Run.\n'
            f'options = {options!r}\n%matplotlib inline\n\n'+source+
            f'\nresult = compute({kind!r}, df, options)\nemit_result(result)\n')

"""Small, explicit GIS interchange readers; no GDAL dependency or executable data."""
import io
import json
from pathlib import Path
import numpy as np
import pandas as pd


def require(condition,en,fr):
    if not condition: raise ValueError(en+' / '+fr)


def read_geojson(path):
    path=Path(path)
    require(path.stat().st_size<=40*1024**2,'GeoJSON exceeds 40 MB','GeoJSON dépasse 40 Mo')
    source=json.loads(path.read_text(encoding='utf-8-sig'))
    require(isinstance(source,dict),'Expected GeoJSON','GeoJSON attendu')
    if source.get('crs'):
        crs=str(source['crs'])
        require('4326' in crs or 'CRS84' in crs,'Only WGS84 point GeoJSON is supported','Seuls les points GeoJSON WGS84 sont pris en charge')
    features=source.get('features') if source.get('type')=='FeatureCollection' else [source] if source.get('type')=='Feature' else None
    require(isinstance(features,list) and 1<=len(features)<=100000,'Use 1–100,000 point features','Utilisez 1 à 100 000 entités ponctuelles')
    rows=[]
    for feature in features:
        geometry=feature.get('geometry') or {}
        require(geometry.get('type')=='Point','This reader supports point features, not polygon/line layers','Ce lecteur accepte les points, pas les polygones/lignes')
        position=geometry.get('coordinates',[])
        require(isinstance(position,list) and len(position) in (2,3),'Point needs longitude/latitude and optional elevation','Point : longitude/latitude et altitude facultative')
        require(all(isinstance(v,(int,float)) and np.isfinite(v) for v in position),'Coordinates must be finite numbers','Les coordonnées doivent être des nombres finis')
        require(-180<=position[0]<=180 and -90<=position[1]<=90,'GeoJSON uses WGS84 longitude/latitude','GeoJSON utilise la longitude/latitude WGS84')
        row={'Longitude':position[0],'Latitude':position[1]}
        if len(position)==3: row['Elevation_m']=position[2]
        props=feature.get('properties') or {}
        require(isinstance(props,dict),'Invalid point properties','Propriétés ponctuelles invalides')
        for key,value in props.items():
            key=str(key)
            while key in row: key='Property_'+key
            row[key]=json.dumps(value,ensure_ascii=False) if isinstance(value,(list,dict)) else value
        rows.append(row)
    return pd.DataFrame(rows)


def read_ascii_grid(path):
    path=Path(path)
    require(path.stat().st_size<=40*1024**2,'ASCII grid exceeds 40 MB','Grille ASCII supérieure à 40 Mo')
    lines=path.read_text(encoding='utf-8-sig').splitlines()
    header={}; start=0
    known={'ncols','nrows','xllcorner','yllcorner','xllcenter','yllcenter','cellsize','nodata_value'}
    for index,line in enumerate(lines):
        parts=line.split()
        if not parts: continue
        if parts[0].lower() not in known:
            start=index; break
        require(len(parts)==2,'Invalid grid header','En-tête de grille invalide')
        header[parts[0].lower()]=float(parts[1])
    require('ncols' in header and 'nrows' in header and 'cellsize' in header,'Missing grid dimensions','Dimensions de grille absentes')
    cols=int(header['ncols']); rows=int(header['nrows']); cell=header['cellsize']
    require(cols==header['ncols'] and rows==header['nrows'] and 1<=cols*rows<=100000 and cols>0 and rows>0 and np.isfinite(cell) and cell>0,
            'Use a positive square-cell grid with at most 100,000 cells','Grille à cellules carrées positives, limitée à 100 000 cellules')
    require(('xllcorner' in header or 'xllcenter' in header) and ('yllcorner' in header or 'yllcenter' in header),
            'Grid origin is missing','Origine de la grille absente')
    x0=header.get('xllcenter',header.get('xllcorner',0)+cell/2)
    y0=header.get('yllcenter',header.get('yllcorner',0)+cell/2)
    require(np.isfinite(x0) and np.isfinite(y0),'Grid origin must be finite','L’origine de la grille doit être finie')
    values=np.loadtxt(io.StringIO('\n'.join(lines[start:])),ndmin=2)
    require(values.shape==(rows,cols),'Grid values do not match the declared shape','Valeurs incompatibles avec les dimensions déclarées')
    values=np.where(values==header.get('nodata_value',-9999),np.nan,values)
    x,y=np.meshgrid(x0+np.arange(cols)*cell,y0+np.arange(rows-1,-1,-1)*cell)
    return pd.DataFrame({'X':x.ravel(),'Y':y.ravel(),'Value':values.ravel()})

# RECIPE END

def source_code(path):
    import inspect
    source=inspect.getsource(__import__(__name__,fromlist=['read_geojson'])).split('# RECIPE END')[0]
    reader='read_ascii_grid' if Path(path).suffix.lower()=='.asc' else 'read_geojson'
    return source+f'\ndf = {reader}({str(path)!r})\n'

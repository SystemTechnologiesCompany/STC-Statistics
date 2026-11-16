"""Typed spreadsheet, regular GIS grid and surface mesh exports."""
import os
from pathlib import Path
import tempfile
import numpy as np
import pandas as pd
from .science import require


def atomic_write(path,writer):
    path=Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent,suffix=path.suffix,delete=False) as stream:
        temporary=Path(stream.name)
    try:
        writer(temporary)
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def literal(value):
    return "'"+value if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')) else value


def export_table(table,path):
    suffix=Path(path).suffix.lower()
    require(suffix in ('.xlsx','.csv'),'Choose .xlsx or .csv','Choisissez .xlsx ou .csv')
    safe=table.copy()
    safe.columns=[literal(str(c)) for c in safe.columns]
    safe.index=safe.index.map(lambda v:literal(v) if isinstance(v,str) else v)
    for column in safe.columns:
        if safe[column].dtype=='object' or pd.api.types.is_string_dtype(safe[column].dtype):
            safe[column]=safe[column].map(literal)
    if suffix=='.xlsx':
        require(len(safe)<1048576,'Excel row limit exceeded; use CSV','Limite Excel dépassée ; utilisez CSV')
        atomic_write(path,lambda target:safe.to_excel(target,engine='openpyxl',index=True,index_label='Row'))
    else:
        atomic_write(path,lambda target:safe.to_csv(target,index=True,index_label='Row',encoding='utf-8-sig'))


def export_ascii(result,path):
    require(result.get('kind')=='map' and len(result['axes'])==2,'Only a 2D regular grid can be exported','Seule une grille régulière 2D peut être exportée')
    x,y=result['axes']; field=np.asarray(result['field'])
    cell=float(result['spacing'])
    require(field.shape==(len(y),len(x)) and np.allclose(np.diff(x),cell) and np.allclose(np.diff(y),cell),
            'Grid cells must be square and regular','Les cellules doivent être carrées et régulières')
    nodata=-9999.
    if np.any(field[np.isfinite(field)]==nodata): nodata=-3.402823466e38
    require(not np.any(field[np.isfinite(field)]==nodata),'NoData value collides with the grid','Valeur NoData présente dans la grille')
    epsg=result.get('crs_epsg')
    projection_path=Path(path).with_suffix('.prj')
    require(epsg is not None or not projection_path.exists(),
            'An existing projection sidecar could be wrong; choose a new filename',
            'Un ancien fichier de projection pourrait être incorrect ; choisissez un autre nom')
    header=f'ncols {len(x)}\nnrows {len(y)}\nxllcorner {x[0]-cell/2:.17g}\nyllcorner {y[0]-cell/2:.17g}\ncellsize {cell:.17g}\nNODATA_value {nodata:.17g}\n'
    def writer(target):
        with target.open('w',encoding='ascii') as stream:
            stream.write(header)
            np.savetxt(stream,np.where(np.isfinite(field),field,nodata)[::-1],fmt='%.17g')
    atomic_write(path,writer)
    if epsg:
        zone=int(epsg)%100; south=int(epsg)>=32700
        wkt=(f'PROJCS["WGS 84 / UTM zone {zone}{"S" if south else "N"}",'
             'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]],'
             f'PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",{zone*6-183}],'
             f'PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",{10000000 if south else 0}],UNIT["metre",1],AUTHORITY["EPSG","{epsg}"]]')
        atomic_write(projection_path,lambda target:target.write_text(wkt,encoding='ascii'))


def export_obj(result,path):
    require(result.get('kind')=='scene' and result.get('mode') in ('surface','wireframe','tin'),
            'Choose a surface/TIN/wireframe model','Choisissez une surface/TIN/maillage')
    if result['mode']=='tin':
        vertices=np.column_stack([result['points'],result['values']]); faces=np.asarray(result['triangles'],int)+1
    else:
        x,y=result['axes']; field=np.asarray(result['field']); xx,yy=np.meshgrid(x,y)
        valid=np.isfinite(field); mapping=np.full(field.shape,-1,int)
        mapping[valid]=np.arange(valid.sum())+1
        vertices=np.column_stack([xx[valid],yy[valid],field[valid]]); faces=[]
        for i in range(len(y)-1):
            for j in range(len(x)-1):
                a,b,c,d=mapping[i,j],mapping[i,j+1],mapping[i+1,j+1],mapping[i+1,j]
                if min(a,b,c)>0: faces.append((a,b,c))
                if min(a,c,d)>0: faces.append((a,c,d))
    require(len(vertices)>0 and len(faces)>0,'No finite surface triangles','Aucun triangle valide')
    def writer(target):
        with target.open('w',encoding='ascii') as stream:
            stream.write('# STC Statistics surface; native coordinates; view exaggeration not applied\n')
            for vertex in vertices: stream.write('v '+' '.join(f'{v:.17g}' for v in vertex)+'\n')
            for face in faces: stream.write('f '+' '.join(str(int(v)) for v in face)+'\n')
    atomic_write(path,writer)

"""Versioned project archives: typed data, notebook outputs and desktop settings."""
import io
import json
import os
from pathlib import Path
import tempfile
import zipfile
import pandas as pd
import nbformat


def save_project(path, frame, notebook, settings):
    payload = {'format': 'STC Statistics', 'version': 1, 'settings': settings,
               'notebook': json.loads(nbformat.writes(notebook))}
    encoded = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    data = frame.to_parquet(index=True) if frame is not None else None
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=Path(path).parent, suffix='.stcproj', delete=False) as f:
            temporary = f.name
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as z:
            z.writestr('project.json', encoded)
            if data is not None:
                z.writestr('data.parquet', data)
        os.replace(temporary, path)
    finally:
        if temporary and Path(temporary).exists():
            Path(temporary).unlink()


def load_project(path):
    with zipfile.ZipFile(path) as z:
        if len(z.infolist()) > 2 or any(i.file_size > 512*1024**2 for i in z.infolist()):
            raise ValueError('Project archive too large')
        if z.getinfo('project.json').file_size > 64*1024**2:
            raise ValueError('Project metadata too large')
        payload = json.loads(z.read('project.json'))
        if payload.get('format') != 'STC Statistics' or payload.get('version') != 1:
            raise ValueError('Unsupported project format')
        notebook = nbformat.reads(json.dumps(payload['notebook']), as_version=4)
        nbformat.validate(notebook)
        frame = pd.read_parquet(io.BytesIO(z.read('data.parquet'))) if 'data.parquet' in z.namelist() else None
    return frame, notebook, payload['settings']


def clean_frame(frame, columns, operation, value=''):
    result = frame.copy(deep=True)
    if not columns:
        raise ValueError('Select columns / Sélectionnez des colonnes')
    if operation == 'duplicates':
        return result.drop_duplicates(subset=columns)
    if operation == 'drop':
        return result.dropna(subset=columns)
    for c in columns:
        if operation == 'numeric':
            result[c] = pd.to_numeric(result[c].astype('string').str.strip().str.replace(',', '.', regex=False), errors='coerce')
        elif operation in ('mean', 'median'):
            numbers = pd.to_numeric(result[c], errors='raise')
            fill = getattr(numbers, operation)()
            if pd.isna(fill):
                raise ValueError(f'{c}: no numeric values')
            result[c] = numbers.fillna(fill)
        elif operation == 'mode':
            modes = result[c].mode()
            if modes.empty:
                raise ValueError(f'{c}: no mode')
            result[c] = result[c].fillna(modes.iloc[0])
        elif operation == 'constant':
            fill = float(value) if pd.api.types.is_numeric_dtype(result[c]) else value
            result[c] = result[c].fillna(fill)
        else:
            raise ValueError('Unknown operation')
    return result

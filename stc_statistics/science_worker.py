"""Disposable computation process: cancelling cannot corrupt a project/kernel."""
import json
import os
from pathlib import Path
import sys
import traceback
import pandas as pd
from .science import compute,pack_result


def main():
    folder=Path(sys.argv[1]).resolve()
    try:
        request=json.loads((folder/'request.json').read_text(encoding='utf-8'))
        frame=pd.read_parquet(folder/'data.parquet')
        def progress(percent):
            print(json.dumps({'progress':int(percent)}),flush=True)
        progress(5)
        result=compute(request['kind'],frame,request['options'],progress)
        progress(95)
        encoded=json.dumps(pack_result(result),ensure_ascii=True,allow_nan=False)
        if len(encoded)>48*1024**2:
            raise ValueError('Result exceeds the project budget; reduce grid size/repeats / Résultat trop grand : réduisez la grille/répétitions')
        (folder/'result.tmp').write_text(encoded,encoding='utf-8')
        os.replace(folder/'result.tmp',folder/'result.json')
        progress(100)
    except Exception as exc:
        (folder/'diagnostic.log').write_text(traceback.format_exc()[-24000:],encoding='utf-8')
        message=str(exc) if isinstance(exc,ValueError) and ' / ' in str(exc) else 'Calculation failed. Check your data and settings. / Calcul impossible. Vérifiez les données et paramètres.'
        (folder/'error.json').write_text(json.dumps({'message':message,'code':'STC-SCI101'}),encoding='utf-8')
        return 1
    return 0


if __name__=='__main__':
    sys.exit(main())

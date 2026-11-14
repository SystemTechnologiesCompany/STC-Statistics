"""Create small application-only updates for the existing bundled runtime."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import zipfile
from stc_statistics.update_installer import FORMAT, safe_name, validate_patch, version
from stc_statistics.version import APP_VERSION


def build_patch(root, destination, target, from_versions, notes=''):
    root,destination=Path(root),Path(destination)
    version(target)
    for previous in from_versions:
        if version(previous)>=version(target):
            raise ValueError('Target must be newer than every supported source version')
    files={}
    for path in [root/'main.py',*(root/'stc_statistics').rglob('*')]:
        if not path.is_file() or '__pycache__' in path.parts:
            continue
        name=path.relative_to(root).as_posix()
        if safe_name(name):
            files[name]=path.read_bytes()
    files['stc_statistics/version.py']=f"APP_VERSION = {target!r}\n".encode()
    metadata={'format':FORMAT,'version':target,'from_versions':list(from_versions),
              'python':f'{sys.version_info.major}.{sys.version_info.minor}',
              'files':{name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}}
    destination.mkdir(parents=True,exist_ok=True)
    package=destination/f'STC_Statistics_{target}_Update.zip'
    with zipfile.ZipFile(package,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('patch.json',json.dumps(metadata,indent=2))
        for name,raw in files.items():
            z.writestr(name,raw)
    digest=hashlib.sha256(package.read_bytes()).hexdigest()
    for previous in from_versions:
        validate_patch(package,digest,previous,target)
    manifest={'version':target,'package_type':FORMAT,'sha256':digest,'size_bytes':package.stat().st_size,
              'download_url':f'https://github.com/SystemTechnologiesCompany/STC-Statistics/releases/download/v{target}/{package.name}',
              'release_notes':notes}
    feed=destination/'update.json'
    feed.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return package,feed


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',default=APP_VERSION)
    parser.add_argument('--from-version',action='append',required=True)
    parser.add_argument('--output',default='releases')
    parser.add_argument('--notes',default='')
    args=parser.parse_args()
    package,feed=build_patch(Path(__file__).resolve().parent,args.output,args.version,args.from_version,args.notes)
    print(f'Created {package} and {feed}. No EXE was built or changed.')

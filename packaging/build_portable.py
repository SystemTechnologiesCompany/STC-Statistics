"""Create a single self-extracting Windows app using the installed, working Python layout."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from stc_statistics.version import APP_VERSION
from stc_statistics.licensing import require_configured_release
require_configured_release(root)

output = root / 'dist'
output.mkdir(exist_ok=True)
working = root / 'build' / 'portable'
working.mkdir(parents=True, exist_ok=True)
payload = working / 'runtime.zip'
base = Path(sys.base_prefix)
packages = Path(sys.prefix) / 'Lib' / 'site-packages'
ignored = {'__pycache__', 'tests', 'test', 'PyInstaller', '_pyinstaller_hooks_contrib', 'altgraph'}

def add_tree(archive, source, prefix, exclude_site=False):
    for directory, dirs, files in os.walk(source):
        dirs[:] = [name for name in dirs if name not in ignored and not (exclude_site and name == 'site-packages')]
        for name in files:
            if name.endswith(('.pyc', '.pyo', '.whl')):
                continue
            file = Path(directory) / name
            archive.write(file, (Path(prefix) / file.relative_to(source)).as_posix())

print('Bundling the private Python runtime and application packages...', flush=True)
with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for file in base.iterdir():
        if file.is_file() and (file.suffix.lower() in ('.exe', '.dll') or file.name == 'LICENSE.txt'):
            archive.write(file, file.name)
    add_tree(archive, base / 'DLLs', 'DLLs')
    add_tree(archive, base / 'Lib', 'Lib', exclude_site=True)
    add_tree(archive, base / 'tcl', 'tcl')
    add_tree(archive, packages, 'Lib/site-packages')
    add_tree(archive, root / 'stc_statistics', 'app/stc_statistics')
    archive.write(root / 'main.py', 'app/main.py')
    archive.writestr(f'python{sys.version_info.major}{sys.version_info.minor}._pth', '.\nDLLs\nLib\nLib/site-packages\napp\nimport site\n')
digest = hashlib.sha256(payload.read_bytes()).hexdigest()
source = (root / 'packaging' / 'PortableLauncher.cs').read_text(encoding='utf-8')
source = source.replace('_PAYLOAD_HASH_', digest).replace('_APP_VERSION_', APP_VERSION)
compiled_source = working / 'Launcher.cs'
compiled_source.write_text(source, encoding='utf-8')
compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET' / 'Framework64' / 'v4.0.30319' / 'csc.exe'
command = [str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
           '/reference:System.Windows.Forms.dll', '/reference:System.IO.Compression.dll',
           '/reference:System.IO.Compression.FileSystem.dll', '/win32icon:' + str(root / 'packaging' / 'stc.ico'),
           '/resource:' + str(payload) + ',stc_payload', '/out:' + str(output / 'STC Statistics.exe'), str(compiled_source)]
subprocess.run(command, check=True)
(output / 'STC_Statistics_build.json').write_text(json.dumps({
    'version': APP_VERSION, 'packaging': 'private-python-runtime', 'payload_sha256': digest,
    'update_config': json.loads((root / 'stc_statistics' / 'update_config.json').read_text(encoding='utf-8')),
}, indent=2), encoding='utf-8')
print('Created dist/STC Statistics.exe ({:.1f} MiB)'.format((output / 'STC Statistics.exe').stat().st_size / 1024 / 1024), flush=True)

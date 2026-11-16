"""Build the STC Windows setup wizard without replacing the portable baseline EXE."""
import argparse
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from stc_statistics.version import APP_VERSION
from stc_statistics.licensing import require_configured_release
from stc_statistics.update_installer import app_version,version


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024*1024),b''):
            value.update(block)
    return value.hexdigest()


def runtime_entry(name):
    parts=PurePosixPath(name).parts
    if not parts or name.startswith('/') or '\\' in name or ':' in name or any(p in ('..','.') for p in parts):
        raise ValueError('Unsafe runtime archive entry')
    return parts[0]!='app' and '__pycache__' not in parts and not name.endswith(('.pyc','.pyo'))


def stage_payload(root,stage,payload):
    root,stage,payload=Path(root),Path(stage),Path(payload)
    require_configured_release(root)
    metadata=json.loads((root/'dist/STC_Statistics_build.json').read_text(encoding='utf-8'))
    if digest(payload)!=metadata['payload_sha256']:
        raise ValueError('The private runtime archive does not match its verified build metadata')
    stage.mkdir(parents=True,exist_ok=False)
    runtime=stage/'runtime'
    runtime.mkdir()
    with zipfile.ZipFile(payload) as archive:
        for entry in archive.infolist():
            if not runtime_entry(entry.filename):
                continue
            target=runtime.joinpath(*PurePosixPath(entry.filename).parts)
            if not target.resolve().is_relative_to(runtime.resolve()):
                raise ValueError('Runtime extraction outside staging directory')
            if entry.is_dir():
                target.mkdir(parents=True,exist_ok=True)
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with archive.open(entry) as source,target.open('wb') as destination:
                    shutil.copyfileobj(source,destination)
    application=runtime/'app'
    application.mkdir()
    shutil.copy2(root/'main.py',application/'main.py')
    shutil.copytree(root/'stc_statistics',application/'stc_statistics',
                    ignore=shutil.ignore_patterns('__pycache__','*.pyc','*.pyo'))
    current=app_version(application)
    if current!=APP_VERSION:
        raise ValueError('Staged application version mismatch')
    if not (runtime/'pythonw.exe').is_file() or not (runtime/'python.exe').is_file():
        raise ValueError('The private interpreter is missing')
    (runtime/'.complete').write_text(metadata['payload_sha256'],encoding='ascii')
    shutil.copy2(root/'packaging/stc-statistics-desktop.ico',stage/'stc-statistics-desktop.ico')
    (stage/'installation.json').write_text(json.dumps({
        'product':'STC Statistics','version':current,'packaging':'installed-private-runtime',
        'architecture':'windows-x64','runtime_payload_sha256':metadata['payload_sha256']},indent=2),encoding='utf-8')
    (stage/'THIRD_PARTY_NOTICES.txt').write_text(
        'STC Statistics includes a private Python runtime and open-source libraries.\n'
        'Their original license files are retained in runtime/LICENSE.txt, runtime/Lib,\n'
        'runtime/Lib/site-packages/*dist-info/licenses and vendor directories.\n'
        'Python: https://www.python.org/psf/license/\n'
        'Qt for Python / PySide6: https://doc.qt.io/qtforpython-6/licenses.html\n'
        'Qt/PySide libraries remain separate replaceable files. Corresponding source:\n'
        'https://download.qt.io/official_releases/QtForPython/\n'
        'Other included libraries retain their individual notices and licenses.\n',encoding='utf-8')
    info={
      'en': 'STC Statistics\nSystem Technologies Company\n\n'
            'Install the statistics workspace for this Windows account.\n'
            'Windows 10 (1809 or newer) / Windows 11, 64-bit. Python and libraries are included.\n\n'
            'Activation: enter your STC UNIC CODE after opening the app.\n'
            'One license activates one PC and one Windows account. Internet is required at startup.\n'
            'No account registration is needed. Your data and notebooks are not sent for licensing.\n\n'
            'Need a code or a transfer? Contact STC:\n'
            'https://www.linkedin.com/company/system-technologies-company-stc/\n\n'
            'Updates download and install from inside the app.\n'
            'Projects, activation credentials and update recovery files are preserved on uninstall.\n',
      'fr': 'STC Statistics\nSystem Technologies Company\n\n'
            'Installez votre espace de statistiques pour ce compte Windows.\n'
            'Windows 10 (1809 ou plus récent) / Windows 11, 64 bits. Python et les bibliothèques sont inclus.\n\n'
            'Activation : saisissez votre STC UNIC CODE à la première ouverture.\n'
            'Une licence active un PC et un compte Windows. Internet est nécessaire au démarrage.\n'
            'Aucune inscription. Vos données et notebooks ne sont pas transmis pour la licence.\n\n'
            'Code ou transfert : contactez STC.\n'
            'https://www.linkedin.com/company/system-technologies-company-stc/\n\n'
            'Les mises à jour se téléchargent et s’installent dans l’application.\n'
            'Les projets, identifiants d’activation et fichiers de récupération sont conservés à la désinstallation.\n'
    }
    for language,text in info.items():
        (stage/f'setup-info-{language}.txt').write_text(text,encoding='utf-8-sig')
    validate_stage(stage)
    return current


def validate_stage(stage):
    stage=Path(stage)
    allowed={'runtime','STC Statistics.exe','stc-statistics-desktop.ico','installation.json',
             'THIRD_PARTY_NOTICES.txt','setup-info-en.txt','setup-info-fr.txt','wizard-large.bmp','wizard-small.bmp'}
    if any(p.name not in allowed for p in stage.iterdir()):
        raise ValueError('Unexpected installer staging content')
    for file in stage.rglob('*'):
        if not file.is_file():
            continue
        relative=file.relative_to(stage)
        public_ca=(file.name=='cacert.pem' and relative.parts[:2]==('runtime','Lib'))
        if ((file.suffix.lower()=='.pem' and not public_ca)
                or file.suffix.lower() in ('.env','.sqlite','.sqlite3','.stcp','.stcproj','.stcproject')
                or file.name.startswith('.env') or file.name in ('activation.bin','edge-secrets.env','pepper.key')
                or any(part in ('.licensing_private','licensing_server','supabase','.git','.venv') for part in relative.parts)):
            raise ValueError('Private material or a user project was found in installer staging')
    app=stage/'runtime/app'
    if (app/'licensing_server').exists() or (app/'supabase').exists():
        raise ValueError('Server administration must not be shipped to buyers')
    require_configured_release(app)
    return app_version(app)


def find_compiler(explicit=None):
    candidates=[explicit,os.environ.get('STC_ISCC'),shutil.which('ISCC.exe'),
                ROOT/'build/installer-tools/InnoSetup7/ISCC.exe',
                Path(os.environ.get('ProgramFiles','C:/Program Files'))/'Inno Setup 7/ISCC.exe',
                Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Inno Setup 7/ISCC.exe']
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate).resolve()
    raise FileNotFoundError('Inno Setup 7+ compiler not found. Install it from jrsoftware.org, or set STC_ISCC to ISCC.exe.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--iscc')
    parser.add_argument('--reuse-stage',action='store_true',help='Reuse the validated private runtime staging directory')
    args=parser.parse_args()
    require_configured_release(ROOT)
    compiler=find_compiler(args.iscc)
    baseline=ROOT/'dist/STC Statistics.exe'
    baseline_hash=digest(baseline)
    work=ROOT/'build/installer'/APP_VERSION
    stage=work/'stage'
    work.mkdir(parents=True,exist_ok=True)
    if args.reuse_stage:
        if validate_stage(stage)!=APP_VERSION:
            raise ValueError('Staging version differs; prepare a new stage')
    else:
        if stage.exists():
            raise FileExistsError('Installer stage already exists. Use --reuse-stage after validation, or choose a fresh build directory.')
        print('Staging the verified private interpreter and current licensed application...',flush=True)
        stage_payload(ROOT,stage,ROOT/'build/portable/runtime.zip')
    csharp=(ROOT/'packaging/InstalledLauncher.cs').read_text(encoding='utf-8').replace('_APP_VERSION_',APP_VERSION)
    source=work/'InstalledLauncher.cs'
    source.write_text(csharp,encoding='utf-8-sig')
    csc=Path(os.environ.get('WINDIR','C:/Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(csc),'/nologo','/target:winexe','/platform:x64','/optimize+',
                    '/reference:System.Windows.Forms.dll','/win32icon:'+str(stage/'stc-statistics-desktop.ico'),
                    '/out:'+str(stage/'STC Statistics.exe'),str(source)],check=True)
    subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                    str(ROOT/'packaging/installer_artwork.ps1'),'-Stage',str(stage)],check=True)
    validate_stage(stage)
    # Preserve Unicode strings for the compiler independent of Windows code page.
    script=work/'installer.iss'
    script.write_text((ROOT/'packaging/installer.iss').read_text(encoding='utf-8'),encoding='utf-8-sig')
    output=ROOT/'dist/setup'
    output.mkdir(parents=True,exist_ok=True)
    log=work/'compiler.log'
    print('Compiling the English/French Windows setup wizard...',flush=True)
    with log.open('w',encoding='utf-8') as stream:
        result=subprocess.run([str(compiler),'/DStageDir='+str(stage),'/DAppVersion='+APP_VERSION,
                               '/DOutputDir='+str(output),str(script)],stdout=stream,stderr=subprocess.STDOUT)
    if result.returncode:
        print(log.read_text(encoding='utf-8',errors='replace')[-8000:])
        raise RuntimeError('Installer compilation failed; see '+str(log))
    installer=output/f'STC_Statistics_{APP_VERSION}_Setup.exe'
    if digest(baseline)!=baseline_hash:
        raise RuntimeError('The original portable EXE changed unexpectedly')
    (output/f'STC_Statistics_{APP_VERSION}_Setup.json').write_text(json.dumps({
        'version':APP_VERSION,'filename':installer.name,'sha256':digest(installer),
        'size_bytes':installer.stat().st_size,'platform':'Windows 10 (1809+)/11 x64',
        'signed':False,'baseline_portable_exe_unchanged':True},indent=2),encoding='utf-8')
    print('Created '+str(installer))
    print('Original portable EXE unchanged. No license codes, tokens or signing keys are included.')


if __name__=='__main__':
    main()

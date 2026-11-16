"""Standalone, stdlib-only app patch validator and restart/rollback helper.

Copied outside app/ before installation so it survives the directory swap.
User projects and the bundled interpreter/libraries are never replaced.
"""
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import time
import uuid
import zipfile

MAX_PACKAGE = 64 * 1024**2
MAX_EXPANDED = 192 * 1024**2
FORMAT = 'stc-app-patch-v1'
RUNTIME_ID = 'stc-python314-v1'
MIN_APP_VERSION = '0.5.1'


def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'\d+\.\d+\.\d+',value):
        raise ValueError('Invalid patch version')
    return tuple(map(int,value.split('.')))


def file_hash(path):
    digest=hashlib.sha256()
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024**2),b''):
            digest.update(chunk)
    return digest.hexdigest()


def app_version(root):
    tree=ast.parse((Path(root)/'stc_statistics/version.py').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='APP_VERSION' for t in node.targets):
            value=ast.literal_eval(node.value)
            version(value)
            return value
    raise ValueError('Application version is missing')


def safe_name(name):
    path=PurePosixPath(name)
    if ('\\' in name or ':' in name or path.is_absolute() or any(p in ('','..','.') for p in name.split('/'))
            or any(p.rstrip(' .')!=p for p in path.parts)):
        raise ValueError('Unsafe patch path')
    if any(re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])',p.split('.')[0],re.I) for p in path.parts):
        raise ValueError('Reserved Windows filename')
    if name=='main.py':
        return True
    return (len(path.parts)>=2 and path.parts[0]=='stc_statistics'
            and path.suffix.lower() in ('.py','.json','.png','.ico','.svg','.ttf','.otf'))


def validate_patch(package, expected_hash, current_version, target_version):
    if not re.fullmatch(r'[a-fA-F0-9]{64}',expected_hash or ''):
        raise ValueError('A SHA-256 checksum is required')
    if Path(package).stat().st_size>MAX_PACKAGE or file_hash(package)!=expected_hash.lower():
        raise ValueError('Update checksum mismatch or package too large')
    if version(target_version)<=version(current_version):
        raise ValueError('Update must be newer than the installed app')
    with zipfile.ZipFile(package) as z:
        entries=z.infolist()
        names=[i.filename for i in entries]
        if len(names)>1500 or len(set(n.casefold() for n in names))!=len(names):
            raise ValueError('Duplicate entries or too many patch files')
        if sum(i.file_size for i in entries)>MAX_EXPANDED or 'patch.json' not in names:
            raise ValueError('Invalid patch archive size or manifest')
        if z.getinfo('patch.json').file_size>1024**2:
            raise ValueError('Patch manifest too large')
        manifest=json.loads(z.read('patch.json'))
        if (manifest.get('format')!=FORMAT or manifest.get('version')!=target_version
                or manifest.get('python')!=f'{sys.version_info.major}.{sys.version_info.minor}'):
            raise ValueError('This update is not compatible with the installed app/runtime')
        if manifest.get('cumulative') is not None:
            if (manifest['cumulative'] is not True or manifest.get('runtime_id')!=RUNTIME_ID
                    or version(current_version)<version(manifest.get('minimum_version'))):
                raise ValueError('This cumulative update requires another runtime')
        elif current_version not in manifest.get('from_versions',[]):
            raise ValueError('This legacy update does not support the installed app')
        files=manifest.get('files',{})
        if not isinstance(files,dict) or set(files)!=set(names)-{'patch.json'}:
            raise ValueError('Patch file list mismatch')
        required={'main.py','stc_statistics/app.py','stc_statistics/version.py','stc_statistics/update_installer.py'}
        if not required.issubset(files):
            raise ValueError('Incomplete application patch')
        for entry in entries:
            if entry.filename=='patch.json':
                continue
            if (not safe_name(entry.filename) or (entry.external_attr>>16)&0o170000==0o120000
                    or entry.flag_bits&1):
                raise ValueError('Unsafe or encrypted patch entry')
            raw=z.read(entry)
            if hashlib.sha256(raw).hexdigest()!=files[entry.filename]:
                raise ValueError('Patch file checksum mismatch')
            if entry.filename.endswith('.py'):
                compile(raw,entry.filename,'exec')
        tree=ast.parse(z.read('stc_statistics/version.py').decode('utf-8'))
        declared=[ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='APP_VERSION' for t in n.targets)]
        if declared!=[target_version]:
            raise ValueError('Packaged code version mismatch')
    return manifest


def stage_patch(package, destination, expected_hash, current_version, target_version):
    manifest=validate_patch(package,expected_hash,current_version,target_version)
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(package) as z:
        for name in manifest['files']:
            target=destination.joinpath(*PurePosixPath(name).parts)
            if not target.resolve().is_relative_to(destination):
                raise ValueError('Patch path escapes staging directory')
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(z.read(name))
    return manifest


def replace_with_retry(source,destination):
    for attempt in range(25):
        try:
            os.replace(source,destination)
            return
        except PermissionError:
            if os.name!='nt' or attempt==24:
                raise
            time.sleep(min(.025*(attempt+1),.2))


def atomic_json(path, data):
    path=Path(path)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
        # Windows readers/antivirus can briefly hold a file without delete sharing.
        # Do not roll back a valid update over a transient status-file lock.
        replace_with_retry(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def wait_for_exit(pid, timeout=180):
    if not pid:
        return
    if pid<2 or pid==os.getpid():
        raise ValueError('Invalid application PID')
    if os.name=='nt':
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong]
        kernel.OpenProcess.restype=ctypes.c_void_p
        kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
        kernel.CloseHandle.argtypes=[ctypes.c_void_p]
        handle=kernel.OpenProcess(0x00100000,False,pid)
        if not handle:
            if ctypes.get_last_error()==87:
                return
            raise OSError('Cannot wait for running application')
        try:
            if kernel.WaitForSingleObject(handle,int(timeout*1000))!=0:
                raise TimeoutError('Close STC Statistics before installing the update')
        finally:
            kernel.CloseHandle(handle)
    else:
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            try:
                os.kill(pid,0)
            except ProcessLookupError:
                return
            time.sleep(.2)
        raise TimeoutError('Application did not close')


def launch_app(runtime, workspace=None, health=None, reverted=False):
    command=[str(Path(runtime)/('pythonw.exe' if os.name=='nt' else 'bin/python')), '-B',str(Path(runtime)/'app/main.py')]
    if workspace:
        command+=['--restore-workspace',str(workspace)]
    if health:
        command+=['--update-health',str(health)]
    if reverted:
        command+=['--update-reverted']
    env=dict(os.environ,STC_PORTABLE_ROOT=str(runtime))
    env.pop('PYTHONHOME',None)
    env.pop('PYTHONPATH',None)
    log=open(Path(health).parent/'restart.log' if health else Path(runtime).parent/'update-restart.log','ab')
    try:
        return subprocess.Popen(command,cwd=str(Path(runtime)/'app'),env=env,stdout=log,stderr=log,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    finally:
        log.close()


def install_job(job_file, launcher=launch_app, health_timeout=60):
    job_file=Path(job_file).resolve()
    job=json.loads(job_file.read_text(encoding='utf-8'))
    runtime=Path(job['runtime']).resolve()
    app=runtime/'app'
    if (runtime.name[:8]!='runtime-' or not (runtime/'.complete').is_file()
            or not (app/'main.py').is_file() or not job_file.is_relative_to(runtime.parent/'updates')):
        raise ValueError('Not an STC runtime/update job')
    if not Path(sys.executable).resolve().is_relative_to(runtime):
        # Tests pass an explicit fixture flag; the executable entry point never accepts it.
        if launcher is launch_app:
            raise ValueError('Installer must use the existing private runtime')
    folder=job_file.parent
    package=folder/'update.zip'
    stage=folder/'staged-app'
    workspace=folder/'workspace.stcproj'
    health=folder/'healthy.json'
    status=folder/'status.json'
    backup=runtime/('app-backup-'+folder.name)
    failed=runtime/('app-failed-'+folder.name)
    lock=runtime.parent/'updates/install.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.close(fd)
    swapped=False
    old_moved=False
    parent_closed=False
    child=None
    try:
        current=app_version(app)
        if current!=job['from_version']:
            raise ValueError('Installed app changed after the update was prepared')
        atomic_json(status,{'state':'verifying'})
        stage_patch(package,stage,job['sha256'],current,job['version'])
        atomic_json(folder/'ready.json',{'ready':True,'version':job['version']})
        wait_for_exit(job.get('pid'))
        parent_closed=True
        # All moves are confined to the verified runtime or its own update job.
        for path in (app,backup,failed):
            if path.parent!=runtime or path.is_symlink():
                raise ValueError('Unsafe application directory')
        atomic_json(status,{'state':'installing','backup':str(backup)})
        replace_with_retry(app,backup)
        old_moved=True
        replace_with_retry(stage,app)
        swapped=True
        atomic_json(status,{'state':'restarting','backup':str(backup)})
        child=launcher(runtime,workspace if workspace.is_file() else None,health)
        deadline=time.monotonic()+health_timeout
        while time.monotonic()<deadline:
            if health.is_file():
                ready=json.loads(health.read_text(encoding='utf-8'))
                if ready.get('version')==job['version'] and ready.get('workspace_restored') is True:
                    atomic_json(status,{'state':'installed','version':job['version'],'backup':str(backup),'workspace':str(workspace)})
                    return True
            if child.poll() is not None:
                break
            time.sleep(.2)
        raise RuntimeError('Updated app failed its startup/workspace check')
    except Exception as exc:
        if swapped:
            if child is not None and child.poll() is None:
                child.terminate()
                child.wait(timeout=15)
            replace_with_retry(app,failed)
        if old_moved:
            replace_with_retry(backup,app)
            launcher(runtime,workspace if workspace.is_file() else None,None,True)
        elif parent_closed and job.get('pid'):
            launcher(runtime,workspace if workspace.is_file() else None,None,True)
        atomic_json(status,{'state':'rolled_back' if old_moved else 'failed','error':str(exc),'workspace':str(workspace)})
        return False
    finally:
        lock.unlink(missing_ok=True)


if __name__=='__main__':
    try:
        success=install_job(sys.argv[1])
        sys.exit(0 if success else 1)
    except Exception as error:
        print(str(error),file=sys.stderr)
        sys.exit(1)

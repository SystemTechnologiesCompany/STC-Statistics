"""Compatibility policy for complete application snapshots, not chained deltas."""
import json
from pathlib import Path
from .update_installer import FORMAT,RUNTIME_ID,MIN_APP_VERSION,version

BASE_VERSIONS=tuple([f'0.5.{n}' for n in range(1,7)]+['1.0.0','1.0.1'])


def compatible_sources(root,target,requested=None):
    target_tuple=version(target)
    requested=list(requested or [])
    for previous in requested:
        if version(previous)>=target_tuple:
            raise ValueError('Target must be newer than every supported source version')
    bootstrap=target=='0.5.1' and requested==['0.5.0']
    minimum='0.5.0' if bootstrap else MIN_APP_VERSION
    if any(version(previous)<version(minimum) for previous in requested):
        raise ValueError('Original 0.5.0 installations require the one-time updater bootstrap')
    known=set(BASE_VERSIONS)|set(requested)
    # Carry forward compatible release history; never depend on intermediate
    # release downloads remaining available on GitHub.
    for feed in (Path(root)/'releases').glob('*/update.json'):
        try:
            if feed.stat().st_size>256*1024: continue
            item=json.loads(feed.read_text(encoding='utf-8'))
            if item.get('package_type')!=FORMAT: continue
            if item.get('runtime_id') not in (None,RUNTIME_ID): continue
            if item.get('runtime_id') is None and version(item['version'])>version('1.0.1'): continue
            candidates=[item['version']]+item.get('from_versions',[])
            for candidate in candidates:
                if version(minimum)<=version(candidate)<target_tuple: known.add(candidate)
        except (OSError,ValueError,TypeError,KeyError): continue
    # Every earlier patch in a known release line remains installable, even
    # when only --from-version 1.0.2 was supplied while publishing 1.0.3.
    lines={}
    for candidate in known|{target}:
        major,minor,patch=version(candidate)
        if patch>10000: raise ValueError('Release patch number exceeds the supported policy range')
        lines[major,minor]=max(lines.get((major,minor),0),patch)
    for (major,minor),maximum in lines.items():
        known.update(f'{major}.{minor}.{patch}' for patch in range(maximum+1))
    sources=sorted((v for v in known if version(minimum)<=version(v)<target_tuple),key=version)
    if not sources: raise ValueError('No compatible earlier application version')
    return sources,minimum

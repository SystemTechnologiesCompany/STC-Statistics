"""Build a public-release ZIP and update feed; does not upload or publish anything."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
from stc_statistics.updates import valid_https_url, version_tuple
from stc_statistics.version import APP_VERSION


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download-url', required=True, help='Public HTTPS URL for the ZIP you will upload.')
    parser.add_argument('--feed-url', required=True, help='Public HTTPS URL for the update.json you will upload.')
    parser.add_argument('--notes', default='')
    parser.add_argument('--windows-exe', action='store_true', help='Publish the compiled Windows EXE rather than the source package.')
    args = parser.parse_args()
    if not valid_https_url(args.download_url) or not valid_https_url(args.feed_url):
        parser.error('Both URLs must be public HTTPS addresses.')
    version_tuple(APP_VERSION)
    root = Path(__file__).resolve().parent
    from stc_statistics.licensing import require_configured_release
    require_configured_release(root)
    destination = root / 'releases'
    destination.mkdir(exist_ok=True)
    archive_path = destination / f"STC_Statistics_{APP_VERSION}{'_Windows' if args.windows_exe else ''}.zip"
    names = ['main.py', 'make_release.py', 'requirements.txt', 'README.md', 'Setup.cmd', 'Setup.ps1', 'Start.cmd']
    files = [root / name for name in names] + list((root / 'stc_statistics').glob('*.py')) + list((root / 'stc_statistics').glob('*.json')) + list((root / 'stc_statistics' / 'assets').glob('*'))
    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
        if args.windows_exe:
            exe = root / 'dist' / 'STC Statistics.exe'
            metadata = root / 'dist' / 'STC_Statistics_build.json'
            if not exe.is_file() or not metadata.is_file():
                parser.error('Build the Windows executable first with Build_EXE.cmd.')
            built = json.loads(metadata.read_text(encoding='utf-8'))
            if built.get('version') != APP_VERSION or built.get('update_config') != {'manifest_url': args.feed_url, 'download_url': args.download_url}:
                parser.error('Configure update_config.json with these URLs and rebuild the executable before publishing.')
            archive.write(exe, exe.name)
            archive.write(root / 'packaging' / 'README_Windows.txt', 'README.txt')
        else:
            for file in files:
                if file.name!='update_config.json':
                    archive.write(file, file.relative_to(root).as_posix())
            archive.writestr('stc_statistics/update_config.json', json.dumps({'manifest_url': args.feed_url, 'download_url': args.download_url}, indent=2))
    manifest = {'version': APP_VERSION, 'download_url': args.download_url, 'release_notes': args.notes,
                'sha256': hashlib.sha256(archive_path.read_bytes()).hexdigest()}
    (destination / 'update.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Created {archive_path.name} and update.json in releases/. Upload them to the exact URLs supplied.')


if __name__ == '__main__':
    main()

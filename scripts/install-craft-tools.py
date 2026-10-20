#!/usr/bin/env python3
"""Pinned named Craft CLI acquisition. Preview by default; never starts an app."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import tempfile
import zipfile

APPS = ('photocraft', 'vectorcraft', 'cadcraft', 'soundcraft', 'figcraft', 'designcraft',
        'lightcraft', 'filmcraft', 'effectcraft', 'pdfcraft', 'wordcraft', 'deckcraft', 'gridcraft')
REQUIREMENT = ('=anchor apple generic and certificate 1[field.1.2.840.113635.100.6.2.6] exists '
               'and certificate leaf[field.1.2.840.113635.100.6.1.13] exists '
               'and certificate leaf[subject.OU] = "DJ6XS33FX8" and notarized')

ASSETS = {
    'agent/bin/start-craft-mcp.sh': 0o755,
    'agent/craft/mcp.json': 0o644,
    'agent/craft/packages.json': 0o644,
    'agent/craft/source.json': 0o644,
    'agent/skills/crafting-apps/SKILL.md': 0o644,
    'agent/skills/crafting-apps/vectorcraft.md': 0o644,
}


def deploy_assets(source, destination, apply=False):
    safe(destination / 'runtime/deployment-backups/placeholder')
    changes = []
    for relative, mode in ASSETS.items():
        src, target = safe(source / relative), safe(destination / relative)
        if not src.is_file() or stat.S_IMODE(src.stat().st_mode) != mode:
            raise ValueError('Craft source asset missing or mode mismatch')
        if target.exists() and not target.is_file():
            raise ValueError('Craft asset target is not regular')
        new = src.read_bytes()
        old = target.read_bytes() if target.exists() else None
        old_mode = stat.S_IMODE(target.stat().st_mode) if old is not None else None
        if old == new and old_mode == mode:
            continue
        changes.append((relative, old, old_mode, new, mode))
    for relative, old, old_mode, new, mode in changes:
        print(json.dumps({'asset': relative, 'beforeSha256': hashlib.sha256(old).hexdigest() if old is not None else None,
                          'afterSha256': hashlib.sha256(new).hexdigest(), 'beforeMode': old_mode, 'afterMode': mode}))
    if not apply or not changes:
        return
    backups = safe(destination / 'runtime/deployment-backups')
    backups.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='craft-assets-', dir=backups))
    print(f'Craft asset recovery: {backup}', flush=True)
    receipts = []
    for relative, old, old_mode, new, mode in changes:
        target = safe(destination / relative)
        if old is not None:
            before = backup / 'before' / relative
            before.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            before.write_bytes(old); before.chmod(0o600)
        receipt = {'path': relative, 'beforeSha256': hashlib.sha256(old).hexdigest() if old is not None else None,
                   'beforeMode': old_mode, 'afterSha256': hashlib.sha256(new).hexdigest(), 'afterMode': mode, 'verified': False}
        receipts.append(receipt)
        (backup/'receipt.json').write_text(json.dumps(receipts, indent=2)+'\n')
        if ((target.read_bytes() if target.exists() else None) != old
                or (stat.S_IMODE(target.stat().st_mode) if target.exists() else None) != old_mode
                or safe(source / relative).read_bytes() != new):
            raise ValueError('Craft asset drift; backup retained')
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.craft-asset-', delete=False) as out:
            out.write(new); out.flush(); os.fsync(out.fileno()); temporary = Path(out.name)
        temporary.chmod(mode)
        os.replace(temporary, target)
        if target.read_bytes() != new or stat.S_IMODE(target.stat().st_mode) != mode:
            raise ValueError('Craft asset verification mismatch')
        receipt['verified'] = True
        (backup/'receipt.json').write_text(json.dumps(receipts, indent=2)+'\n')


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe(path):
    """Static checks, not protection against hostile concurrent writers."""
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError('unsafe Craft path')
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError('unsafe Craft symlink')
        if part != path and part.exists() and not part.is_dir():
            raise ValueError('Craft ancestor must be a directory')
    return path


def tree(path):
    safe(path)
    if not path.is_dir():
        raise ValueError('Craft installation is not a directory')
    files = {}
    for item in sorted(path.rglob('*')):
        safe(item)
        if item.is_dir():
            continue
        if not item.is_file():
            raise ValueError('unsafe Craft special file')
        files[item.relative_to(path).as_posix()] = {
            'sha256': digest(item), 'mode': f'{stat.S_IMODE(item.stat().st_mode):04o}',
            'size': item.stat().st_size}
    return files


def validate(manifest, apps):
    if manifest.get('schemaVersion') != 1 or manifest.get('platform') != 'macos-universal':
        raise ValueError('unsupported Craft manifest')
    if not apps or len(set(apps)) != len(apps):
        raise ValueError('empty or duplicate Craft selection')
    for app in apps:
        if app not in APPS or app not in manifest['packages']:
            raise ValueError('unknown Craft package')
        p = manifest['packages'][app]
        if not re.fullmatch(r'\d+\.\d+\.\d+', p['version']):
            raise ValueError('unsafe Craft version')
        name = f'{app}-cli-{p["version"]}-macos-universal.zip'
        url = f'https://github.com/storytold/{app}/releases/download/v{p["version"]}/{name}'
        if (p['archive'] != name or p['url'] != url
                or not re.fullmatch('[0-9a-f]{64}', p['archiveSha256'])
                or not re.fullmatch('[0-9a-f]{40}', p['sourceCommit'])
                or not 0 < p['archiveSize'] < 512 * 1024 * 1024):
            raise ValueError('unsafe Craft archive pin')


def archive_files(path, package):
    safe(path)
    if path.stat().st_size != package['archiveSize'] or digest(path) != package['archiveSha256']:
        raise ValueError('Craft archive integrity mismatch')
    base = package['archive'][:-4]
    files, seen, total = {}, set(), 0
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            parts = PurePosixPath(item.filename).parts
            mode = item.external_attr >> 16
            if (not parts or parts[0] != base or any(x in ('.', '..') for x in parts)
                    or '\\' in item.filename or item.filename in seen
                    or stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or item.flag_bits & 1):
                raise ValueError('unsafe Craft archive member')
            seen.add(item.filename)
            total += item.file_size
            if total > 1024 * 1024 * 1024 or len(seen) > 1024:
                raise ValueError('Craft archive expansion limit')
            if item.is_dir():
                continue
            if len(parts) < 2 or stat.S_IMODE(mode) not in (0o644, 0o755):
                raise ValueError('unsafe Craft archive file mode/path')
            with archive.open(item) as stream:
                sha = hashlib.file_digest(stream, 'sha256').hexdigest()
            files['/'.join(parts[1:])] = {'sha256': sha, 'mode': f'{stat.S_IMODE(mode):04o}', 'size': item.file_size}
    app = base.split('-cli-')[0]
    if not {app + '-cli', 'LICENSE-MIT', 'LICENSE-APACHE', 'README.md'} <= files.keys():
        raise ValueError('Craft archive missing binary or licenses/readme')
    if files[app + '-cli']['mode'] != '0755':
        raise ValueError('Craft binary is not executable')
    if package.get('files') is not None and files != package['files']:
        raise ValueError('Craft archive content pin mismatch')
    return files


def trust(binary):
    result = subprocess.run(['/usr/bin/lipo', '-archs', str(binary)], check=True,
                            capture_output=True, text=True, timeout=30)
    if set(result.stdout.split()) != {'arm64', 'x86_64'}:
        raise ValueError('Craft binary is not exact arm64/x86_64 universal')
    subprocess.run(['/usr/bin/codesign', '--verify', '--strict', '--all-architectures',
                    '--check-notarization', '-R', REQUIREMENT, str(binary)], check=True, timeout=60)


def install_packages(manifest, home, apps, local=None, apply=False, download=False, verify_trust=False):
    validate(manifest, apps)
    safe(home)
    root = safe(home / '.artcraft')
    safe(root / 'receipts' / 'placeholder')
    safe(root / 'downloads' / 'placeholder')
    reports = []
    for app in apps:
        p = manifest['packages'][app]
        name = p['archive'][:-4]
        target = safe(root / name)
        files = p.get('files')
        source = safe(local / name) if local else None
        archive = safe(root / 'downloads' / p['archive'])
        if target.exists() and files is not None:
            if tree(target) != files:
                raise ValueError(f'{app}: existing installation mismatch; never overwritten')
            reports.append({'app': app, 'status': 'unchanged', 'path': str(target)})
            continue
        if source and source.exists() and files is not None:
            if tree(source) != files:
                raise ValueError(f'{app}: local source mismatch')
            method = 'copy'
        else:
            method = 'archive'
            if archive.exists():
                files = archive_files(archive, p)
            elif not apply:
                reports.append({'app': app, 'status': 'needs-archive', 'path': str(target),
                                'url': p['url'], 'bytes': p['archiveSize'], 'sha256': p['archiveSha256']})
                continue
            elif download:
                archive.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                # Unique partial file retained on failure; no blind retry or replacement.
                fd, partial_name = tempfile.mkstemp(prefix=app + '-', suffix='.partial', dir=archive.parent)
                os.close(fd)
                partial = Path(partial_name)
                subprocess.run(['/usr/bin/curl', '--fail', '--location', '--proto', '=https',
                                '--proto-redir', '=https', '--max-time', '300', '--max-filesize',
                                str(p['archiveSize']), '--output', str(partial), p['url']], check=True, timeout=310)
                files = archive_files(partial, p)
                if archive.exists():
                    raise ValueError('Craft archive destination appeared; partial retained')
                os.rename(partial, archive)
            else:
                raise ValueError(f'{app}: pinned archive unavailable; explicit download consent required')
        if target.exists():
            if tree(target) != files:
                raise ValueError(f'{app}: existing installation mismatch; never overwritten')
            reports.append({'app': app, 'status': 'unchanged', 'path': str(target)})
            continue
        report = {'app': app, 'status': method if apply else 'would-' + method, 'path': str(target), 'files': files}
        reports.append(report)
        if not apply:
            continue
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=f'.{app}-stage-', dir=root))
        # Failed stages retained, never recursively deleted by this installer.
        if method == 'copy':
            if platform.system() == 'Darwin':
                # macOS Python lacks os.listxattr; copy2 alone drops quarantine.
                # ditto preserves directory/file extended attributes and licenses.
                subprocess.run(['/usr/bin/ditto', '--rsrc', '--extattr', '--acl',
                                str(source), str(stage)], check=True, timeout=120)
            else:
                shutil.copytree(source, stage, dirs_exist_ok=True, copy_function=shutil.copy2)
            if tree(source) != files:
                raise ValueError('Craft source drift during copy; stage retained')
        else:
            with zipfile.ZipFile(archive) as z:
                for relative, record in files.items():
                    dst = stage / relative
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(name + '/' + relative) as src, dst.open('xb') as out:
                        shutil.copyfileobj(src, out)
                    dst.chmod(int(record['mode'], 8))
        if tree(stage) != files:
            raise ValueError('Craft stage verification mismatch; stage retained')
        if verify_trust:
            trust(stage / (app + '-cli'))
        safe(target)
        if target.exists():
            raise ValueError('Craft target appeared; stage retained')
        os.rename(stage, target)
        if tree(target) != files:
            raise ValueError('Craft installed verification mismatch')
        receipts = safe(root / 'receipts')
        receipts.mkdir(mode=0o700, exist_ok=True)
        fd, receipt_name = tempfile.mkstemp(prefix=app+'-', suffix='.json', dir=receipts)
        with os.fdopen(fd, 'w') as out:
            json.dump({**report, 'archiveSha256': p['archiveSha256'], 'verified': True}, out, indent=2)
    print(json.dumps(reports, indent=2))
    return reports


def deliver(manifest, source, destination, home, apps, local=None, apply=False, download=False, enable=False):
    if (source is None) != (destination is None):
        raise ValueError('Craft source and destination must be supplied together')
    if source is not None:
        safe(source); safe(destination)
        spec = importlib.util.spec_from_file_location('craft_promotion', Path(__file__).with_name('check-craft-promotion.py'))
        promoter = importlib.util.module_from_spec(spec); spec.loader.exec_module(promoter)
        promoter.verify(source)
        if json.loads(safe(source / 'agent/craft/packages.json').read_bytes()) != manifest:
            raise ValueError('Craft package source drift')
        if source == destination or source in destination.parents or destination in source.parents:
            raise ValueError('Craft source/destination overlap')
        spec = importlib.util.spec_from_file_location('craft_reconcile', Path(__file__).with_name('reconcile-craft-mcp.py'))
        reconciler = importlib.util.module_from_spec(spec); spec.loader.exec_module(reconciler)
        # Validate entire config and asset boundary before package or HOME writes.
        reconciler.reconcile(source, destination, enable=apps if enable else ())
        deploy_assets(source, destination)
    reports = install_packages(manifest, home, apps, local, apply, download, verify_trust=True)
    if source is not None and apply:
        deploy_assets(source, destination, apply=True)
        reconciler.reconcile(source, destination, apply=True, enable=apps if enable else ())
    return reports


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--apps', nargs='+', choices=APPS, default=list(APPS))
    parser.add_argument('--home', type=Path, default=Path.home())
    parser.add_argument('--local', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--enable', action='store_true')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--download', action='store_true')
    args = parser.parse_args()
    if args.apply and platform.system() != 'Darwin':
        raise SystemExit('Craft packages require macOS; no changes made')
    deliver(json.loads(args.manifest.read_bytes()), args.source, args.destination, args.home,
            args.apps, args.local, args.apply, args.download, args.enable)

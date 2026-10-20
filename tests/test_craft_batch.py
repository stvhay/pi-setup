"""Craft-only delivery contracts. Synthetic tools only; no Craft/Pi starts."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
APPS = dict(photocraft='0.9.0', vectorcraft='0.12.0', cadcraft='0.7.0', soundcraft='0.7.0',
            figcraft='0.6.0', designcraft='0.8.0', lightcraft='0.8.0', filmcraft='0.8.0',
            effectcraft='0.10.0', pdfcraft='0.8.0', wordcraft='0.7.0', deckcraft='0.7.0', gridcraft='0.7.0')
NEW = list(APPS)[4:]


def module(name):
    path = ROOT / f'scripts/{name}.py'
    assert path.exists(), f'missing {name}'
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize('app', NEW)
def test_new_launcher_exact_contract(tmp_path, app):
    home, cwd = tmp_path / 'home', tmp_path / 'project space'
    cwd.mkdir()
    binary = home / f'.artcraft/{app}-cli-{APPS[app]}-macos-universal/{app}-cli'
    binary.parent.mkdir(parents=True)
    binary.write_text(f'#!{sys.executable}\nimport json,os,sys\nprint(json.dumps(dict(argv=sys.argv[1:],cwd=os.getcwd(),env={{k:v for k,v in os.environ.items() if k.endswith("CONFIG_DIR")}},input=sys.stdin.read())))\n')
    binary.chmod(0o755)
    root = cwd / f'.artcraft/{app}-workspace'
    proc = subprocess.run([str(ROOT / 'pi/agent/bin/start-craft-mcp.sh'), app], cwd=cwd,
                          env={'HOME':str(home),'PATH':'/usr/bin:/bin','CDPATH':'/wrong'},
                          input='protocol\n', text=True, capture_output=True, timeout=5)
    assert proc.returncode == 0, proc.stderr
    got = json.loads(proc.stdout)
    argv = ['mcp']
    if app == 'figcraft': argv += ['--no-system-fonts']
    if app == 'filmcraft': argv += ['--data-dir', str(root / 'data')]
    if app == 'pdfcraft': argv += ['--root', str(root)]
    if app in ('effectcraft', 'wordcraft'):
        argv += ['--automation-read-root', str(root), '--automation-write-root', str(root)]
    assert got['argv'] == argv
    assert got['cwd'] == str(root)
    assert got['input'] == 'protocol\n'
    if app in ('lightcraft','effectcraft'):
        assert got['env'][app.upper() + '_CONFIG_DIR'] == str(root / 'config')
    assert root.stat().st_mode & 0o777 == 0o700
    # Repeats preserve files and modes.
    keep = root / 'keep'; keep.write_text('keep'); root.chmod(0o750)
    subprocess.run([str(ROOT / 'pi/agent/bin/start-craft-mcp.sh'), app], cwd=cwd,
                   env={'HOME':str(home),'PATH':'/usr/bin:/bin'}, input='', text=True,
                   capture_output=True, check=True, timeout=5)
    assert keep.read_text() == 'keep' and root.stat().st_mode & 0o777 == 0o750


@pytest.mark.parametrize('app', NEW)
def test_new_launcher_refuses_workspace_symlink(tmp_path, app):
    home = tmp_path / 'home'; cwd = tmp_path / 'cwd'; cwd.mkdir()
    binary = home / f'.artcraft/{app}-cli-{APPS[app]}-macos-universal/{app}-cli'
    binary.parent.mkdir(parents=True); binary.write_text('#!/bin/sh\necho BAD\n'); binary.chmod(0o755)
    (cwd / '.artcraft').mkdir(); (cwd / f'.artcraft/{app}-workspace').symlink_to(tmp_path)
    proc = subprocess.run([str(ROOT / 'pi/agent/bin/start-craft-mcp.sh'), app], cwd=cwd,
                          env={'HOME':str(home),'PATH':'/usr/bin:/bin'}, capture_output=True, text=True)
    assert proc.returncode != 0 and proc.stdout == ''
    assert 'unsafe directory:' in proc.stderr


def template(apps):
    return {'mcpServers': {app+'-pilot': {'command':'agent/bin/start-craft-mcp.sh', 'args':[app],
            'enabled':False, 'cwd':'.', 'timeout':30, 'exposure':'codemode'} for app in apps}}


def config_fixture(tmp_path):
    src, dst = tmp_path/'src', tmp_path/'.pi'
    (src/'agent/craft').mkdir(parents=True); (src/'agent/bin').mkdir()
    (dst/'agent').mkdir(parents=True)
    (src/'agent/craft/mcp.json').write_text(json.dumps(template(APPS)))
    launcher = src/'agent/bin/start-craft-mcp.sh'; launcher.write_text('#!/bin/sh\nexit 99\n'); launcher.chmod(0o755)
    old = template(list(APPS)[:4])
    for v in old['mcpServers'].values():
        v['command'] = str(dst/'agent/bin/start-craft-mcp.sh'); v['enabled'] = True
        v['env'] = {'PRIVATE':'keep'}
    old['mcpServers']['unrelated'] = {'url':'https://example.invalid'}
    (dst/'agent/mcp.json').write_text(json.dumps(old)); (dst/'agent/mcp.json').chmod(0o600)
    return src, dst, old


def test_all_templates_preserve_existing_enablement_and_noop(tmp_path):
    m = module('reconcile-craft-mcp'); src,dst,old = config_fixture(tmp_path)
    m.reconcile(src,dst,apply=True)
    target=dst/'agent/mcp.json'; got=json.loads(target.read_bytes())
    for k,v in old['mcpServers'].items(): assert got['mcpServers'][k] == v
    for app in NEW: assert got['mcpServers'][app+'-pilot']['enabled'] is False
    before=(target.read_bytes(),target.stat().st_ino)
    m.reconcile(src,dst,apply=True)
    assert (target.read_bytes(),target.stat().st_ino) == before
    m.reconcile(src,dst,apply=True,enable=['figcraft'])
    assert json.loads(target.read_bytes())['mcpServers']['figcraft-pilot']['enabled'] is True
    assert json.loads(target.read_bytes())['mcpServers']['deckcraft-pilot']['enabled'] is False


@pytest.mark.parametrize('problem', ['collision','unowned','unknown-enable'])
def test_batch_config_fails_before_write(tmp_path,problem):
    m=module('reconcile-craft-mcp'); src,dst,data=config_fixture(tmp_path)
    if problem=='collision': data['mcpServers']['figcraft_pilot']={'enabled':False}
    if problem=='unowned': data['mcpServers']['figcraft-pilot']={'command':'unowned'}
    target=dst/'agent/mcp.json';target.write_text(json.dumps(data));old=target.read_bytes()
    with pytest.raises(ValueError): m.reconcile(src,dst,apply=True,enable=['unknown'] if problem=='unknown-enable' else [])
    assert target.read_bytes()==old and not (dst/'runtime').exists()


def package_fixture(tmp_path):
    import hashlib
    local = tmp_path/'local'; name='figcraft-cli-0.6.0-macos-universal'
    root=local/name; root.mkdir(parents=True)
    (root/'figcraft-cli').write_bytes(b'fake binary'); (root/'figcraft-cli').chmod(0o755)
    for filename in ('LICENSE-MIT','LICENSE-APACHE','README.md'):
        (root/filename).write_bytes(b'license'); (root/filename).chmod(0o644)
    files={p.name:{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'mode':f'{p.stat().st_mode & 0o777:04o}', 'size':p.stat().st_size} for p in root.iterdir()}
    pkg={'version':'0.6.0','sourceCommit':'a'*40,'archive':name+'.zip', 'archiveSha256':'b'*64,
         'archiveSize':1,'url':'https://github.com/storytold/figcraft/releases/download/v0.6.0/'+name+'.zip','files':files}
    return local, {'schemaVersion':1,'platform':'macos-universal','packages':{'figcraft':pkg}}


def test_package_local_copy_preview_repeat_and_drift(tmp_path):
    m=module('install-craft-tools'); local,manifest=package_fixture(tmp_path); home=tmp_path/'home';home.mkdir()
    m.install_packages(manifest,home,['figcraft'],local=local)
    assert list(home.iterdir())==[]
    m.install_packages(manifest,home,['figcraft'],local=local,apply=True)
    root=home/'.artcraft/figcraft-cli-0.6.0-macos-universal'; target=root/'figcraft-cli'
    before=(target.read_bytes(),target.stat().st_ino)
    m.install_packages(manifest,home,['figcraft'],local=local,apply=True)
    assert (target.read_bytes(),target.stat().st_ino)==before
    assert (root/'LICENSE-MIT').read_bytes()==b'license'
    target.write_bytes(b'drift')
    with pytest.raises(ValueError,match='mismatch'): m.install_packages(manifest,home,['figcraft'],local=local,apply=True)
    assert target.read_bytes()==b'drift'


@pytest.mark.parametrize('bad',['source-bytes','source-link','dest-link','escape','unknown'])
def test_package_invalid_inputs_no_install(tmp_path,bad):
    m=module('install-craft-tools');local,manifest=package_fixture(tmp_path);home=tmp_path/'home';home.mkdir()
    root=local/'figcraft-cli-0.6.0-macos-universal'
    if bad=='source-bytes': (root/'figcraft-cli').write_bytes(b'bad')
    if bad=='source-link': (root/'figcraft-cli').unlink();(root/'figcraft-cli').symlink_to(root/'LICENSE-MIT')
    if bad=='dest-link': (home/'.artcraft').symlink_to(local)
    if bad=='escape': manifest['packages']['figcraft']['version']='../../escape'
    with pytest.raises(ValueError): m.install_packages(manifest,home,['unknown' if bad=='unknown' else 'figcraft'],local=local,apply=True)
    assert not (home/'.artcraft/figcraft-cli-0.6.0-macos-universal').exists() or bad=='dest-link'


def test_archive_integrity_and_traversal(tmp_path):
    import hashlib,zipfile
    m=module('install-craft-tools'); _,manifest=package_fixture(tmp_path);pkg=manifest['packages']['figcraft']
    archive=tmp_path/pkg['archive'];base=pkg['archive'][:-4]
    with zipfile.ZipFile(archive,'w') as z:
        for name,data,mode in [('figcraft-cli',b'fake binary',0o100755)]+[(n,b'license',0o100644) for n in ('LICENSE-MIT','LICENSE-APACHE','README.md')]:
            info=zipfile.ZipInfo(base+'/'+name);info.external_attr=mode<<16;z.writestr(info,data)
    pkg['archiveSha256']=hashlib.sha256(archive.read_bytes()).hexdigest();pkg['archiveSize']=archive.stat().st_size
    assert m.archive_files(archive,pkg)==pkg['files']
    with zipfile.ZipFile(archive,'a') as z:z.writestr(base+'/../escape',b'bad')
    with pytest.raises(ValueError):m.archive_files(archive,pkg)
    pkg['archiveSha256']=hashlib.sha256(archive.read_bytes()).hexdigest();pkg['archiveSize']=archive.stat().st_size
    with pytest.raises(ValueError,match='unsafe'):m.archive_files(archive,pkg)


def test_scoped_assets_preview_backup_and_noop(tmp_path):
    m=module('install-craft-tools')
    assert hasattr(m,'deploy_assets'), 'missing scoped asset deploy'
    src,dst=tmp_path/'source',tmp_path/'.pi'
    for relative,mode in m.ASSETS.items():
        path=src/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'new');path.chmod(mode)
    old=dst/'agent/bin/start-craft-mcp.sh';old.parent.mkdir(parents=True);old.write_bytes(b'old');old.chmod(0o755)
    unrelated=dst/'agent/settings.json';unrelated.write_bytes(b'keep private')
    m.deploy_assets(src,dst)
    assert old.read_bytes()==b'old' and not (dst/'runtime').exists()
    m.deploy_assets(src,dst,apply=True)
    assert old.read_bytes()==b'new' and unrelated.read_bytes()==b'keep private'
    backups=list((dst/'runtime/deployment-backups').glob('craft-assets-*/before/agent/bin/start-craft-mcp.sh'))
    assert len(backups)==1 and backups[0].read_bytes()==b'old'
    inode=old.stat().st_ino
    m.deploy_assets(src,dst,apply=True)
    assert old.stat().st_ino==inode and len(list((dst/'runtime/deployment-backups').glob('craft-assets-*')))==1


def test_owned_v2_source_manifest(tmp_path):
    m=module('check-craft-promotion')
    assert hasattr(m,'OWNED'), 'missing pi-setup-owned asset contract'
    import hashlib
    files={}
    for target,mode in m.OWNED.items():
        path=tmp_path/target;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'owned');path.chmod(int(mode,8))
        files[target]={'mode':mode,'sha256':hashlib.sha256(b'owned').hexdigest()}
    manifest={'schemaVersion':2,'repository':'pi-setup','origin':{'repository':'artcraft-setup','commit':'a'*40},'files':files}
    (tmp_path/'agent/craft/source.json').write_text(json.dumps(manifest))
    m.verify(tmp_path)
    (tmp_path/'agent/bin/start-craft-mcp.sh').write_bytes(b'drift')
    with pytest.raises(ValueError):m.verify(tmp_path)


def test_craft_cli_rejects_scope_conflicts():
    script=ROOT/'scripts/update-pi-config.sh'
    p=subprocess.run([str(script),'--craft','--file','agent/bin/start-craft-mcp.sh'],capture_output=True,text=True)
    assert p.returncode != 0 and 'cannot combine' in p.stderr


def test_craft_cli_documents_scoped_batch():
    p=subprocess.run([str(ROOT/'scripts/update-pi-config.sh'),'--help'],capture_output=True,text=True)
    assert p.returncode==0 and '--craft-apps' in p.stdout and '--craft-local' in p.stdout


def delivery_fixture(tmp_path):
    import hashlib
    m=module('install-craft-tools'); promoter=module('check-craft-promotion')
    src,dst,_=config_fixture(tmp_path)
    local,manifest=package_fixture(tmp_path)
    for relative,mode in m.ASSETS.items():
        path=src/relative
        if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'asset')
        path.chmod(mode)
    (src/'agent/craft/packages.json').write_text(json.dumps(manifest))
    provenance={'schemaVersion':2,'repository':'pi-setup','origin':{'repository':'artcraft-setup','commit':'a'*40},'files':{p:{'mode':mode,'sha256':hashlib.sha256((src/p).read_bytes()).hexdigest()} for p,mode in promoter.OWNED.items()}}
    (src/'agent/craft/source.json').write_text(json.dumps(provenance))
    home=tmp_path/'home';home.mkdir()
    return m,src,dst,home,local,manifest


def test_deliver_enforces_source_hashes_before_any_write(tmp_path):
    m,src,dst,home,local,manifest=delivery_fixture(tmp_path)
    (src/'agent/bin/start-craft-mcp.sh').write_text('#!/bin/sh\necho drift\n')
    with pytest.raises(ValueError,match='drift'):
        m.deliver(manifest,src,dst,home,['figcraft'],local,apply=True)
    assert list(home.iterdir())==[] and not (dst/'runtime').exists()


@pytest.mark.parametrize('obstruction',['agent/craft','agent/skills','runtime','.artcraft'])
def test_deliver_rejects_file_ancestors_before_any_write(tmp_path,obstruction):
    m,src,dst,home,local,manifest=delivery_fixture(tmp_path)
    target=(home if obstruction=='.artcraft' else dst)/obstruction
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(b'keep')
    with pytest.raises(ValueError,match='directory'):
        m.deliver(manifest,src,dst,home,['figcraft'],local,apply=True)
    assert target.read_bytes()==b'keep' and not (dst/'agent/bin').exists()
    assert not (home/'.artcraft/figcraft-cli-0.6.0-macos-universal').exists()


@pytest.mark.parametrize('architectures', ['x86_64 arm64', 'arm64', 'arm64 arm64e x86_64'])
def test_trust_uses_archs_and_requires_exact_universal(monkeypatch, architectures):
    from types import SimpleNamespace
    m=module('install-craft-tools');calls=[]
    def run(argv,**kw):
        calls.append(argv)
        return SimpleNamespace(stdout=architectures)
    monkeypatch.setattr(m.subprocess,'run',run)
    if architectures!='x86_64 arm64':
        with pytest.raises(ValueError,match='universal'):m.trust(Path('/fake/tool'))
        assert len(calls)==1
    else:
        m.trust(Path('/fake/tool'))
        assert '--all-architectures' in calls[1] and '--check-notarization' in calls[1]
        assert 'and notarized' in calls[1][-2]
    assert calls[0]==['/usr/bin/lipo','-archs','/fake/tool']


def test_local_copy_preserves_directory_xattrs(tmp_path, monkeypatch):
    import shutil
    m=module('install-craft-tools');local,manifest=package_fixture(tmp_path);home=tmp_path/'home';home.mkdir()
    source=local/'figcraft-cli-0.6.0-macos-universal';copied=[]
    monkeypatch.setattr(m.platform,'system',lambda:'Darwin')
    def copy(argv,**kwargs):
        copied.append(argv)
        shutil.copytree(argv[-2],argv[-1],dirs_exist_ok=True)
    monkeypatch.setattr(m.subprocess,'run',copy)
    m.install_packages(manifest,home,['figcraft'],local=local,apply=True)
    assert len(copied)==1 and copied[0][:4]==['/usr/bin/ditto','--rsrc','--extattr','--acl']
    assert copied[0][-2]==str(source)


def test_delivery_complete_and_repeat_preserves_unrelated(tmp_path,monkeypatch):
    m,src,dst,home,local,manifest=delivery_fixture(tmp_path)
    checked=[];monkeypatch.setattr(m,'trust',lambda path:checked.append(str(path)))
    old=json.loads((dst/'agent/mcp.json').read_bytes())
    m.deliver(manifest,src,dst,home,['figcraft'],local,apply=True)
    assert len(checked)==1
    for k,v in old['mcpServers'].items():assert json.loads((dst/'agent/mcp.json').read_bytes())['mcpServers'][k]==v
    paths=list(dst.rglob('*'))+list(home.rglob('*'))
    frozen={str(p):(p.read_bytes(),p.stat().st_ino) for p in paths if p.is_file()}
    m.deliver(manifest,src,dst,home,['figcraft'],local,apply=True)
    assert frozen=={str(p):(p.read_bytes(),p.stat().st_ino) for p in paths if p.is_file()}
    assert len(checked)==1

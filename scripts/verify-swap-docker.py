"""Destructive kernel-swap fixture: ONLY on a disposable GitHub-hosted runner.

Creates one 64MiB swap file in an otherwise absent managed directory. Never run
on a customer VPS. Test teardown swaps off only this fixture's own active file.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path('/var/lib/buzz-agents-v2/swap')
BROKER = 'buzz-ci-swap-broker'
HELPER = 'buzz-agents-swap-v1'


def run(argv):
    return subprocess.check_output(argv, text=True, timeout=90).strip()


def wait_state(wanted):
    for _ in range(60):
        try:
            value = json.loads((ROOT/'status.json').read_text())
            if value.get('state') == wanted:
                return value
            if value.get('state') == 'attention':
                raise RuntimeError('Swap fixture failed: '+value.get('reason','unknown'))
        except FileNotFoundError:
            pass
        time.sleep(1)
    raise RuntimeError('Swap fixture timeout')


def main():
    if (os.geteuid() != 0 or os.environ.get('GITHUB_ACTIONS') != 'true'
            or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        raise SystemExit('Only an explicitly disposable GitHub-hosted runner is allowed')
    image = os.environ['BUZZ_BROKER_IMAGE']
    if ROOT.exists() or ROOT.is_symlink():
        raise SystemExit('Refusing preexisting swap state')
    for name in (BROKER,HELPER):
        if run(['docker','ps','-aq','--filter','name=^/'+name+'$']):
            raise SystemExit('Refusing preexisting fixture container')
    ROOT.mkdir(parents=True,mode=0o700)
    existing_kib=sum(int(line.split()[2]) for line in Path('/proc/swaps').read_text().splitlines()[1:])
    target_mb=(existing_kib+1023)//1024+64
    request=ROOT/'request.json';request.write_text(json.dumps({'target_mb':target_mb}));request.chmod(0o600)
    broker_id=None;helper_id=None
    try:
        broker_id=run(['docker','run','-d','--name',BROKER,'--network','none','--read-only',
                      '--cap-drop','ALL','--security-opt','no-new-privileges:true',
                      '--label','com.docker.compose.service=broker',
                      '--mount','type=bind,src=/var/lib/buzz-agents-v2,dst=/var/lib/buzz-agents-v2',
                      '--mount','type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock',
                      '--entrypoint','python',image,'-c','import time;time.sleep(600)'])
        code='import os; from buzz_agents.swap_manager import reconcile; from buzz_agents.host import execute,inspect_container; reconcile(execute,inspect_container,os.environ["HOSTNAME"])'
        run(['docker','exec',broker_id,'python','-c',code])
        helper_id=json.loads((ROOT/'helper.json').read_text())['id']
        result=wait_state('ready')
        assert result['managed_mb']==64 and result['total_mb']>=63,result
        manifest=json.loads((ROOT/'pool.json').read_text())
        assert len(manifest['shards'])==1
        path=ROOT/manifest['shards'][0]['name']
        inode=path.stat().st_ino
        with path.open('rb') as f:header=f.read(4096)
        assert b'SWAPSPACE2' in header
        current=json.loads(run(['docker','inspect',helper_id]))[0]
        assert current['HostConfig']['Privileged'] is False
        assert current['HostConfig']['NetworkMode']=='none'
        assert [c.removeprefix('CAP_') for c in current['HostConfig']['CapAdd']]==['SYS_ADMIN'],current['HostConfig']['CapAdd']
        assert len(current['Mounts'])==1
        # Repeated controller reconciliation does not replace or grow the pool.
        run(['docker','exec',broker_id,'python','-c',code])
        assert json.loads((ROOT/'helper.json').read_text())['id']==helper_id
        run(['docker','stop','--time','45',helper_id])
        # Simulate kernel swap state being lost at reboot, with files retained.
        run(['swapoff','--',str(path)])
        (ROOT/'status.json').unlink()
        run(['docker','start',helper_id])
        wait_state('ready')
        assert path.stat().st_ino==inode
        with path.open('rb') as f:assert f.read(4096)==header
        assert str(path) in run(['docker','exec',helper_id,'cat','/proc/swaps'])
        print(json.dumps({'ok':True,'activation':True,'idempotent':True,'reactivation':True,
                          'boot_order_verified':False}))
    finally:
        # Stop the only controller first so it cannot recreate a helper.
        if broker_id:run(['docker','rm','-f',broker_id])
        if helper_id is None:
            found=run(['docker','ps','-aq','--filter','name=^/'+HELPER+'$'])
            if found:
                candidate=json.loads(run(['docker','inspect',found]))[0]
                assert (candidate.get('Config',{}).get('Labels') or {}).get('io.buzz-agents.swap-helper')=='1'
                assert len(candidate.get('Mounts',[]))==1 and candidate['Mounts'][0]['Source']==str(ROOT)
                helper_id=candidate['Id']
        if helper_id:run(['docker','stop','--time','45',helper_id])
        # /proc/swaps path rendering differs across mount namespaces. Always
        # address our own fixture inode via its host path, before unmounting it.
        for path in ROOT.glob('chunk-*'):
            result=subprocess.run(['swapoff','--',str(path)],capture_output=True,text=True)
            if result.returncode and 'Invalid argument' not in result.stderr:
                raise RuntimeError('Fixture swap cleanup failed: '+result.stderr.strip())
        if helper_id:run(['docker','rm','-f',helper_id])
        shutil.rmtree(ROOT)


if __name__ == '__main__':
    main()

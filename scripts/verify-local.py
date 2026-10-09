"""Run the declared local confidence package once; retain failures and platform gaps."""
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    out=ROOT/'.sonol-test/runtime/easy-v03'
    out.mkdir(parents=True,exist_ok=True)
    go=os.environ.get('BUZZ_BUILD_GO') or shutil.which('go')
    commands=[('python-tests',['python3','-m','unittest','discover','-s','tests','-v'],ROOT),
              ('provider-tests',[go,'test','-race','-v','./...'],ROOT/'provider'),
              ('setup-tests',[go,'test','-race','-v','./...'],ROOT/'setup'),
              ('provider-vet',[go,'vet','./...'],ROOT/'provider'),
              ('setup-vet',[go,'vet','./...'],ROOT/'setup'),
              ('shell-syntax',['sh','-n','scripts/install-host.sh'],ROOT),
              ('artifact-integrity',['python3','scripts/verify-artifacts.py'],ROOT)]
    def execute(item):
        name,argv,cwd=item
        start=time.monotonic()
        try:
            result=subprocess.run(argv,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=240)
            raw=result.stdout;code=result.returncode
        except subprocess.TimeoutExpired as error:
            raw=(error.stdout or b'')+b'\nTIMEOUT: unproven\n';code=124
        (out/(name+'.log')).write_bytes(raw)
        return {'name':name,'argv':argv,'cwd':str(cwd.relative_to(ROOT)),'exit_code':code,
                'elapsed_seconds':round(time.monotonic()-start,3),'log':str((out/(name+'.log')).relative_to(ROOT))}
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(execute,commands))
    sources={}
    for folder in ['buzz_agents','scripts','provider','setup']:
        for p in sorted((ROOT/folder).glob('*')):
            if p.is_file() and p.suffix in ('.py','.go','.sh'):
                if p.suffix=='.py':ast.parse(p.read_text(),filename=str(p))
                sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    report={'status':'passed_local_only' if all(x['exit_code']==0 for x in results) else 'failed',
            'scope':'direct focused commands; no policy-validator receipt','commands':results,'source_sha256':sources,
            'not_run':['Docker image build and Compose execution','Native Windows wizard and Buzz provider discovery',
                       'Real SSH forced-command/sudo/PTY login','Official subscription login and token refresh',
                       'Two-AI collaboration','New scheduled task after full Windows shutdown','KVM 2 CPU/RAM measurements']}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'commands':[{k:x[k] for k in ['name','exit_code','elapsed_seconds']} for x in results]},indent=2))
    return 0 if report['status']=='passed_local_only' else 1


if __name__=='__main__':raise SystemExit(main())

#!/usr/bin/env python3
"""A test ACP peer, not a real AI. Uses no provider account or network."""
import json
import sys
for line in sys.stdin:
    request=json.loads(line)
    if request.get('method')=='test/descendant':
        import subprocess
        child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
        print(json.dumps({'id':request['id'],'result':{'pid':child.pid}}),flush=True)
        continue
    if request.get('method')=='test/idle-eof':
        sys.stdout.close()
        raise SystemExit(0)
    if request.get('method')=='test/stderr-exit':
        print('authentication required SECRET-TEST-DO-NOT-LOG', file=sys.stderr, flush=True)
        raise SystemExit(9)
    if request.get('method')=='test/stderr':
        print('authentication required SECRET-TEST-DO-NOT-LOG', file=sys.stderr, flush=True)

    if request.get('method')=='session/prompt':
        if request['params'].get('hold'):
            import time
            print(json.dumps({'method':'session/update','params':{}}),flush=True)
            time.sleep(60)
        if request['params'].get('crash'):
            raise SystemExit(7)
        result={'stopReason':'end_turn'}
    elif request.get('method')=='initialize':
        result={'protocolVersion':1,'agentCapabilities':{}}
    elif 'id' not in request:
        continue
    else:
        result={}
    print(json.dumps({'jsonrpc':'2.0','id':request['id'],'result':result}),flush=True)

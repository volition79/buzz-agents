#!/usr/bin/env python3
"""A test ACP peer, not a real AI. Uses no provider account or network."""
import json
import sys
for line in sys.stdin:
    request=json.loads(line)
    if request.get('method')=='session/prompt':
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

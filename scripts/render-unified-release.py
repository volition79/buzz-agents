"""Prepare a unified candidate from reviewed immutable images; never publish tags."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from buzz_agents.release_contract import validate, PREFIX


def compose(broker):
    # Bootstrap has no variable or domain discovery requirements. The broker
    # pulls its embedded immutable runtime via Docker, not via container network.
    source=(Path(__file__).resolve().parents[1]/'compose.portal.yaml').read_text()
    a=source.index('  runtime-image:');b=source.index('  broker:',a)
    source=source[:a]+source[b:]
    a=source.index('    depends_on:\n      runtime-image:');b=source.index('    network_mode: none',a)
    source=source[:a]+source[b:]
    source=source.replace('${BUZZ_BROKER_IMAGE:?Set the published broker image digest}',broker)
    source=source.replace('${BUZZ_PORTAL_IMAGE:?Set the published portal image digest}',PREFIX+'portal:stable')
    return source

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('release','runtime','portal','output'):p.add_argument('--'+key,required=True)
    args=p.parse_args()
    contract=validate(dict(schema=1,api=1,release=args.release,runtime=args.runtime,portal=args.portal))
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/'buzz-release.json').write_text(json.dumps(contract,indent=2)+'\n')
    (out/'compose.stable.yaml').write_text(compose(PREFIX+'broker:stable'))
    (out/'BUILD-ARGS.json').write_text(json.dumps({
        'BUZZ_RELEASE':args.release,'BUZZ_RELEASE_RUNTIME':args.runtime,'BUZZ_RELEASE_PORTAL':args.portal},indent=2)+'\n')
    print('Candidate prepared only. Do not publish stable before Docker/portal/rollout acceptance.')

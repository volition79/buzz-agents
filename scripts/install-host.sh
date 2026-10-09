#!/bin/sh
# Run once as the VPS administrator after reviewing the sources.
# Does NOT change buzz-rpka, the firewall, sshd configuration or existing volumes.
set -eu
if [ "$(id -u)" != 0 ] || [ "$#" != 4 ]; then
  echo "Usage as root: $0 SOURCE_DIRECTORY LOCAL_IMAGE_TAG OWNER_HEX wss://EXISTING_RELAY" >&2
  exit 1
fi
command -v visudo >/dev/null
command -v sudo >/dev/null
command -v docker >/dev/null
if id buzzdeploy >/dev/null 2>&1; then
  echo "buzzdeploy already exists; review existing account before installing." >&2
  exit 1
fi
SRC=$(CDPATH= cd -- "$1" && pwd)
IMAGE=$2
OWNER=$3
RELAY=$4
export SRC IMAGE OWNER RELAY
python3 - <<'PY'
import json, os, pathlib, re, subprocess, sys
sys.path.insert(0, os.environ['SRC'])
from buzz_agents.config import HEX, relay_url
if not HEX.fullmatch(os.environ['OWNER']): raise SystemExit('Invalid human public key')
relay_url(os.environ['RELAY'])
if not re.fullmatch(r'[a-z0-9][a-z0-9._/:-]{0,200}', os.environ['IMAGE']): raise SystemExit('Use a local Docker image tag')
if pathlib.Path('/opt/buzz-agents').exists(): raise SystemExit('/opt/buzz-agents exists; no overwrite. Review migration guide.')
subprocess.run(['docker','compose','version'],check=True,stdout=subprocess.DEVNULL)
subprocess.run(['docker','image','inspect',os.environ['IMAGE']],check=True,stdout=subprocess.DEVNULL)
PY
install -d -m 0755 /opt/buzz-agents /opt/buzz-agents/host
cp -R "$SRC/buzz_agents" /opt/buzz-agents/
chown -R root:root /opt/buzz-agents
chmod -R go-w /opt/buzz-agents
python3 - <<'PY'
import json,os,pathlib,subprocess
image=os.environ['IMAGE']
info=json.loads(subprocess.check_output(['docker','image','inspect',image]))[0]
settings={'image':image,'image_id':info['Id'],'owner':os.environ['OWNER'],
 'relay':os.environ['RELAY'].rstrip('/'),'state_dir':'/var/lib/buzz-agents-v2',
 'memory_budget_mb':5120,'max_bots':8}
p=pathlib.Path('/opt/buzz-agents/host/settings.json')
p.write_text(json.dumps(settings,indent=2)+'\n');p.chmod(0o600)
PY
cat > /usr/local/sbin/buzz-agents-receive <<'EOF'
#!/bin/sh
cd /opt/buzz-agents
exec /usr/bin/env -i PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin HOME=/root PYTHONPATH=/opt/buzz-agents /usr/bin/python3 -m buzz_agents.host
EOF
chmod 0755 /usr/local/sbin/buzz-agents-receive
if ! id buzzdeploy >/dev/null 2>&1; then
  useradd --create-home --shell /bin/sh buzzdeploy
fi
install -d -o buzzdeploy -g buzzdeploy -m 0700 /home/buzzdeploy/.ssh
# A validated, narrow sudo rule. The SSH key must also have a forced command.
printf '%s\n' 'buzzdeploy ALL=(root) NOPASSWD: /usr/local/sbin/buzz-agents-receive ""' > /etc/sudoers.d/buzz-agents-receive
chmod 0440 /etc/sudoers.d/buzz-agents-receive
visudo -cf /etc/sudoers.d/buzz-agents-receive
printf '%s\n' 'Host receiver installed. Add ONLY your public SSH key with the restrict/command options documented in DEPLOYMENT.md.'

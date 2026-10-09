from copy import deepcopy
from buzz_agents.config import normalize
OWNER = 'a' * 64
PUBKEY = 'b' * 64
RELAY = 'wss://relay.example.com'


def agent(command='codex-acp', key='0' * 63 + '1'):
    return {'name':'기획자', 'relay_url':RELAY, 'private_key_nsec':key,
            'auth_tag':['auth',OWNER,'', 'c' * 128], 'parallelism':1,
            'respond_to':'owner-only','respond_to_allowlist':[],
            'launch':{'command':command,'args':[], 'env':{},
                      'policy_env':{'BUZZ_ACP_SYSTEM_PROMPT':'각자 역할에 따라 자유롭게 협업하세요.',
                                    'BUZZ_ACP_MODEL':'test-model'}, 'owner_pubkey':OWNER}}


def config(command='codex-acp', pub=PUBKEY, options=None):
    return normalize(agent(command), options or {}, OWNER, RELAY, derive=lambda _:pub)


def settings(root):
    return {'state_dir':str(root),'image':'buzz-agents:0.2.0','image_id':'sha256:'+'d'*64,
            'owner':OWNER,'relay':RELAY,'memory_budget_mb':5120,'max_bots':8}

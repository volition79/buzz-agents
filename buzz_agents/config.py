"""Validate the desktop provider contract. Do not invent a second persona resolver."""
import hashlib
import json
import re
from urllib.parse import urlsplit
from .common import ToolError, crypto

HEX = re.compile(r"[0-9a-f]{64}\Z")
SLUG = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}\Z")
COMMANDS = {"codex-acp": "codex", "claude-agent-acp": "claude"}
# Unknown settings fail explicitly. Secrets, host paths and alternative API routes
# are NOT copied wholesale from the desktop to an unattended VPS.
ENV_ALLOWED = {
    "BUZZ_ACP_SYSTEM_PROMPT", "BUZZ_ACP_TEAM_INSTRUCTIONS", "BUZZ_ACP_SESSION_TITLE",
    "BUZZ_ACP_DISPLAY_NAME", "BUZZ_ACP_MODEL", "ANTHROPIC_MODEL",
    "BUZZ_ACP_EFFORT_LEVEL", "CLAUDE_CODE_EFFORT_LEVEL", "CODEX_REASONING_EFFORT",
    "BUZZ_ACP_SESSION_POLICY", "BUZZ_ACP_RELAY_OBSERVER", "BUZZ_ACP_LAZY_POOL",
    "BUZZ_ACP_IDLE_POOL_SLEEP", "BUZZ_ACP_IDLE_TIMEOUT", "BUZZ_ACP_MAX_TURN_DURATION",
    "BUZZ_ACP_AGENTS", "BUZZ_ACP_PERMISSION_MODE", "BUZZ_ACP_CONTEXT_MESSAGE_LIMIT",
    "BUZZ_ACP_NO_MEMORY", "BUZZ_ACP_NO_BASE_PROMPT", "BUZZ_ACP_EXIT_AFTER_INACTIVITY",
    "BUZZ_ACP_MULTIPLE_EVENT_HANDLING", "BUZZ_ACP_MAX_TURNS_PER_SESSION",
    "BUZZ_ACP_DEDUP", "BUZZ_ACP_RESPOND_TO", "BUZZ_ACP_RESPOND_TO_ALLOWLIST",
    "BUZZ_ACP_REPLAY_FLOOR", "LANG", "LC_ALL", "TZ", "BUZZ_ACP_MEMORY",
}


def integer(value, low, high, code):
    if type(value) is not int or not low <= value <= high:
        raise ToolError(code)
    return value


def relay_url(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ToolError("invalid_relay")
    url = urlsplit(value)
    if (url.scheme != "wss" or not url.hostname or url.username or url.password
            or url.query or url.fragment or url.path not in ("", "/")):
        raise ToolError("invalid_relay")
    return value.rstrip("/")


def decode_nsec(value):
    """NIP-19 Bech32 decoding only. Curve operations use the external library."""
    if not isinstance(value, str):
        raise ToolError("invalid_agent_identity")
    if HEX.fullmatch(value):
        return value
    if len(value) != 63 or not value.startswith("nsec1") or value != value.lower():
        raise ToolError("invalid_agent_identity")
    alphabet = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
    try:
        words = [alphabet.index(c) for c in value[5:]]
    except ValueError:
        raise ToolError("invalid_agent_identity") from None
    checksum = 1
    for word in [ord(c) >> 5 for c in "nsec"] + [0] + [ord(c) & 31 for c in "nsec"] + words:
        high = checksum >> 25
        checksum = ((checksum & 0x1ffffff) << 5) ^ word
        for i, generator in enumerate((0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)):
            if (high >> i) & 1:
                checksum ^= generator
    if checksum != 1:
        raise ToolError("invalid_agent_identity")
    accumulator = bits = 0
    result = bytearray()
    for word in words[:-6]:
        accumulator = (accumulator << 5) | word
        bits += 5
        if bits >= 8:
            bits -= 8
            result.append((accumulator >> bits) & 255)
    if len(result) != 32 or bits >= 5 or ((accumulator << (8 - bits)) & 255):
        raise ToolError("invalid_agent_identity")
    return result.hex()


def public_key(key):
    result = crypto("public", key)
    if not isinstance(result, str) or not HEX.fullmatch(result):
        raise ToolError("invalid_agent_identity")
    return result


def normalize(agent, options, owner, relay, *, derive=public_key):
    if not isinstance(agent, dict) or not isinstance(options, dict) or not HEX.fullmatch(owner):
        raise ToolError("invalid_payload")
    if str(agent.get("provider", "")).strip() == "relay-mesh":
        raise ToolError("relay_mesh_not_supported")
    allowed_options = {"ssh_alias", "workspace", "memory_mb", "cpus", "max_turn_seconds", "turn_limit", "window_seconds", "daily_limit"}
    if set(options) - allowed_options:
        raise ToolError("unsupported_provider_configuration")
    if relay_url(agent.get("relay_url")) != relay_url(relay):
        raise ToolError("relay_mismatch")
    launch = agent.get("launch")
    if not isinstance(launch, dict) or launch.get("owner_pubkey") != owner:
        # Fail closed on old desktop payloads; no fallback to raw persona records.
        raise ToolError("desktop_launch_contract_required")
    command = launch.get("command")
    if command not in COMMANDS:
        raise ToolError("unsupported_harness_use_codex_acp_or_claude_agent_acp")
    if launch.get("args") not in ([], None):
        raise ToolError("custom_harness_arguments_not_supported")
    key = decode_nsec(agent.get("private_key_nsec"))
    pubkey = derive(key)
    if not HEX.fullmatch(pubkey) or pubkey == owner:
        raise ToolError("human_key_must_not_be_deployed")
    auth = agent.get("auth_tag")
    if isinstance(auth, str):
        try:
            auth = json.loads(auth)
        except ValueError:
            raise ToolError("invalid_owner_attestation") from None
    if (not isinstance(auth, list) or len(auth) != 4 or auth[0] != "auth" or auth[1] != owner
            or not all(isinstance(s, str) for s in auth) or len(auth[2]) > 4096
            or not re.fullmatch(r"[0-9a-f]{128}", auth[3])):
        raise ToolError("owner_attestation_required")
    # The Relay is the authority that cryptographically validates the attestation.
    env = {}
    for layer in (launch.get("policy_env", {}), launch.get("env", {})):
        if not isinstance(layer, dict) or len(layer) > 60:
            raise ToolError("invalid_environment")
        for name, value in layer.items():
            if name not in ENV_ALLOWED:
                raise ToolError("unsupported_environment_" + (name if re.fullmatch(r"[A-Z0-9_]{1,70}", name) else "name"))
            if not isinstance(value, str) or "\x00" in value or len(value.encode()) > 65536:
                raise ToolError("invalid_environment")
            env[name] = value
    startup_env = {}
    if "BUZZ_ACP_REPLAY_FLOOR" in env:
        floor = env.pop("BUZZ_ACP_REPLAY_FLOOR")
        if not re.fullmatch(r"[0-9]{1,20}", floor) or int(floor) >= 2**64:
            raise ToolError("invalid_replay_floor")
        startup_env["BUZZ_ACP_REPLAY_FLOOR"] = floor
    name = agent.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100 or any(ord(c) < 32 for c in name):
        raise ToolError("invalid_name")
    respond = agent.get("respond_to", "owner-only")
    if respond not in ("owner-only", "allowlist", "nobody"):
        raise ToolError("public_anyone_mode_disabled")
    allow = agent.get("respond_to_allowlist") or []
    if not isinstance(allow, list) or len(allow) > 100 or any(not isinstance(k, str) or not HEX.fullmatch(k) for k in allow):
        raise ToolError("invalid_allowlist")
    if respond == "allowlist" and not allow:
        raise ToolError("allowlist_required")
    # Respect the resolved Buzz launch count; legacy payloads default to ten.
    requested = agent.get("parallelism")
    if requested is not None:
        integer(requested, 1, 32, "invalid_parallelism")
    native_workers = env.get("BUZZ_ACP_AGENTS", str(requested if requested is not None else 10))
    if not re.fullmatch(r"[1-9][0-9]?", native_workers) or int(native_workers) > 32:
        raise ToolError("invalid_parallelism")
    env.update(BUZZ_PRIVATE_KEY=key, NOSTR_PRIVATE_KEY=key, BUZZ_RELAY_URL=relay_url(relay),
               BUZZ_AUTH_TAG=json.dumps(auth, separators=(",", ":")), BUZZ_ACP_AGENT_OWNER=owner,
               BUZZ_ACP_RESPOND_TO=respond, BUZZ_ACP_AGENTS=native_workers, BUZZ_ACP_SUBSCRIBE="mentions",
               BUZZ_ACP_RESPOND_TO_ALLOWLIST=",".join(allow), BUZZ_ACP_NO_PRESENCE="false",
               BUZZ_ACP_NO_IGNORE_SELF="false", BUZZ_ACP_HEARTBEAT_INTERVAL="0")
    # Policy bounds, not a prescribed collaboration order.
    max_seconds = integer(options.get("max_turn_seconds", 1800), 60, 7200, "invalid_turn_seconds")
    try:
        native_max = int(env.get("BUZZ_ACP_MAX_TURN_DURATION", str(max_seconds)))
    except (TypeError, ValueError):
        raise ToolError("invalid_native_turn_timeout") from None
    if native_max <= 0:
        raise ToolError("invalid_native_turn_timeout")
    max_seconds = min(max_seconds, native_max)
    env["BUZZ_ACP_MAX_TURN_DURATION"] = str(max_seconds)
    try:
        idle = int(env.get("BUZZ_ACP_IDLE_TIMEOUT", "300"))
    except ValueError:
        raise ToolError("invalid_idle_timeout") from None
    env["BUZZ_ACP_IDLE_TIMEOUT"] = str(max(1, min(idle, max_seconds - 1)))
    workspace = options.get("workspace", "team")
    if workspace == "private":
        workspace = "bot-" + pubkey[:20]
    if not isinstance(workspace, str) or not SLUG.fullmatch(workspace):
        raise ToolError("invalid_workspace")
    memory = integer(options.get("memory_mb", 1536), 512, 16777216, "invalid_memory")
    cpus = options.get("cpus", 0.75)
    if type(cpus) not in (int, float) or not 0.1 <= cpus <= 1048576:
        raise ToolError("invalid_cpu")
    policy = {"max_turn_seconds": max_seconds,
              "turn_limit": integer(options.get("turn_limit", 20), 1, 500, "invalid_turn_limit"),
              "window_seconds": integer(options.get("window_seconds", 3600), 60, 86400, "invalid_window"),
              "daily_limit": integer(options.get("daily_limit", 100), 1, 2000, "invalid_daily_limit")}
    result = {"schema": 2, "name": name, "pubkey": pubkey, "owner": owner,
              "provider": COMMANDS[command], "command": command, "env": env,
              "workspace": workspace, "memory_mb": memory, "cpus": cpus, "policy": policy}
    result["fingerprint"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    result["startup_env"] = startup_env
    return result

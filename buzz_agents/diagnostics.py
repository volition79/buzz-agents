"""Public machine codes only; raw adapter/provider output is never a log line."""
import json

VALIDATION_ERRORS = frozenset("""
invalid_payload unsupported_provider_configuration relay_mismatch invalid_relay
desktop_launch_contract_required unsupported_harness_use_codex_acp_or_claude_agent_acp
custom_harness_arguments_not_supported invalid_agent_identity human_key_must_not_be_deployed
invalid_owner_attestation owner_attestation_required invalid_environment invalid_name
public_anyone_mode_disabled invalid_allowlist allowlist_required invalid_parallelism
invalid_turn_seconds invalid_native_turn_timeout invalid_idle_timeout invalid_workspace
invalid_memory invalid_cpu invalid_turn_limit invalid_window invalid_daily_limit
nostr_helper_failed nostr_helper_invalid relay_mesh_not_supported invalid_replay_floor
unsupported_environment request_too_large operation_failed
""".split())

def validation_error(raw):
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get("ok") is not False:
            return None
        code = value.get("error")
        if not isinstance(code, str):
            return None
        if code.startswith("unsupported_environment_"):
            return "unsupported_environment"
        return code if code in VALIDATION_ERRORS else None
    except (ValueError, UnicodeError):
        return None

# Convert output to categories, never echo user text, paths, model IDs or secrets.
class RuntimeDiagnostics:
    def __init__(self):
        self.buffer = bytearray()
        self.seen = set()
    def feed(self, chunk):
        result = []
        for offset in range(0, len(chunk), 4096):
            result.extend(self._feed(chunk[offset:offset + 4096]))
        return result

    def _feed(self, chunk):
        self.buffer.extend(chunk)
        # Bounded overlap covers split phrases without storing arbitrary logs.
        data = bytes(self.buffer[-8192:]).lower()
        self.buffer[:] = data[-512:]
        patterns = (
            ("runtime_authentication_required", (b"authentication required", b"not logged in", b"unauthorized", b"auth expired")),
            ("runtime_rate_limited", (b"rate limit", b"too many requests")),
            ("runtime_model_unavailable", (b"model not found", b"invalid model", b"model is not available")),
            ("runtime_adapter_initialization_failed", (b"agent initialize failed", b"agent timed out during init", b"agent failed to spawn")),
            ("runtime_relay_connection_failed", (b"connection refused", b"failed to connect", b"tls error")),
            ("runtime_configuration_invalid", (b"configuration error", b"unexpected argument", b"invalid value")),
        )
        result = []
        patterns += tuple((code, (code.encode(),)) for code in (
            "runtime_prompt_failed", "runtime_adapter_exited", "runtime_protocol_failed"))
        for code, needles in patterns:
            if code not in self.seen and (any(n in data for n in needles) or
                                          ("buzz-agents-diagnostic:" + code).encode() in data):
                self.seen.add(code)
                result.append(code)
        return result

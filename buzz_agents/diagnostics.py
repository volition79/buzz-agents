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
            ("runtime_process_creation_failed", (b"cannot fork", b"resource temporarily unavailable", b"unable to create new native thread")),
            ("runtime_approval_review_failed", (b"automatic approval review failed:",)),
            ("runtime_configuration_invalid", (b"configuration error", b"unexpected argument", b"invalid value")),
        )
        result = []
        patterns += tuple((code, (code.encode(),)) for code in (
            "runtime_prompt_failed", "runtime_adapter_exited", "runtime_protocol_failed",
            "runtime_approval_review_failed", "runtime_process_creation_failed"))
        for code, needles in patterns:
            if code not in self.seen and (any(n in data for n in needles) or
                                          ("buzz-agents-diagnostic:" + code).encode() in data):
                self.seen.add(code)
                result.append(code)
        return result


DIAGNOSTIC_CODES = frozenset("""runtime_authentication_required runtime_rate_limited
runtime_model_unavailable runtime_adapter_initialization_failed runtime_relay_connection_failed
runtime_configuration_invalid runtime_prompt_failed runtime_adapter_exited runtime_protocol_failed
runtime_approval_review_failed runtime_process_creation_failed runtime_process_limit""".split())
REASON_CODES = frozenset("""operator_action_required first_subscription_login_required explicit_login
external_graceful_stop external_stop_incomplete native_clean_exit native_process_failed supervisor_fault
clock_moved_backwards turn_window_limit daily_start_limit quota_storage_failed worker_lifetime_check_failed
turn_deadline adapter_or_guard_fault unexpected_container_restart""".split())


def structured_diagnostic(message):
    """Inspect only bounded tool-result text, never serialize/log the raw frame."""
    if not isinstance(message, dict) or message.get('method') != 'session/update':
        return None
    params = message.get('params')
    update = params.get('update') if isinstance(params, dict) else None
    if not isinstance(update, dict) or update.get('sessionUpdate') not in ('tool_call', 'tool_call_update'):
        return None
    content = update.get('content')
    if not isinstance(content, list):
        return None
    for item in content[:16]:
        nested = item.get('content') if isinstance(item, dict) else None
        if isinstance(nested, dict) and nested.get('type') == 'text':
            text = nested.get('text')
            if isinstance(text, str) and 'automatic approval review failed:' in text[:8192].lower():
                return 'runtime_approval_review_failed'
    return None

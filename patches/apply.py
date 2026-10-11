"""Fail closed against the exact pinned upstream lib; notices only."""
import hashlib
from pathlib import Path
import shutil
import sys
root = Path(sys.argv[1])
path = root / 'crates/buzz-acp/src/lib.rs'
raw = path.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '486be818391a4c4af0513a3ef1c1c4b70c0e044663bbe974fe3906c7a53b6da4', 'upstream source changed'
text = raw.decode()
def replace(old, new):
    global text
    assert text.count(old) == 1, 'upstream patch context changed'
    text = text.replace(old, new)
replace('/// Returns `true` when `error` is a non-retryable authentication failure.', 'mod hosting_recovery;\n\n/// Returns `true` when `error` is a non-retryable authentication failure.')
replace('                spawn_failure_notice(rest_client, &batch, content);\n            } else if let Some(dead) = queue.requeue(batch) {', '                let content = hosting_recovery::append(content, Some(hosting_recovery::Kind::Authentication));\n                spawn_failure_notice(rest_client, &batch, content);\n            } else if let Some(dead) = queue.requeue(batch) {')
replace('                );\n                spawn_failure_notice(rest_client, &dead, content);\n            }\n        } else {', '                );\n                let kind = match &result.outcome {\n                    PromptOutcome::Error(acp::AcpError::AgentError { message, .. }) => hosting_recovery::classify(message),\n                    _ => None,\n                };\n                let content = hosting_recovery::append(content, kind);\n                spawn_failure_notice(rest_client, &dead, content);\n            }\n        } else {')
path.write_text(text)
shutil.copyfile(Path(__file__).with_name('hosting_recovery.rs'), path.with_name('hosting_recovery.rs'))

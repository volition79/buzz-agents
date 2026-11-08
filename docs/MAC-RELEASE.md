# Mac connector management update

Apple Silicon connection bundle added beside Windows. Intel Mac is not supported.
Existing Windows connection credentials, bot identities, AI authentication and
workspaces are preserved. This release retains the previous runtime digest and
sets `management_only=true`; bot-by-bot Update/restart is not needed for this change.

Native macOS connector/provider tests, Windows compatibility fixtures and actual
Docker packaging are verified. Publication runs an actual management upgrade and
rollback test preserving account, device access and the existing route first.

**Mac limitation:** Finder/Gatekeeper and a real Buzz/VPS journey have not been
verified. The connector is unsigned/not notarized for public macOS distribution.
If macOS blocks opening the bundle, stop and contact the maintainer; do not disable
security or erase an existing working connection. Native CI tests do not certify
the downloaded double-click flow. Publication was explicitly requested after
these remaining gaps were disclosed.

The canonical pinned `compose.stable.yaml` installation URL is unchanged. Existing
stable installations can update the `buzz-agents` management project, preserving
its name, volumes and route. Older digest-pinned installations require their
existing migration instructions. Never delete/recreate a project to update it.

`rollback.json` records exact previous and current image references. If rollback
is required, restore both previous management references in the same project;
retain volumes, route and runtime. This update does not promise recovery of active
in-memory work after an unrelated restart, nor unlimited AI subscription usage.

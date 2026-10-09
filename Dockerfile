# syntax=docker/dockerfile:1.7
# This is an original deployment image. No third-party agent image is used.
# The sprig manifest is tied to the official build recorded in DEPLOYMENT.md.
# Resolve this tag to a manifest digest for a release build; see DEPLOYMENT.md.
ARG PYTHON_IMAGE=python:3.12.15-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258

FROM ghcr.io/block/buzz-sprig:sha-4db7bb0@sha256:eb739a94eab5745e9804232fbbc048f8b2e348be3a7a15deb623200f83c80c2c AS sprig
FROM node:24-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS node
FROM ${PYTHON_IMAGE} AS runtime

ARG PYTHON_IMAGE
ARG CODEX_ACP_VERSION=2.1.1
ARG CLAUDE_ACP_VERSION=0.88.0

LABEL org.opencontainers.image.title="buzz-agents" \
      org.opencontainers.image.description="Native independently configurable Buzz bots with loop/time guards" \
      org.opencontainers.image.version="0.4.0" \
      io.buzz-agents.sprig.source="4db7bb0e7f904b2f0ea232aacae6cd7f6b8a3b39" \
      io.buzz-agents.sprig.image="ghcr.io/block/buzz-sprig:sha-4db7bb0@sha256:eb739a94eab5745e9804232fbbc048f8b2e348be3a7a15deb623200f83c80c2c" \
      io.buzz-agents.node.image="node:24-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20" \
      io.buzz-agents.python.image="${PYTHON_IMAGE}" \
      io.buzz-agents.codex-acp="${CODEX_ACP_VERSION}" \
      io.buzz-agents.claude-agent-acp="${CLAUDE_ACP_VERSION}"

ENV PATH=/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin \
    HOME=/home/agent \
    LANG=C.UTF-8 \
    TZ=UTC \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NO_BROWSER=1

# Both runtime stages use Debian bookworm. Node's bundled npm and license are
# retained; Python and Debian package notices remain in the final base image.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
COPY --from=node /usr/local/LICENSE /usr/local/share/licenses/node/LICENSE
COPY --from=sprig --chmod=0755 /usr/local/bin/sprig /usr/local/bin/sprig

# A checksum protects this separately copied upstream distribution notice.
ADD --checksum=sha256:108cb15997e51b75a8d18b0c1e2c52bd3879d051ab02118973387df1e4aab584 --chmod=0444 \
    https://raw.githubusercontent.com/block/buzz/4db7bb0e7f904b2f0ea232aacae6cd7f6b8a3b39/LICENSE \
    /usr/local/share/licenses/buzz/LICENSE

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates git libatomic1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
    && for tool in buzz-acp buzz buzz-dev-mcp git-credential-nostr git-sign-nostr rg tree; do \
         ln -s sprig "/usr/local/bin/$tool"; \
       done \
    && groupadd --gid 10001 agent \
    && useradd --uid 10001 --gid 10001 --home-dir /home/agent \
       --shell /bin/bash --no-create-home agent \
    && install -d -o 10001 -g 10001 -m 0700 /home/agent /workspace /state \
    && install -d -o 0 -g 0 -m 0700 /worker-state \
    && install -d -o 0 -g 0 -m 0755 /app /opt/buzz-build

# Pin the adapters, and record their actually resolved nested CLI versions.
# This npm resolution is not a complete transitive dependency lock. A verified
# final image digest is the deployment lock; rebuilding requires revalidation.
RUN npm install --global --omit=dev --no-audit --no-fund \
      "@agentclientprotocol/codex-acp@${CODEX_ACP_VERSION}" \
      "@agentclientprotocol/claude-agent-acp@${CLAUDE_ACP_VERSION}" \
    && npm cache clean --force

WORKDIR /app
COPY --chown=0:0 package.json package-lock.json /app/
COPY --chown=0:0 LICENSE /usr/local/share/licenses/buzz-agents/LICENSE
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
    && npm cache clean --force
COPY --chown=0:0 buzz_agents /app/buzz_agents
COPY --chown=0:0 scripts /app/scripts
COPY --chown=0:0 guard-bin /app/guard-bin
RUN chmod -R a+rX,go-w /app \
    && chmod 0755 /app/guard-bin/codex-acp /app/guard-bin/claude-agent-acp \
    && python /app/scripts/preflight.py > /opt/buzz-build/inventory.json \
    && chmod 0444 /opt/buzz-build/inventory.json

# Generated Compose starts a limited-root supervisor. Native Buzz and the AI
# subprocesses drop to UID/GID 10001 with no supplementary groups.
USER 10001:10001
CMD ["python", "-m", "buzz_agents.native"]

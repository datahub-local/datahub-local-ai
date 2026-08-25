# Multi-arch is mandatory, not optional: agents are scheduled onto Orange Pis
# (arm64) as well as the amd64 nodes, and an MCP server that only has an amd64
# image fails to schedule silently from the agent's point of view — the tool
# simply never appears and the report comes out blander.
FROM debian:trixie AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/app/.venv
ENV UV_PYTHON_INSTALL_DIR=/opt/python

WORKDIR /app

COPY .python-version pyproject.toml ./

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && uv python install "$(cat .python-version)" \
    && uv venv --python "$(cat .python-version)" --managed-python --relocatable /app/.venv \
    && UV_LINK_MODE=copy uv sync --no-dev --no-install-project --all-extras

COPY src/ /app/src/
COPY projects/ /app/projects/

RUN UV_LINK_MODE=copy uv sync --no-dev --all-extras

FROM debian:trixie

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 65532 --shell /usr/sbin/nologin mcp

ENV PATH=/app/.venv/bin:$PATH

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /opt/python /opt/python
COPY --from=builder /app/src /app/src
COPY --from=builder /app/projects /app/projects

# The server holds no credential of its own — Prometheus needs no auth on this
# cluster and Kubernetes reads go through the pod ServiceAccount — so it has no
# reason to run as root.
USER 65532

EXPOSE 8080

# The MCP endpoint answers on every path, so a health probe must use one of the
# reserved health paths rather than the service root.
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz').read()"

# python -m mcp_runner serves one project's tools over MCP.
ENTRYPOINT ["python", "-m", "mcp_runner"]
CMD ["--project", "homelab_facts", "--port", "8080"]

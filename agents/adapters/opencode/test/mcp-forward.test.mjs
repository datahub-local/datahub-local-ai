// The upstream GitHub MCP server binds loopback and validates the Host header
// against that address. Forwarding the client's Host gets a 403 "invalid Host
// header", the client parks the server, and every github tool silently
// disappears from the agent. The proxy must speak loopback upstream.

import assert from "node:assert/strict";
import { test } from "node:test";

import { upstreamHeaders } from "../mcp-forward.mjs";

const request = {
  host: "datahub-local-core-automation-mcp-github.automation.svc.cluster.local:8080",
  accept: "application/json, text/event-stream",
  "content-type": "application/json",
  authorization: "Bearer stale-token-from-a-persisted-config",
};

test("the client's Host never reaches the upstream server", () => {
  const out = upstreamHeaders(request, "ghs_minted", 8081);
  assert.equal(out.host, "127.0.0.1:8081");
});

test("the minted token replaces whatever the client sent", () => {
  const out = upstreamHeaders(request, "ghs_minted", 8081);
  assert.equal(out.authorization, "Bearer ghs_minted");
});

test("everything else passes through", () => {
  const out = upstreamHeaders(request, "ghs_minted", 8081);
  assert.equal(out.accept, request.accept);
  assert.equal(out["content-type"], request["content-type"]);
});

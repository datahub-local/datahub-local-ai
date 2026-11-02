// Upstream MCP servers validate the Host header against the address they bind
// to, and the GitHub server binds loopback inside this pod. Forwarding the
// client's Host (the Service DNS name) is answered with 403 "invalid Host
// header" and the client parks the server, so the proxy terminates the name and
// speaks loopback upstream.
export function upstreamHeaders(requestHeaders, token, upstreamPort) {
  return {
    ...requestHeaders,
    host: `127.0.0.1:${upstreamPort}`,
    authorization: `Bearer ${token}`,
  };
}

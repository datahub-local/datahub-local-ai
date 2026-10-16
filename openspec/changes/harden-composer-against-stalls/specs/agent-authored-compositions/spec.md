# Spec Delta

## ADDED Requirements

### Requirement: An authoring turn survives a transient model-endpoint stall

The composer's runtime SHALL carry explicit settings for the model calls it makes, and MUST NOT
rely on the vendor's defaults for either: a retry window that outlasts a silence of several
minutes at the model endpoint, and a request idle timeout that exceeds the model gateway's own
streaming timeout, so the gateway's verdict ends an attempt before the runtime's does. The
model gateway SHALL apply a timeout to a streaming call that is separate from, and larger than,
its non-streaming request timeout: for a streaming call that timeout bounds the gap between
chunks, and the gateway cannot substitute another deployment once a stream has emitted to the
client. An authoring turn that exhausts its retry window SHALL end as a failure that names the
model endpoint and the reason.

#### Scenario: A stall inside the window is recovered

- **WHEN** the model endpoint stops sending chunks for longer than the gateway's streaming
  timeout and resumes within the runtime's retry window
- **THEN** a further attempt is made
- **AND** the turn completes without human action

#### Scenario: An exhausted window fails loudly

- **WHEN** every attempt in the retry window fails
- **THEN** the turn fails naming the model endpoint and the reason
- **AND** the failure is reported rather than left for the caller to discover as a missing
  artifact

#### Scenario: The runtime outlasts the gateway

- **WHEN** the runtime's request idle timeout is compared with the gateway's streaming timeout
- **THEN** the runtime's is larger
- **AND** the gateway's verdict is what ends each attempt

#### Scenario: A stalled stream has no substitution

- **WHEN** a streaming call has already delivered content to the client and then stops
- **THEN** the gateway reports the provider's failure rather than substituting another
  deployment
- **AND** the runtime's retry is what recovers the turn

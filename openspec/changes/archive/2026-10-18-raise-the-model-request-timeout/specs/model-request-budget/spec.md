# Spec Delta

## ADDED Requirements

### Requirement: A model call waits for the gateway's failover

Every model node in this repository SHALL allow at least 120 seconds for one request, so a primary
model that stalls for the gateway's own timeout still leaves room for the fallback to answer before
the client abandons the call. The budget SHALL be set on the node itself, because neither the
credential nor the instance carries one, and SHALL be checked across every workflow rather than in
one lane, so a new workflow is not silently exempt.

#### Scenario: A failover is not cut off by the client

- **WHEN** the gateway spends its own timeout on a primary model and then fails over
- **THEN** the client is still waiting
- **AND** the node does not report a timeout while the gateway is answering

#### Scenario: A new model node is not exempt

- **WHEN** a workflow is added or a model node is added to one
- **THEN** the offline sweep finds it and requires the same budget
- **AND** a node below the floor fails offline rather than at run time

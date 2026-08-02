# API Documentation

Contracts that cross a process boundary: HTTP endpoints exposed by the
`dashboard` service, event schemas published on the message bus, and the
`BrokerAdapter` port that venue integrations implement.

**Empty at ATLAS-TASK-0001.** No process exposes an interface yet, and there
are no event schemas to publish. Documenting an API that does not exist
produces a document that is wrong from the day it is written.

## What lands here

| Document | Source of truth | Arrives with |
|---|---|---|
| `events.md` | Event contracts in `atlas.events` | the message bus |
| `broker-port.md` | The `BrokerAdapter` protocol | the broker abstraction |
| `dashboard-http.md` | Generated OpenAPI schema | the dashboard service |

## Rule

API documentation is generated from, or verified against, the code it
describes. A hand-maintained copy of a schema drifts from the schema, and the
drift is invisible until an integration breaks. Where generation is not
practical, a contract test in `tests/contract/` must assert that the document
and the implementation still agree.

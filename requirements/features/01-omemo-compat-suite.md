# OMEMO Compatibility Test Suite

## Vision

Reproducible interoperability testing for XMPP OMEMO (XEP-0384) across server and client implementations. The suite downloads current upstream sources, runs their unit tests, and executes cross-implementation scenarios that expose wire-level incompatibilities.

## User Stories

### US-1: Download implementations
**As a** developer maintaining OMEMO clients  
**I want** a script that clones current ejabberd, library, and client sources  
**So that** tests always run against the latest published code.

**Acceptance criteria:**
- `scripts/download-implementations.py` clones all configured repos into `vendor/`
- Re-running updates existing clones (`git pull`)
- Optional implementations can be skipped with `--skip-optional`

### US-2: Run upstream unit tests
**As a** library maintainer  
**I want** upstream pytest suites executed automatically  
**So that** regressions in python-omemo, slixmpp-omemo, etc. are caught.

**Acceptance criteria:**
- `scripts/run-suite.sh --upstream` runs configured test commands per implementation
- Failures are reported with implementation id and exit code

### US-3: Cross-backend compatibility
**As a** client developer  
**I want** oldmemo (Conversations-style) and twomemo (OMEMO 2) tested against each other  
**So that** mixed-client deployments are verified.

**Acceptance criteria:**
- Alice (twomemo-only) can decrypt Bob (oldmemo-only) messages after session setup
- Key transport (empty payload) messages work in both directions
- Multi-device fan-out encrypts for all recipient devices

### US-4: Standard conformance
**As a** standards contributor  
**I want** tests derived from XEP-0384 requirements  
**So that** implementations do not introduce new restrictions.

**Acceptance criteria:**
- Namespace URIs match the specification
- Required XML elements are present in serialized messages
- Fingerprint format uses Curve25519 identity key bytes

### US-5: Wire-level E2E
**As a** integrator  
**I want** real XMPP stanzas over ejabberd  
**So that** PEP/pubsub and server configuration issues are caught.

**Acceptance criteria:**
- Docker Compose starts ejabberd with OMEMO-friendly pubsub config
- Two slixmpp clients exchange encrypted messages
- Tests skip gracefully when Docker is unavailable

### US-6: Known incompatibility scenarios
**As a** bug triager  
**I want** documented failure scenarios as regression tests  
**So that** fixes can be verified and stay green.

**Acceptance criteria:**
- `tests/scenarios/known_issues.yaml` lists scenarios with metadata
- Each scenario has a corresponding pytest that fails until fixed (or documents current status)

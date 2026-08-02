# OMEMO static audit methodology

This suite uses two complementary layers (see also `config/conversations-siskin-compat.yaml`).

## 1. Wire-format compatibility (what we did first)

- Compare namespaces, PEP node names, bundle XML, IV length, auth-tag-in-key layout.
- Run happy-path wire roundtrips (Gradle/Smack proxies).
- Use python-oldmemo as Conversations legacy wire reference.

**Limitation:** Passing roundtrips do **not** prove vendor send paths are correct. Smack enforces its own `expected ⊆ encoded` logic.

## 2. Control-flow audit (Kompatibilitätsaudit approach)

Pin exact commits (`config/audit-source-pins.yaml`). Trace **send** and **receive** paths in vendor source:

### Core invariant

For each outbound message, define:

- `expected`: `(bareJid, deviceId)` of all active, trust-allowed recipient devices at send time.
- `encoded`: devices that received a `<key rid="…">` in the header.

**Rule:** `expected ⊆ encoded` must hold before the stanza is sent. Partial coverage (`encoded ⊂ expected`) causes decrypt failures that look like crypto bugs ([#162](https://github.com/tigase/siskin-im/issues/162), [#240](https://github.com/monal-im/Monal/issues/240)).

### Review checklist

| Area | What to trace |
|------|----------------|
| Device list fetch | PEP failure → empty list vs error |
| Bundle fetch | timeout/forbidden → skip vs retry |
| Session build | failed cipher → drop key vs abort send |
| Self-device filter | compare device id only vs `(jid, deviceId)` |
| MUC decrypt | first matching `rid` vs all candidates |
| Bundle publish | announce device before bundle on wire |
| Trust callback | UI trust vs libsignal `isTrusted` |
| Stale PEP | cache TTL, refresh before send |

### Severity

- **P0:** partial send on wire (silent key drop)
- **P1:** wrong device filter, PEP/bundle publish gaps, MUC `rid` handling
- **P2:** stale lists, missing EME metadata

### Regression fixtures

Deterministic XML + key-state tests (`tests/compatibility/test_audit_regression_fixtures.py`), not only live roundtrips.

### Automated static tests

`tests/compatibility/test_source_control_flow_audit.py` re-checks pinned vendor files for known problematic patterns until upstream fixes land. **These pass when the bug is still present** (they document source patterns).

### Failing vendor-bug tests

`tests/compatibility/test_vendor_open_bugs.py` asserts the **correct** invariant (`expected ⊆ encoded`, trust gating, etc.) and **fails** while vendor behavior violates it. Marked `vendor_bug`. Run:

```bash
python3 -m pytest tests/compatibility/test_vendor_open_bugs.py -v -m vendor_bug
```

When an upstream fix lands, the corresponding `vendor_bug` test should start passing — that is the signal to remove or flip the test.

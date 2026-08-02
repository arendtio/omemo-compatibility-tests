### Automated static tests

`tests/compatibility/test_source_control_flow_audit.py` and `test_monal_control_flow_audit.py`
**fail** when pinned vendor source still contains known bug patterns (`assert_no_pattern`).

### Behavioral invariant tests

`tests/compatibility/test_vendor_open_bugs.py` asserts correct runtime invariants
(`expected ⊆ encoded`, trust gating, etc.) and **fails** while vendor behavior violates them.

### CI policy

The default `legacy` job runs audit + vendor_bug tests. **CI is red while upstream bugs remain open.**
When a fix lands, the corresponding tests start passing — that is the signal to update the compat registry.

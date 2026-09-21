# 01: Manage image retention and previewed deletion

**What to build:** Complete local YAML-backed Regex retention TUI and CLI, with preview, confirmation and all four deletion modes as accepted in SPEC v1.

**Blocked by:** None.

**Status:** verified

- [x] SPEC A01–A12 behavior implemented; tests cover config, planning and execution failures.
- [x] Installation and commands documented using uv.
- [x] Complete implementation independently reviewed and P2 fixed in 2dc32e1; independent recheck PASS.
- [x] Actual implementation paths delivered for QA mapping.
- [x] No existing host Docker resources deleted.

Evidence: docs/qa/results.md; implementation 5041f66 + correction 2dc32e1; integrated 50 tests and mypy PASS.

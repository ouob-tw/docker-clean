# Implementation plan

SPEC v1 is accepted. Use a single mixed backend/terminal application implementation ticket to keep the deletion contract and TUI aligned. Python with uv, Textual and PyYAML is the proposed implementation stack; use the Docker CLI as the Engine boundary with argument arrays, never shell interpolation.

1. Independent QA drafts requirement scenarios while implementation delivers config, planning, TUI and CLI as one vertical slice.
2. Review the complete committed implementation independently for standards and SPEC behavior, fix findings, then validate the integrated revision.
3. QA exercises the real terminal application and a disposable isolated Docker daemon; do not remove existing host images or containers. Report missing evidence honestly.

Ownership: implementer owns application, packaging, README and implementation tests. QA owns docs/evidence and isolated test harness. Orchestrator owns SPEC, PLAN, tracker, decisions and task cards. Shared application files are edited only by implementer until review corrections finish.

Invariants: regex protection dominates both cleanup flags; no container mutation; preview limits execution; invalid configuration fails closed; destructive tests never target the host daemon.

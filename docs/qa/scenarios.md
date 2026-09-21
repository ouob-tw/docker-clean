# Independent acceptance scenarios

Derived from accepted SPEC v1 before implementation inspection (2026-09-21).

All destructive actions must target a disposable daemon, never the host socket. Save the daemon identity and a host container inventory before and after. CLI/API calls prepare fixtures or inspect results; terminal keystrokes exercise the actual TUI.

| SPEC | Independent observable scenario |
| --- | --- |
| A01 | Start with absent config; verify both checkboxes off; add/edit/delete regex and see matched tags change; select a tagged image to produce escaped anchored rules; save, exit, reopen and compare YAML and controls. Untagged image must not produce a name rule. |
| A02 | Fixture tags include postgres:16, postgres:160, namespace/postgres:16, registry.example:5000/team/app:1.2 and app:1x2. Exercise exact anchors, prefix, literal dot and OR; compare visible matches to independently declared expected tags. |
| A03 | Add protected and unprotected aliases to one ID. In each flag combination, neither alias nor ID may receive a delete operation. |
| A04 | Missing file, invalid YAML, non-list keep, non-string rule, nonboolean options, invalid regex, unreadable config: CLI refuses deletion. Externally change config while TUI open; save must preserve external content and request reload. |
| A05 | Four flag modes each use fresh single-tag, multi-tag and untagged images. Assert actual tag/ID existence afterward; default multi-tag conflict fails without force escalation. |
| A06 | Running and stopped containers reference different candidate images. Default mode skips both; force preview names both and reflects Docker result. Compare full container inspect records and IDs before/after, excluding volatile read-only statistics. |
| A07 | Cancel CLI and TUI preview and compare inventories; all-protected fixture yields zero candidate operations; explicit empty keep prominently states no protection. |
| A08 | Pause after preview then separately alter config, move tag to new ID, add protected alias, and add container reference. Confirm old plan cannot delete new or newly protected targets. |
| A09 | Unreachable socket and permission denied socket produce errors; real multi-tag rejection produces nonzero CLI result while other valid candidates may finish. TUI exposes failures. |
| A10 | Observe real untag/deleted output, failure/skip distinctions and capacity wording; never claim sum of image sizes equals freed bytes. |
| A11 | Create parent image, child image, volume, network, running/stopped containers; delete only previewed child and verify parent and every non-image resource remain. |
| A12 | Point client at TCP/SSH Docker destination or corresponding context; cleanup refuses with explicit local-only explanation. |

Evidence states: PASS requires the stated observable check; FAIL records divergence; UNPROVEN means evidence cannot establish a guarantee; NOT_EXECUTED means no run. Controlled fake state is integration evidence, never real Docker or terminal E2E.

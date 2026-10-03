# Issue tracker

本專案程式碼位於 `ouob-tw/docker-clean`；議題仍採本機 Markdown。需求來源為根目錄 SPEC.md，票券位於 `.scratch/image-clean/issues/`，逐票記錄相依關係。核准紀錄及任務卡位於 `.lat/`，不提交 Git。

驗收紀錄與情境位於 `docs/qa/`，原始證據依紀錄中的路徑保存，架構決策位於 `docs/adr/`。未解問題另建本機票券。狀態採 ready-for-agent、in-progress、verified；不自行關閉使用者票券。

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`
- The spec is `.scratch/<feature-slug>/spec.md`
- Implementation issues are one file per ticket at `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`, never a single combined tickets file
- Triage state is recorded as a `Status:` line near the top of each issue file (see `triage-labels.md` for the role strings)
- Comments and conversation history append to the bottom of the file under a `## Comments` heading

## When a skill says "publish to the issue tracker"

Create a new file under `.scratch/<feature-slug>/` (creating the directory if needed).

## When a skill says "fetch the relevant ticket"

Read the file at the referenced path. The user will normally pass the path or the issue number directly.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a file with one **child** file per ticket.

- **Map**: `.scratch/<effort>/map.md` (the Notes / Decisions-so-far / Fog body).
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md`, numbered from `01`, with the question in the body. A `Type:` line records the ticket type (`research`/`prototype`/`grilling`/`task`); a `Status:` line records `claimed`/`resolved`.
- **Blocking**: a `Blocked by: NN, NN` line near the top. A ticket is unblocked when every file it lists is `resolved`.
- **Frontier**: scan `.scratch/<effort>/issues/` for files that are open, unblocked, and unclaimed; first by number wins.
- **Claim**: set `Status: claimed` and save before any work.
- **Resolve**: append the answer under an `## Answer` heading, set `Status: resolved`, then append a context pointer (gist + link) to the map's Decisions-so-far in `map.md`.

## Existing ticket policy

Existing image-clean tickets keep their paths, dependency records, and `ready-for-agent` / `in-progress` / `verified` states. The wayfinder states above apply only to new wayfinder maps. Verification does not authorize closing user tickets.

# 03: Compact table, stable selection and persisted terminal themes

**What to build:** Apply the user's directly requested UI refinements after initial delivery: compact checkbox, column order tag/size/date/reason, wrapped long tags, readable sizes and second-resolution dates, full ID in details, Space/Enter/mouse selection without jumping, clearer tag-removal label, native terminal theme with YAML persistence.

**Blocked by:** 01.

**Status:** verified

- [x] Layout and selection implementation, cursor regression RED on 7a58116 then GREEN.
- [x] Theme setting defaults to terminal, persists explicit selection without saving unrelated drafts, preserves external edit protection.
- [x] Independent standards/spec reviews; QA helper selection side effect corrected in f4f27f3.
- [x] NO_COLOR native-theme defect reproduced on f4f27f3 and fixed in ed4cc85; independent recheck PASS.
- [x] Final independent real-terminal recheck and owned resource cleanup (QA 9eb0660, product ed4cc85).

Evidence: docs/qa/ui-update.md. No Docker deletion is authorized by this UI task.

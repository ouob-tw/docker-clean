# 介面更新：獨立終端 QA

2026-09-21，production code `9648616`（執行期間 HEAD 更新至僅修改測試的 `f4f27f3`）。使用獨立 tmux `toga-ui-qa`，140×42，啟動 `uv run docker-clean tui --config /tmp/toga-ui-qa.yaml`；Docker 僅讀取盤點，未操作「確認刪除」。

| 項目 | 結果與實際證據 |
|---|---|
| 精簡介面 | PASS：選項與按鈕各自單行；選、tag、大小、建立日期、動作原因依序顯示，表格無完整 ID 欄。見 `evidence/ui-update/initial.txt`。 |
| 大小與日期 | PASS：實際顯示 `313.2 MiB`、`3.7 GiB` 與 `2026-07-30 06:01:43`。 |
| 長 tag 完整換行 | PASS：首行 `gohakka-f5-retirement-testexec-final-2265286-int` 接次行 `egration-product-consumer:latest`，串接與真實 `docker image ls` 完全相同。 |
| 捲動後 Space／Enter | PASS：游標移到捲動後的多行 tag；Space 畫面差異僅為該列 `□→✓`，Enter 後完整文字畫面與原始快照相同。見 `before-space.txt`、`after-space.txt`、`after-enter.txt`。 |
| 滑鼠點換行部分 | PASS：送入實際 SGR mouse press/release 至第二行 `(8,17)`，只有同一 image 選取標記改變；`after-mouse.txt` 與 `after-space.txt` 完全相同。 |
| 主題與草稿分離 | PASS：規則草稿 `^toga-draft$`、勾選 `remove_tags=True` 後，Ctrl+T 選 dracula；草稿仍在畫面，但 YAML 只保存 theme，keep 仍為空、remove_tags 仍 false。見 `drafts-preserved.txt`、`theme-only.yaml`。 |
| 重開與 terminal 還原 | PASS：退出、重開後 dracula 配色的 ANSI capture 與先前相符；再以 Ctrl+T 選 terminal，設定回存 `theme: terminal`，畫面配色也改回。見 `reopened-dracula-ansi.txt`、`restored-terminal-ansi.txt`、`restored-terminal.yaml`。 |
| 終端原生 ANSI | PASS（一般彩色終端）：另以 `env -u NO_COLOR uv run docker-clean tui --config /tmp/toga-ui-qa.yaml` 重開，header 使用 default，色彩序列為 ANSI `34m`／`30m`／`39m`／`49m`，非固定 RGB。見 `terminal-color-enabled-ansi.txt`。宿主 GUI 色盤切換未測。 |
| NO_COLOR 環境 | PASS（`ed4cc85` 修正後獨立重驗）：舊版曾實際輸出黑底黑字，重開仍相同（`reopened-terminal-ansi.txt`）；修正後相同 `NO_COLOR=1` 啟動，header 使用 default，不再輸出 RGB 黑底黑字。見 `fixed-no-color-terminal.txt`。 |

以上證據均位於 `docs/qa/evidence/ui-update/`；以完整畫面差異比對確認選取沒有跳回頂端。範圍限本次 140×42 的實際操作，未重跑刪除情境。

`ed4cc85` 最終獨立重驗：`NO_COLOR=1` 下 Ctrl+T 選 dracula，YAML 保存後退出重開；畫面正常、保持無色輸出。移除 `NO_COLOR` 再重開同一設定，dracula header 實際呈現 RGB `49;52;66`／`248;248;242`；Ctrl+T 回 terminal 後 header 回到 default，YAML 為 `theme: terminal`。見 `fixed-no-color-reopened-dracula.txt`、`fixed-color-dracula.txt`、`fixed-color-terminal.txt` 與 `fixed-*.yaml`。因此同時驗證修正、保存、重開與原生色模式還原。

根 agent 另回報：舊版 `7a58116` 的游標測試曾失敗（預期 15，實際 0），`f4f27f3` 的 NO_COLOR 真實 PTY 測試重現黑底黑字失敗；紅燈紀錄已保存為 `cursor-red.log`、`no-color-red.log`。最終 `ed4cc85` 共 63 項測試通過（6.46 秒）、mypy 6 檔通過。此段為根 agent 的獨立測試結果，非本終端 QA 重新執行。

清理：Ctrl+Q 結束自身 tmux session，確認 session 已不存在；暫存 YAML 以 trash-cli 移除。保留上述證據檔；未修改 production code、使用者設定或 Docker 資源。

主控整合核對：Standards／Spec 獨立審查皆完成；發現的 QA focus helper 點擊資料列造成額外勾選已在 `f4f27f3` 修正並獨立重驗。原生色初始化修正 `ed4cc85` 亦經獨立審查通過。主控確認相關 tmux session 已退出，自己的驗收暫存資料已清理；沒有未處理的本次審查項目。

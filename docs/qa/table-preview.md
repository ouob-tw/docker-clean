# 表格預覽、Regex 篩選與鍵盤操作

日期：2026-09-22。基準：`/tmp/docker-clean-table-preview-base`；審查快照：`/tmp/docker-clean-table-preview-review/changes.diff`。

- PASS：聚焦按鈕可用 Space／Enter 操作；輸入框仍可輸入空白。取消按下動畫，避免快速操作被忽略。
- PASS：「使用說明」位於最右上角；標題不展開。刷新按鈕使用「刷新」文字。
- PASS：「Regex 篩選」只改變清單顯示，保留勾選；空輸入恢復全部，無效 Regex 保留前次篩選並顯示錯誤。
- PASS：無 tag 顯示 `None`，`^None$` 可篩選或 Regex 勾選；Docker 資料仍為空 tag 清單。勾選的後續修正與驗證見下。
- PASS：白名單預覽維持表格，包含全部已勾選項目，不受篩選限制；可取消勾選及勾回原項目。全部取消後不可確認；確認只刪除仍勾選的 ID（假 Docker 行為驗證）。
- PASS：預覽動作原因包含容器引用；詳細資料可查看完整 ID 與全部 tag。80×24 實際渲染沒有操作區重疊。
- PASS：146 項單元與整合測試，mypy 12 個來源檔案；包括 E-Ink、捲動邊界、刪除進度與真實 PTY／zmx 滑鼠回歸。
- NOT_EXECUTED：真實 Docker 破壞性刪除。所有新增驗證均使用假 Docker。

證據：[修正前失敗](evidence/table-preview/red.log)、[完整測試](evidence/table-preview/green.log)、[主畫面](evidence/table-preview/main.svg)、[表格預覽](evidence/table-preview/preview.svg)、[詳細資料](evidence/table-preview/details.svg)、[None 篩選](evidence/table-preview/none-filter.svg)。同目錄 `.txt` 為實際渲染字元記錄。舊版保留規則模式仍使用文字預覽。

Claude（nemo）首次獨立審查未發現阻擋問題，另在隔離快照重跑 141 項測試通過（hcom #20760）。提出的介面細節已補正：防止雙擊重複開啟說明／詳細資料；容器引用另起一行，避免勾選改變換行而截斷，且不清空或重建表格；預覽後焦點移入表格。新增 5 個情境修正前均失敗，修正後通過，[重現紀錄](evidence/table-preview/review-red.log)。後續審查快照：`/tmp/docker-clean-table-preview-final-review/follow-up.diff`。

Claude 最後覆核通過，無待修問題；隔離副本完整 146 項測試通過（hcom #20794）。確認視窗攔截不影響正常關閉、動作文字不超過欄位最小寬度，因此容器資訊換行與列高不受勾選影響；預覽後 Space 直接切換表格勾選。

後續新增「顯示全部」：位於「Regex 篩選」旁，只解除篩選，保留 Regex 與勾選；沒有篩選時停用。從預覽使用時回到完整清單並停用確認，必須重新預覽。80×24 工具列仍完整顯示。新增操作測試修正前失敗，修正後連同篩選、版面、白名單與進度共 31 項通過；mypy 13 個檔案通過。[修正前](evidence/table-preview/show-all-red.log)、[相關測試](evidence/table-preview/show-all-green.log)。本次差異：`/tmp/docker-clean-show-all-review/changes.diff`。

「顯示全部」經 Claude（nemo）覆核通過，無阻擋問題；隔離副本完整單元與整合測試 150 項通過（hcom #20872）。確認解除篩選不改動 Regex 或勾選，各清單更新路徑會同步按鈕停用狀態。

後續修正 `None` 無法 Regex 勾選：先前只有篩選啟用 `None` 比對，現在兩者共用相同規則。`^None$` 命中無 tag 項目，`.*` 也包含無 tag；空規則不勾選，大小寫遵循 Python Regex。直接 Regex 勾選與先篩選再勾選，均驗證可預覽並只刪除確認的無 tag ID（假 Docker），原始 tag 清單保持空值。修正前 3 項失敗，修正後相關 38 項通過；mypy 13 個檔案通過。[重現](evidence/table-preview/none-select-red.log)、[測試](evidence/table-preview/none-select-green.log)。審查差異：`/tmp/docker-clean-none-select-review/changes.diff`。

Claude（nemo）覆核未發現正確性阻擋，隔離副本完整 152 項測試通過（hcom #20898）。審查另提出短 Regex（如 `o`）也會命中顯示名稱 `None`；依既有 `re.search` 契約及篩選／勾選一致的需求保留此行為，不新增無 tag 專用的 `fullmatch` 例外。README 已明確說明，精確選取仍使用 `^None$`；確認前仍須預覽。

```sh
uv run pytest tests/unit tests/integration -q
uv run mypy src
```

# 表格互動與刪除進度驗證

日期：2026-09-21。範圍：一般 TUI 與白名單 TUI 的排序、勾選、滾輪邊界、白名單黑白樣式、刪除進度與結果紀錄。

## 重現與修正

| 項目 | 修正前 | 修正後 |
|---|---|---|
| 預設排序 | 依 image ID 排列 | tag 字母升冪；標題切換排序；大小與日期採實值 |
| 勾選閃爍 | 500 筆清單勾選一次，清表 1 次、重建 500 列 | 原地更新勾選與原因；清表 0 次，游標與捲動不變 |
| E-Ink | 實際渲染含 #070707、#4c4c4c、#cccccc | 聚焦、停用按鈕與執行中畫面僅黑白 |
| 滾輪邊界 | 表格到頂／底後，外層位置由 5 變成 3／7 | 外層不動；正常表格捲動距離等於原生設定 |
| 刪除卡死 | 阻塞的 Docker 呼叫返回前，確認事件無法返回 | Docker 查詢／刪除在背景；主介面可繼續處理按鍵 |
| 結果紀錄 | 同一完整 ID 在兩行回報中重複 3 次 | 同一 image 合併，顯示名稱並保留原始回報 |
| 進度與閱讀位置 | 無逐項進度 | 按 image 計數；新紀錄置頂，閱讀舊紀錄時保留位置 |

修正前基準為本次開始時的工作區快照 `/tmp/docker-clean-toga-baseline`，包含當時尚未提交的白名單功能。不是以 Git HEAD 代替該基準。

紅燈證據：[顯示與滾輪](evidence/interface-progress/display-scroll-red.log)、[介面阻塞](evidence/interface-progress/freeze-red.log)、[重複 ID](evidence/interface-progress/log-red.log)。凍結的第二版差異位於 `/tmp/docker-clean-toga-progress-review/changes.diff`。

## 驗證範圍

- PASS：Textual 真實事件派送、滑鼠標題點擊、鍵盤選取、渲染色彩、上下滾輪邊界與步長。
- PASS：阻塞 Docker 查詢及刪除時介面可回應，禁止重複確認、選取與 Ctrl+Q 離開。
- PASS：兩種模式的查詢失敗停止後續項目、個別刪除失敗繼續、最後盤點失敗保留紀錄並清空過期表格，主狀態明確要求重新盤點。
- PASS：詳細紀錄由新到舊；在頂部跟進，在舊紀錄處保留畫面位置。
- PASS：既有保留規則、預覽及刪除一致性測試；型別檢查。
- NOT_EXECUTED：本次未使用真實 Docker Engine 進行破壞性驗收，未刪除主機 image。上述介面測試使用假 Docker，不能當成真實刪除證據。

可重跑：

```sh
uv run pytest tests/unit tests/integration -q
uv run mypy src
```

完整單元＋整合測試：118 passed；mypy：9 個來源檔案通過。結果見 [green.log](evidence/interface-progress/green.log)。

Claude（nemo）第一輪審查指出滾輪重複派送與舊模式 tag 結果未合併，均已修正；正常捲動步長與多 tag 合併已加入回歸測試。第二輪指出最後盤點失敗後的過期表格及舊模式即時預覽被隱藏，均已修正並加入兩種模式的回歸情境。勾選時保留當下列位置，排序於再次點擊標題或重建清單時重套，已明載 SPEC／README。最後修正差異凍結於 `/tmp/docker-clean-toga-final-review/changes.diff`。

Claude 最後覆核：無剩餘阻擋問題，獨立疊加快照重跑 118 項通過（hcom #20557）。非阻擋文字備註：逐項查詢失敗但最後盤點成功時，主狀態仍顯示「執行已結束」，進度區會明確顯示「尚有 N 個未處理」，並保留失敗紀錄；不代表全部 image 完成。

## 後續：所有內層捲動區隔離

使用者要求所有容器內捲到邊界時都不能帶動外層。原本只有表格隔離，Regex 輸入框與詳細紀錄仍會傳遞滾輪事件。現共用僅停止事件冒泡的處理，保留 Textual 原生的一次捲動，套用到兩種 TUI 的表格、輸入框與紀錄區。

定向測試 29 項通過：上下邊界、空／短內容、可捲動內容、兩種模式、正常反向捲動距離，以及游標位於外層內容時仍可正常捲動。修正前 16 項失敗、12 項通過，失敗皆為外層位置被內層帶動，見 [containment-red.log](evidence/interface-progress/containment-red.log)。完整回歸見 [containment-green.log](evidence/interface-progress/containment-green.log)。

完整單元＋整合測試：143 passed；mypy：10 個來源檔案通過。本次沒有操作真實 Docker 刪除。

Claude（nemo）覆核通過，無 findings；獨立快照重跑同樣 143 passed，確認共用處理只阻止冒泡、沒有重複捲動，紀錄子項目的事件也不會到外層（hcom #20599）。

# 精簡主畫面與懸浮視窗驗證

日期：2026-09-22。基準：`/tmp/docker-clean-modal-base`（本次變更前的完整來源與測試快照）。

## 結果

- PASS：原本兩行說明移入「使用說明」懸浮視窗，Escape 可返回主畫面；E-Ink 保持黑白。
- PASS：白名單輸入內容預設 2 行，3 行時自動增高，最多 4 行，更多內容在框內捲動，清空後縮回 2 行。邊框另占上下各一列。
- PASS：主畫面無外層捲軸；中央在清單與完整預覽間切換，底部操作按鈕保持固定。Ctrl+Q／Ctrl+P 靠右，Ctrl+T 功能保留但不顯示。
- PASS：刪除開啟進度懸浮視窗，背景工作阻塞時仍可回應，執行中不允許 Escape／Ctrl+Q 關閉；完成後可返回清單，再次執行使用新視窗與新紀錄。
- PASS：log 按時間由舊到新排列，停在底部跟進，往上閱讀時位置不變；查詢／刪除／最後盤點失敗的既有處理保留。
- PASS：真實 PTY 與 zmx 字元座標滑鼠測試。測試改為讀取實際表格座標，不沿用舊版面硬編碼列號。
- PASS：完整單元＋整合測試 135 項；mypy 11 個來源檔案通過。
- NOT_EXECUTED：真實 Docker 破壞性刪除；測試與畫面取樣皆使用假 Docker，未修改主機 image。

測試數由先前 143 項調整：原先每種模式重複跑的巢狀外層捲動情境，改以共用元件的實際巢狀測試容器驗證；主程式另驗證無外層捲軸及固定操作區。保留原有邊界、反向捲動步長及外層正常捲動的檢查，另新增精簡版面與視窗生命週期情境。

## 證據

- [修正前版面失敗](evidence/compact-modals/layout-red.log)：固定底部操作與輸入兩行測試皆在基準失敗。
- [完整測試](evidence/compact-modals/green.log)。
- 實際 Textual 渲染：[主畫面](evidence/compact-modals/main.svg)、[使用說明](evidence/compact-modals/help.svg)、[完整預覽](evidence/compact-modals/preview.svg)、[刪除結果](evidence/compact-modals/results.svg)。同目錄 `.txt` 為渲染字元記錄。
- 審查快照：`/tmp/docker-clean-modal-review/changes.diff`。

Claude（nemo）覆核無阻擋問題（hcom #20671），獨立快照重跑 135 項通過；另以 40／200 個瞬間完成的假 image 驗證 log 最後仍跟進到底部。完整預覽僅在按「預覽」後顯示，為本次替換舊版常駐預覽的預期行為。執行中 Escape／Ctrl+Q 不關閉進度視窗，返回按鈕保持停用。

後續同排調整：操作按鈕與 Footer 改為底部同一排，Footer 使用剩餘寬度並靠右。更新既有版面測試檢查同列、不重疊、不超出視窗；版面與真實 PTY／zmx 點擊共 5 項通過。前述 SVG 是合併底列前的歷史畫面。

同排調整經 Claude 覆核通過，獨立完整測試 135 項通過（hcom #20703）；兩種模式在 80×24 驗證完整顯示。寬度限制：60 欄時右側快捷鍵文字會被裁切；審查量測白名單約需 63 欄、舊模式約需 66 欄。依使用者同排要求，不自動換成第二排。

```sh
uv run pytest tests/unit tests/integration -q
uv run mypy src
```

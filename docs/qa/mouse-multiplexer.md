# 多工終端滑鼠誤開選單修正

## 問題與機制

使用者回報 HERDR 與 zmx 內點選 image 卻持續開啟選單。檢查環境為 Textual 8.2.8、HERDR 0.9.0、zmx 0.6.0。

HERDR v0.9.0 的 [input.rs](https://github.com/herdrdev/herdr/blob/v0.9.0/src/pane/input.rs#L64) 在收到字元座標時，可以在子程式已要求 1016 像素模式的情況下繼續編碼為字元 SGR；[對應測試](https://github.com/herdrdev/herdr/blob/v0.9.0/src/pane/terminal.rs#L5051) 明確涵蓋這條路徑。Textual 收到 2048 resize 支援後會啟用像素模式，並用像素／字元尺寸比換算滑鼠座標。

以本機終端尺寸 85×20、595×440 pixels 重現解析：字元點擊 (30,15) 被解讀成 (4,0)，落在左上角 HeaderIcon，觸發 CommandPalette。zmx 的存在不代表它本身有同一轉換錯誤；本次查到的 v0.6.0 實作為轉送協議流量，未將問題歸因為 zmx 特有 bug。

## 修正

`cedcc84` 在 CLI 載入 Textual 前設定其支援的 `TEXTUAL_SMOOTH_SCROLL=0`。TUI 啟動前再輸出 `1016l`、`2048l`，清除先前程式遺留的模式。保留 1006 字元滑鼠，不修改全域終端設定或多工終端安裝。

## 驗證

- RED：修正前的真正 PTY 測試，在終端回報 resize 支援後送入字元滑鼠事件，實際得到 `screens=['Screen','CommandPalette']`、`selected=[]`；符合使用者症狀。
- GREEN：同一流程改為選取 `sha256:a`、畫面堆疊只有主畫面；確認啟動輸出重設模式，且未啟用 1016。測試刻意帶入 `TEXTUAL_SMOOTH_SCROLL=1`，證明 CLI 相容性設定有效。
- 實際 zmx：相同測試透過獨立、隨機命名的 zmx session 執行通過。測試使用假的 Engine 盤點，不接觸 Docker 刪除；這是終端協議整合測試，不是 Docker E2E。
- 兩位獨立 reviewer 重跑上述 direct／zmx 兩項皆 PASS。完整 unit／integration 測試 65 passed；`uv run mypy src` 通過（6 個來源檔案）。實體 HERDR 視窗的人工滑鼠點擊未在本次重做，不能將協議重現寫成該項已驗證。
- 每次測試只清理自己建立的 zmx session 與 PTY，不關閉使用者既有 session。

重跑：`uv run pytest tests/integration/test_mouse_protocol.py -q`。zmx 未安裝的環境會明確跳過 zmx 分支。

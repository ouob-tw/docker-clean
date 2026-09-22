# E-Ink 配色與 ZMX 啟動互動

## 變更

- 白名單入口預設 E-Ink 白底黑字；選取／聚焦反相，停用按鈕以刪除線區別。舊版 `tui` 設定不變。
- CLI 的字元滑鼠模式補上輸入解析相容層：忽略未啟用的 in-band 尺寸回報，滑鼠始終按字元座標解碼。視窗大小由 PTY 與 SIGWINCH 決定。
- Textual 8.2.8 的 parser 收到 CSI 48 時，會無條件開啟 `mouse_pixels`；原有 `TEXTUAL_SMOOTH_SCROLL=0` 只阻止協商，無法阻止已在傳輸中的回報。相容層只在本程序 CLI 啟用，未修改套件、ZMX 或 Ghostty 安裝。

## 重現與驗證

- 原先無延遲回報的 direct／ZMX、100×40／76×20 測試均正常；不能將它們當成使用者問題的重現。
- RED：在真實 ZMX／PTY 送入延遲 CSI 48 後，再點 Regex 並輸入 `example`，原版得到空字串、未勾選；滑鼠落點錯誤。
- RED：兩個真實 ZMX 客戶端共用 session，由第二個客戶端接管 76×20 PTY，再送入其延遲尺寸回報。停用相容層時得到 `app=[100,40]`、`pty=[76,20]`，證明版面與實際終端不同步。非主導客戶端的純協議回應會被 ZMX 丟棄，不能宣稱任意客戶端回報都會混入。
- GREEN：同一雙客戶端測試啟用相容層後，app／PTY 維持一致；第一個客戶端再次輸入時，仍能正常透過 SIGWINCH 切回 100×40。
- E-Ink 的 Textual 互動與實際 PTY 輸出驗證包含 `NO_COLOR=1`，確認黑字白底。
- 完整單元／整合測試 96 passed；mypy 通過（8 個來源檔案）。

重跑：

```sh
uv run pytest tests/integration/test_startup.py tests/integration/test_mouse_protocol.py tests/integration/test_terminal_colors.py tests/integration/test_whitelist_tui.py -q
uv run pytest tests/unit tests/integration -q
uv run mypy src
```

測試使用假的 Docker 盤點，不執行刪除。真實 ZMX 的協議重現通過不代表已驗證 Mac Ghostty → SSH → ZMX 的實體畫面；該完整路徑仍待使用者重試。多客戶端依然共用單一 PTY 尺寸，修正不提供各端獨立排版。

# 容器清理驗證（2026-09-22）

- PASS：`uv run mypy src`；`git diff --check`。
- PASS：`uv run pytest tests/unit tests/integration -q`，204 passed。
- PASS：新增 34 項單元案例，涵蓋期限邊界、保留服務副本、Swarm、其他狀態、無效時間與設定、刪除前狀態／設定變更、部分成功後查詢失敗、設定路徑相容。
- PASS：全域安裝 `/home/swy/.local/bin/dc container clean --json` 真實本機 Engine 唯讀預覽。當次 108 個容器、14 個候選、0 筆刪除紀錄；數量會隨主機狀態改變。
- PASS：Python 3.11 全部 120 項單元測試。gone 複查發現 f-string 引號不相容 Python 3.11，修正後以最低支援版本驗證。
- PASS：gone 最終複查無阻擋項目；獨立唯讀審查後補明查詢期間容器消失將停止當次清理，改善操作紀錄與 SPEC 範圍說明。
- NOT_EXECUTED：真正刪除的隔離 Engine E2E。現有 QA 隔離 Engine 未執行，不以 mock 或主機預覽替代刪除證據。
- NOT_EXECUTED：凌晨排程；本次未安裝或啟用 cron。

主機設定已建立 `images.yaml` 與 `containers.yaml`，保留原 `config.yaml`。未刪除任何既有容器、image 或 volume。

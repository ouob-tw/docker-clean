# ADR 001：本機映像清理邊界

狀態：採用。需求依據：SPEC v1。

## 決策

- 採 Python、uv、Textual 與 PyYAML，提供同一套規劃及執行邏輯給 CLI 和 TUI。
- 使用 Docker CLI 與本機 Engine 溝通，參數以陣列傳遞，不使用 shell 拼接。
- 每次預覽保存明確的 image ID、tag、容器引用與設定版本；刪除前重新檢查，只縮減原名單，不擴張。
- 保留規則的優先級高於 force；刪除皆帶 `--no-prune`，避免額外清除未預覽的父映像。
- Docker 資料不具跨步驟交易保證，因此不能宣稱預覽、檢查及刪除之間完全無競態。

## 理由與影響

使用既有 Docker 權限與連線能力，減少獨立服務與設定。互動層與 Docker 執行共用契約，避免 CLI 和 TUI 的保留邏輯不同。真實刪除行為在專用 Docker daemon 驗證，不能在既有主機 image 上試刪。

## 延後事項

遠端 Engine、排程清理、容器及 volume 清理不在第一版範圍。

## 參考

[Docker image rm](https://docs.docker.com/reference/cli/docker/image/rm/) 定義 tag、force 與 no-prune 行為。

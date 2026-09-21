# Docker Clean

以 Python Regex 保留本機 Docker image；提供 Textual TUI 與每次預覽、確認後才執行的 CLI。僅清理 image／tag，沒有 prune、排程或跳過確認功能。

## 安裝與使用

需要 Python 3.11+、uv、Docker CLI，以及本機 Docker Engine 的存取權限。

```sh
uv sync --locked
uv run docker-clean tui
uv run docker-clean clean
# 或安裝成日常指令
uv tool install .
docker-clean tui
```

預設設定為 `~/.config/docker-clean/config.yaml`，也可在子命令後指定 `--config /path/config.yaml`。設定不存在時只能由 TUI 建立，`clean` 會停止。TUI 每行一條規則，可直接新增、編輯或刪除；選項預設關閉。Enter 或點擊 image 列可勾選，再按「產生規則」把實際 tag 轉成跳脫且有 `^...$` 錨點的 Regex。無 tag 的 image 不產生名稱規則。

儲存後按「預覽」，檢查下方完整內容，再按「確認刪除」；「取消」不操作 Docker。CLI 須輸入完整 `DELETE` 才執行。修改規則或選項會使舊預覽失效。TUI 的列表可水平捲動，完整預覽可垂直捲動，包含完整 ID、所有 tag、建立時間、bytes、引用容器與原因；Ctrl+Q 離開。

```yaml
keep:
  - '^postgres:16$'
  - '^myorg/.*:.*$'
cleanup:
  remove_tags: false
  force: false
```

以上只作範例，不會自動加入設定。`keep: []` 合法，畫面會警告沒有保留規則。Python 標準函式庫 `re.search` 為匹配引擎，多規則採 OR；比對完整 `repository:tag`，不轉換 registry／port／namespace。`^postgres:16$` 精確匹配，`^postgres:` 匹配所有該 repository tag；字面小數點用 `\.`。同一 ID 任一 tag 命中時，整個 image 與全部 tag 在任何模式都保留。空白規則也是合法 Regex，會匹配所有有 tag 的 image；空編輯器表示空規則清單。無 tag 不用 `<none>:<none>` 假名稱匹配。

設定讀取、型別、YAML、Regex 任一錯誤皆停止；不會退回沒有保護的設定。未知欄位也拒絕。儲存完整驗證後以原子替換寫入，偵測外部修改時須重新載入。

## 四種模式

| 移除 tag | force | 未被規則保護的 image |
|---|---|---|
| 關 | 關 | 跳過所有容器引用；按 ID 正常刪除，衝突如實失敗 |
| 開 | 關 | 跳過所有容器引用；逐一正常移除 tag，無 tag 者按 ID |
| 關 | 開 | 按 ID force 刪除；容器引用列入預覽，由 Docker 決定結果 |
| 開 | 開 | 逐一 force 移除 tag，無 tag 者按 ID；引用列入預覽 |

執行一律帶 `--no-prune`，避免連帶清除未預覽的父映像。不停止、刪除、重啟或修改容器，也不清理 volume、network、build cache 或主機目錄。最後一個 tag 移除時可能同時刪除 image。force 不保證成功或釋放資料。顯示的 image 大小含共用層，不能直接加總成可回收容量；結果分列 Docker 回報的 `Untagged` 與 `Deleted`，同一操作可能兩者都有。個別失敗不自動升級 force；CLI 有失敗回傳 1。

## 連線與競態限制

遵守 Docker 的 `DOCKER_CONTEXT` 優先於 `DOCKER_HOST`，否則使用目前 context。僅接受 `unix:///...` 本機 socket，TCP（包括 loopback）及 SSH 都拒絕；建立預覽後以固定 socket 執行，外部切換 context 不會改向其他 Engine。

每個刪除操作前重新讀取設定並盤點 Docker，設定更動或查詢失敗會停止；image、tag、容器引用改變則跳過該 image，不擴大已確認名單。多 tag 模式會扣除自己已成功移除的 tag，再比對剩餘狀態。Docker API 沒有涵蓋預覽到刪除的交易鎖，最後一次查詢與刪除之間仍有競態，尤其 force；本工具不宣稱完全消除。原子設定儲存也不能鎖住不合作的外部編輯器於最後檢查與替換間的極短競態。

## 開發驗證

```sh
uv run mypy src
uv run pytest                         # 只有單元測試
uv run pytest tests/integration      # Textual Pilot，使用假的 Docker
uv run pytest tests/unit tests/integration
```

單元／Pilot 測試不能代替真正終端或 Docker 的刪除證據。獨立驗收資料放在 `docs/evidence/`；破壞性驗證只允許專用隔離 Engine，不能操作主機既有映像。

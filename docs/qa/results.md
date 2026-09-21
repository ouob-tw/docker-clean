# 獨立驗收結果

狀態：A01–A12 PASS；資源清理紀錄見文末。

## 範圍與環境

- 需求情境先於實作檢視撰寫，見 [scenarios.md](scenarios.md)。
- CLI 完整矩陣候選：`5041f66107039ac2af6f6a0848d9c4ea4fbc8bff`；最終 TUI：`2dc32e1aae3cd88e828af71c5bd2fb475f702dba`。兩版 CLI／planner／Engine 未變，後者僅修正 TUI selection 與其回歸測試。
- 真實 Docker 28.5.2/vfs，專用 DinD 容器 `docker-clean-qa-toga-20260921`，daemon ID `67350f7e-6d40-44b5-96fd-e8287ae7dbdf`。
- 僅掛載 `/tmp/docker-clean-qa-toga-20260921/socket`；不掛主機 Docker socket、不開外部 port，daemon 資料使用獨立 tmpfs。原先 tmpfs 預設 noexec 導致 fixture 無法啟動；改為 exec 後 runtime smoke 通過，此環境問題不算產品缺陷。
- 終端：真實 tmux 200×65，送入鍵盤及 SGR 滑鼠事件；沒有 Textual Pilot、UI mock 或呼叫 widget method。
- 實際 CLI：`uv run docker-clean clean --config <獨立測試檔>`；確認輸入 `DELETE`。每次都固定 `DOCKER_HOST` 為隔離 socket 並移除 `DOCKER_CONTEXT`。

## 已取得證據

| 項目 | 結果 | 證據及界線 |
| --- | --- | --- |
| A01 | PASS | 真實終端新增、修改、刪除規則、第二列選取、registry tag 跳脫規則、無 tag 不產生規則、儲存、重開及兩旗標持久化；修正版完整 terminal replay 通過。 |
| A02 | PASS | `run_matching.py` 透過實際 CLI 預覽驗證完整 tag、anchors、搜尋匹配、repository 前綴、registry port、字面小數點及 OR；TUI 顯示即時保護。 |
| A03 | PASS | 四旗標組合各建立雙 tag image，只保護其中一 tag；兩個 tag 與 ID 均保留。 |
| A04 | PASS | CLI 缺檔、無法讀取、YAML 損壞、keep 型別錯、非字串、無效 regex、字串 false、整數選項均停止；真實 TUI 外部修改後 Save 拒絕，外部內容完整保留。 |
| A05 | PASS | 四組合實際操作單 tag、多 tag、無 tag；預設多 tag 衝突回傳失敗，沒有升級 force。 |
| A06 | PASS | 運行中與已退出容器均列入預覽；每模式完整 `docker inspect` JSON 前後相等，非僅數量相等。 |
| A07 | PASS | CLI 取消、零候選及空清單提示；TUI 預覽捲動後取消，image 盤點未變。 |
| A08 | PASS | 實際 CLI 在確認提示暫停後修改設定、改指向、新增保護 tag、新增容器引用，均保留受影響目標；修正版真實 TUI 選取→外部刪除→預覽→產生規則通過。選項改變後，舊確認按鈕不能執行。 |
| A09 | PASS | 無 socket、socket 權限不足、真實多 tag 刪除拒絕皆明確非零；真實 TUI 無法連線畫面亦驗證。 |
| A10 | PASS | 真正 Docker Untagged/Deleted 結果分開，顯示共用層不可加總，無保證回收容量；真實 TUI 預覽→確認後，目標消失並顯示 Untagged／Deleted。 |
| A11 | PASS | 真實 public plan→execute 僅納入 child，未列入預覽的無 tag parent 保留；四模式中保留父 base、volume、network 與完整容器資料。 |
| A12 | PASS | TCP 及 SSH endpoint 於 CLI 被本機限制拒絕，未嘗試刪除。 |

force 實際結果：按 ID force 刪除運行中引用 image，Docker 回報 `cannot be forced`，CLI exit 1；已退出引用 image 可刪除。逐 tag force 時運行中 image 僅 Untagged，已退出 image Untagged 與 Deleted；CLI exit 0。兩模式所有容器 inspect 完全一致。

## 獨立審查

主控回報兩路獨立審查固定範圍 `2d3dd70...5041f66`：Standards 無硬性規範違反；Spec 無破壞性範圍違規。兩路均重現同一 P2：選取 image 後由外部刪除，Preview 更新盤點但未清除 selection，Generate Rules 會 KeyError。修正方保留修正前 RED 與修正後 GREEN 證據，見 `evidence/implementation-selection-{red,green}.log`；QA 真實終端重驗通過。獨立 reviewer 複查 `5041f66...2dc32e1` PASS，並回報 3 項 Pilot integration tests PASS。

主控於最終 `2dc32e1` 實際執行 unit/integration：50 passed（4.17s）；mypy：6 source files PASS。主控亦用 git diff 確認 `5041f66` 與 `2dc32e1` 的 config、engine、plan、cli、__init__ 逐 byte 無差異。此段為主控證據，不冒充 QA 自行執行。

## 重跑

先依 `tests/qa_e2e/README.md` 建立隔離 daemon，再執行：

```bash
uv run python tests/qa_e2e/run_cli.py
uv run python tests/qa_e2e/run_matching.py
uv run python tests/qa_e2e/run_changes.py
uv run python tests/qa_e2e/run_parent.py
uv run python tests/qa_e2e/run_terminal.py
```

`run_parent.py` 使用公開 planner/executor 與真實 Engine，故可刻意將無 tag parent 排除於預覽；它不是完整 CLI 路徑。其他腳本透過真實 CLI 預覽／確認。終端透過 `run_terminal.py` 重跑，畫面見 `evidence/tui-replay-*.txt`。

## 程式路徑與證據

- `src/docker_clean/config.py`：設定型別、Regex 驗證、缺檔／權限、原子儲存、外部修改。`evidence/invalid-*.log`、`unreadable.log`、`tui-replay-external-conflict.txt`。
- `src/docker_clean/engine.py`：本機 endpoint、全量 container 引用、固定 socket、逐項 image rm `--no-prune`。`remote.log`、`ssh.log`、`permission.log`、`parent.log`。
- `src/docker_clean/plan.py`：OR 搜尋匹配、同 ID 保護、四模式、確認後重新盤點／設定驗證、原生結果區分。`qa-case-{00,01,10,11}.log`、`matching-*.log`、`change-*.log`。
- `src/docker_clean/cli.py`：公開入口、DELETE／取消、零候選、非零失敗。`cancel.log`、`zero.log`、四模式 logs。
- `src/docker_clean/tui.py`：真實鍵盤／滑鼠動作、重開、checkbox、table selection、修改後預覽失效、外部修改拒絕、確認刪除與結果。`tui-replay-*.txt`、`tui-reopened.txt`、`tui-final-*.txt`。

每模式完整容器 inspect 的前後 SHA256 與相等判斷存於 `qa-case-*-container-equality.json`。沒有以 container count、label 或 mock 代替完整比較。DataTable 在較窄終端需水平捲動；本輪真實操作主尺寸為 200×65，錯誤畫面另用 120×45，未宣稱所有尺寸的易用性均驗證。Docker 預覽與刪除間不存在完整交易鎖，本輪只證明受控變更情境被阻止，未宣稱消除所有外部競態。

## 清理完成

- 專用 DinD 容器與其 tmpfs 內所有 fixtures 已移除；沒有其他主機 container ID 消失。所有 QA tmux 終端皆已退出。
- 原主機 container ID 集合 139→139 完全相同；原 image 406 個全保留，新增 1 個共享 `docker:28-dind` base 並依約保留。詳見 `evidence/host-inventory-comparison.json`。此盤點只證明 ID 保留，不宣稱主機其他服務的所有執行狀態完全未變。
- QA 臨時目錄 `/tmp/docker-clean-qa-toga-20260921` 與自產生 pycache 已用 trash-cli 清理；必要證據已保存在本資料夾。未知來源的 `.env`、`.serena/` 完全未讀取內容或修改。

## QA harness 複查修正（保留原驗收紀錄）

最終 harness 複查在 `6097448` 找到兩個 P2：權限測試的 host `docker exec chmod` 未固定 endpoint；`exists()` 把所有 inspect 失敗都當作不存在，可能將權限或連線錯誤誤判為刪除成功。

本次只修正 QA 工具：管理命令統一經清除繼承 Docker context／TLS 設定的 `host_docker()`，固定 `unix:///var/run/docker.sock`；setup／cleanup 範例亦明列 endpoint。`exists()` 改為要求成功取得完整 image inventory，再比對完整 ID 或 repository:tag；查詢錯誤直接拋出，不回傳不存在，無 tag 亦不虛構名稱。

- RED：在 `6097448` 的舊 harness，模擬 subprocess 權限拒絕後應拋出錯誤的測試，實際因 `DID NOT RAISE CalledProcessError` 失敗。見 `evidence/harness-boundary-red.log`。
- GREEN：修正後 `uv run pytest tests/unit/test_qa_harness.py -q`，7 passed。另涵蓋成功 inventory 的 ID／registry port tag／無 tag／缺少目標，以及管理命令不繼承 remote context。見 `evidence/harness-boundary-green.log`。
- 此處使用 mock subprocess，是 harness 邊界單元測試，**不是新增 Docker E2E 證據**。修正後再次建立 daemon、重跑破壞性驗收為 **NOT_EXECUTED**；原有真實執行證據維持原版本，不回寫或冒充本次修正版執行。原紀錄未觀察到連線錯誤被誤判為刪除成功；完整 container equality、成功 Docker 原生結果與既有 image 保留檢查仍是原執行的獨立證據。

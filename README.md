# Docker Clean

提供 Delete 勾選刪除、Keep 保留規則流程與自動化 CLI。清理本機 Docker image／tag，另提供依停止期限與保留清單清理容器的 CLI；不使用 prune。

## Image 清理入口

- `dcl image keep`：開啟保留規則 TUI，命中者保留、清理其餘。
- `dcl image delete`：開啟刪除選取 TUI，只刪除勾選者。
- `dcl image clean`：自動化 CLI，使用以下參數。

畫面標題分別標示 Image Keep／Delete。舊 `docker-clean tui`／`whitelist` 保留相容，新指令也可寫成 `docker-clean keep`／`delete`。

## 自動化 CLI：dcl image clean

```sh
uv run dcl image clean --delete '^myapp:dev-'
uv run dcl image clean --keep '^postgres:'
uv run dcl image clean --delete '^myapp:dev-' --keep ':stable$' --yes --json
# uv tool install . 後可直接使用 dcl image clean
```

預設只預覽、不詢問輸入；加上 `--yes` 才執行。`--delete` 只選命中的 image，`--keep` 保護命中的整個 image；兩者同時使用時保留優先。只有 `--keep` 時清理其餘 image。兩個參數都可重複，多條採 OR，以 Python `re.search` 比對完整 tag；任一 tag 命中即作用於整個 ID。至少提供一條規則，空白或無效 Regex 拒絕執行；全部匹配請明確用 `.*`。

`--delete '^None$'` 選無 tag image；`--keep` 僅匹配真實 tag，沿用既有保留語意。預設跳過任何容器引用；`--force` 才要求強制刪除，與 `--yes` 分開。按 ID 刪除包含全部 tag，使用 `--no-prune`，不改動容器。刪除前重新盤點，狀態變動就跳過，查詢失敗停止；競態限制同下文。

此入口不讀寫 TUI YAML 設定。`--json` 輸出單一 JSON 物件，包含 `mode`、`ok`、規則、`force`、`entries`（image、動作、理由、目標）及 `results`（status、target、detail）；規則驗證或初次盤點錯誤包含 `ok: false` 與 `error`；逐項執行失敗則以 `ok: false` 及 `results[].detail` 回報。語法錯誤仍由參數解析器輸出至 stderr。結束碼：0 成功／預覽／無候選／狀態變動跳過，1 規則驗證或 Docker 操作失敗，2 命令語法錯誤。自動化可檢查 results 區分成功與跳過；不保證回收容量。

## 安裝與使用

需要 Python 3.11+、uv、Docker CLI，以及本機 Docker Engine 的存取權限。

```sh
uv sync --locked
uv run dcl image delete
uv run dcl image keep
uv run docker-clean clean
# 或安裝成日常指令
uv tool install .
dcl image keep
```

## Delete 刪除（新流程）

執行 `uv run dcl image delete`。預設使用 E-Ink 白底黑字主題，游標與聚焦按鈕黑白反相，停用按鈕以刪除線區別，避免依賴灰底或淡字。初始不勾選任何 image，不讀寫舊的保留設定；Regex 與勾選只用於本次操作。

1. 上方輸入框每行一條 Python Regex；多條採 OR，使用 `re.search` 比對完整 `repository:tag`。「Regex 篩選」只改變顯示，「Regex 勾選」將命中項目加入勾選。旁邊「顯示全部」解除篩選，保留 Regex 與勾選；未篩選時停用。空白行忽略，清空後篩選也可恢復全部；無效 Regex 保留既有篩選與勾選。
2. 下方表格用 Space／Enter／點擊增減勾選，也可「清除勾選」。同一 image 任一 tag 命中就勾選整個 image。無 tag 顯示 `None`，可用 `^None$` 篩選或「Regex 勾選」；`.*` 也包含無 tag 項目。`None` 僅用於顯示與比對，不會新增實際 tag。
3. 按「預覽」，表格顯示全部已勾選 image，不受篩選限制，動作原因包含容器引用。可取消勾選或勾回原項目，確認只刪除仍勾選者。「詳細資料」顯示游標項目的完整 ID、全部 tag 與容器引用。「取消／返回」恢復原篩選清單。修改 Regex 或套用篩選／Regex 勾選後須重新預覽。
4. 按「確認強制刪除」呼叫 `forceDeleteImage`，逐項執行 `docker image rm --no-prune --force <完整 ID>`。所有 tag 都在刪除範圍內；不停止或刪除容器，Docker 拒絕時如實顯示失敗。

零勾選無法確認。刪除前重新檢查盤點狀態，image／tag／容器引用變動就跳過該項；查詢失敗停止後續刪除，不擴大預覽名單。Ctrl+T 可切換本次主題，Ctrl+Q 離開。

`None` 與實際 tag 使用相同的 `re.search` 規則，因此 `o` 也會命中 `None`；只選無 tag 項目請用 `^None$`。

兩種 TUI 預設依 tag 字母升冪排序，點擊欄位標題切換升冪／降冪。勾選保持當下列位置；若按勾選或動作原因排序，再點標題即可重新排列。主畫面沒有外層捲軸，中央清單或預覽自行捲動，底部操作按鈕固定。輸入框與詳細紀錄的滾輪到達邊界時不會帶動外層，內容不足以捲動時也一樣。

Delete 輸入框顯示兩到四行內容，超過後在框內捲動。右上角「使用說明」開啟懸浮視窗，標題不再展開。聚焦按鈕可用 Space／Enter 操作。「刷新」重新取得 Docker 資料。底部操作按鈕與快捷鍵位於同一排，按鈕靠左、Ctrl+Q／Ctrl+P 靠右；Ctrl+T 仍可切換主題。

兩個 TUI 入口都可按 Ctrl+T，搜尋並選擇 `e-ink`。保留規則（`keep`）會保存所選主題，重開後繼續使用；Delete 預設為 e-ink，切換只作用於本次。e-ink 在 `NO_COLOR` 環境下仍保留明確的白底黑字。

確認後開啟懸浮視窗，顯示按 image 計算的進度與目前階段，Docker 工作在背景執行緒執行。詳細 log 舊的在上、新的在下，保留原始回報；停在底部時跟進新紀錄，往上閱讀時保留位置。執行期間仍可捲動，背景操作與視窗關閉暫時鎖住；完成後按「返回清單」或 Esc 關閉。查詢中止時會顯示尚未處理的數量，不會顯示假完成。

## Keep 保留規則流程（keep／clean）

預設設定為 `~/.config/docker-clean/images.yaml`（新檔不存在時相容舊 `config.yaml`），也可在子命令後指定 `--config /path/config.yaml`。設定不存在時只能由 TUI 建立，`clean` 會停止。TUI 每行一條規則，可直接新增、編輯或刪除；選項預設關閉。Enter 或點擊 image 列可勾選，再按「產生規則」把實際 tag 轉成跳脫且有 `^...$` 錨點的 Regex。無 tag 的 image 不產生名稱規則。

儲存後按「預覽」，檢查中央的完整內容，再按「確認刪除」；「取消」不操作 Docker。CLI 須輸入完整 `DELETE` 才執行。修改規則或選項會使舊預覽失效。列表依序顯示 tag（長名稱換行）、人類可讀大小、精確到秒的建立日期、動作原因；Space／Enter／點擊可勾選，不跳回第一列。完整 ID 與引用容器保留在詳細預覽；Ctrl+Q 離開。

預設 `theme: terminal` 使用終端原生 ANSI 色盤及預設前景／背景，因此隨終端配色顯示。Ctrl+T 開啟主題選單，切換後自動存入 YAML，下次沿用；選回 `terminal` 可恢復跟隨終端。切換主題只存主題，不順便儲存規則編輯或清理選項。

滑鼠固定使用字元座標，避免 HERDR／zmx 等多工終端路徑將像素模式與字元座標混用、誤開左上角選單。啟動會重設遺留的像素／in-band resize 模式，並停用 Textual 像素平滑捲動；一般滑鼠選取與捲動仍可使用。升級後請退出舊 TUI 再重新啟動。

延遲到達的 in-band 尺寸回報也會忽略，避免重新啟用像素換算或蓋過 PTY 尺寸；正常縮放仍透過 SIGWINCH 更新。兩台終端同時 attach 同一 ZMX session 時仍共用一個畫面尺寸，由最後輸入的客戶端主導；兩台視窗大小不同，未操作的一端可能顯示不完整。需要各自獨立版面時，使用不同 session。

```yaml
theme: terminal
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

畫面的「逐一移除標籤」對同一 image ID 的全部 tag 操作，並非刪除同名 repository 下不同版本的所有 image；保留規則優先。

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

單元／Pilot 測試不能代替真正終端或 Docker 的刪除證據。獨立驗收結果見 [QA 紀錄](docs/qa/results.md)，重跑方式見 [驗收指令](tests/qa_e2e/README.md)；破壞性驗證只允許專用隔離 Engine，不能操作主機既有映像。

## 容器自動清理

`dcl container clean` 依「最後停止時間」清理普通容器，預設只預覽。只接受 exited；執行中、從未啟動、其他狀態及 Swarm 管理的容器一律跳過。

設定範例見 [examples/containers.yaml](examples/containers.yaml)。檢查其中保留清單後，存為 `~/.config/docker-clean/containers.yaml`。`stopped_days: 7` 表示連續停止滿 7 天。`keep.compose` 的 project 不指定 services 時保留整套部署；指定 services 時保留列出服務的全部實例。`keep.container_names` 精確比對容器名稱。任何保留規則命中即保留。設定不存在或錯誤時停止；明確 `keep: {}` 表示沒有保留規則。

```bash
dcl container clean          # 只顯示候選與摘要
dcl container clean --all    # 查看全部容器與保留原因
dcl container clean --config /path/to/containers.yaml --json
dcl container clean --yes
```

刪除容器及內部檔案，保留掛載資料。不刪 image 或其他資源，不使用 force。保留的匿名 volume 不保證下次重建自動掛回。刪除前重新檢查狀態及設定，無法完全消除外部啟停的競態。若容器在列出後、inspect 前被其他程序移除，本次清理會報錯停止，等待下次排程；不自動重試。結果失敗退出碼為 1，語法錯誤為 2；JSON 含已完成紀錄，即使後續查詢失敗也不丟失。

image 設定的新預設位置是 `~/.config/docker-clean/images.yaml`。若只有舊 `config.yaml`，仍相容讀寫該檔；兩者存在時新檔優先，明確 `--config` 不受影響。要遷移可用 `cp -n ~/.config/docker-clean/config.yaml ~/.config/docker-clean/images.yaml`，保留原檔且不覆蓋新檔。`dcl image clean` 仍只使用命令列規則。

每日 03:00 排程範例（先預覽確認規則，再自行加入 `crontab -e`）：

```bash
mkdir -p ~/.local/state/docker-clean
command -v dcl
```

以下 `/ABS/PATH/dcl` 必須替換為上一步的絕對路徑；cron 帳號需有 Docker 權限，PATH 需包含 docker。系統時區決定 03:00 的實際時間；台灣主機應為 Asia/Taipei。cron 服務必須啟用。

```cron
PATH=/usr/local/bin:/usr/bin:/bin
0 3 * * * /usr/bin/flock -n /home/swy/.local/state/docker-clean/container.lock /ABS/PATH/dcl container clean --yes --json >> /home/swy/.local/state/docker-clean/container.log 2>&1
```

以上為此主機範例，其他帳號需替換 `/home/swy`。紀錄可由系統 logrotate 管理；工具不安裝排程，也不順便清理 image。Swarm 舊 task 容器需另外盤點，不屬於本指令範圍。

容器文字預覽只展開候選的掛載資訊；`--all` 額外列出其他容器，但不改變清理範圍。沒有候選時顯示摘要，不要求執行刪除。執行後顯示刪除／跳過／失敗／未處理數量；盤點未完成時明確標示，未處理數量為未知。

`--json` 始終保留全部容器，即使搭配 `--all` 也不改變內容。新增 `entries[].category`、`summary`、`stopped_days`、`plan_complete`，分類依保留優先規則互斥統計；`plan_complete: false` 時摘要只代表已完成判斷的項目。

# Docker Clean

預覽並清理本機 Docker image 與已停止的容器。image 可用互動介面選取，也可用 `dcl` 指令自動化；容器清理只透過指令執行。

## 安裝

需要 Python 3.11+、[uv](https://docs.astral.sh/uv/)、Docker CLI，以及本機 Docker Engine 的存取權限。本工具只接受本機 Unix socket，不操作遠端 Docker context。

```sh
uv sync --locked
uv run dcl --help
```

以下範例在專案目錄使用 `uv run dcl`；若要從其他目錄直接執行，可先在專案目錄執行 `uv tool install .`，再將 `uv run dcl` 換成 `dcl`。

## 清理 image

### 手動勾選要刪除的 image

```sh
uv run dcl image delete
```

啟動時沒有預選項目。可用 Space、Enter 或滑鼠勾選；上方輸入框每行可填一條 Python Regex，按「Regex 篩選」縮小清單，或按「Regex 勾選」加入符合項目。篩選只影響顯示，不改動已勾選項目。無 tag 的 image 顯示為 `None`，可用 `^None$` 比對。

勾選後按「預覽」檢查完整 image ID、所有 tag 與容器引用，再按「確認強制刪除」。同一 image 的全部 tag 都在刪除範圍內；強制刪除仍可能被 Docker 拒絕。這個模式不讀寫保留規則設定。

### 保留符合規則的 image，清理其餘項目

```sh
uv run dcl image keep
```

先設定哪些映像（image）要保留，再預覽其餘項目的清理結果：

1. 在清單勾選想保留的映像，按「加入保留規則」。只勾選還不會加入規則。
2. 每個標籤（tag）會各加一條規則到上方輸入框。例如 `nginx:latest` 會變成 `^nginx:latest$`，表示保留這個完整標籤；沒有標籤的映像會略過。
3. 按「儲存」保存整個規則框與清理選項，再按「預覽」查看哪些會保留、哪些會刪除。
4. 檢查後按「確認刪除」才會執行清理。

也可以直接編輯上方規則：每行一條正規表示式（Python Regex），符合其中一條就保留。例如 `^nginx:` 保留 nginx 的所有版本，`^nginx:latest$` 只比對這個完整標籤。規則用 Python `re.search` 搜尋完整標籤文字；同一映像只要有一個標籤符合，就會保留整個映像。修改後需儲存並重新預覽。

預設跳過仍被容器使用的映像，包含已停止的容器。「強制刪除 image」會把這些映像也列入清理，但 Docker 仍可能拒絕；符合保留規則的映像仍會保留。「逐一移除標籤」會逐個移除待清理映像的標籤，移除最後一個時可能連映像一起刪除。

規則存於 `~/.config/docker-clean/images.yaml`。首次執行可由 `image keep` 建立；也可用 `--config /path/to/images.yaml` 指定檔案，例如：

```yaml
theme: terminal
keep:
  - '^postgres:16$'
  - '^myorg/.*:.*$'
cleanup:
  remove_tags: false
  force: false
  unused_days: 14
```

`keep: []` 表示沒有保留規則。`unused_days` 只適用於下方的 `dcl image clean`，不限制 `image keep` 介面的清理。

### 用指令預覽或執行

`image clean` 只採用上述設定檔的 `keep` 與 `cleanup.unused_days`，不採用 `force`、`remove_tags`；設定檔不存在或無效時會停止。預設只預覽，加入 `--yes` 才執行。範例中的 14 天門檻也會套用於下列指令。

```sh
uv run dcl image clean                                      # 預覽已達期限且未受保護的 image
uv run dcl image clean --delete '^myapp:dev-'               # 只預覽符合規則者
uv run dcl image clean --delete '^myapp:' --keep ':stable$'  # 保留規則優先
uv run dcl image clean --delete '^myapp:dev-' --yes          # 執行刪除
```

`--delete` 和 `--keep` 可重複使用；任何 tag 命中都作用於整個 image ID。預設跳過被容器引用的 image；未設定 `unused_days` 時，只有明確加上 `--force` 才要求 Docker 強制刪除。可用 `--config PATH` 指定設定檔，或用 `--json` 取得機器可讀的預覽與結果。

設定 `cleanup.unused_days: 14` 後，從首次盤點發現「無任何容器引用、未受保留規則保護」開始計時，滿 14 天才列為候選，**不看 image 建立日期**。預覽也會更新紀錄；未設定期限時，沒有天數限制。可用 `--unused-days DAYS` 臨時覆寫，啟用期限時不可搭配 `--force`。

紀錄存於 `~/.local/state/docker-clean/image-unused.json`。再次觀察到容器引用、命中保留規則、image 消失，或盤點間隔超過 36 小時，都會清除或重設計時。紀錄遺失會重新計時，損壞則停止清理。每日盤點無法偵測兩次檢查間短暫出現又移除的容器。

舊入口 `docker-clean keep`、`docker-clean delete` 和 `docker-clean clean` 仍可使用；其中 `docker-clean clean` 不套用 `unused_days`，並要求輸入 `DELETE` 確認。

## 清理已停止的容器

先將 [容器設定範例](examples/containers.yaml) 複製到 `~/.config/docker-clean/containers.yaml`，依需求修改停止天數與保留清單。最小設定如下：

```yaml
version: 1
stopped_days: 14
keep:
  compose:
    - project: my-project
  container_names:
    - important-container
```

`stopped_days` 以最後停止時間計算，只清理停止滿指定天數的普通容器；執行中與 Swarm 管理的容器會跳過。`compose` 的 `project` 不指定 `services` 時保留整個專案；指定時只保留列出的服務。容器名稱與 Compose 名稱採精確比對。明確設定 `keep: {}` 表示不保留任何容器。

```sh
uv run dcl container clean                                  # 預覽候選與分類摘要
uv run dcl container clean --all                            # 額外列出其餘容器與原因
uv run dcl container clean --config /path/to/containers.yaml --json
uv run dcl container clean --yes                            # 依預覽範圍執行
uv run dcl container clean --ignore-age                     # 手動預覽所有已停止且未受保護的容器
uv run dcl container clean --ignore-age --yes               # 忽略 14 天期限後執行
```

容器設定不存在或無效時會停止。`--ignore-age` 只供手動清理；仍會跳過保留規則、非 exited 狀態與 Swarm 容器，且需加 `--yes` 才會刪除。`--yes` 會刪除候選容器及容器內的檔案，保留掛載資料；不使用 force，也不刪除 image。

## 自動清理

提供兩組獨立的 [systemd user 排程](deploy/systemd)，啟用後到點直接執行刪除，不再詢問確認：

| 台北時間 | 對象 | 清理條件（依上述設定範例） |
|---|---|---|
| 每天 03:00 | 容器 | `exited` 滿 14 天、未受保留規則保護，且非 Swarm 容器 |
| 每天 03:15 | image | 每日盤點無容器引用滿 14 天，且未受保留規則保護 |

**timer 決定何時執行，service 決定執行哪個指令。** service 使用 `Type=oneshot`，跑完就結束。錯過排程不補跑；同一 service 尚未結束時不會重複啟動。

### 安裝與啟用

先準備上述兩份 YAML，確認保留清單。**image 排程要等待 14 天，必須在 `images.yaml` 設定 `cleanup.unused_days: 14`；省略就沒有天數限制。**

在專案目錄執行以下前置步驟。service 範例使用 `/home/swy`，其他帳號須先將複製後的 service 路徑改成自己的路徑。

```sh
uv tool install --reinstall .
mkdir -p ~/.config/systemd/user
cp deploy/systemd/*.service deploy/systemd/*.timer ~/.config/systemd/user/
dcl container clean                 # 檢查容器候選
dcl image clean                     # 檢查 image 候選，開始記錄無引用時間
```

確認預覽後，啟用需要的 timer；只需其中一種清理時，執行對應那一行即可。

```sh
sudo loginctl enable-linger "$USER"  # 登出後仍能執行排程
systemctl --user daemon-reload
systemctl --user enable --now docker-clean-container.timer
systemctl --user enable --now docker-clean-image.timer
```

### 修改規則、參數與時間

| 想修改什麼 | 修改位置 | 生效方式 |
|---|---|---|
| 保留清單、清理天數 | `~/.config/docker-clean/` 下的 `containers.yaml`／`images.yaml` | 下次執行自動讀取 |
| 指令參數、設定檔路徑 | service 的 `ExecStart` | 重新載入後，下次執行使用 |
| 排程時間 | timer 的 `OnCalendar` | 重新載入並重啟 timer |

例如把 image 排程改成每天 04:00：

```sh
systemctl --user edit --full docker-clean-image.timer
# 將 OnCalendar 改成：OnCalendar=*-*-* 04:00:00 Asia/Taipei
systemctl --user restart docker-clean-image.timer
```

修改執行參數則用 `systemctl --user edit --full docker-clean-image.service` 編輯 `ExecStart`。`systemctl edit` 儲存後會自動重新載入；若直接編輯檔案，需另執行 `systemctl --user daemon-reload`。

### 查看與停用

```sh
systemctl --user list-timers 'docker-clean-*'
journalctl --user -u docker-clean-image.service
systemctl --user disable --now docker-clean-image.timer
```

查看容器紀錄或停用容器排程，將最後兩行的 `image` 換成 `container`。

## 操作邊界

image 刪除不會停止或刪除容器，也不清理 volume、network 或 build cache。執行前會重新檢查設定與 Docker 狀態；項目變動時跳過，查詢失敗時停止。Docker 在最後檢查與刪除之間仍可能發生變動。畫面上的 image 大小包含共用層，不能加總當作可回收容量。

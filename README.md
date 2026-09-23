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

在介面中編輯保留規則，按「儲存」，再按「預覽」檢查候選項目，最後按「確認刪除」。也可勾選清單中的 image，按「產生規則」建立該 tag 的精確規則。預設跳過被容器引用的 image；介面可另外設定「逐一移除標籤」與強制刪除。

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

規則以 Python `re.search` 比對完整 tag；多條規則採 OR。同一 image ID 只要有一個 tag 命中，就保留整個 image。`keep: []` 表示沒有保留規則，預覽時請仔細確認候選範圍。

### 用指令預覽或執行

`image clean` 會讀取上述設定檔的 `keep` 與 `cleanup.unused_days`；設定檔不存在或無效時會停止。預設只預覽，加入 `--yes` 才執行。範例中的 14 天門檻也會套用於下列指令。

```sh
uv run dcl image clean                                      # 預覽已達期限且未受保護的 image
uv run dcl image clean --delete '^myapp:dev-'               # 只預覽符合規則者
uv run dcl image clean --delete '^myapp:' --keep ':stable$'  # 保留規則優先
uv run dcl image clean --delete '^myapp:dev-' --yes          # 執行刪除
```

`--delete` 和 `--keep` 可重複使用；任何 tag 命中都作用於整個 image ID。預設跳過被容器引用的 image；未設定 `unused_days` 時，只有明確加上 `--force` 才要求 Docker 強制刪除。可用 `--config PATH` 指定設定檔，或用 `--json` 取得機器可讀的預覽與結果。

設定 `cleanup.unused_days: 14` 後，只清理每日盤點持續無容器引用滿 14 天的 image：

```sh
uv run dcl image clean          # 只預覽 Docker；開始記錄無引用時間
uv run dcl image clean --yes    # 只刪除已達期限的候選
```

紀錄存於 `~/.local/state/docker-clean/image-unused.json`。image 被容器引用、命中 `images.yaml` 的 `keep` 規則，或盤點中斷超過 36 小時，計時就重新開始；紀錄損壞時停止清理。這是每日盤點的結果，無法偵測兩次盤點間短暫出現又移除的容器。可用 `--unused-days DAYS` 臨時覆寫設定；啟用期限時不可搭配 `--force`。

舊入口 `docker-clean keep`、`docker-clean delete` 和 `docker-clean clean` 仍可使用；其中 `docker-clean clean` 會要求輸入 `DELETE` 確認。

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

### 每天 03:00 自動清理

確認保留清單與預覽後，可安裝 [systemd user timer](deploy/systemd/docker-clean-container.timer) 與 [service](deploy/systemd/docker-clean-container.service)。範例使用 `/home/swy` 的安裝與設定路徑；其他帳號須先修改 service 內的路徑。`loginctl enable-linger` 需要管理員權限，讓 user timer 在登出後仍可執行。

```sh
uv run dcl container clean
mkdir -p ~/.config/systemd/user
cp deploy/systemd/docker-clean-container.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now docker-clean-container.timer
systemctl --user list-timers docker-clean-container.timer
journalctl --user -u docker-clean-container.service
```

timer 每天台北時間 03:00 執行 `dcl container clean --yes`。關機期間錯過的排程不補跑；同一 service 執行中不會重複啟動。停用可執行 `systemctl --user disable --now docker-clean-container.timer`。

image 另用 [03:15 timer](deploy/systemd/docker-clean-image.timer) 與 [service](deploy/systemd/docker-clean-image.service) 每日檢查。確認 `images.yaml` 的保留規則、安裝新版 `dcl` 後，啟用排程：

```sh
uv tool install --reinstall .
cp deploy/systemd/docker-clean-image.{service,timer} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now docker-clean-image.timer
systemctl --user list-timers docker-clean-image.timer
journalctl --user -u docker-clean-image.service
```

需要永久保留的 image，請在 `images.yaml` 的 `keep` 加入精確 Regex，例如 `'^portainer/helper-reset-password:latest$'`；修改後會在下次盤點生效。暫停 image 排程可執行 `systemctl --user disable --now docker-clean-image.timer`。

## 操作邊界

image 刪除不會停止或刪除容器，也不清理 volume、network 或 build cache。執行前會重新檢查設定與 Docker 狀態；項目變動時跳過，查詢失敗時停止。Docker 在最後檢查與刪除之間仍可能發生變動。畫面上的 image 大小包含共用層，不能加總當作可回收容量。

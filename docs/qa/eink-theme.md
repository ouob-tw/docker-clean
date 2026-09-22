# 保留規則介面恢復 E-Ink

日期：2026-09-22。使用者確認入口為 `tui`。

原因：E-Ink 原本只在白名單介面註冊，保留規則介面的主題選單與設定驗證均不接受 `e-ink`。另外，`tui` 在 `NO_COLOR` 環境下的輸出濾鏡會移除明確的黑白底色。

- 兩個入口共用既有 E-Ink 配色與樣式，並各自註冊；原有預設主題不變。
- `tui` 接受並保存 `theme: e-ink`，重開套用；切換主題不儲存未完成的規則。
- E-Ink 已是黑白配色，輸出保留明確的黑白對比；其他主題保留既有 `NO_COLOR` 行為。

驗證：

- PASS：真實 Textual 主題選單從 nord 搜尋、選取 e-ink；兩入口均可選，保留規則重開仍為 e-ink。
- PASS：表格及 Checkbox 聚焦渲染僅含黑白；未完成的規則編輯未被切換主題寫入設定。
- PASS：真實 PTY 在 `NO_COLOR=1` 下，兩入口均輸出黑字白底；terminal 主題原有終端配色測試仍通過。
- PASS：5 項針對性測試；mypy 13 個來源檔案。
- PASS：[完整單元與整合測試](evidence/eink-theme/green.log) 149 項通過。

證據：[選單修正前失敗](evidence/eink-theme/picker-red.log)、[NO_COLOR 修正前失敗](evidence/eink-theme/no-color-red.log)、[tui 實際渲染](evidence/eink-theme/tui.svg)。皆使用假 Docker 資料，沒有刪除主機 image。

審查基準：`/tmp/docker-clean-eink-base`；固定差異：`/tmp/docker-clean-eink-review/changes.diff`。

Claude（nemo）獨立覆核通過，隔離副本完整 149 項測試通過（hcom #20847）；另確認 `NO_COLOR` 下由 terminal 切到 e-ink 再切回時，輸出能正確切換黑白色與終端預設色。

```sh
uv run pytest tests/integration/test_eink_theme.py tests/integration/test_terminal_colors.py -q
uv run pytest tests/unit tests/integration -q
uv run mypy src
```

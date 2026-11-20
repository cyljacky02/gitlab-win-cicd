# 變更審核清單自動化｜部門分享簡報

說明把公槽 Excel 的變更審核清單搬到 M365 Excel Online，並以 Power Automate＋Office Scripts 每天發 Teams 卡片通知、在卡片回報結果、完成時主表自動填 Y。共 **6 頁、約 9 分鐘**，全部為原生可編輯 PowerPoint 物件，沿用 `ai-mcp-sharing` 的主題。

- **[change-checklist-automation.pptx](change-checklist-automation.pptx)** · [PDF](change-checklist-automation.pdf) · [總覽](overview.png) · [講稿](speaker-notes.md)
- [deck.json](deck.json)：可見文字與講者備註的來源

| 頁 | 主旨 | 時間 |
|---|---|---|
| 1 | 封面：以前是公槽 Excel、當天手動公告、結果靠人回填 | 1.5 分鐘 |
| 2 | 改了什麼：清單位置／當天通知／結果回報，以前 → 現在 | 1.5 分鐘 |
| 3 | 每天的流程：新增變更 → 每天抓取 → 發送卡片 → 卡片回報，結果寫回 Excel | 2 分鐘 |
| 4 | Teams 卡片示意：完成／失敗／取消與原因／備註，各自的記錄方式 | 1.5 分鐘 |
| 5 | 本週試行要請大家幫忙的事，以及試行順利後的分工 | 1.5 分鐘 |
| 6 | 目的：日常手動作業逐步自動化；歡迎來討論其他想自動化的作業 | 1 分鐘 |

## 上台前請確認

- 第 1 頁頁尾的 `〔姓名〕〔部門〕〔日期〕`：直接在 PPT 修改，或改 `deck.json` 後重建。
- 第 4 頁卡片是**示意圖**，欄位為 `〔…〕` 佔位。若想改放真實卡片截圖，可在 PPT 中蓋上截圖。
- 第 5 頁講稿的「沒收到卡片就先照原方式公告」是建議備案，請依主管決定調整。
- 內容依目前設計描述：**只有「完成」會回填主表 Y**；失敗／取消記錄在回應工作表。若流程有變，請同步修改第 2～4 頁。

## 修改與重建

在 repo 根目錄（Windows PowerShell）：

```powershell
.\.venv-slides\Scripts\python.exe tools/render_change_automation.py --previews
.\.venv-slides\Scripts\python.exe -m unittest discover -s tests -p test_change_automation.py -v
```

使用 `tools/requirements-poc-review.txt`；需要微軟正黑體與桌面 PowerPoint（`--pptx-only` 只產 PPTX／講稿）。**手改 PPT 後再重建會覆寫**，請先另存或用 `--output-dir`。工具拒絕寫入其他歷史簡報目錄。

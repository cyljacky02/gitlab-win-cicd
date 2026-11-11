# 期中工作報告｜Windows 換版自動化部署 × WinCD

報告期間 9/29 – 11/13，三個月目標至 12/28。共 **11 頁**，全部為原生可編輯 PowerPoint 物件。

- **[midterm-report.pptx](midterm-report.pptx)** · [PDF](midterm-report.pdf) · [總覽](overview.png) · [講稿](speaker-notes.md)
- [deck.json](deck.json)：可見文字、行事曆資料與講者備註的來源

| 頁 | 主題 | 備註 |
|---|---|---|
| 1 | 封面 | 〔姓名〕〔部門〕〔報告日期〕請直接在 PPT 修改 |
| 2 | 三個月目標：完成自動化部署建置 50%（含 ADO＋WinCD）、自動化測試第二階段 25%（AI 導入，0%） | 9/29 → 12/28 時間軸 |
| 3 | **行事曆** 9/28 – 11/22（8 週） | 左 2/3 行事曆＋右側 6 張說明卡；虛線＝預計 |
| 4 | 任務範圍的變化 | 可選；不用時設為「隱藏投影片」 |
| 5 | 比較三種做法：GitLab Runner／Rundeck／Azure DevOps | 否決／試做／採用 |
| 6 | POC 成果 | 已驗證與正式環境待驗分開 |
| 7 | 導入進度 | **2 個截圖佔位框** |
| 8 | WinCD 是什麼 | **1 個截圖佔位框**（TUI） |
| 9 | WinCD 功能重點與目前狀態 | |
| 10 | 學到的東西 | |
| 11 | 後續規劃：ADO／WinCD／AI 三條線的依序步驟，終點 12/28 | 尚未開始的項目不標時程 |

## 放截圖

佔位框在 PPT 中命名為 `Screenshot placeholder: …`（可在「選取範圍窗格」找到）。插入圖片後蓋上去或刪除佔位框即可。**手改 PPT 後不要再執行重建**，否則會覆寫；要重建請先另存或用 `--output-dir`。

## 修改與重建

行事曆的事件、日期、顏色、旗標，以及後續規劃的步驟與狀態（`doing`／`todo`），都在 `deck.json`。在 repo 根目錄：

```powershell
.\.venv-slides\Scripts\python.exe tools/render_midterm_report.py --previews
.\.venv-slides\Scripts\python.exe -m unittest discover -s tests -p test_midterm_report.py -v
```

沿用 `render_poc_review.py` 的主題與原生物件寫入、`export_presentation_pdf.ps1` 的 PowerPoint 匯出；需要微軟正黑體與桌面 PowerPoint（`--pptx-only` 可只產 PPTX）。工具拒絕寫入其他歷史簡報目錄。

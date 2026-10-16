# Windows 自動化部署實作計畫｜六頁同步版

**目前以使用者手改的六頁 PPT 為準。** 已同步內容、日期、頁碼與講者備註；只重新設計最後一頁的圖示、配色與後續擴展路線。

## 最新交付

- [六頁 PowerPoint](six-page-v3/windows-cd-journey.pptx)
- [六頁 PDF](six-page-v3/windows-cd-journey.pdf)
- [六頁總覽](six-page-v3/overview.png)
- [預計行程預覽](six-page-v3/preview-06.png)
- [目前內容與講者備註](windows-cd-journey.md)

使用者正在編輯的 `architecture-v2/windows-cd-journey.pptx` **沒有覆寫**。第 1～5 頁直接保留手改後的原生文字、形狀、線條、配色與位置，沒有重新套回先前九頁版。更新內容只影響講者備註及不可見的投影片名稱；第 6 頁則重畫行程。六頁依序為：

| 頁 | 內容 | 本輪更新 |
|---|---|---|
| 1 | 從程式建置到受控部署／Windows 自動化部署實作計畫 | 保留手改封面與「預計 12/28 前完成」 |
| 2 | 預期效益 | 保留手改版 |
| 3 | 端到端目標架構 | 保留手改圖形與「Agent 主動連 ADO 取得換版檔案」；詳細限制留在備註 |
| 4 | 分支與環境 | 保留簡化過的正式分支示例 |
| 5 | 換版與復原 | 保留流程與人工功能確認；備註修正為新版頁碼 |
| 6 | 預計行程 | 對應修改後六站的圖示、階段色彩及後續擴展虛線 |

## 行程同步與視覺微調

保留起伏路線與大致排版，不另改階段順序、不新增未確認日期：

| 站 | 依手改 PPT 同步的內容 | 圖示／色彩 |
|---|---|---|
| 01 | POC & 跨部門討論（10/12 ~ 10/23）／驗證架構可行性 | 人物討論，藍色 |
| 02 | 協調架構部門／安裝、配置 Azure DevOps | 主機與配置，青綠色 |
| 03 | 串接 CI/CD Pipeline／以「雷影」系統為首發驗證標的 | 串聯的 Pipeline 節點，藍色 |
| 04 | SIT & UAT 驗測／整合與例外測試 | 檢核表＋勾選章，青綠色 |
| 05 | Production 正式環境／依程序取得核准後試辦上線 | 試辦旗幟，橙色 |
| 06 | 後續發展／陸續串接其他專案、實現可複製的自動化換版 | 多專案擴展圖，青綠色；以虛線區別後續範圍 |

底部原本空白的橫條改成「本輪預計 12/28 前完成／後續發展：逐案擴展，時程另議」，避免把後續所有專案串接誤認為同一期限。12/28 年份未指定；10/12 ~ 10/23 是 POC／討論的暫定行程，不代表已完成。

色彩與符號僅為階段分組，**不表示已驗證、已成功或已獲上線批准**。SIT 與 UAT 合併顯示並非取消驗收、權限負向測試或復原演練。正式換版的版本／應用／目標綁定放行、放行前零預拷、流量恢復前人工確認等控制保持不變。

## 內容與版型來源

- `windows-cd-journey.md`：**目前六頁**的可見內容與完整備註。前五頁標題、重點與內文會比對手改快照；最後一頁六站的標題、日期與說明直接由 Markdown 讀取，以 `｜` 分隔。
- `inputs/windows-cd-journey-manual-six.pptx`：本輪手改檔的獨立快照，是第 1～5 頁原生物件版型來源；不是使用者正在編輯的原檔。重建唯讀載入，絕不回存快照。
- `inputs/windows-cd-journey-manual-six.pdf`：快照經 PowerPoint 輸出的比對基準。
- `tools/render_journey_slides.py`：目前六頁流程使用 `validate_manual_template()`、`timeline()`、`build_six()`；保留第一至第五頁形狀樹，只更新備註並重畫最後一頁。舊九頁版型函式為歷史用途，不是目前六頁版的前五頁生成來源。
- `tools/export_presentation_pdf.ps1`：用 PowerPoint 輸出**實際 PPTX** 的 PDF；開啟暫存的唯讀、未命名複本，完成後只關閉該複本，絕不儲存／關閉使用者正在編輯的簡報，也不呼叫 PowerPoint Quit。

這不是任意 Markdown 轉簡報工具。若只改前五頁 Markdown 而沒有對應修改快照，重建會明確報錯，避免默默忽略內容修改。下一輪人工改稿時，先將新的 PPT 另存為新的快照，並同步 Markdown，再用 `--template` 指定；不要直接改寫目前快照或使用者開啟中的檔案。第六頁的內容與排版可分別改 Markdown 與 `timeline()`。

## 重建

在 repo 根目錄執行（Windows PowerShell，需已安裝桌面 PowerPoint）：

```powershell
.\.venv-slides\Scripts\python.exe -m pip install -r tools/requirements-journey.txt
.\.venv-slides\Scripts\python.exe tools/render_journey_slides.py --previews
.\.venv-slides\Scripts\python.exe -m unittest discover -s tests -v
```

預設寫入 `journey/six-page-v3/`，不改任何舊版／手改檔。可用 `--output-dir` 指定新的輸出目錄、`--template` 指定另一份六頁快照。

字型使用 Windows 的 `msjh.ttc`／`msjhbd.ttc`，可用 `--font-dir` 指定；PPTX 未嵌字型。無 PowerPoint 時可加 `--pptx-only` 只產出 PPTX，此時不產 PDF 或 PNG；`--previews` 必須搭配成功的 PDF 輸出。PDF／PPTX 先寫暫存檔，成功後才發布；遇到被占用的目的檔會報錯，不會偷偷改寫其他版本。

## 驗證

- 自動測試：六頁內容與順序、日期及「雷影」首發標的、來源與快照一致性、備註與頁碼、行程文字不重疊／圖形不越界、對比度及前五頁原生形狀樹完全保留。
- 原版、先前 Journey、手改原檔與快照在建置前後以 hash 比較，確認未被改寫。
- 六頁 PDF 由 PowerPoint 實際開啟產出的 PPTX 轉出，不再由 ReportLab 另繪整份 PDF。前五頁可和手改快照的 PDF 做逐像素比對。
- 已檢視六頁總覽與新行程預覽；尚未人工逐頁播放動畫或投影測試，會前請在簡報電腦確認字型與播放效果。

## 歷史版本（保留，不是目前內容來源）

- 原提案：[PPTX](../windows-cd-initial-plan.pptx) · [PDF](../windows-cd-initial-plan.pdf)
- 第一份九頁 Journey：[PPTX](windows-cd-journey.pptx) · [PDF](windows-cd-journey.pdf) · [總覽](overview.png)
- 架構 v2：使用者已將 [PPTX](architecture-v2/windows-cd-journey.pptx) 手改為六頁；該資料夾的舊 PDF 與 PNG 仍為當時九頁輸出，**不可視為手改 PPT 的最新預覽**。本輪最新配對 PPTX／PDF 在 `six-page-v3/`。
- 九頁 v2 Markdown：[封存來源](inputs/windows-cd-journey-nine-page-v2.md)。此檔在 `inputs/` 下只作歷史閱讀，當中的圖片／文件相對路徑依原本目錄解讀。
- 原完整架構：[draw.io](../diagrams/windows-deployment-map.drawio) · [PNG](../diagrams/windows-deployment-map.png) · [向量 PDF](../diagrams/windows-deployment-map.pdf)，維持不變。

視覺風格仍延續三張參考照片的優先順序：IMG_4443 行程路線 → IMG_4442 branch 分流 → IMG_4441 架構分區。沒有直接貼入照片、浮水印或參考圖未確認的技術資訊。

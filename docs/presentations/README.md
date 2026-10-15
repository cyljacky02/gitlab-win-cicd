# Windows 正式部署治理｜初步計劃簡報

## 交付

- [Markdown 內容與流程圖來源](windows-cd-initial-plan.md)
- [PPTX（第 4 頁為圖像，其餘為原生物件）](windows-cd-initial-plan.pptx)
- [固定版面 PDF](windows-cd-initial-plan.pdf)
- [Mermaid／draw.io 圖源](diagrams/README.md)
- [架構圖 draw.io 原檔](diagrams/windows-deployment-map.drawio) · [高清 PNG](diagrams/windows-deployment-map.png) · [可放大向量 PDF](diagrams/windows-deployment-map.pdf)
- 拆分原檔：[上半部部署架構](diagrams/windows-deployment-architecture.drawio) · [下半部換版／復原](diagrams/windows-target-release-flow.drawio)（[PNG／PDF 索引](diagrams/README.md)）
- [換版與復原可行性查核](../research/windows-release-recovery-feasibility.md)：工具鏈可支援，但備份／健康檢查／F5／退版與跨主機失敗停止需受控腳本及編排；尚未實機驗證。
- [端到端架構圖設計研究](../research/end-to-end-architecture-diagram-design.md)
- [簡報設計研究與官方參考資料](../research/presentation-design-guidance.md)

**v0.7：共 7 頁＝封面＋議程＋5 頁內容（含時程），無附錄。** 面向非開發讀者，只討論 Azure DevOps Server，Express 作為 POC 起點，不預定正式採購版本。

| 頁 | 主旨 |
|---|---|
| 1 | 封面：保留 GitLab 建置，正式換版由授權部門掌握 |
| 2 | 議程：原因、架構、環境、換版與時程 |
| 3 | 合併舊版第 2–3 頁：只送檔也算正式主機存取 |
| 4 | 完整交付架構＋多台 Target＋下／上 F5 的單台換版、退版與失敗隔離流程 |
| 5 | 三分支各自建置；SIT／UAT 自動，Production 人工選版放行 |
| 6 | 放行後取檔、換版、健康檢查與復原 |
| 7 | 建議時程：POC → 協調架構部門安裝 ADO → GitLab 整合 → SIT → UAT → Production |

第 4 頁中間管理區以「收到成功通知 → 取得並保存版本 → 選版、選目標、確認放行」三段流程呈現；接收器、API、Importer、hash 等實作細節移到講者備註，不代表移除這些必要角色。左右兩區保持不變；單台換版／復原圖另改為白話動作與 ①～⑧ 圈號，實作限制留在備註。

第 4 頁以 ①～⑧ 說明上半部架構，下半部展開每台 Target 的換版／復原；不增加頁數。使用者已確認「下／上 F5」為退出／恢復負載平衡流量。具體模式、連線等待、控制身分與位置仍待確認。多機畫成 01、02、…、N，建議逐台且失敗停止後續，批次與最低容量待定。復原成功不等於新版本部署成功；復原失敗保持隔離、告警，不回池。

時程以 **12/31** 為目標，年份未指定；各階段日期、資源與上線批准待共同確認。

[事件驅動串接查證](../research/gitlab-ado-event-trigger.md) 是本版架構依據：**GitLab 成功 webhook → 受保護接收器 → 固定 importer → Server Build Artifacts → Classic Release**。管理 Agent 執行匯入，每台 Windows 的專用 Deployment Group Agent 執行部署；正式放行前不得預拷。接收器／匯入驗證／可靠交接是需實作的邏輯，不宣稱原生 GitLab artifact 整合。Server 有 incoming webhook 支援，但 GitLab 驗證互通仍需另測；本版不依賴該互通性。

CI job 直呼 Queue API 有文件化能力基礎，但存在 pipeline 尚未成功的競態及憑證暴露面，故不作首選。[前版輪詢研究](../research/gitlab-cd-artifact-handoff.md) 保留為歷史比較，不再是本版推薦。查證不是現場整合測試；有效 ACL、Express 安裝版行為與零預拷均列入 POC。

不以個人測試環境狀態為對外敘事。其他部門已有 ADO 運行先例是規劃背景，不等於本案通過驗收。

用途是跨部門討論可行性與合規要求，不是正式選型、合規認證或上線批准。技術細節、資料來源與證據範圍留在 Markdown／PPTX 講者備註，不另加附錄投影片。PDF 不含講者備註。

## 可編輯性

**第 4 頁是 2800×1575 高清圖片**，其餘頁保留 PPTX 原生文字、流程方塊、菱形與箭頭。架構圖可編輯主檔是 `diagrams/windows-deployment-map.drawio`，內含真正的節點、容器與連接線，不是包著一張圖片。獨立 PDF 為向量圖、可選取文字；簡報 PDF 第 4 頁為圖像。

架構圖箭頭區分控制、資料及應用流量，表示工作／資料語意，不是完整網路連線方向；ADO Agents 主動連 Server 取工作。完整圖資訊較密，簡報供總覽，逐步講解時建議開啟獨立 PDF 或 draw.io 放大。

其他四張 Mermaid 圖仍由 Markdown 生成；架構圖獨立維護，不受既有 Mermaid 渲染器限制。不保證 draw.io GUI 與初始程式輸出的像素級一致。

## 從 Markdown 重建

在 repo 根目錄執行（Windows PowerShell）：

```powershell
python -m venv .venv-slides
.\.venv-slides\Scripts\python.exe -m pip install -r tools/requirements-slides.txt
.\.venv-slides\Scripts\python.exe tools/render_slides.py docs/presentations/windows-cd-initial-plan.md
```

不需啟用虛擬環境。若希望啟用，PowerShell 使用 `.\.venv-slides\Scripts\Activate.ps1`；CMD 使用 `.venv-slides\Scripts\activate.bat`。

需要 Windows 的 `msjh.ttc`／`msjhbd.ttc`；可用 `--font-dir` 指定合法取得的字型檔目錄。原生文字頁 PDF 嵌入字型子集；PPTX 使用 Microsoft JhengHei，未嵌入字型，其他電腦可能出現替代字型及版面差異。第 4 頁圖像不依賴簡報電腦字型。

重建會覆寫同名 PPTX、PDF、四份 Mermaid 與其 draw.io 檔；這些頁的修改請回寫 Markdown。**不會重建或覆寫 `windows-deployment-map.drawio`／PNG／獨立 PDF。**

### 手動調整第 4 頁

1. 在 diagrams.net 開啟 `diagrams/windows-deployment-map.drawio`，編輯節點、連線及文字後儲存。
2. 匯出 PNG 為同目錄 `windows-deployment-map.png`，使用白底、維持整頁 16:9、至少 2800 像素寬；同時更新獨立 PDF。不要只匯出選取範圍或裁掉留白造成比例改變。
3. 再執行上面的 `render_slides.py`，將最新 PNG 放入第 4 頁。手改 draw.io 不會自動更新 PNG。

`tools/build_deployment_map.py` 是本次初始產圖種子，使用同一場景資料產出 draw.io、向量 PDF、PNG；**手改後不要再執行，否則會覆寫完整圖與兩份拆分圖的 draw.io、PNG、PDF，共九個檔案**。僅需重新生成初始圖時，安裝 `tools/requirements-map.txt` 後顯式執行該工具；它不是簡報重建的一部分。

## Markdown 格式

這是專用 Markdown／Mermaid 子集渲染器，不是任意文件轉換器：

- `---`：換頁；`#`：標題；`>`：本頁重點。
- `##`／`-`：1–3 張內容卡片。流程圖頁只保留一段短解釋。
- `mermaid` fenced block：`flowchart LR`、雙引號節點、`<br/>` 換行、判斷菱形、`subgraph`、有標籤箭頭、虛線、預設色彩類別。
- `%% @name`：圖名；`@node`／`@lane`：在 880×280 圖區內的座標與尺寸；`@route`：轉折點；`@ports`：連線進出邊；`@label`：箭頭標籤位置。這些是標準 Mermaid 註解，其他 Mermaid 工具忽略座標，會自行排版。
- `![替代文字](相對圖片路徑.png)`：整頁圖片，與卡片／Mermaid 互斥；保留 `#` 標題、`>` 重點與講者備註。等比例置中，不裁切，標題保留在 PPTX 圖像背後作語意標題。
- `<!-- notes ... -->`：講者備註，不顯示在投影片與 PDF 中。

PPTX／PDF 使用同一份版面資料各自渲染，PDF 不是 PowerPoint 另存，因此不同 PowerPoint／字型環境不保證像素級一致。

## 品質檢查

- PPTX／PDF 均為 7 頁，無附錄，逐頁具獨立標題與講者備註。
- 四份 Mermaid 圖源通過 Mermaid 官方套件語法解析；架構圖驗證 XML 引用、容器／文字邊界及連線不穿越無關方塊。
- 原生頁正文／圖中文字至少 18 pt；此數值**不適用於第 4 頁完整架構圖縮放後的文字**。詳細閱讀請用獨立向量 PDF／draw.io 放大。
- PDF 原生頁中文可選取、字型已嵌入；第 4 頁是圖像，獨立架構 PDF 則為可選取的向量文字。
- 已檢視架構 PNG 與簡報 PDF 第 4 頁；PPTX 僅第 4 頁為整頁圖片，另有替代文字與講者備註。
- 未使用桌面 PowerPoint 播放，也未在 diagrams.net UI 中逐圖匯入檢查；會前請在簡報電腦確認字型與版面。

原有四份 `cdpoc-architecture-*.md` 未覆寫。統一架構文件與正式選型結論仍是後續交付。
